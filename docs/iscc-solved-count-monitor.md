---
issue: 13
title: "[自动化监控] ISCC 题目解出数量监控与飞书告警脚本"
source: https://github.com/w1ndys/prompts/issues/13
state: closed
---

# ISCC 题目解出数量监控脚本开发文档

## 1. 目标

实现一个可被 `cron` 等定时任务周期性运行的脚本，用于监控 ISCC 平台三个赛道中“我方未解出题目”的解出人数变化。

脚本需要完成：

1. 自动登录 ISCC。
2. 缓存登录 Cookie，避免每次运行都重新登录。
3. 获取三个赛道的题目列表。
4. 获取我方已经解出的题目，用于过滤。
5. 缓存每个“我方未解出题目”的历史解出数量。
6. 当某题当前解出数量相比上次缓存数量增加超过 `10` 时：
   - 拉取该题具体解出人列表；
   - 通过飞书机器人发送 Markdown 富文本告警。
7. 更新本地缓存，供下次运行比对。

> 注意：抓包中包含明文账号密码，开发时不要写死在代码中，应放入环境变量或配置文件，并建议及时更换已泄露密码。

---

## 2. 请求流程分析

### 2.1 基础信息

ISCC 站点域名：

```text
https://iscc.isclab.org.cn
```

大多数接口为同源 XHR 请求，通用请求头：

```http
Accept: */*
X-Requested-With: XMLHttpRequest
Referer: 对应页面地址
User-Agent: 浏览器 UA
```

登录接口是表单提交：

```http
Content-Type: application/x-www-form-urlencoded
```

---

## 3. 登录流程

### 3.1 登录请求

抓包中的登录请求：

```http
POST https://iscc.isclab.org.cn/login
Content-Type: application/x-www-form-urlencoded
```

请求体：

```text
name=<用户名>&password=<密码>
```

示例：

```text
name=W1ndys&password=******
```

### 3.2 登录响应

响应状态码：

```http
302 FOUND
```

重定向到队伍页面：

```text
https://iscc.isclab.org.cn/team/{team_id}
```

示例：

```text
/team/b5fb4ac70c4d684db5f2ffced81b0b42
```

### 3.3 登录后相关接口

登录后队伍页面会请求：

```http
GET /solves/{team_id}
GET /fails/{team_id}
```

其中：

- `/solves/{team_id}`：获取该队伍已解出题目。
- `/fails/{team_id}`：获取该队伍提交失败记录。

本程序主要使用 `/solves/{team_id}` 判断“我方已解出题目”。

---

## 4. 三个赛道接口梳理

从抓包看，ISCC 有三个赛道，分别对应三组接口。

---

### 4.1 普通题目赛道 Challenges

#### 4.1.1 题目列表

```http
GET https://iscc.isclab.org.cn/chals
Referer: https://iscc.isclab.org.cn/challenges
```

返回 JSON，内容为普通题目列表。

#### 4.1.2 解出数量列表

```http
GET https://iscc.isclab.org.cn/solves
Referer: https://iscc.isclab.org.cn/challenges
```

返回 JSON，内容为普通题目的解出数量汇总。

#### 4.1.3 题目详情

```http
GET https://iscc.isclab.org.cn/chals/{challenge_id}
Referer: https://iscc.isclab.org.cn/challenges
```

示例：

```http
GET /chals/28
```

#### 4.1.4 具体解出人

```http
GET https://iscc.isclab.org.cn/chal/{challenge_id}/solves
Referer: https://iscc.isclab.org.cn/challenges
```

示例：

```http
GET /chal/28/solves
```

该接口返回体可能较大，例如抓包中 `/chal/28/solves` 返回约 `306 KB`。

---

### 4.2 擂台赛道 Arena

#### 4.2.1 题目列表

```http
GET https://iscc.isclab.org.cn/arenas
Referer: https://iscc.isclab.org.cn/arena
```

#### 4.2.2 解出数量列表

```http
GET https://iscc.isclab.org.cn/arenasolves
Referer: https://iscc.isclab.org.cn/arena
```

#### 4.2.3 题目详情

```http
GET https://iscc.isclab.org.cn/arenas/{arena_id}
Referer: https://iscc.isclab.org.cn/arena
```

示例：

```http
GET /arenas/4
```

#### 4.2.4 具体解出人

```http
GET https://iscc.isclab.org.cn/are/{arena_id}/solves
Referer: https://iscc.isclab.org.cn/arena
```

示例：

```http
GET /are/4/solves
```

---

### 4.3 闯关 / 测评赛道 Measure

#### 4.3.1 题目列表

```http
GET https://iscc.isclab.org.cn/measures
Referer: https://iscc.isclab.org.cn/measure
```

#### 4.3.2 解出数量列表

```http
GET https://iscc.isclab.org.cn/solves_measure
Referer: https://iscc.isclab.org.cn/measure
```

#### 4.3.3 题目详情

```http
GET https://iscc.isclab.org.cn/measure/{measure_id}
Referer: https://iscc.isclab.org.cn/measure
```

示例：

```http
GET /measure/3
```

#### 4.3.4 具体解出人

```http
GET https://iscc.isclab.org.cn/measure/{measure_id}/solves
Referer: https://iscc.isclab.org.cn/measure
```

示例：

```http
GET /measure/3/solves
```

---

## 5. 推荐程序运行流程

整体流程如下：

```text
启动脚本
  |
  v
读取配置
  |
  v
加载本地 Cookie 缓存
  |
  v
使用 Cookie 请求一个需要登录的接口验证登录状态
  |
  +-- Cookie 有效 --> 继续
  |
  +-- Cookie 无效 --> 执行登录，保存新 Cookie
  |
  v
获取 team_id
  |
  v
获取我方已解出题目列表 /solves/{team_id}
  |
  v
并发获取三个赛道：
    - 题目列表
    - 解出数量列表
  |
  v
合并题目数据，过滤我方已解题目
  |
  v
读取本地 solve_count 缓存
  |
  v
对每个未解出题目比较：
    delta = 当前解出数量 - 上次解出数量
  |
  +-- delta > 10 --> 拉取具体解出人列表，发送飞书告警
  |
  +-- delta <= 10 --> 不告警
  |
  v
更新本地缓存
  |
  v
结束
```

---

## 6. 配置设计

建议使用环境变量或 `.env` 文件。

### 6.1 环境变量

```bash
ISCC_USERNAME="your_username"
ISCC_PASSWORD="your_password"
ISCC_BASE_URL="https://iscc.isclab.org.cn"

FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxxx"

ALERT_THRESHOLD=10

CACHE_DIR="./cache"
COOKIE_FILE="./cache/iscc_cookie.json"
STATE_FILE="./cache/solve_state.json"
```

### 6.2 配置说明

| 配置 | 说明 |
|---|---|
| `ISCC_USERNAME` | ISCC 用户名 |
| `ISCC_PASSWORD` | ISCC 密码 |
| `ISCC_BASE_URL` | ISCC 站点地址 |
| `FEISHU_WEBHOOK` | 飞书机器人 Webhook |
| `ALERT_THRESHOLD` | 解出数量变化阈值，默认 `10` |
| `CACHE_DIR` | 缓存目录 |
| `COOKIE_FILE` | Cookie 缓存文件 |
| `STATE_FILE` | 解出数量状态缓存文件 |

---

## 7. 本地缓存设计

### 7.1 Cookie 缓存

文件：

```text
cache/iscc_cookie.json
```

推荐结构：

```json
{
  "cookies": [
    {
      "name": "session",
      "value": "xxxx",
      "domain": "iscc.isclab.org.cn",
      "path": "/",
      "expires": 1770000000
    }
  ],
  "team_id": "b5fb4ac70c4d684db5f2ffced81b0b42",
  "updated_at": "2026-05-09T09:30:00+08:00"
}
```

说明：

- 如果登录响应中存在 `Set-Cookie`，需要持久化。
- `team_id` 可以从登录后 `302 Location` 中提取。
- 如果 Cookie 失效，重新登录并覆盖该文件。

---

### 7.2 解出数量缓存

文件：

```text
cache/solve_state.json
```

推荐结构：

```json
{
  "version": 1,
  "updated_at": "2026-05-09T09:30:00+08:00",
  "items": {
    "challenge:28": {
      "track": "challenge",
      "id": 28,
      "title": "题目名称",
      "category": "Web",
      "solve_count": 123,
      "last_alert_count": 123,
      "updated_at": "2026-05-09T09:30:00+08:00"
    },
    "arena:4": {
      "track": "arena",
      "id": 4,
      "title": "题目名称",
      "category": "Arena",
      "solve_count": 45,
      "last_alert_count": 45,
      "updated_at": "2026-05-09T09:30:00+08:00"
    },
    "measure:3": {
      "track": "measure",
      "id": 3,
      "title": "题目名称",
      "category": "Measure",
      "solve_count": 67,
      "last_alert_count": 67,
      "updated_at": "2026-05-09T09:30:00+08:00"
    }
  }
}
```

### 7.3 缓存 Key 设计

不同赛道的 ID 可能重复，因此缓存 Key 必须带赛道前缀：

```text
challenge:{id}
arena:{id}
measure:{id}
```

示例：

```text
challenge:28
arena:4
measure:3
```

---

## 8. 数据标准化设计

由于抓包中没有具体 JSON 内容，只能根据接口语义做兼容式解析。

建议在程序中统一转换为标准结构。

### 8.1 标准题目结构

```ts
interface ChallengeItem {
  key: string;              // challenge:28
  track: string;            // challenge | arena | measure
  id: number | string;
  title: string;
  category?: string;
  score?: number;
  solvedByMe: boolean;
  solveCount: number;
}
```

### 8.2 三个赛道配置

```ts
const TRACKS = [
  {
    track: "challenge",
    listUrl: "/chals",
    solveCountUrl: "/solves",
    detailUrl: id => `/chals/${id}`,
    solverUrl: id => `/chal/${id}/solves`,
    referer: "/challenges"
  },
  {
    track: "arena",
    listUrl: "/arenas",
    solveCountUrl: "/arenasolves",
    detailUrl: id => `/arenas/${id}`,
    solverUrl: id => `/are/${id}/solves`,
    referer: "/arena"
  },
  {
    track: "measure",
    listUrl: "/measures",
    solveCountUrl: "/solves_measure",
    detailUrl: id => `/measure/${id}`,
    solverUrl: id => `/measure/${id}/solves`,
    referer: "/measure"
  }
]
```

---

## 9. 登录状态判断

### 9.1 优先使用 Cookie 访问接口

可以用以下接口之一验证 Cookie：

```http
GET /chals
```

或者：

```http
GET /solves/{team_id}
```

判断逻辑：

1. 返回 `200`。
2. `Content-Type` 是 `application/json`。
3. 响应体能正常解析 JSON。
4. 没有被重定向到 `/login`。
5. 没有返回登录页 HTML。

伪代码：

```python
def is_logged_in(session):
    resp = session.get("/chals", allow_redirects=False)
    if resp.status_code in [301, 302] and "/login" in resp.headers.get("Location", ""):
        return False
    if resp.status_code != 200:
        return False
    if "application/json" not in resp.headers.get("Content-Type", ""):
        return False
    return True
```

---

## 10. 登录实现

### 10.1 请求

```http
POST /login
Content-Type: application/x-www-form-urlencoded
```

表单：

```python
{
    "name": ISCC_USERNAME,
    "password": ISCC_PASSWORD
}
```

### 10.2 成功判断

登录成功时：

- 状态码通常为 `302`；
- `Location` 指向 `/team/{team_id}`；
- Cookie Jar 中应有登录态 Cookie。

伪代码：

```python
def login(session):
    resp = session.post(
        BASE_URL + "/login",
        data={
            "name": USERNAME,
            "password": PASSWORD
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": BASE_URL + "/login",
            "Origin": BASE_URL
        },
        allow_redirects=False
    )

    if resp.status_code != 302:
        raise RuntimeError("登录失败：未返回 302")

    location = resp.headers.get("Location", "")
    team_id = parse_team_id(location)

    if not team_id:
        raise RuntimeError("登录失败：无法从 Location 中提取 team_id")

    save_cookie(session.cookies, team_id)
    return team_id
```

### 10.3 team_id 提取

```python
import re

def parse_team_id(location):
    m = re.search(r"/team/([a-fA-F0-9]+)", location)
    if m:
        return m.group(1)
    return None
```

---

## 11. 获取我方已解题目

接口：

```http
GET /solves/{team_id}
```

示例：

```http
GET /solves/b5fb4ac70c4d684db5f2ffced81b0b42
```

用途：

- 判断哪些题目已经被我方解决；
- 后续监控只关注“我方未解出题目”。

需要注意：

抓包中 `/solves/{team_id}` 返回内容大小与 `/solves` 相同，具体结构需要在实际调试时确认。

建议解析策略：

1. 如果返回数组：
   - 遍历每一项；
   - 尝试读取 `chalid`、`chal_id`、`challenge_id`、`id` 等字段。
2. 如果返回对象：
   - 尝试从 `solves`、`data`、`items` 字段取数组。
3. 对不同赛道可能需要区分字段，比如：
   - `type`
   - `category`
   - `track`
   - `chal_type`

建议实现一个兼容解析函数：

```python
def extract_solved_keys_by_me(team_solves_json):
    """
    返回 Set[str]
    例如：
    {
      "challenge:28",
      "arena:4",
      "measure:3"
    }
    """
```

如果无法可靠区分赛道，至少需要记录 ID，并在三个赛道中做保守匹配。但更推荐通过实际响应 JSON 补充字段映射。

---

## 12. 获取三个赛道题目和解出数量

### 12.1 普通题目

请求：

```http
GET /chals
GET /solves
```

### 12.2 Arena

请求：

```http
GET /arenas
GET /arenasolves
```

### 12.3 Measure

请求：

```http
GET /measures
GET /solves_measure
```

### 12.4 并发请求建议

三组赛道可以并发拉取：

```python
tracks_data = await gather(
    fetch_track("challenge"),
    fetch_track("arena"),
    fetch_track("measure")
)
```

但需要注意：

- 不建议并发拉取所有具体解出人列表；
- 只有触发告警的题目才拉取具体解出人；
- 具体解出人接口返回体可能较大。

---

## 13. 解出数量解析

### 13.1 目标

把接口返回的解出数量统一转换成：

```python
{
    "challenge:28": 123,
    "arena:4": 45,
    "measure:3": 67
}
```

### 13.2 兼容字段

解出数量接口可能返回以下字段之一：

```text
id
chalid
chal_id
challenge_id
arena_id
measure_id
solves
solve_count
count
value
```

建议实现宽松解析：

```python
def get_id(item):
    for key in ["chalid", "chal_id", "challenge_id", "arena_id", "measure_id", "id"]:
        if key in item:
            return item[key]
    return None

def get_solve_count(item):
    for key in ["solves", "solve_count", "count", "value"]:
        if key in item:
            return int(item[key])
    return 0
```

---

## 14. 告警判断逻辑

### 14.1 只监控未解出题目

过滤逻辑：

```python
unsolved_items = [
    item for item in all_items
    if item.key not in solved_by_me
]
```

### 14.2 阈值判断

需求是：

> 当检测到数量比上次检查相差超过 10 的时候，发送飞书机器人上报。

判断：

```python
delta = current_count - previous_count

if delta > ALERT_THRESHOLD:
    alert()
```

默认：

```python
ALERT_THRESHOLD = 10
```

### 14.3 首次运行

首次运行没有历史缓存，应只建立基线，不发送告警。

```python
if previous_count is None:
    save_current_as_baseline()
    continue
```

否则第一次运行可能会对所有已有解题数较多的题目发送大量告警。

### 14.4 数量减少

如果出现当前数量小于历史数量：

```python
delta < 0
```

可能原因：

- 平台重新计数；
- 题目下架；
- 解题记录清理；
- 缓存错误。

建议：

- 不发送增长告警；
- 更新缓存为当前值；
- 可记录 warning 日志。

---

## 15. 具体解出人列表

只有在触发告警时请求具体解出人接口。

### 15.1 普通题目

```http
GET /chal/{id}/solves
```

### 15.2 Arena

```http
GET /are/{id}/solves
```

### 15.3 Measure

```http
GET /measure/{id}/solves
```

### 15.4 解出人展示策略

具体解出人接口可能返回很多数据，不建议完整发到飞书。

建议只展示最近若干条，例如最近 10 条或 20 条。

```python
MAX_SOLVER_DISPLAY = 10
```

告警中展示：

- 最近解出队伍名；
- 解出时间；
- 排名或用户 ID，如果有。

字段兼容：

```text
team
team_name
name
user
username
date
time
created_at
```

---

## 16. 飞书机器人告警

### 16.1 Webhook

```http
POST {FEISHU_WEBHOOK}
Content-Type: application/json
```

### 16.2 推荐使用 interactive Markdown 卡片

飞书机器人支持 `interactive` 消息，可以使用 Markdown 元素。

示例 payload：

```json
{
  "msg_type": "interactive",
  "card": {
    "config": {
      "wide_screen_mode": true
    },
    "header": {
      "title": {
        "tag": "plain_text",
        "content": "ISCC 解出数量异常增长"
      },
      "template": "orange"
    },
    "elements": [
      {
        "tag": "markdown",
        "content": "**题目**：Web 签到题\n**赛道**：challenge\n**题目 ID**：28\n**当前解出数**：123\n**上次解出数**：110\n**增长**：+13\n**阈值**：10"
      },
      {
        "tag": "hr"
      },
      {
        "tag": "markdown",
        "content": "**最近解出队伍**：\n1. teamA - 2026-05-09 09:20:01\n2. teamB - 2026-05-09 09:21:13"
      }
    ]
  }
}
```

### 16.3 Markdown 内容模板

```markdown
**ISCC 解出数量异常增长**

**题目**：{title}
**赛道**：{track}
**分类**：{category}
**题目 ID**：{id}

**当前解出数**：{current_count}
**上次检查数**：{previous_count}
**增长数量**：+{delta}
**告警阈值**：{threshold}

**最近解出队伍**：
{solver_list}
```

### 16.4 失败重试

飞书发送失败时建议：

- 记录日志；
- 可重试 2 次；
- 不要因为飞书失败阻止缓存更新，否则下次会重复告警。

---

## 17. HTTP 请求头设计

建议统一请求头：

```python
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}
```

不同接口补充 `Referer`：

```python
def headers_for(referer_path):
    h = DEFAULT_HEADERS.copy()
    h["Referer"] = BASE_URL + referer_path
    return h
```

登录时补充：

```python
{
    "Origin": BASE_URL,
    "Referer": BASE_URL + "/login",
    "Content-Type": "application/x-www-form-urlencoded"
}
```

---

## 18. 异常处理

### 18.1 Cookie 失效

表现：

- 接口返回 `302 /login`；
- 接口返回 HTML 登录页；
- 状态码 `401`、`403`；
- JSON 解析失败。

处理：

```text
重新登录 -> 保存 Cookie -> 重试当前请求一次
```

### 18.2 接口失败

接口失败时：

- 记录错误；
- 当前赛道可以跳过；
- 不建议清空缓存。

### 18.3 缓存文件损坏

处理：

- 备份损坏文件，例如 `solve_state.json.bak`；
- 重新初始化；
- 首次初始化不发送告警。

### 18.4 题目下架

如果缓存中存在，但本次题目列表中不存在：

- 保留缓存；
- 或标记为 `inactive`；
- 不参与告警。

---

## 19. cron 示例

每 5 分钟执行一次：

```bash
*/5 * * * * cd /opt/iscc-monitor && /usr/bin/python3 main.py >> logs/cron.log 2>&1
```

建议使用文件锁，避免上一次未结束时下一次又启动。

示例：

```bash
*/5 * * * * flock -n /tmp/iscc-monitor.lock bash -c 'cd /opt/iscc-monitor && /usr/bin/python3 main.py >> logs/cron.log 2>&1'
```

---

## 20. 推荐目录结构

```text
iscc-monitor/
├── main.py
├── config.py
├── iscc_client.py
├── parser.py
├── cache.py
├── feishu.py
├── requirements.txt
├── .env
├── cache/
│   ├── iscc_cookie.json
│   └── solve_state.json
└── logs/
    └── cron.log
```

---

## 21. Python 依赖建议

`requirements.txt`：

```text
requests
python-dotenv
filelock
```

如果希望异步并发，可使用：

```text
httpx
python-dotenv
filelock
```

---

## 22. 核心伪代码

```python
def main():
    config = load_config()

    with file_lock():
        client = IsccClient(config)

        client.load_cookie()

        if not client.is_logged_in():
            client.login()

        team_id = client.get_team_id()
        solved_by_me = client.fetch_my_solves(team_id)

        all_items = []

        for track in TRACKS:
            challenges = client.fetch_json(track.listUrl, track.referer)
            solve_counts = client.fetch_json(track.solveCountUrl, track.referer)

            normalized_items = normalize_track_items(
                track=track,
                challenges=challenges,
                solve_counts=solve_counts,
                solved_by_me=solved_by_me
            )

            all_items.extend(normalized_items)

        state = load_state()

        alerts = []

        for item in all_items:
            if item.solvedByMe:
                continue

            previous = state.get(item.key)

            if previous is None:
                state[item.key] = make_state_item(item)
                continue

            previous_count = previous["solve_count"]
            current_count = item.solveCount
            delta = current_count - previous_count

            if delta > config.ALERT_THRESHOLD:
                solvers = client.fetch_solvers(item.track, item.id)
                send_feishu_alert(
                    item=item,
                    previous_count=previous_count,
                    current_count=current_count,
                    delta=delta,
                    solvers=solvers
                )

            state[item.key] = make_state_item(item)

        save_state(state)
```

---

## 23. 关键实现注意事项

1. **不要硬编码账号密码**
   抓包中的密码已经暴露，应尽快更换，并通过环境变量注入。

2. **Cookie 缓存必须加权限保护**
   建议：

   ```bash
   chmod 600 cache/iscc_cookie.json
   chmod 600 .env
   ```

3. **首次运行不告警**
   首次运行只建立基线。

4. **只监控我方未解出题目**
   防止已解题目解出数增长造成无意义告警。

5. **具体解出人接口按需调用**
   例如 `/chal/28/solves` 返回 300KB，不适合每次全量拉取。

6. **飞书告警建议合并**
   如果一次运行多个题目触发告警，可以：
   - 每题一条消息；
   - 或合并为一条卡片消息。

7. **缓存更新时机**
   建议即使飞书发送失败，也更新 `solve_count`，但可以记录 `last_alert_failed`，避免下次重复轰炸。

8. **日志中不要打印密码、Cookie、Webhook**。

---

## 24. 接口总表

| 功能 | 方法 | 路径 | Referer |
|---|---:|---|---|
| 登录 | POST | `/login` | `/login` |
| 队伍已解 | GET | `/solves/{team_id}` | `/team/{team_id}` |
| 队伍失败提交 | GET | `/fails/{team_id}` | `/team/{team_id}` |
| 普通题目列表 | GET | `/chals` | `/challenges` |
| 普通题解出数量 | GET | `/solves` | `/challenges` |
| 普通题详情 | GET | `/chals/{id}` | `/challenges` |
| 普通题解出人 | GET | `/chal/{id}/solves` | `/challenges` |
| Arena 题目列表 | GET | `/arenas` | `/arena` |
| Arena 解出数量 | GET | `/arenasolves` | `/arena` |
| Arena 题目详情 | GET | `/arenas/{id}` | `/arena` |
| Arena 解出人 | GET | `/are/{id}/solves` | `/arena` |
| Measure 题目列表 | GET | `/measures` | `/measure` |
| Measure 解出数量 | GET | `/solves_measure` | `/measure` |
| Measure 题目详情 | GET | `/measure/{id}` | `/measure` |
| Measure 解出人 | GET | `/measure/{id}/solves` | `/measure` |

---

## 25. 最终效果

脚本周期运行后，可以实现：

- 自动复用登录态；
- 自动检测登录失效并重新登录；
- 自动监控三个赛道中我方未解出题目的解出人数变化；
- 当某题短时间内解出人数增长超过阈值时，通过飞书机器人提醒；
- 告警中包含题目、赛道、增长数量、当前解出数和最近解出人信息。
