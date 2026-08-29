---
issue_number: 19
title: "[安全审计] chatlog-keeper 数据库解密原理与代码安全审计"
author: "w1ndys"
created_at: "2026-08-16 19:12:21 UTC"
updated_at: "2026-08-29 03:44:22 UTC"
labels: ["prompt"]
source_url: "https://github.com/w1ndys/prompts/issues/19"
---

# [安全审计] chatlog-keeper 数据库解密原理与代码安全审计

# chatlog-keeper 数据库解密原理与代码审计报告

- 审计对象：[`labazhou2024/chatlog-keeper`](https://github.com/labazhou2024/chatlog-keeper)
- 审计分支：`main`
- 审计 commit：`0289b9b29b91f2c16e33cbf928579a647891d554`
- 审计范围：数据库解密、密钥获取与缓存、进程调试/内存读取、WAL/快照、路径与网络访问、依赖与 CI
- 审计方式：源码静态阅读、Python AST/compileall、项目测试

## 一、结论摘要

项目的核心解密实现不是“破解服务器”，而是：

1. 从当前用户自己运行的 QQ/微信进程内存中取得本地数据库口令或主密钥；
2. 根据本地加密数据库的页头盐值派生 SQLCipher 页密钥；
3. 对每个 4096 字节页先做 HMAC 校验，再用 AES-256-CBC 解密；
4. 对正在使用的数据库先复制主库、WAL、SHM，随后把已提交的 WAL frame 合并到明文 SQLite 副本；
5. 读取消息表并导出 JSON/HTML。

核心密码学链路总体清晰，且实现了逐页认证、错误密钥拒绝、WAL 校验、临时文件清理等防护。未发现明显的“把密钥上传到远端”或任意远程执行后门。

但仓库的“纯本地、不会联网”表述并不完全准确：`wechat_link_fetcher.py` 明确包含公众号文章 HTTP 抓取功能。另外，网络白名单存在可绕过的后缀匹配问题；用户安装时依赖未锁定；主动取钥默认会强制关闭正在运行的 QQ/微信。这些问题建议修复后再把项目作为高敏感数据工具分发。

## 二、数据库解密原理

### 2.1 微信 4.x

证据：`chatlog_keeper/wechat_db.py:396-450, 804-923`

数据库以 4096 字节为一页，页 1 大致布局为：

```text
page 1 = salt(16) | encrypted_body | IV(16) | HMAC-SHA512(64)
page N = encrypted_body | IV(16) | HMAC-SHA512(64)
```

项目兼容两种微信密钥语义：

- 旧版微信：内存中的 32 字节 `enc_key` 直接作为 AES 页密钥；
- 新版微信 4.1.10.31+：内存中的 `enc_key` 实际是 master/password，需要：

```text
page_key = PBKDF2-HMAC-SHA512(enc_key, page1_salt, 256000, 32)
```

页认证密钥为：

```text
mac_key = PBKDF2-HMAC-SHA512(page_key, page1_salt XOR 0x3A, 2, 32)
```

随后计算：

```text
HMAC-SHA512(mac_key, encrypted_body || page_IV || little_endian(page_no))
```

只有 HMAC 匹配时，才使用 AES-256-CBC 解密该页。代码中的 `_effective_page_key()` 会先尝试 raw-key，再尝试 PBKDF2-derived key，并以 page-1 HMAC 作为判定依据（`wechat_db.py:409-450`）。这比单纯检查 key 长度可靠得多。

解密主库时，`_decrypt_db_v4_snapshot()` 逐页读取，校验失败立即终止，不会发布不完整明文；输出采用临时文件后 `os.replace()`（`wechat_db.py:804-889`）。

### 2.2 QQ NTQQ

证据：`chatlog_keeper/qq_db.py:570-660, 975-1022, 1025-1140`

NTQQ 数据库前面额外有 1024 字节 wrapper/header。去掉后，主体仍是 SQLCipher 风格的 4096 字节页。

当前 NTQQ 主要参数为：

```text
passphrase = 进程内存中的 16/32 字节可打印 ASCII 口令
AES key    = PBKDF2-HMAC-SHA512(passphrase, salt, 4000, 32)
MAC key    = PBKDF2-HMAC-SHA512(AES key, salt XOR 0x3A, 2, 32)
page tag   = HMAC-SHA1(MAC key, body || IV || little_endian(page_no))
```

项目同时保留 SHA-1/SHA-512 及不同 reserve 大小的兼容组合（`qq_db.py:630-643`），先用 page-1 HMAC 确定实际参数，再逐页认证、AES-256-CBC 解密。

NTQQ 还有一个特殊点：1024 字节 wrapper 会改变 SQLite Windows pending-byte/锁页位置。项目在 Windows 上使用隔离 SQLite helper，调整 pending byte 后以 `mode=ro&immutable=1` 打开，并执行 `PRAGMA query_only=ON`、`quick_check` 和默认拒绝的 authorizer（`_qq_sqlite_helper.py:161-188, 297-325`）。这是针对 NTQQ 文件格式的工程性兼容处理，不是密码学步骤。

### 2.3 密钥获取

有两条路径：

1. **被动扫描**：通过 Windows `ReadProcessMemory`/macOS 对目标客户端进程做只读内存扫描，寻找候选 key；每个候选都必须通过本地数据库 page-1 HMAC oracle 验证（`qq_db.py:678-816`）。
2. **主动调试**：Windows PowerShell 脚本启动一个新的客户端调试进程，在数据库 key 设置函数处设置 INT3 软件断点，从寄存器/栈读取候选，再由 HMAC oracle 验证。脚本路径和 SHA-256 被固定校验（`active_key.py:288-301, 355-390`）。

因此它依赖的是“本机客户端已经拥有解密所需材料”，而不是从服务器破解密钥。

## 三、做得较好的地方

### 1. 密钥候选不是只看格式，而是用 HMAC oracle 验证

微信和 QQ 都以本地数据库 page-1 HMAC 验证候选 key，显著降低误把随机内存字符串当密钥的风险。

### 2. 逐页解密与失败关闭

主库解密使用 4 KB page 流式处理，并对每一页认证；错误、截断页、尾部不完整页都会失败，不会静默输出一份看似可用但实际损坏的数据库。

### 3. 对 live DB 做主库/WAL/SHM 快照

`core/_snapshot.py:100-132` 会在复制前后比较文件族签名，繁忙写入时重试；这比直接读取正在变化的数据库可靠。

### 4. QQ helper 的只读边界比较完整

`_qq_sqlite_helper.py` 使用 immutable/read-only 连接、`query_only`、`quick_check` 和 authorizer；协议还限制了表名、函数和 SQL 形式，降低了“解密 helper 被当作任意 SQLite 执行器”的风险。

### 5. 发布工作流有较强的版本/制品绑定

CI/release workflow 固定了 GitHub Actions 引用，release 会校验 tag、commit、源代码包、可执行文件和 checksum。这个方向是对的。

## 四、发现的问题

### [中] F1：公众号抓取 URL 白名单可被后缀绕过，存在 SSRF 风险

证据：`chatlog_keeper/wechat_link_fetcher.py:71-79`

```python
host = m.group(1).lower()
return any(host.endswith(h) for h in _FETCHABLE_HOSTS)
```

`endswith("mp.weixin.qq.com")` 会接受形如：

```text
https://attacker-mp.weixin.qq.com/...
```

这类域名并不等于 `mp.weixin.qq.com`。同时没有使用结构化 URL 解析、没有限制端口、没有解析 DNS 后拒绝内网/回环/链路本地地址，也没有防 DNS rebinding。当前该模块在仓库中未发现默认调用点，风险主要在调用者将聊天中的 URL 交给 `fetch_article()` 时触发。

此外，README 多处声明“全程不联网”，但该模块会通过 `urllib.request.urlopen()` 访问网络（`wechat_link_fetcher.py:214-224`），文档与实现不一致。

**建议：**

- 使用 `urllib.parse.urlsplit()`；只允许 `scheme=https`、无用户名密码、默认端口、hostname 精确等于允许列表；
- 做 DNS 解析并拒绝 loopback、private、link-local、CGNAT、保留地址；连接前后再次校验解析结果；
- 明确将文章抓取标为可选联网功能，不要把项目整体描述成绝对离线。

### [中] F2：普通安装路径的依赖未锁定，存在供应链风险

证据：`pyproject.toml:29-33`、`requirements.txt:1-4`：

```text
pycryptodome>=3.18
numpy>=1.21
zstandard>=0.20
```

用户按 README 执行 `pip install .` 时会解析当前可用的最新兼容版本。该工具会读取进程内存、解密并落盘聊天记录，依赖被投毒或被接管后的影响明显高于普通 CLI 工具。Release workflow 虽有 hash-locked requirements，但普通用户安装路径没有复用同一锁定文件。

**建议：**发布带 hash 的 lock/requirements 文件，安装文档优先使用已审计的 source bundle + 锁定依赖；至少固定上限并在 CI 做依赖漏洞扫描和 provenance 校验。

### [中] F3：主动取钥默认强制关闭正在运行的客户端，副作用偏大

证据：

- `chatlog_keeper/scripts/windows_wechat_get_key.ps1:37-39, 950-960`
- `chatlog_keeper/scripts/windows_ntqq_get_key.ps1:51-57, 1278-1292`

默认 `$KillExisting = $true`，发现 WeChat/QQ 运行时执行 `Stop-Process -Force`。这会造成未保存状态丢失、正在发送/接收中的操作中断，甚至在客户端数据库正在写入时增加损坏风险。虽然有 `RequireClosedClient`，但默认 CLI 行为仍然允许强制关闭。

**建议：**默认拒绝自动关闭；先提示用户手动退出并等待确认；如果确实要支持强制关闭，应设置显式 `--force-close-client`，并在关闭前执行优雅退出、等待 WAL checkpoint/进程退出后再启动调试实例。

### [低/设计风险] F4：密钥以明文缓存，ACL 不是加密

证据：

- QQ：`chatlog_keeper/qq_db.py:483-511, 545-565`
- 微信：`chatlog_keeper/wechat_db.py:453-500` 附近
- 权限实现：`chatlog_keeper/core/_secrets.py:511-616`

项目将 master key/passphrase 写入本地 secret 文件，POSIX 使用 `0700/0600`，Windows 设置受限 ACL。这能防止普通其他用户读取，但不能防御同一用户权限下的恶意程序、调试器、备份软件或被盗的用户目录。由于这是解密工具的必要能力，不一定算漏洞，但 README 应明确说明“权限保护而非加密存储”。

**建议：**优先使用 Windows DPAPI、macOS Keychain 或 Linux Secret Service；如果保留文件缓存，应提供禁用缓存、密钥轮换和清理命令。

### [低] F5：缓存/导出文件的并发与敏感信息边界仍需收紧

证据：`wechat_link_fetcher.py:92-103, 266-317`

文章缓存使用固定的 `.tmp` 文件名并直接 `replace`，多进程并发时可能互相覆盖；`save_as_doc()` 直接把远程正文和来源元数据写入 markdown，权限跟随默认 umask，且没有统一的 owner-only 文件创建策略。对于聊天内容和文章正文，这会扩大本地泄露面。

**建议：**使用随机 owner-only 临时文件、fsync 后原子替换，并统一经过私有文件写入器；导出目录/文件权限应在 CLI 层明确设置并向用户展示。

## 五、未发现的高危问题

截至本次审计，没有看到以下证据：

- 将 QQ/微信 key、聊天记录上传到第三方服务器的默认路径；
- 默认启用任意远程命令执行；
- 将用户输入直接拼接成 shell 命令的 `shell=True` 路径；
- QQ helper 默认开放任意 SQL 写操作；
- 未经 HMAC 验证就接受内存扫描候选 key。

不过，主动调试脚本本身具备读取/终止目标进程、修改断点和读取寄存器的高权限能力，建议用户只运行经过 checksum 校验、与源码 commit 对应的 release 制品，不要直接运行来源不明的二进制。

## 六、验证结果

在 Linux 环境对源码执行：

```text
Python compileall：PASS
AST parse：PASS
pytest：539 passed, 89 skipped
```

跳过项主要是 Windows/macOS 专用行为，不能据此证明 Windows/macOS 的实际密钥提取和客户端兼容性全部正确；这些路径仍需要在干净的真实客户端样本上做集成测试。

## 七、建议修复优先级

1. **立即修复**：F1 精确 URL 校验 + SSRF 防护；修正文档“绝对离线”表述。
2. **立即修复**：主动取钥默认不强杀 QQ/微信，改成显式确认/显式 force 模式。
3. **短期修复**：给普通安装路径提供 hash-locked 依赖；对 release 依赖和 PyPI provenance 做 CI 检查。
4. **短期修复**：密钥缓存接入系统密钥环，或至少明确同用户威胁模型。
5. **后续改进**：导出与文章缓存统一使用私有原子写入，补充 Windows/macOS 真机集成测试和故障恢复测试。

## 总体评级

**密码学/数据库页处理：中上；本地安全边界：中上；分发与默认行为：需要改进。**

项目的“如何打开数据库”原理基本成立，核心实现也有较多 fail-closed 设计；但它处理的是聊天记录和数据库密钥，网络白名单、依赖锁定和主动流程副作用不应以普通 CLI 的标准对待。修复上述问题后，再考虑把“本地安全、零联网”作为强承诺写入项目定位。
