# 强智教务系统 HTTP API 文档（登录、选课与结果查询）

本文档描述曲阜师范大学强智教务系统（`zhjw.qfnu.edu.cn`）的登录、选课与选课结果查询接口。

## 基本约定

- **基础地址**：`http://zhjw.qfnu.edu.cn`
- **会话**：所有请求复用同一套 Cookie（会话 Cookie，如 `JSESSIONID`）；验证码、`scode`、`sxh` 与该会话绑定。
- **User-Agent**：默认 `Mozilla/5.0`；选课请求使用完整浏览器 UA（Chrome/Edge 132）；结果查询请求使用 Chrome 141。
- **重定向**：登录提交后的 SSO 交接仅允许跟随同源重定向；登录状态验证必须禁止自动跟随重定向，以便识别 `301/302`。

> 响应特征：搜索/选课接口在会话失效时，响应体可能被替换为登录页（同时含 `请输入账号`、`请输入密码`、`请输入验证码`）；账号异地登录时响应体含 `您的账号在其它地方登录`。

## 接口一览

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/` | 初始化会话 |
| `GET` | `/verifycode.servlet` | 获取验证码图片 |
| `POST` | `<OCR 服务>/ocr` | 识别验证码文本 |
| `POST` | `/Logon.do?method=logon&flag=sess` | 获取 `scode` / `sxh` |
| `POST` | `/Logon.do?method=logonLdap` | 提交登录 |
| `GET` | `/jsxsd/framework/xsMain.jsp` | 学生登录状态验证 |
| `GET` | `/jsxsd/framework/jsMain.jsp` | 教师登录状态验证 |
| `GET` | `/jsxsd/xsxk/xklc_list` | 获取选课轮次 |
| `GET` | `/jsxsd/xsxk/xsxk_index?jx0502zbid=<轮次ID>` | 进入选课轮次 |
| `POST` | `/jsxsd/xsxkkc/<模块标识>?<查询参数>` | 搜索课程 |
| `GET` | `/jsxsd/xsxkkc/<操作动作>?kcid=&jx0404id=&_=` | 选课 |
| `GET` | `/jsxsd/xkgl/xsxkjgcx` | 选课结果查询页面 |
| `POST` | `/jsxsd/xkgl/loadXsxkjgList` | 加载选课结果列表 |

---

## 一、登录

登录流程复用同一套 Cookie，成功后 Cookie 中即带有效会话，供后续搜索/选课请求使用。

### 1.1 初始化会话

```http
GET /
User-Agent: Mozilla/5.0
```

- 成功条件：HTTP 状态码 < 400（响应体直接丢弃）。
- 响应中的 Cookie 必须保存并用于后续请求。

### 1.2 获取验证码图片

```http
GET /verifycode.servlet
User-Agent: Mozilla/5.0
```

- 成功条件：HTTP 200 且响应体非空（验证码图片二进制数据）。

### 1.3 OCR 识别验证码（外部服务）

OCR 服务地址由调用方提供：

```http
POST <OCR 服务地址>/ocr
Content-Type: application/x-www-form-urlencoded
User-Agent: Mozilla/5.0
```

表单字段：

| 字段 | 含义 |
| --- | --- |
| `image` | 验证码图片字节的 base64 编码 |

响应（JSON）：

| 字段 | 含义 |
| --- | --- |
| `code` | 数字或字符串，`200` 或 `0` 表示成功 |
| `data` | 识别出的验证码文本 |
| `message` | 错误信息 |

响应示例：

```json
{
  "code": 200,
  "data": "abcd",
  "message": "ok"
}
```

### 1.4 获取 scode / sxh

```http
POST /Logon.do?method=logon&flag=sess
Content-Type: application/x-www-form-urlencoded
User-Agent: Mozilla/5.0

(空请求体)
```

- 响应：纯文本，格式 `scode#sxh`（用 `#` 分割成两段，两段均不能为空）；返回空或 `no` 视为失败。

### 1.5 生成 encoded

输入：用户名、密码、`scode`、`sxh`。

1. 拼接明文：`username + "%%%" + password`。
2. 遍历明文字符，对索引 `0` 至 `19` 的每个字符：先写入该字符；若 `sxh` 在同一索引处是数字 `n`，则从 `scode` 当前游标处顺序取 `n` 个字符追加，并将游标前移（游标耗尽后不再追加）。
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

表单字段：

| 字段 | 值 |
| --- | --- |
| `userAccount` | **空字符串**（账号密码不在此提交，凭证在 `encoded` 中，必须留空） |
| `userPassword` | **空字符串**（同上） |
| `RANDOMCODE` | OCR 识别出的验证码 |
| `encoded` | 1.5 步生成的凭证 |

- **成功响应**：通常为 HTTP `302`，先跳转到 `/jsxsd/xk/LoginToXk?method=jwxt&ticqzket=<一次性票据>`，再通过同源重定向进入 `/jsxsd/framework/xsMain.jsp`；客户端只在该登录交接阶段跟随同源重定向，不得跟随外部源，也不要记录票据。
- **失败响应**：正文可能含 `密码错误` / `用户名或密码错误` / `用户名密码错误` / `您提供的用户名或者密码有误`（表示账号密码错误），或 `验证码错误` / `验证码不正确`（表示验证码错误）。

### 1.7 登录状态验证

学生访问：

```http
GET /jsxsd/framework/xsMain.jsp
```

教师访问：

```http
GET /jsxsd/framework/jsMain.jsp
```

- 请求必须禁止自动跟随重定向（与 1.6 的登录交接阶段不同）。
- 成功条件：HTTP 200，且正文包含 `教学一体化服务平台` 或 `glyphicon-class`。

---

## 二、选课轮次

### 2.1 获取轮次列表

```http
GET /jsxsd/xsxk/xklc_list
```

- 页面中含选课入口元素（`#jrxk`）与轮次列表链接（`a[onclick*=xsxkFun]`）。
- **`jx0502zbid` 参数**：选课轮次 ID，教务系统用它唯一标识一个选课轮次。来源：`#jrxk` 元素的 `href`，或其 `onclick` 中 `jrxk('...')` 的引号内值；轮次列表链接的 URL 查询参数 `jx0502zbid`。

### 2.2 进入选课轮次

```http
GET /jsxsd/xsxk/xsxk_index?jx0502zbid=<轮次ID>
```

- 请求成功即视为已进入该轮次；后续课程搜索和选课请求继续使用同一 Cookie 会话。

---

## 三、课程搜索

### 3.1 模块与操作映射

| 模块标识 | 中文含义 | 操作动作（oper） | 来源页面（referer） |
| --- | --- | --- | --- |
| `xsxkKnjxk` | 专业内跨年级选课 | `knjxkOper` | `comeInKnjxk` |
| `xsxkBxqjhxk` | 本学期计划选课 | `bxqjhxkOper` | `comeInBxqjhxk` |
| `xsxkXxxk` | 选修选课 | `xxxkOper` | `comeInXxxk` |
| `xsxkFawxk` | 计划外选课 | `fawxkOper` | `comeInFawxk` |
| `xsxkGgxxkxk` | 公选课选课 | `ggxxkxkOper` | `comeInGgxxkxk` |

### 3.2 搜索请求

```http
POST /jsxsd/xsxkkc/<模块标识>?kcxx=<课程号>&skls=<教师>&sfym=false&sfct=false&sfxx=false&skxq=<星期>&skjc=<节次编码>
Content-Type: application/x-www-form-urlencoded

iDisplayStart=0&iDisplayLength=10000
```

URL 查询参数：

| 参数 | 含义 |
| --- | --- |
| `kcxx` | 课程号（用户配置的课程编号） |
| `skls` | 授课教师（教师姓名） |
| `sfym` | 是否过滤已满，固定 `false` |
| `sfct` | 是否过滤冲突，固定 `false` |
| `sfxx` | 是否过滤限选，固定 `false` |
| `skxq` | 星期几（仅配置了星期几时携带） |
| `skjc` | 节次编码（仅配置了节次范围时携带，编码规则见 3.3） |

POST 请求体（`application/x-www-form-urlencoded`）：

| 字段 | 值 |
| --- | --- |
| `iDisplayStart` | `0` |
| `iDisplayLength` | `10000` |

- 成功条件：HTTP 200；响应体为 JSON。

### 3.3 节次编码规则（skjc）

| 用户配置值 | 发送的 skjc 值 |
| --- | --- |
| `1-2` | `1-2-` |
| `3-5` | `3-4-5` |
| `6-7` | `6-7-` |
| `8-9` | `8-9-` |
| `10-12` | `10-11-12` |

- 规则：前四档保留起止两端并在末尾加 `-`；跨三档的档位把中间节次展开。未在表中的值原样透传（如 `5-6` → `5-6`，空值 → 不发送）。

### 3.4 搜索响应 JSON

响应格式：`{"aaData": [...]}`，数组每个元素为一门候选课程。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `kch` | string | 课程号 |
| `kcmc` | string | 课程名称 |
| `skls` | string | 授课教师 |
| `syrs` | string | 剩余人数（可能为空或 `"0"`） |
| `jx0404id` | string | 教学班 ID |
| `jx02id` | string | 课程 ID |
| `jx0504id` | int | 开课计划 ID |
| `sksj` | string | 上课时间（展示文本） |
| `xkrs` | int | 选课人数 |
| `pkrs` | int | 排课人数 |
| `dwmc` | string | 开课单位 |
| `ktmc` | string | 课堂名称 |
| `skdd` | string | 上课地点 |
| `ctsm` | string/null | 冲突说明（null 或空表示无冲突） |
| `zcxqjcList` | array | 周次/星期/节次列表，元素为 `{zc 周次, xq 星期, jc 节次}`（均为 string） |

- `aaData` 为空不算错误，返回空结果。

---

## 四、选课

### 4.1 选课请求构造

```http
GET /jsxsd/xsxkkc/<操作动作>?kcid=<课程ID>&jx0404id=<教学班ID>&_=<当前Unix毫秒时间戳>
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0
Accept: */*
X-Requested-With: XMLHttpRequest
Referer: http://zhjw.qfnu.edu.cn/jsxsd/xsxkkc/<来源页面>
```

查询参数：

| 参数 | 含义 |
| --- | --- |
| `kcid` | 课程 ID（候选的 `jx02id`） |
| `jx0404id` | 教学班 ID（候选的 `jx0404id`） |
| `_` | 当前 Unix 毫秒时间戳（防缓存） |

- 成功条件：HTTP 200。

### 4.2 选课响应 JSON

响应格式：`{"success": ..., "message": "...", "jfViewStr": "..."}`。

| 字段 | 含义 |
| --- | --- |
| `success` | 形态不固定，可能是布尔值、字符串或数组 |
| `message` | 教务系统返回的提示文本 |
| `jfViewStr` | 附加文本 |

---

## 五、选课结果查询

### 5.1 选课结果查询页面

```http
GET /jsxsd/xkgl/xsxkjgcx
```

- 选课结果查询页面，作为 5.2 请求的 `Referer` 上下文。

### 5.2 加载选课结果列表

```http
POST /jsxsd/xkgl/loadXsxkjgList
Content-Type: application/x-www-form-urlencoded
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36
Referer: http://zhjw.qfnu.edu.cn/jsxsd/xkgl/xsxkjgcx

xnxqid=<学期ID>
```

表单字段：

| 字段 | 含义 |
| --- | --- |
| `xnxqid` | 学期 ID（学期标识） |

- 响应：HTML 表格。数据行（`<tr>`，无 `<th>` 表头，且 `<td>` 数量 ≥ 10）按列下标（0 起）取值：

| 列下标 | 字段 |
| --- | --- |
| 1 | 课程名称 |
| 2 | 课程编号 |
| 3 | 上课教师 |
| 5 | 学分 |
| 9 | 选课时间 |

- 选课时间格式示例：`2025-08-25 09:00:19.0`，`Asia/Shanghai` 时区，末尾 `.0`（小数秒）可去除。

---

## 附录：关键请求速查表

| 步骤 | 方法 | URL | 关键参数/特征 |
| --- | --- | --- | --- |
| 登录：会话初始化 | GET | `http://zhjw.qfnu.edu.cn` | 读后丢弃响应体 |
| 登录：验证码 | GET | `http://zhjw.qfnu.edu.cn/verifycode.servlet` | 字节流 |
| 登录：OCR | POST | `<OCR>/ocr` | 表单 `image`=base64 |
| 登录：scode/sxh | POST | `http://zhjw.qfnu.edu.cn/Logon.do?method=logon&flag=sess` | 返回 `scode#sxh` |
| 登录：提交 | POST | `http://zhjw.qfnu.edu.cn/Logon.do?method=logonLdap` | 账号字段留空；成功后同源 SSO 302 交接 |
| 登录：确认（学生） | GET | `http://zhjw.qfnu.edu.cn/jsxsd/framework/xsMain.jsp` | 禁止跟随重定向；含"教学一体化服务平台"或"glyphicon-class" |
| 登录：确认（教师） | GET | `http://zhjw.qfnu.edu.cn/jsxsd/framework/jsMain.jsp` | 同上 |
| 轮次列表 | GET | `http://zhjw.qfnu.edu.cn/jsxsd/xsxk/xklc_list` | `#jrxk` 入口；`a[onclick*=xsxkFun]` 列表 |
| 进入轮次 | GET | `http://zhjw.qfnu.edu.cn/jsxsd/xsxk/xsxk_index?jx0502zbid=<id>` | — |
| 搜索 | POST | `http://zhjw.qfnu.edu.cn/jsxsd/xsxkkc/<模块>` | 查询 `kcxx/skls/sfym/sfct/sfxx/skxq/skjc`；体 `iDisplayStart=0&iDisplayLength=10000` |
| 选课 | GET | `http://zhjw.qfnu.edu.cn/jsxsd/xsxkkc/<操作>?kcid=&jx0404id=&_=` | `Referer` 为 `comeIn*` 页面；`X-Requested-With: XMLHttpRequest` |
| 结果查询页面 | GET | `http://zhjw.qfnu.edu.cn/jsxsd/xkgl/xsxkjgcx` | 结果列表的 `Referer` |
| 结果列表 | POST | `http://zhjw.qfnu.edu.cn/jsxsd/xkgl/loadXsxkjgList` | 表单 `xnxqid`=学期 ID；返回 HTML 表格 |

*接口返回内容可能因教务系统版本或角色而变化，实际行为以线上响应为准。*
