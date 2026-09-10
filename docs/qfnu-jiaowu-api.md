# 强智教务系统 HTTP API 文档（登录、选课与结果查询）

本文档描述曲阜师范大学强智教务系统（`zhjw.qfnu.edu.cn`）的登录、选课与选课结果查询接口。含实验学时的课程（课名带 `[讲课学时]` / `[实验学时]`）必须走第四节的拆分学时流程，不能只提交一次 `kcid + jx0404id`。

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
| `POST` | `/jsxsd/xsxkkc/<模块标识>?<查询参数>` | 搜索课程（含讲课/实验拆分班） |
| `GET` | `/jsxsd/xsxkkc/iscx?jx0404id=&kcid=` | 选课前校验（浏览器会调，语义未完全确认） |
| `GET` | `/jsxsd/xsxkkc/<操作动作>?kcid=&jx0404id=&_=` | 选课（普通课） |
| `GET` | `/jsxsd/xsxkkc/<操作动作>?kcid=&cfbs=&jx0404id=` | 选课（拆分学时，见 4.3） |
| `GET` | `/jsxsd/xsxkkc/<模块标识>Cfbs?...` | 拆分学时续选页面 |
| `GET` | `/jsxsd/xkgl/xsxkjgcx` | 选课结果查询页面 |
| `POST` | `/jsxsd/xkgl/loadXsxkjgList` | 加载选课结果列表 |
| `GET` | `/jsxsd/xsxkjg/xsxkkb` | 选课课表页（浏览器选课后会打开） |

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

| 模块标识 | 中文含义 | 操作动作（oper） | 来源页面（referer） | 拆分续选页 |
| --- | --- | --- | --- | --- |
| `xsxkKnjxk` | 专业内跨年级选课 | `knjxkOper` | `comeInKnjxk` | `xsxkKnjxkCfbs` |
| `xsxkBxqjhxk` | 本学期计划选课 | `bxqjhxkOper` | `comeInBxqjhxk` | 未抓包，命名应为 `xsxkBxqjhxkCfbs` |
| `xsxkXxxk` | 选修选课 | `xxxkOper` | `comeInXxxk` | 未抓包 |
| `xsxkFawxk` | 计划外选课 | `fawxkOper` | `comeInFawxk` | 未抓包 |
| `xsxkGgxxkxk` | 公选课选课 | `ggxxkxkOper` | `comeInGgxxkxk` | 未抓包 |

拆分学时样本只覆盖 `xsxkKnjxk`。其它模块的 oper / Referer 仍按上表；续选页按 `xsxk<模块>Cfbs` 推断。

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
- 官方页面搜索体还会带 DataTables 的 `sEcho` / `mDataProp_*`，`iDisplayLength=15`。只发 `iDisplayStart=0&iDisplayLength=10000` 仍然可用。
- 官方 URL 可能多一个空参数 `skxq_xx0103=`，可忽略。

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
| `skdd` | string | 上课地点（可能含 `<br>`、全角空格） |
| `ctsm` | string/null | 冲突说明（null 或空表示无冲突） |
| `zcxqjcList` | array | 周次/星期/节次列表，元素为 `{zc 周次, xq 星期, jc 节次}`（均为 string） |
| `cfbs` | int | 拆分标识。实测：`1`=讲课学时，`4`=实验学时；其它值未观测到 |
| `parentjx0404id` | string | 父教学班 ID。讲课班等于自身 `jx0404id`；实验班指向对应讲课班 |
| `fzmc` | string/null | 实验分组名，如 `分组01`；讲课班为 `null` |
| `xf` | number | 学分（讲课/实验行可能相同） |
| `kcsx` | int | 课程属性（样本为 `3`） |

- `aaData` 为空不算错误，返回空结果。
- 带实验学时的课，**同一次搜索会同时返回讲课班和实验班**。课名形如 `电子测量[讲课学时]`、`电子测量[实验学时]`；`jx02id` 相同，`jx0404id` 不同。

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
- 普通课（无 `[讲课学时]` / `[实验学时]`）按上表即可。
- 拆分学时必须带 `cfbs` 等参数，见 4.3；只提交讲课班会停在「还有[实验学时]需要选」。

### 4.2 选课响应 JSON

响应格式：`{"success": ..., "message": "...", "jfViewStr": "..."}`。

| 字段 | 含义 |
| --- | --- |
| `success` | 形态不固定，可能是布尔值、字符串或数组 |
| `message` | 教务系统返回的提示文本 |
| `jfViewStr` | 附加文本 |

- **`success: true` 不等于整门课选完。** 拆分学时第一次提交也会 `success: true`，但 `message` 含 `还有[...]需要选`，必须继续 4.3。
- 浏览器点「选课」前会先调 `GET /jsxsd/xsxkkc/iscx?jx0404id=<教学班ID>&kcid=<课程ID>`，样本响应 `{"status":[false,true]}`。两布尔的精确含义未确认，选课主路径不依赖它。

### 4.3 拆分学时选课（讲课学时 + 实验学时）

适用：搜索结果里同一 `jx02id` 同时出现 `[讲课学时]` 和 `[实验学时]`，或选课响应 `message` 含 `还有[`。

样本来源：专业内跨年级（`xsxkKnjxk` / `knjxkOper` / `comeInKnjxk`），学期 `2025-2026-1`。其它模块未抓包，页面脚本命名规律是 `xsxk<模块>Cfbs`，oper 仍用该模块的 `<操作动作>`。

**不要只提交讲课班。** 只选讲课会停在「还有[实验学时]需要选」；实验分组（`分组01` / `分组02`）时间和节次不同，必须再选一个实验班。

#### 流程

```text
搜索（kcxx=课程号）
  → aaData 里同时有 讲课班 cfbs=1 和若干实验班 cfbs=4
选讲课班
  GET knjxkOper?kcid=<jx02id>&cfbs=1&jx0404id=<讲课班ID>&xkzy=&trjf=&_=<毫秒>
  → {"success":true,"message":"还有[实验学时]需要选","cfbs":"4","yxcfbs":"1","yxjx0404id":"<讲课班ID>","jfViewStr":""}
打开续选页（浏览器弹窗，程序可跳过 HTML，直接搜）
  GET /jsxsd/xsxkkc/xsxkKnjxkCfbs?kcid=<jx02id>&cfbs=4&yxjx0404id=<讲课班ID>&yxcfbs=1&xkzy=&trjf=
搜剩余学时班
  POST /jsxsd/xsxkkc/xsxkKnjxk?kcid=<jx02id>&cfbs=4&yxjx0404id=<讲课班ID>
  body: 与普通搜索相同的 DataTables 字段
  → 只返回实验班（本样本 2 条：周六 1-2 节分组01、周六 3-4 节分组02）
选实验班
  GET knjxkOper?kcid=<jx02id>&cfbs=4&yxcfbs=1&yxjx0404id=<讲课班ID>&cfmyz=1&jx0404id=<实验班ID>&xkzy=&trjf=
  → {"success":true,"message":"选课成功","jfViewStr":""}
```

页面脚本：若 `message` 仍含 `还有`，用返回的 `cfbs` / `yxcfbs` / `yxjx0404id` 再搜再选（理论上可有第三段学时，本样本只有讲课+实验两段）。`message` 不再含 `还有` 才算整门完成。

#### 第一次提交（讲课班）

```http
GET /jsxsd/xsxkkc/knjxkOper?kcid=<jx02id>&cfbs=1&jx0404id=<讲课班jx0404id>&xkzy=&trjf=&_=<Unix毫秒>
X-Requested-With: XMLHttpRequest
Referer: http://zhjw.qfnu.edu.cn/jsxsd/xsxkkc/comeInKnjxk
```

| 参数 | 来源 | 含义 |
| --- | --- | --- |
| `kcid` | 行的 `jx02id` | 课程 ID，讲课/实验相同 |
| `cfbs` | 讲课行的 `cfbs`，样本 `1` | 本段学时类型 |
| `jx0404id` | 讲课行的 `jx0404id` | 讲课教学班 |
| `xkzy` | 空 | 选课志愿（样本未填） |
| `trjf` | 空 | 投入积分（样本未填） |
| `_` | 当前毫秒 | 防缓存 |

未完成响应示例：

```json
{
  "success": true,
  "message": "还有[实验学时]需要选",
  "cfbs": "4",
  "yxcfbs": "1",
  "yxjx0404id": "<讲课班jx0404id>",
  "jfViewStr": ""
}
```

| 字段 | 含义 |
| --- | --- |
| `cfbs` | 下一段要选的学时类型（样本 `4`=实验） |
| `yxcfbs` | 已经选上的学时类型（样本 `1`=讲课） |
| `yxjx0404id` | 已经选上的教学班 ID，后续请求原样带回 |

#### 续选搜索（只列出剩余学时班）

```http
POST /jsxsd/xsxkkc/xsxkKnjxk?kcid=<jx02id>&cfbs=4&yxjx0404id=<讲课班jx0404id>
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
X-Requested-With: XMLHttpRequest
Referer: http://zhjw.qfnu.edu.cn/jsxsd/xsxkkc/xsxkKnjxkCfbs?kcid=<jx02id>&cfbs=4&yxjx0404id=<讲课班jx0404id>&yxcfbs=1&xkzy=&trjf=

sEcho=1&iColumns=12&sColumns=&iDisplayStart=0&iDisplayLength=15&mDataProp_0=kch&mDataProp_1=kcmc&mDataProp_2=fzmc&mDataProp_3=xf&mDataProp_4=skls&mDataProp_5=sksj&mDataProp_6=skdd&mDataProp_7=xqmc&mDataProp_8=xkrs&mDataProp_9=syrs&mDataProp_10=ctsm&mDataProp_11=czOper
```

- 这里的查询参数是 `kcid + cfbs + yxjx0404id`，**不再用 `kcxx`**。
- 返回的实验班 `parentjx0404id` 等于已选讲课班；`fzmc` 为分组名。

#### 第二次提交（实验班）

```http
GET /jsxsd/xsxkkc/knjxkOper?kcid=<jx02id>&cfbs=4&yxcfbs=1&yxjx0404id=<讲课班jx0404id>&cfmyz=1&jx0404id=<实验班jx0404id>&xkzy=&trjf=
X-Requested-With: XMLHttpRequest
Referer: http://zhjw.qfnu.edu.cn/jsxsd/xsxkkc/xsxkKnjxkCfbs?...
```

| 参数 | 来源 | 含义 |
| --- | --- | --- |
| `cfbs` | 实验行 / 上一次响应，样本 `4` | 本段学时类型 |
| `yxcfbs` | 上一次响应 | 已选学时类型 |
| `yxjx0404id` | 上一次响应 | 已选讲课班 |
| `cfmyz` | 页面写死 `1` | 拆分确认标记；续选必须带 |
| `jx0404id` | 选中的实验行 | 实验教学班（不要再传讲课班 ID） |

完成响应示例：

```json
{
  "success": true,
  "message": "选课成功",
  "jfViewStr": ""
}
```

官方续选页用 `$.ajax({url: knjxkOper+param, data:{jx0404id,xkzy,trjf}, async:false})`，GET 时 `data` 会拼进 query，与上面整串 query 等价。

#### 识别与定位

| 信号 | 用法 |
| --- | --- |
| `kcmc` 含 `[讲课学时]` / `[实验学时]` | 必须走拆分流程 |
| `cfbs` | `1` 先选讲课，`4` 再选实验 |
| `parentjx0404id` | 实验班挂在哪节讲课班下 |
| `fzmc` | 区分实验分组（同场地不同节次） |
| `message` 含 `还有` | 还没选完，用返回的 `cfbs/yxcfbs/yxjx0404id` 继续 |

样本结构（字段已脱敏）：

| 行 | kcmc | cfbs | fzmc | 时间 | 地点 |
| --- | --- | --- | --- | --- | --- |
| 讲课 | `…[讲课学时]` | 1 | null | 1-12 周 周二 5-7 节 | 格物楼B101 |
| 实验分组01 | `…[实验学时]` | 4 | 分组01 | 1-18 周 周六 1-2 节 | 实验中心C区C609、C611 |
| 实验分组02 | `…[实验学时]` | 4 | 分组02 | 1-18 周 周六 3-4 节 | 同上（节次不同） |

选课课表 `/jsxsd/xsxkjg/xsxkkb` 成功后会同时出现 `…[讲课学时]` 与 `…[实验学时](分组02)`。

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

### 5.3 选课课表页

浏览器选课成功后会打开：

```http
GET /jsxsd/xsxkjg/xsxkkb
Referer: http://zhjw.qfnu.edu.cn/jsxsd/xsxkkc/comeInKnjxk
```

- 拆分学时课程在课表里分行显示讲课与实验（实验行课名后带分组，如 `(分组02)`）。
- 程序验收可用 5.2 列表，不必依赖本页。

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
| 选课前校验 | GET | `http://zhjw.qfnu.edu.cn/jsxsd/xsxkkc/iscx?jx0404id=&kcid=` | 样本 `{"status":[false,true]}` |
| 选课（普通） | GET | `http://zhjw.qfnu.edu.cn/jsxsd/xsxkkc/<操作>?kcid=&jx0404id=&_=` | `Referer` 为 `comeIn*`；`X-Requested-With: XMLHttpRequest` |
| 选课（讲课段） | GET | 同上，加 `cfbs=1` | `success:true` 且 `message` 含 `还有` 时未完成 |
| 拆分续选页 | GET | `http://zhjw.qfnu.edu.cn/jsxsd/xsxkkc/<模块>Cfbs?kcid=&cfbs=&yxjx0404id=&yxcfbs=` | HTML；程序可跳过，直接续搜 |
| 续选搜索 | POST | `http://zhjw.qfnu.edu.cn/jsxsd/xsxkkc/<模块>?kcid=&cfbs=&yxjx0404id=` | 只用 `kcid`，不用 `kcxx` |
| 选课（实验段） | GET | `<操作>?kcid=&cfbs=4&yxcfbs=1&yxjx0404id=&cfmyz=1&jx0404id=` | `message` 为 `选课成功` 才算整门完成 |
| 结果查询页面 | GET | `http://zhjw.qfnu.edu.cn/jsxsd/xkgl/xsxkjgcx` | 结果列表的 `Referer` |
| 结果列表 | POST | `http://zhjw.qfnu.edu.cn/jsxsd/xkgl/loadXsxkjgList` | 表单 `xnxqid`=学期 ID；返回 HTML 表格 |
| 选课课表 | GET | `http://zhjw.qfnu.edu.cn/jsxsd/xsxkjg/xsxkkb` | 浏览器选课后打开；讲课/实验分行显示 |

*接口返回内容可能因教务系统版本或角色而变化，实际行为以线上响应为准。*
