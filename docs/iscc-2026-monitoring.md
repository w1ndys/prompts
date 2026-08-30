## 🤖 Assistant

# ISCC 2026 竞赛平台 - 自动化监控脚本开发文档

---

## 目录

1. [系统概述](#1-系统概述)
2. [HAR 文件 API 流程分析](#2-har-文件-api-流程分析)
3. [API 接口详细说明](#3-api-接口详细说明)
4. [脚本架构设计](#4-脚本架构设计)
5. [详细实现规范](#5-详细实现规范)
6. [配置文件说明](#6-配置文件说明)
7. [部署与运维](#7-部署与运维)

---

## 1. 系统概述

### 1.1 目标平台

- **平台名称**: ISCC 2026 (信息安全与对抗竞赛)
- **平台地址**: `https://iscc.isclab.org.cn`
- **服务器信息**: nginx/1.10.3 (Ubuntu) @ 39.96.201.215
- **技术栈**: Python Flask + Jinja2 模板 + jQuery + Foundation 前端

### 1.2 三大赛道

| 赛道编号 | 赛道名称 | 页面路径 | 列表API | 已解决API | 详情API | 解题记录API |
|---------|---------|---------|--------|----------|--------|------------|
| Track 1 | **练武题** (破阵夺旗赛) | `/challenges` | `GET /chals` | `GET /solves` | `GET /chals/{id}` | `GET /chal/{id}/solves` |
| Track 2 | **擂台题** (无限擂台赛) | `/arena` | `GET /arenas` | `GET /arenasolves` | `GET /arenas/{id}` | `GET /are/{id}/solves` |
| Track 3 | **实战题** | `/measure` | `GET /measures` | `GET /solves_measure` | `GET /measure/{id}` | `GET /measure/{id}/solves` |

### 1.3 脚本需求

通过 cron 定时运行，实现以下功能：

1. **登录 Cookie 缓存** - 持久化登录 Session，复用有效 Cookie，过期自动重新登录
2. **解题数缓存** - 缓存每个**未解出**题目的已解人数
3. **增量监控告警** - 当某个题目的解出人数比上次检查**相差超过 10** 时，通过飞书 Webhook 机器人发送 Markdown 富文本通知

---

## 2. HAR 文件 API 流程分析

### 2.1 登录流程 (`iscc-login.har`)

```
┌──────────┐     POST /login           ┌──────────┐
│  Browser │ ──────────────────────────> │  Server  │
│          │   name=W1ndys             │          │
│          │   password=isccws0814@    │          │
│          │ <────────────────────────── │          │
│          │   302 Found               │          │
│          │   Location: /team/{hash}  │          │
│          │   (Session Cookie 隐式设置) │          │
└──────────┘                           └──────────┘
```

**关键发现**:
- 登录请求类型: `POST`，Content-Type: `application/x-www-form-urlencoded`
- 参数: `name={username}&password={password}`
- 成功响应: HTTP 302，Location 头指向 `/team/{team_hash}`
- Cookie 由 Flask Session 管理，HAR 中未显示显式 Set-Cookie，推测为 HttpOnly Session Cookie

### 2.2 练武题 (Challenges) 赛道请求流程

触发页面: `GET /challenges` → 加载 `chalboard.js`

```
┌─────────────────────────────────────────────────────────────────┐
│ 页面加载后自动发起 (chalboard.js):                               │
│                                                                 │
│  ① GET /chals                                                   │
│     └─ 返回: {"game": [{category, id, value, name, ...}],       │
│               "categories": [...]}                              │
│                                                                 │
│  ② GET /solves                                                  │
│     └─ 返回: {"solves": [{"chalid": 28}, {"chalid": 15}, ...]}  │
│        用于标记哪些题目已被当前用户解出 (按钮变灰)                 │
│                                                                 │
│  ③ 用户点击题目按钮 → GET /chals/{id}                            │
│     └─ 返回: {id, name, category, value, description,           │
│               files, solves, ...}                                │
│     └─ 其中 `solves` 字段为该题目的解出人数 (关键字段)            │
│                                                                 │
│  ④ 查看解题队伍 → GET /chal/{id}/solves                          │
│     └─ 返回: {"teams": [{name, date, score, id}, ...]}          │
└─────────────────────────────────────────────────────────────────┘
```

**关键响应体示例** (`GET /chals/28`):
```json
{
    "category": "...",
    "description": "...",
    "files": [...],
    "id": 28,
    "name": "灵感笔记",
    "solves": 1234,
    "value": 50
}
```

### 2.3 擂台题 (Arena) 赛道请求流程

触发页面: `GET /arena` → 加载 `arenaboard.js`

```
页面加载后自动发起 (arenaboard.js):
  ① GET /arenas       → {"game": [{category, id, value}, ...]}
  ② GET /arenasolves  → {"solves": [{"chalid": ...}, ...]}
  ③ 点击题目 → GET /arenas/{id}   → 含 `solves` 字段
  ④ 查看解题 → GET /are/{id}/solves → {"teams": [...]}
```

### 2.4 实战题 (Measure) 赛道请求流程

触发页面: `GET /measure` → 加载 `measure_chalboard.js`

```
页面加载后自动发起 (measure_chalboard.js):
  ① GET /measures        → {"game": [{category, id, value}, ...]}
  ② GET /solves_measure  → {"solves": [{"chalid": ...}, ...]}
  ③ 点击题目 → GET /measure/{id}  → 含 `solves` 字段
  ④ 查看解题 → GET /measure/{id}/solves → {"teams": [...]}
```

**实战题关键响应** (`GET /measure/3`):
```json
{
    "category": "新型车联网安全网络协议破解",
    "description": "...",
    "files": [],
    "flag_source_url": "http://113.105.122.178:28444/current",
    "id": 3,
    "name": "内网服务漏洞利用",
    "solves": 844,
    "value": 200,
    "verify_mode": "local"
}
```

---

## 3. API 接口详细说明

### 3.1 登录接口

| 属性 | 值 |
|------|-----|
| **URL** | `POST /login` |
| **Content-Type** | `application/x-www-form-urlencoded` |
| **参数** | `name={username}&password={password}` |
| **成功响应** | HTTP 302，Location: `/team/{team_hash}` |
| **失败响应** | HTTP 200，页面显示错误 (重定向回 /login) |
| **Cookie** | Flask Session Cookie (HttpOnly) |

**脚本处理要点**:
- 需要开启 Cookie Jar 自动管理
- 登录后验证是否成功（检测是否被重定向到 `/team/` 路径）
- Cookie 过期后 (请求返回 302 到 `/login`)，需要自动重新登录

### 3.2 通用认证验证

所有 API 需要有效的登录 Session。判断 Session 是否有效：
- 请求任意需要认证的 API（如 `/chals`），如果返回的是登录页重定向（HTTP 302, Location 包含 `/login`），则 Session 已过期

### 3.3 三大赛道 API 对照表

| 功能 | 练武题 | 擂台题 | 实战题 |
|------|--------|--------|--------|
| **题目列表** | `GET /chals` | `GET /arenas` | `GET /measures` |
| **已解题目列表** | `GET /solves` | `GET /arenasolves` | `GET /solves_measure` |
| **题目详情 (含solves)** | `GET /chals/{id}` | `GET /arenas/{id}` | `GET /measure/{id}` |
| **解题队伍列表** | `GET /chal/{id}/solves` | `GET /are/{id}/solves` | `GET /measure/{id}/solves` |

> **注意**: 列表接口返回的数据中**不包含** `solves` 人数，必须请求每个题目的详情接口获取解出人数。

### 3.4 响应体数据结构

#### 列表接口 (`/chals`, `/arenas`, `/measures`)

```json
{
    "game": [
        {
            "category": "WEB",
            "id": 28,
            "value": 50
        }
    ]
}
```

> 注：`/chals` 额外包含 `categories` 数组字段。

#### 已解题目接口 (`/solves`, `/arenasolves`, `/solves_measure`)

```json
{
    "solves": [
        {"chalid": 28},
        {"chalid": 15}
    ]
}
```

#### 题目详情接口 (`/chals/{id}`, `/arenas/{id}`, `/measure/{id}`)

```json
{
    "id": 28,
    "name": "灵感笔记",
    "category": "WEB",
    "value": 50,
    "description": "...",
    "files": [],
    "solves": 1234,
    "verify_mode": "local"
}
```

**`solves` 字段**是监控的核心指标，表示该题目当前的解出总人数。

#### 解题队伍列表 (`/chal/{id}/solves`, 类似模式)

```json
{
    "teams": [
        {
            "id": 1,
            "name": "miaoaixuan",
            "date": "2026-05-09 09:42:32",
            "score": 200
        }
    ]
}
```

---

## 4. 脚本架构设计

### 4.1 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                    Cron Scheduler                            │
│                  (crontab / systemd timer)                    │
└──────────────────────┬───────────────────────────────────────┘
                       │ 定期触发 (建议每 5-10 分钟)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    iscc_monitor.py                            │
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │ 登录模块  │   │ 数据采集  │   │ 缓存管理  │   │ 通知模块  │  │
│  │ auth.py  │──>│collector │──>│ cache.py │──>│notifier  │  │
│  │          │   │ .py      │   │          │   │ .py      │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
│       │              │               │               │       │
│       ▼              ▼               ▼               ▼       │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │ Session  │   │  HTTP    │   │  JSON    │   │  Feishu  │  │
│  │ Cookie   │   │ Requests │   │  File    │   │ Webhook  │  │
│  │ (pickle) │   │          │   │ (store)  │   │          │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 数据流

```
1. 加载配置 (config.yaml/json)
       │
2. 尝试加载缓存的 Session Cookie
       │
3. 验证 Session 有效性 (GET /chals)
       ├── 有效 → 继续
       └── 过期 → POST /login → 保存新 Cookie
       │
4. 遍历三个赛道:
   ├── GET /chals → 获取练武题列表
   ├── GET /solves → 获取已解练武题 ID 集合
   ├── 对每个 未解出 的题目:
   │   ├── GET /chals/{id} → 获取 solves 人数
   │   ├── 对比缓存中的上一次值
   │   ├── 差值 > 10 → 加入通知队列
   │   └── 更新缓存
   ├── 同样流程处理 /arenas 和 /measures
       │
5. 构建飞书 Markdown 通知 → POST Webhook
       │
6. 持久化缓存到本地文件
```

### 4.3 缓存文件结构

```json
{
    "last_run": "2026-05-09T12:00:00",
    "session_cookie": {
        "cookie_jar_state": "...",
        "expires_at": "2026-05-10T06:18:54"
    },
    "solves_cache": {
        "challenges": {
            "15": {"name": "deepvoid", "solves": 250, "value": 125},
            "17": {"name": "喧宾夺主的信号", "solves": 200, "value": 80}
        },
        "arena": {
            "4": {"name": "...", "solves": 50, "value": 500}
        },
        "measure": {
            "3": {"name": "内网服务漏洞利用", "solves": 844, "value": 200},
            "4": {"name": "协议数据包解析", "solves": 0, "value": 500}
        }
    }
}
```

---

## 5. 详细实现规范

### 5.1 项目结构

```
iscc_monitor/
├── main.py              # 入口，编排整体流程
├── config.yaml           # 配置文件
├── auth.py              # 登录与 Session 管理
├── collector.py         # 数据采集模块
├── cache.py             # 缓存读写模块
├── notifier.py          # 飞书通知模块
├── requirements.txt     # 依赖
├── data/
│   └── cache.json       # 运行时缓存文件 (自动生成)
└── README.md
```

### 5.2 核心模块伪代码

#### `main.py` - 主流程

```python
#!/usr/bin/env python3
"""
ISCC 2026 解题监控脚本
通过 crontab 定期运行，监控三大赛道题目解出人数变化
"""

import logging
from auth import AuthManager
from collector import DataCollector
from cache import CacheManager
from notifier import FeishuNotifier
from config import load_config

def main():
    config = load_config("config.yaml")
    setup_logging(config)

    # 1. 初始化模块
    auth = AuthManager(config)
    cache = CacheManager(config["cache_file"])
    collector = DataCollector(auth, config)
    notifier = FeishuNotifier(config["feishu_webhook_url"])

    # 2. 登录 / 恢复 Session
    if not auth.restore_session(cache.get_session()):
        auth.login()
        cache.save_session(auth.get_session_state())

    # 3. 验证登录状态
    if not auth.verify_session():
        auth.login()
        cache.save_session(auth.get_session_state())

    # 4. 遍历三个赛道采集数据
    notifications = []
    tracks = [
        {
            "name": "练武题",
            "list_url": "/chals",
            "solved_url": "/solves",
            "detail_url_tpl": "/chals/{id}",
            "cache_key": "challenges"
        },
        {
            "name": "擂台题",
            "list_url": "/arenas",
            "solved_url": "/arenasolves",
            "detail_url_tpl": "/arenas/{id}",
            "cache_key": "arena"
        },
        {
            "name": "实战题",
            "list_url": "/measures",
            "solved_url": "/solves_measure",
            "detail_url_tpl": "/measure/{id}",
            "cache_key": "measure"
        }
    ]

    for track in tracks:
        changes = collector.check_track(track, cache)
        notifications.extend(changes)

    # 5. 发送通知
    if notifications:
        notifier.send(notifications)

    # 6. 更新缓存
    cache.save()

if __name__ == "__main__":
    main()
```

#### `auth.py` - 登录与 Session 管理

```python
"""
登录与 Session 管理模块

关键点:
1. Session Cookie 使用 Python requests.Session 对象自动管理
2. Cookie 通过 pickle 序列化持久化到缓存文件
3. 每次运行先尝试恢复 Session，失败则重新登录
"""

import requests
import pickle
import logging
from urllib.parse import urljoin

class AuthManager:
    def __init__(self, config):
        self.base_url = config["base_url"]  # https://iscc.isclab.org.cn
        self.username = config["username"]
        self.password = config["password"]
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ISCC-Monitor/1.0",
            "Accept": "application/json, text/html",
            "Accept-Language": "zh-CN,zh;q=0.9"
        })

    def login(self) -> bool:
        """POST /login 登录"""
        resp = self.session.post(
            urljoin(self.base_url, "/login"),
            data={"name": self.username, "password": self.password},
            allow_redirects=False
        )
        if resp.status_code == 302 and "/team/" in resp.headers.get("Location", ""):
            logging.info("登录成功")
            return True
        logging.error("登录失败，请检查用户名密码")
        return False

    def verify_session(self) -> bool:
        """验证 Session 是否有效（请求 /chals 判断）"""
        try:
            resp = self.session.get(
                urljoin(self.base_url, "/chals"),
                allow_redirects=False
            )
            return resp.status_code == 200  # 200 表示已登录
        except Exception:
            return False

    def get_session_state(self) -> bytes:
        """导出 Session Cookie 状态"""
        return pickle.dumps(self.session.cookies)

    def restore_session(self, state: bytes) -> bool:
        """恢复 Session Cookie"""
        if not state:
            return False
        try:
            self.session.cookies = pickle.loads(state)
            return self.verify_session()
        except Exception:
            return False
```

#### `collector.py` - 数据采集

```python
"""
数据采集模块

对每个赛道:
1. GET 列表接口 → 获取所有题目 ID
2. GET 已解接口 → 获取用户已解题目 ID 集合
3. 对未解题目调用详情接口 (带重试+延迟) 获取 solves 人数
4. 与缓存值对比，记录变化
"""

import time
import logging
from urllib.parse import urljoin

THRESHOLD = 10  # 解出人数变化阈值

class DataCollector:
    def __init__(self, auth, config):
        self.auth = auth
        self.base_url = config["base_url"]
        self.request_delay = config.get("request_delay", 1.0)

    def check_track(self, track: dict, cache) -> list:
        """检查单个赛道，返回通知列表"""
        changes = []
        session = self.auth.session

        # 1. 获取题目列表
        resp = session.get(urljoin(self.base_url, track["list_url"]))
        challenges = resp.json().get("game", [])

        # 2. 获取已解题目 ID
        resp = session.get(urljoin(self.base_url, track["solved_url"]))
        solved_ids = {
            item["chalid"] for item in resp.json().get("solves", [])
        }

        # 3. 遍历未解题目
        for chal in challenges:
            chal_id = chal["id"]
            if chal_id in solved_ids:
                continue  # 已解出，跳过

            # 请求详情获取 solves 人数
            time.sleep(self.request_delay)
            detail_url = track["detail_url_tpl"].format(id=chal_id)
            resp = session.get(urljoin(self.base_url, detail_url))
            detail = resp.json()

            current_solves = detail.get("solves", 0)
            chal_name = detail.get("name", f"ID:{chal_id}")
            chal_value = detail.get("value", 0)

            # 与缓存对比
            prev = cache.get_solves(track["cache_key"], chal_id)
            if prev is not None:
                diff = current_solves - prev["solves"]
                if diff > THRESHOLD:
                    changes.append({
                        "track": track["name"],
                        "id": chal_id,
                        "name": chal_name,
                        "value": chal_value,
                        "prev_solves": prev["solves"],
                        "current_solves": current_solves,
                        "diff": diff
                    })
                    logging.info(
                        f"[{track['name']}] {chal_name} 解出人数: "
                        f"{prev['solves']} → {current_solves} (+{diff})"
                    )

            # 更新缓存
            cache.set_solves(track["cache_key"], chal_id, {
                "name": chal_name,
                "value": chal_value,
                "solves": current_solves
            })

        return changes
```

#### `notifier.py` - 飞书通知

```python
"""
飞书 Webhook 机器人通知模块

使用 Markdown 富文本格式，包含:
- 题目名称和所属赛道
- 解出人数变化 (之前 → 现在，增量)
- 题目分值
- 变化触发时间
"""

import requests
import json
from datetime import datetime

class FeishuNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, notifications: list):
        """发送飞书通知"""
        if not notifications:
            return

        card = self._build_card(notifications)
        resp = requests.post(
            self.webhook_url,
            json={"msg_type": "interactive", "card": card}
        )
        return resp.json()

    def _build_card(self, notifications: list) -> dict:
        """构建飞书消息卡片 (Markdown 格式)"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 构建 Markdown 内容
        lines = [
            f"## 🔔 ISCC 解题监控告警",
            f"**检测时间**: {now}",
            f"**触发条件**: 解出人数变化 > 10",
            "",
            "---",
            ""
        ]

        for n in notifications:
            lines.extend([
                f"### 📌 {n['name']}",
                f"",
                f"| 属性 | 值 |",
                f"|------|-----|",
                f"| **赛道** | {n['track']} |",
                f"| **题目 ID** | {n['id']} |",
                f"| **分值** | {n['value']} 分 |",
                f"| **之前解出** | {n['prev_solves']} 人 |",
                f"| **当前解出** | {n['current_solves']} 人 |",
                f"| **新增解出** | **+{n['diff']}** 人 🚀 |",
                f"",
                "---",
                ""
            ])

        lines.append(f"共 {len(notifications)} 个题目发生显著变化")

        return {
            "header": {
                "title": {"tag": "plain_text", "content": "ISCC 解题人数变化告警"},
                "template": "red"
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": "\n".join(lines)
                }
            ]
        }
```

#### `cache.py` - 缓存管理

```python
"""
缓存管理模块

持久化存储:
1. Session Cookie 状态 (pickle → base64)
2. 各赛道题目解出人数记录

文件格式: JSON
"""

import json
import os
import base64
from datetime import datetime

class CacheManager:
    def __init__(self, cache_file: str):
        self.cache_file = cache_file
        self.data = self._load()

    def _load(self) -> dict:
        """加载缓存文件"""
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "r") as f:
                return json.load(f)
        return {
            "last_run": None,
            "session_cookie": None,
            "solves_cache": {
                "challenges": {},
                "arena": {},
                "measure": {}
            }
        }

    def save(self):
        """持久化缓存"""
        self.data["last_run"] = datetime.now().isoformat()
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, "w") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_session(self) -> bytes:
        """获取缓存的 Session Cookie 状态"""
        b64 = self.data.get("session_cookie")
        if b64:
            return base64.b64decode(b64)
        return None

    def save_session(self, state: bytes):
        """保存 Session Cookie 状态"""
        self.data["session_cookie"] = base64.b64encode(state).decode()

    def get_solves(self, track: str, chal_id: int) -> dict:
        """获取某个题目的缓存解出数据"""
        return self.data["solves_cache"][track].get(str(chal_id))

    def set_solves(self, track: str, chal_id: int, data: dict):
        """更新某个题目的解出数据"""
        self.data["solves_cache"][track][str(chal_id)] = data
```

### 5.3 配置文件 `config.yaml`

```yaml
# ISCC 竞赛平台监控配置

base_url: "https://iscc.isclab.org.cn"

# 登录凭据
username: "W1ndys"
password: "isccws0814@"

# 缓存文件路径
cache_file: "./data/cache.json"

# 请求间隔（秒），避免对服务器造成压力
request_delay: 1.5

# 飞书机器人 Webhook URL
feishu_webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxxxxxxxxxxx"

# 日志配置
log_level: "INFO"
log_file: "./data/monitor.log"

# 解题人数变化阈值（超过此数量才发送通知）
threshold: 10
```

### 5.4 `requirements.txt`

```
requests>=2.28.0
pyyaml>=6.0
```

---

## 6. 配置文件说明

### 6.1 飞书 Webhook URL 获取

1. 登录飞书 → 群聊设置 → 群机器人 → 添加自定义机器人
2. 复制 Webhook 地址，格式: `https://open.feishu.cn/open-apis/bot/v2/hook/{token}`
3. 配置安全设置（建议使用**签名校验**或**IP白名单**）

### 6.2 通知消息格式说明

飞书消息卡片使用 `interactive` 类型，支持:
- 标题栏 (header): 红色模板，标题"ISCC 解题人数变化告警"
- Markdown 正文: 表格形式展示每个变化题目的详细信息

### 6.3 Cookie 缓存机制

```
首次运行:
  POST /login → 获取 Cookie → pickle 序列化 → base64 → cache.json

后续运行:
  cache.json → base64 解码 → pickle 反序列化 → 恢复 Session
  → GET /chals 验证 → 有效则复用，无效则重新登录
```

---

## 7. 部署与运维

### 7.1 Crontab 配置

```bash
# 每 10 分钟运行一次
*/10 * * * * cd /path/to/iscc_monitor && /usr/bin/python3 main.py >> /var/log/iscc_monitor.log 2>&1

# 或每 5 分钟 (更频繁)
*/5 * * * * cd /path/to/iscc_monitor && /usr/bin/python3 main.py
```

**推荐频率**: 5-10 分钟。竞赛期间解题高峰每隔几分钟就可能有大量新增解题。

### 7.2 初次部署

```bash
# 1. 创建目录
mkdir -p /opt/iscc_monitor/data

# 2. 复制文件
cp main.py auth.py collector.py cache.py notifier.py config.yaml requirements.txt /opt/iscc_monitor/

# 3. 安装依赖
cd /opt/iscc_monitor
pip3 install -r requirements.txt

# 4. 修改配置
vim config.yaml  # 填入用户名、密码、飞书 Webhook URL

# 5. 手动测试运行
python3 main.py

# 6. 配置 crontab
crontab -e
```

### 7.3 注意事项

| 注意项 | 说明 |
|--------|------|
| **请求频率** | 每次请求间隔 ≥ 1 秒，避免触发服务器限流 |
| **Session 过期** | Flask Session 默认约 31 天，但建议每次运行都验证 |
| **网络异常** | 脚本应具备重试机制 (建议 3 次，指数退避) |
| **首次运行** | 首次运行无缓存，不会触发通知，仅初始化缓存 |
| **并发安全** | cron 任务可能重叠，建议使用文件锁 (`fcntl.flock`) |
| **日志轮转** | 建议配置 logrotate 或使用 `RotatingFileHandler` |
| **密码安全** | 配置文件权限设为 `600`，避免密码泄露 |

### 7.4 错误处理

| 场景 | 处理策略 |
|------|---------|
| 登录失败 | 记录错误日志，退出 (可选: 飞书告警) |
| 列表API失败 | 重试 3 次，仍失败则跳过该赛道 |
| 详情API失败 | 跳过该题目，保留缓存值不更新 |
| 飞书通知失败 | 记录错误日志，不阻断主流程 |
| 缓存文件损坏 | 备份旧文件，创建新缓存 (首次运行模式) |

---

## 附录 A: HAR 文件关键请求索引

### iscc-login.har 关键请求

| 序号 | 方法 | URL | 说明 |
|------|------|-----|------|
| 1 | POST | `/login` | 登录请求，参数 `name` + `password` |
| 2 | GET | `/team/b5fb4ac70c4d684db5f2ffced81b0b42` | 登录成功后跳转页面 |

### iscc-solver.har 关键 API 请求

| 序号 | 页面 | 方法 | URL | 说明 |
|------|------|------|-----|------|
| 3 | challenges | GET | `/chals` | 练武题列表 |
| 4 | challenges | GET | `/solves` | 练武题已解列表 |
| 5 | challenges | GET | `/chals/28` | 练武题详情 (含 solves) |
| 6 | challenges | GET | `/chal/28/solves` | 某题解题队伍 |
| 7 | arena | GET | `/arenas` | 擂台题列表 |
| 8 | arena | GET | `/arenasolves` | 擂台题已解列表 |
| 9 | arena | GET | `/arenas/4` | 擂台题详情 |
| 10 | arena | GET | `/are/4/solves` | 某擂台题解题队伍 |
| 11 | measure | GET | `/measures` | 实战题列表 |
| 12 | measure | GET | `/solves_measure` | 实战题已解列表 |
| 13 | measure | GET | `/measure/3` | 实战题详情 (含 solves: 844) |
| 14 | measure | GET | `/measure/3/solves` | 某实战题解题队伍 |

---

## 附录 B: 飞书通知示例

当检测到变化时，飞书群将收到类似以下格式的消息:

> ### 🔔 ISCC 解题监控告警
> **检测时间**: 2026-05-09 17:30:00
> **触发条件**: 解出人数变化 > 10
>
> ---
>
> ### 📌 内网服务漏洞利用
>
> | 属性 | 值 |
> |------|-----|
> | **赛道** | 实战题 |
> | **题目 ID** | 3 |
> | **分值** | 200 分 |
> | **之前解出** | 844 人 |
> | **当前解出** | 860 人 |
> | **新增解出** | **+16** 人 🚀 |
>
> ---
>
> ### 📌 协议数据包解析
>
> | 属性 | 值 |
> |------|-----|
> | **赛道** | 实战题 |
> | **题目 ID** | 4 |
> | **分值** | 500 分 |
> | **之前解出** | 0 人 |
> | **当前解出** | 15 人 |
> | **新增解出** | **+15** 人 🚀 |
>
> ---
>
> 共 2 个题目发生显著变化
