# 曲阜师范大学 新生入学考试接口文档（本科生）

> 本文档整理自「智慧曲园」前端（Flutter Web）源码分析与线上实测。
> 适用角色：**本科生**（研究生接口主机/端口不同，不在本文档范围内）。

## 1. 环境与地址

| 项 | 值 |
|---|---|
| Base URL（本科） | `http://xuegong.qfnu.edu.cn:8080` |
| 旧 IP 直连（仍可用） | `http://202.194.176.81:8080` |
| 前端页面 | `http://xuegong.qfnu.edu.cn:8088`（仅静态页面，**不代理 API**，直连会 404） |
| 后端容器 | Jetty 9.4.55（部分错误响应为 Spring Boot 风格 JSON） |
| 认证方式 | 请求头 `Authorization: <token>`（token 来自 `POST /isLogin` 响应的 `data` 字段） |

## 2. 接口一：随机抽题

### 基本信息

| 项 | 值 |
|---|---|
| 方法 | `GET` |
| 路径 | `/enrollQuestion/randomQuestions/{题型}/{数量}` |
| 请求体 | 无 |
| 认证 | 无 Cookie 实测也能返回 200（会话校验宽松），正式环境建议携带 `Authorization` |

### 路径参数

| 参数 | 说明 | 示例 |
|---|---|---|
| `{题型}` | 题目类型，需 URL 编码 | `单选`（`%E5%8D%95%E9%80%89`）；`多选`/`判断`/`填空` 待验证 |
| `{数量}` | 抽取题目数量 | `40` |

### 请求示例

```http
GET /enrollQuestion/randomQuestions/%E5%8D%95%E9%80%89/40 HTTP/1.1
Host: xuegong.qfnu.edu.cn:8080
User-Agent: Dart/3.5 (dart:io)
Authorization: <token>
```

curl：

```bash
curl -X GET \
  "http://xuegong.qfnu.edu.cn:8080/enrollQuestion/randomQuestions/%E5%8D%95%E9%80%89/40" \
  -H "Authorization: <token>"
```

### 响应示例（200）

```json
{
  "timestamp": 1787207944.366038664,
  "data": [
    {
      "type": "单选",
      "question": "学生请假和旷课按课程表上课时间计算；离校旷课每天按（）学时计。",
      "optionA": "5",
      "optionB": "6",
      "optionC": "7",
      "optionD": "8",
      "optionAnswer": "B",
      "fillAnswerShow": null,
      "fillAnswerType": null,
      "fillAnswer": null,
      "fillBlankCount": 0
    }
  ]
}
```

### 响应字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `timestamp` | number | 服务端时间戳（秒，带小数） |
| `data` | array | 题目列表 |
| `data[].type` | string | 题型（如「单选」） |
| `data[].question` | string | 题干 |
| `data[].optionA` ~ `optionD` | string | 四个选项内容（D 可为空，前端会跳过空选项） |
| `data[].optionAnswer` | string | 正确答案（A/B/C/D） |
| `data[].fillAnswerShow` / `fillAnswerType` / `fillAnswer` | string/null | 填空题相关（单选题为 null） |
| `data[].fillBlankCount` | number | 填空空数（单选题为 0） |

## 3. 接口二：上传成绩

### 基本信息

| 项 | 值 |
|---|---|
| 方法 | `POST` |
| 路径 | `/enrollQuestion/uploadScore/{学号}/{分数}` |
| 请求体 | 无（参数全部在 URL 路径上） |
| Content-Type | 无需携带 |
| 认证 | `Authorization: <token>` |

### 路径参数

| 参数 | 说明 | 示例 |
|---|---|---|
| `{学号}` | 学生学号（前端入学记录中的 `studentID` 字段） | `2024********` |
| `{分数}` | 本次得分 | `96` |

### 分数计算规则（前端逻辑）

- 满分 100 = 承诺书 20 分 + 单选 40 题 × 2 分（共 80 分）
- **得分 = 100 − 2 × 错题数**

### 请求示例

```http
POST /enrollQuestion/uploadScore/2024********/96 HTTP/1.1
Host: xuegong.qfnu.edu.cn:8080
User-Agent: Dart/3.5 (dart:io)
Authorization: <token>
```

curl：

```bash
curl -X POST \
  "http://xuegong.qfnu.edu.cn:8080/enrollQuestion/uploadScore/2024********/96" \
  -H "Authorization: <token>"
```

### 响应说明

| 状态码 | 含义 |
|---|---|
| `200` | 上传成功（前端提示「成绩上传成功」） |
| `500` | 服务端错误（常见于学号不存在或参数非法，前端提示「成绩上传出错，请手动上传！」） |

500 错误响应示例（学号不存在时实测）：

```json
{
  "timestamp": 1787208822744,
  "status": 500,
  "error": "Internal Server Error",
  "path": "/enrollQuestion/uploadScore/000000000000/100"
}
```

## 4. 前端业务规则（调用时机）

1. 答题完成后计算得分：`100 - 2×错题数`；
2. 与入学记录中的历史最高分（`/student/enroll` 返回的 `enrollScore` 字段）比较：
   - **新分数更高** → 先更新本地最高分，再调用上传接口；
   - 未超过历史最高分 → 不上传；
3. 若入学记录 `statusNow` 为空或「未注册」，结果页显示「返回欢迎页」，否则显示「返回日常」。

## 5. 注意事项

- `xuegong.qfnu.edu.cn:8088` 是纯前端（Flutter Web「智慧曲园」），nginx 未反向代理 `/enrollQuestion/*`，直接请求会 404；API 必须走 **8080**。
- 旧地址 `http://202.194.176.81:8080` 与域名 8080 为同一后端服务，仍可访问，建议统一使用域名。
- 抽题接口未携带任何会话信息也返回了完整题目（含正确答案），如有安全需求请自行评估。
