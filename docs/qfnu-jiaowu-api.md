# 强智教务系统 HTTP API 文档

本文档描述曲阜师范大学强智教务系统（`zhjw.qfnu.edu.cn`）的登录、选课和选课结果查询接口。

## 基本约定

- **基础地址**：`http://zhjw.qfnu.edu.cn`
- **会话**：所有请求必须使用同一个 Cookie 会话；验证码、`scode`、`sxh` 与该会话绑定。
- **请求头**：未特别说明时使用 `User-Agent: Mozilla/5.0`。
- **重定向**：登录状态验证必须禁止自动跟随重定向，以便识别 `301/302`。
- **超时与重试**：单次请求超时建议 30 秒；网络超时、连接被拒绝/重置、broken pipe、HTTP `429` 或 `5xx` 可在当前步骤最多重试 3 次，间隔 1 秒。业务失败不应按网络错误重试。

## 接口一览

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/` | 初始化会话 |
| `GET` | `/verifycode.servlet` | 获取验证码图片 |
| `POST` | `/Logon.do?method=logon&flag=sess` | 获取 `scode` / `sxh` |
| `POST` | `/Logon.do?method=logonLdap` | 提交登录 |
| `GET` | `/jsxsd/framework/xsMain.jsp` | 学生登录状态验证 |
| `GET` | `/jsxsd/framework/jsMain.jsp` | 教师登录状态验证 |
| `GET` | `/jsxsd/xsxk/xklc_list` | 获取选课轮次 |
| `GET` | `/jsxsd/xsxk/xsxk_index?jx0502zbid=<轮次ID>` | 进入选课轮次 |
| `POST` | `/jsxsd/xsxkkc/{模块}?<查询参数>` | 搜索课程 |
| `GET` | `/jsxsd/xsxkkc/{操作}?kcid=<课程ID>&jx0404id=<教学班ID>&_=<毫秒时间戳>` | 执行选课或退选 |
| `POST` | `/jsxsd/xkgl/loadXsxkjgList` | 查询选课结果 |

## 一、登录流程

按以下顺序执行，整个流程复用同一个 Cookie 会话：

1. 初始化会话。
2. 获取验证码图片。
3. 将验证码图片交给 OCR 服务，得到验证码文本。
4. 获取本次会话的 `scode` 与 `sxh`。
5. 按编码规则生成 `encoded` 并提交登录。
6. 访问角色对应的主页确认登录状态。

验证码错误时，从第 1 步重新开始，整体最多重试 3 轮。

### 1.1 初始化会话

```http
GET /
User-Agent: Mozilla/5.0
```

响应状态码小于 `400` 即可进入下一步；响应中的 Cookie 必须保存到后续请求。

### 1.2 获取验证码

```http
GET /verifycode.servlet
User-Agent: Mozilla/5.0
```

成功条件：HTTP `200` 且响应体非空。响应体为验证码图片二进制数据，验证码必须在当前 Cookie 会话中识别并提交。

### 1.3 OCR 识别验证码

OCR 服务地址由调用方提供：

```http
POST {OCR 服务地址}/ocr
Content-Type: application/x-www-form-urlencoded

image=<验证码图片的 base64 编码>
```

响应示例：

```json
{
  "code": 200,
  "data": "abcd",
  "message": "ok"
}
```

`code` 为数字 `200`、`0` 或对应的数字字符串，且 `data` 去除空格后非空时视为成功；识别失败可在本轮内重试，最多 2 次。

### 1.4 获取 `scode` 与 `sxh`

```http
POST /Logon.do?method=logon&flag=sess
Content-Type: application/x-www-form-urlencoded
User-Agent: Mozilla/5.0

(空请求体)
```

成功响应为纯文本 `<scode>#<sxh>`，两个字段均不能为空。响应为空、为 `no`（不区分大小写）或无法按 `#` 拆分时视为失败。两项参数均为本次会话随机生成的值，每次登录都必须重新获取。

### 1.5 生成 `encoded`

输入：用户名、密码、`scode`、`sxh`。

1. 拼接明文：`username + "%%%" + password`。
2. 遍历明文字符。对索引 `0` 至 `19` 的每个字符，先写入该字符；若 `sxh` 在同一索引处是数字 `n`，则从 `scode` 当前游标处顺序取 `n` 个字符追加，并将游标前移。游标耗尽后不再追加。
3. 索引 `20` 及之后的明文字符原样追加，不再插入 `scode`。

示例：`scode=ABC123`、`sxh=201`、用户名 `u`、密码 `p` 时，明文 `u%%%p` 编码为 `uAB%C%p`。

### 1.6 提交登录

```http
POST /Logon.do?method=logonLdap
Content-Type: application/x-www-form-urlencoded
User-Agent: Mozilla/5.0

userAccount=
userPassword=
RANDOMCODE=<OCR 识别出的验证码>
encoded=<按上述规则生成的值>
```

按响应正文依次判断：

| 响应特征 | 结果 |
| --- | --- |
| 含“密码错误”“用户名或密码错误”“用户名密码错误”或“您提供的用户名或者密码有误” | 账号密码错误，立即终止 |
| 含“验证码错误”或“验证码不正确” | 验证码错误，重新执行完整登录流程 |
| 不含上述错误特征 | 进入登录状态验证 |

### 1.7 登录状态验证

学生访问：

```http
GET /jsxsd/framework/xsMain.jsp
```

教师访问：

```http
GET /jsxsd/framework/jsMain.jsp
```

请求必须禁止自动跟随重定向。成功需同时满足：HTTP `200`，且正文包含“教学一体化服务平台”或“glyphicon-class”。`301/302`、非 `200` 或缺少成功标识均表示登录失败；仅网络错误可重试，最多 2 次。

## 二、选课轮次

### 2.1 获取轮次列表

```http
GET /jsxsd/xsxk/xklc_list
```

选课未开放时可间隔 1 秒轮询。响应页面中的有效入口通常包含 `jx0502zbid` 轮次 ID。

### 2.2 进入轮次

```http
GET /jsxsd/xsxk/xsxk_index?jx0502zbid=<轮次ID>
```

进入后，后续课程搜索和选课请求继续使用同一 Cookie 会话。切换轮次或临界时间操作前，重新获取轮次列表并进入最新入口。

## 三、课程搜索

### 3.1 模块与操作参数

| 模块路径片段 | 说明 | 选课操作参数 | Referer 参数 |
| --- | --- | --- | --- |
| `xsxkKnjxk` | 专业内跨年级选课 | `knjxkOper` | `comeInKnjxk` |
| `xsxkBxqjhxk` | 本学期计划选课 | `bxqjhxkOper` | `comeInBxqjhxk` |
| `xsxkXxxk` | 选修选课 | `xxxkOper` | `comeInXxxk` |
| `xsxkFawxk` | 计划外选课 | `fawxkOper` | `comeInFawxk` |
| `xsxkGgxxkxk` | 公选课选课 | `ggxxkxkOper` | `comeInGgxxkxk` |

### 3.2 搜索请求

```http
POST /jsxsd/xsxkkc/{模块}?kcxx=<课程关键字>&skls=<教师>&sfym=false&sfct=false&sfxx=false&skxq=<星期>&skjc=<节次>
Content-Type: application/x-www-form-urlencoded

iDisplayStart=0
iDisplayLength=10000
```

`kcxx`、`skls`、`skxq`、`skjc` 可按需填写；`sfym`、`sfct`、`sfxx` 用于过滤已满、时间冲突和限选课程。

响应示例：

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
      "zcxqjcList": [{"zc": "周次", "xq": "星期", "jc": "节次"}]
    }
  ]
}
```

若响应同时包含“请输入账号”“请输入密码”“请输入验证码”，表示会话已过期，应重新登录。

## 四、选课与退选

```http
GET /jsxsd/xsxkkc/{操作}?kcid=<课程ID>&jx0404id=<教学班ID>&_=<毫秒时间戳>
User-Agent: Mozilla/5.0
Accept: */*
X-Requested-With: XMLHttpRequest
Referer: /jsxsd/xsxkkc/{Referer参数}
```

`{操作}` 和 Referer 参数按上表模块映射。响应通常为 JSON：

```json
{
  "success": true,
  "message": "操作结果消息",
  "jfViewStr": "积分视图字符串"
}
```

结果按以下优先级判断：

1. `message` 含“当前课程已选择其它教学班”：全局永久失败。
2. `message` 含“当前教学班已选择”：视为成功。
3. `message` 含“目前选课人数较多服务器忙”：临时失败，可重试，最多 3 次，间隔 200ms。
4. `success` 为布尔 `true`、字符串 `"true"` 或等价成功值：成功。
5. 其他响应：按具体错误消息判断临时失败、模块永久失败或全局永久失败。

同课程搜索接口一样，响应同时出现“请输入账号”“请输入密码”“请输入验证码”时表示会话过期，应重新登录。

## 五、选课结果查询

```http
POST /jsxsd/xkgl/loadXsxkjgList
Content-Type: application/x-www-form-urlencoded
User-Agent: Mozilla/5.0
Referer: /jsxsd/xkgl/xsxkjgcx

xnxqid=<学期标识>
```

响应为 HTML 表格。数据行至少包含 10 个 `td` 单元格，字段按列索引如下：

| 列索引 | 字段 |
| --- | --- |
| 1 | 课程名称 |
| 2 | 课程编号 |
| 3 | 上课教师 |
| 9 | 选课时间 |

选课时间示例为 `2025-08-25 09:00:19.0`，按 `Asia/Shanghai` 解析；末尾的 `.0` 可去除。

## 六、通用错误处理

- 网络类错误和 HTTP `429`/`5xx`：按当前接口的重试上限重试。
- 账号密码错误：停止重试并提示用户。
- 验证码错误：回到初始化会话，重新获取验证码和 `scode`/`sxh`。
- 会话过期：重新登录后再请求业务接口。
- 检测到“账号在其它地方登录”：停止自动重登，提示人工处理，避免互相踢出。

*接口返回内容可能因教务系统版本或角色而变化，实际行为以线上响应为准。*
