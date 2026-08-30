> 本文档由代码逆向整理，源自 `backend/internal/adapter/jiaowu/`，描述本项目对接曲阜师范大学强智教务系统（`zhjw.qfnu.edu.cn`）的全部 HTTP 接口。
> 仅供本项目开发与维护参考。

## 概览

- **基础域名**：`http://zhjw.qfnu.edu.cn`
- **会话维持**：所有请求共享同一 `http.Client`（带 `cookiejar`），登录后凭 Cookie 维持会话
- **登录重定向**：客户端禁止自动跟随重定向（`CheckRedirect` 返回 `ErrUseLastResponse`），用于登录后状态判断
- **连接池**：`MaxIdleConns=100`，`MaxIdleConnsPerHost=100`，`IdleConnTimeout=90s`，`HTTPTimeout=30s`
- **代码位置**：`backend/internal/adapter/jiaowu/`（`auth.go` / `captcha.go` / `encrypt.go` / `search.go` / `selection.go` / `result.go` / `client.go` / `types.go`）

### URL 常量一览

| 常量 | 路径 | 用途 |
|------|------|------|
| `BaseURL` | `http://zhjw.qfnu.edu.cn` | 基础域名 / 会话初始化 |
| `JwxtCaptchaURL` | `/verifycode.servlet` | 获取验证码图片 |
| `JwxtLoginSessURL` | `/Logon.do?method=logon&flag=sess` | 获取 scode / sxh |
| `JwxtLoginURL` | `/Logon.do?method=logonLdap` | 提交登录 |
| `JwxtMainPageURL` | `/framework/xsMain.jsp` | 登录状态验证主页 |
| `SelectionListURL` | `/jsxsd/xsxk/xklc_list` | 选课轮次列表 |
| `SelectionIndexURL` | `/jsxsd/xsxk/xsxk_index` | 进入选课轮次 |
| `SearchBaseURL` | `/jsxsd/xsxkkc/` | 课程搜索 / 选课操作前缀 |
| `ResultPageURL` | `/jsxsd/xkgl/xsxkjgcx` | 选课结果页（Referer 用） |
| `LoadResultURL` | `/jsxsd/xkgl/loadXsxkjgList` | 加载选课结果列表 |

---

## 一、登录流程（SSO 直登）

登录为多步串行流程，单步失败最多重试 3 次（`LoginStepMaxRetries`），验证码识别最多重试 3 次（`MaxCaptchaRetries`）。

### 1.1 初始化会话

```
GET http://zhjw.qfnu.edu.cn
Header: User-Agent: Mozilla/5.0
```

仅用于获取初始 Cookie，忽略响应体。HTTP >= 400 视为失败。

### 1.2 获取验证码图片

```
GET /verifycode.servlet
Header: User-Agent: Mozilla/5.0
```

- **响应**：验证码图片原始字节（image/*）
- 字节为空视为失败
- 图片经 base64 编码后交由 OCR 服务识别（见第四节）

### 1.3 获取 scode / sxh

```
POST /Logon.do?method=logon&flag=sess
Header: Content-Type: application/x-www-form-urlencoded
Header: User-Agent: Mozilla/5.0
Body: (空)
```

- **响应**：纯文本 `scode#sxh`，以 `#` 分隔
- 返回为空或等于 `no`（不区分大小写）视为失败
- `scode` 与 `sxh` 用于凭证加密（见 1.4 与第三节）

### 1.4 提交登录

```
POST /Logon.do?method=logonLdap
Header: Content-Type: application/x-www-form-urlencoded
Header: User-Agent: Mozilla/5.0
Body:
  userAccount=          (留空)
  userPassword=         (留空)
  RANDOMCODE=<验证码>
  encoded=<加密凭证>     (见第三节)
```

**响应判定逻辑：**

| 响应特征 | 判定 |
|---------|------|
| 含 `密码错误` / `用户名或密码错误` / `用户名密码错误` / `您提供的用户名或者密码有误` | 账号密码错误（终止，不重试） |
| 含 `验证码错误` / `验证码不正确` | 验证码错误（重试，最多 3 次） |
| body 为空，或含 `正在登录` / `location` / `教学一体化服务平台` | 登录成功 |
| 其他 | 未知错误，提取页面文本兜底返回 |

### 1.5 登录状态验证

```
GET /framework/xsMain.jsp
```

- 使用禁止重定向的独立 client（共享同一 Cookie Jar）
- HTTP 302/301 → 被重定向，登录失败
- HTTP != 200 → 失败
- 响应体须包含 `教学一体化服务平台` 或 `glyphicon-class`，否则视为登录失败
- 验证最多重试 2 次（`LoginVerifyMaxRetries`）

---

## 二、凭证加密算法（encoded）

源码：`encrypt.go` `encodeCredentials`，从 v1 完整移植。

1. 拼接明文：`code = username + "%%%" + password`
2. 遍历 `code` 每个字符（仅处理前 20 个字符）：
   - 写入当前字符
   - 取 `sxh[i]` 对应数字 `n`（0-9），从 `scode` 当前位置截取 `n` 个字符插入其后，并前移 `scode` 指针
3. 第 20 个字符之后的内容原样追加

示例（伪）：`encoded = u + scode[...] + s + scode[...] + e + ... + %%% + p + a + s + s ...`

---

## 三、验证码 OCR 识别

源码：`captcha.go`。通过 `CaptchaSolver` 接口注入，默认实现 `OCRCaptchaSolver` 调用外部 OCR 服务（环境变量 `OCR_URL`）。

```
POST {OCR_URL}/ocr
Header: Content-Type: application/x-www-form-urlencoded
Header: User-Agent: Mozilla/5.0
Body: image=<base64 编码的验证码图片>
```

**响应（JSON）：**

```json
{
  "code": 200,          // 数字或字符串，200/0 表示成功
  "data": "abcd",       // 识别出的验证码文本
  "message": "..."      // 失败时的错误信息
}
```

- `code` 非 200 且非 0 → 识别失败
- `data` 去空格后为空 → 失败

---

## 四、课程搜索

源码：`search.go`。教务系统将选课分为 5 个模块，每个模块独立搜索接口。

### 4.1 选课模块（ModuleType）

| 模块常量 | 路径片段 | 说明 | operAction | refererAction |
|---------|---------|------|-----------|---------------|
| `ModuleKnjxk` | `xsxkKnjxk` | 专业内跨年级选课 | `knjxkOper` | `comeInKnjxk` |
| `ModuleBxqjhxk` | `xsxkBxqjhxk` | 本学期计划选课 | `bxqjhxkOper` | `comeInBxqjhxk` |
| `ModuleXxxk` | `xsxkXxxk` | 选修选课 | `xxxkOper` | `comeInXxxk` |
| `ModuleFawxk` | `xsxkFawxk` | 计划外选课 | `fawxkOper` | `comeInFawxk` |
| `ModuleGgxxkxk` | `xsxkGgxxkxk` | 公选课选课 | `ggxxkxkOper` | `comeInGgxxkxk` |

> 搜索遍历顺序：`Knjxk → Bxqjhxk → Xxxk → Fawxk → Ggxxkxk`

### 4.2 搜索请求

```
POST /jsxsd/xsxkkc/{module}?<query>
Header: Content-Type: application/x-www-form-urlencoded
```

**Query 参数：**

| 参数 | 说明 |
|------|------|
| `kcxx` | 课程信息（课程号/课程名关键字） |
| `skls` | 授课教师 |
| `sfym` | 是否过滤已满（固定 `false`） |
| `sfct` | 是否过滤冲突（固定 `false`） |
| `sfxx` | 是否过滤限选（固定 `false`） |
| `skxq` | 上课星期（可选） |
| `skjc` | 上课节次（可选） |

**POST Body：**

| 参数 | 值 | 说明 |
|------|-----|------|
| `iDisplayStart` | `0` | 分页起始 |
| `iDisplayLength` | `10000` | 分页长度（一次取全） |

### 4.3 搜索响应（JSON）

```json
{
  "aaData": [
    {
      "kch": "课程号",
      "kcmc": "课程名称",
      "skls": "授课教师",
      "syrs": "剩余人数",
      "jx0404id": "教学班ID",
      "jx02id": "课程ID",
      "sksj": "上课时间",
      "skdd": "上课地点",
      "zcxqjcList": [ { "zc": "周次", "xq": "星期", "jc": "节次" } ]
    }
  ]
}
```

**会话过期判定**：响应同时包含 `请输入账号`、`请输入密码`、`请输入验证码` → 返回 `ErrSessionExpired`。

---

## 五、选课操作

源码：`selection.go`。服务器繁忙时最多重试 3 次（`SelectionMaxRetries`），间隔 200ms。

```
GET /jsxsd/xsxkkc/{operAction}?kcid=<jx02id>&jx0404id=<jx0404id>&_=<毫秒时间戳>
Header: User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Edg/132.0.0.0
Header: Accept: */*
Header: X-Requested-With: XMLHttpRequest
Header: Referer: /jsxsd/xsxkkc/{refererAction}
```

> `operAction` / `refererAction` 由模块类型映射得到（见 4.1 表）。

**响应（JSON）：**

```json
{
  "success": true,        // bool / string("true"/"false") / 数组
  "message": "操作结果消息",
  "jfViewStr": "积分视图字符串"
}
```

**结果判定优先级：**

| 优先级 | message 特征 | 判定 |
|--------|-------------|------|
| 1 | 含 `当前课程已选择其它教学班` | 全局永久失败（IsGlobalPermanent） |
| 2 | 含 `当前教学班已选择` | 视为成功 |
| 3 | 含 `目前选课人数较多服务器忙` | 非终态，外层重试 |
| 4 | `success` 为 true / "true" | 成功 |
| 5 | 其他 | 交由 `FailureClassifier` 三级分类（Transient / ModulePermanent / GlobalPermanent） |

**会话过期判定**：同搜索接口（账号/密码/验证码三词同现）→ `ErrSessionExpired`。

---

## 六、选课轮次管理

源码：`auth.go`。

### 6.1 获取选课轮次列表

```
GET /jsxsd/xsxk/xklc_list
```

- 轮询等待选课入口出现（选课未开放时持续重试，间隔 1s）
- 入口判定：`#jrxk` 元素存在非 `javascript` 开头的 `href`，或 `onclick` 含 `jrxk('`
- 解析 `a[onclick*='xsxkFun']`，从 `href` 中提取 `jx0502zbid` 作为轮次 ID
- 降级：列表为空时，从 `#jrxk` 提取单个轮次
- 完整入口 URL：`/jsxsd/xsxk/xsxk_index?jx0502zbid=<id>`

### 6.2 进入选课轮次

```
GET /jsxsd/xsxk/xsxk_index?jx0502zbid=<id>
```

### 6.3 刷新选课会话（RefreshSelection）

用于退选/补选切换轮次的临界时间：重新访问 `xklc_list` 获取最新入口并进入。

---

## 七、选课结果查询

源码：`result.go`。

```
POST /jsxsd/xkgl/loadXsxkjgList
Header: Content-Type: application/x-www-form-urlencoded
Header: User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/141.0.0.0
Header: Referer: /jsxsd/xkgl/xsxkjgcx
Body: xnxqid=<termID 学期标识>
```

**响应**：HTML 表格。使用 goquery 解析 `table tr`：

- 跳过含 `th` 的表头行；`td` 少于 10 列的行跳过
- 字段映射（按列索引）：

| 列索引 | 字段 |
|--------|------|
| 1 | 课程名称 |
| 2 | 课程编号 |
| 3 | 上课教师 |
| 9 | 选课时间（格式 `2025-08-25 09:00:19.0`） |

- 选课时间按 `Asia/Shanghai` 解析（去除末尾 `.0`）后转为 UTC

---

## 八、错误与重试常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `LoginStepMaxRetries` | 3 | 登录单步最大重试 |
| `MaxCaptchaRetries` | 3 | 验证码识别最大重试 |
| `LoginVerifyMaxRetries` | 2 | 登录状态验证最大重试 |
| `SelectionMaxRetries` | 3 | 选课服务器繁忙最大重试 |
| `RetryDelay` | 1s | 通用重试间隔 |
| `ErrSessionExpired` | — | 会话过期，需重新登录 |

---

*本文档为代码静态分析结果，实际行为以教务系统线上响应为准。*
