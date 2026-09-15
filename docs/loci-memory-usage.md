# 如何用 Markdown 记忆：随对话不断完善

目标：开发和聊天时，记忆文件自动变厚，但上下文保持瘦。不要把完整协议塞进系统提示词。

配套文件：

- 完整协议：[`loci-markdown-generation.md`](loci-markdown-generation.md)
- 常驻系统提示词：[`../prompt/loci-memory-system.md`](../prompt/loci-memory-system.md)
- 按需 skill：https://github.com/w1ndys/skills/tree/main/markdown-memory

---

## 1. 三层各干什么

| 层 | 放哪 | 何时进模型 | 写什么 |
|---|---|---|---|
| 常驻短规则 | 全局 `AGENTS.md` / 系统提示词 | 每一轮 | 只告诉模型：有大脑、读哪些 L1、有信号就调 skill |
| 写作协议 | `markdown-memory` skill | 有信号或用户说记住时 | 路由、模板、蒸馏、禁止项 |
| 记忆正文 | **私有** Git 仓库 | L1 每次；L2 聊到再读；L3 问历史才读 | 蒸馏后的 Markdown |

只做 skill、不写常驻规则：模型经常忘了检查信号。  
只做长系统提示词、不做 skill：每轮都吃掉大量上下文，开发任务变蠢。  
两层都有、但记忆放在公开仓库：隐私事故。

---

## 2. 一次性落地

### 2.1 私有大脑仓库

新建私有仓库（不要用公开的 `prompts`）。本地克隆后至少有：

```text
brain/
├── AGENTS.md
├── plan.md
├── inbox.md
├── me/preferences.md
├── me/identity.md
├── me/values.md
├── me/insights.md
├── me/learned.md
├── me/evolution.md
├── decisions/
├── projects/index.md
├── projects/side.md
├── tasks/active.md
└── activity/
```

空文件先放模板即可，不要先编内容。模板见协议第 12 节。

`AGENTS.md` 里写清大脑根路径，并写「写入时调用 markdown-memory skill」。

### 2.2 安装 skill

把 `w1ndys/skills` 里的 `markdown-memory` 装到客户端能发现的 skills 目录（用户 skills 或项目 skills）。OhMyAgent / Claude Code / Codex 都能识别带 `SKILL.md` 的目录。

skill 已开启隐式调用：出现可存信号时，模型应自己加载，不必每次打 `/markdown-memory`。

### 2.3 贴常驻短规则

复制 [`../prompt/loci-memory-system.md`](../prompt/loci-memory-system.md) 里的代码块，改大脑路径，贴进：

- OhMyAgent 全局 `AGENTS.md`
- 或 Claude Code 用户级规则
- 或项目 `AGENTS.md`（仅该项目需要记忆时）

不要粘贴 4 万字协议。

### 2.4 多设备

大脑私有仓：每台机器 clone 同一仓库。会话开始 `git pull`，写完记忆后按需 `git push`。系统提示词里的路径按本机改；`projects/index.md` 不要写死另一台机器的绝对路径。

---

## 3. 日常怎么跑

```text
会话开始
  → 读 L1（计划、偏好、项目索引、当前任务）
  → 开始正常开发/聊天

每一轮
  → 先把用户的事做完
  → 轻量问：有没有可存信号？
       无 → 什么都不写
       有 → 加载 skill → 蒸馏 → 路由 → 写文件
  → 最多一句「记住了：……」

会话结束（可选）
  → 用户说「整理记忆」或「同步记忆」
  → 扫本轮还没落盘的决策/教训
  → 提交并推送私有仓
```

开发中典型会写入的东西：

| 对话里发生了什么 | 应写成 |
|---|---|
| 「以后提交用中文 conventional commits」 | `me/preferences.md` 或项目 `profile.md` 约定 |
| 「这个服务就用 Postgres，不用 Mongo」 | 项目 `.loci/decisions/YYYY-MM-DD-postgres.md` |
| 「下次先写测试再改这段解析」 | `me/learned.md` 或项目 insight |
| 「明天把登录补上」 | 任务，不是决策 |
| 「也许以后做插件」 | `inbox.md` 或 `projects/side.md` |
| 修好一个只与本仓库有关的坑 | 项目 `memory.md` 的 Current State / progress，不上大脑 |

没有新结论的纯写码轮次：零文件变化。这是正常的，不是失效。

---

## 4. 不要做的运用方式

1. 把完整协议或本页长文放进系统提示词。
2. 让模型每轮把对话摘要追加到同一个 `memory.md`。
3. 把人生档案放进公开的 `prompts` 仓库。
4. 用向量库代替路由：检索解决「找」，不解决「该不该存、存哪」。
5. 两台电脑同时开着 Agent 写同一文件还不 pull。
6. 期望 skill 会在没有常驻规则时「自己想起来记」。多数客户端不会每轮扫描全部 skill。常驻短规则负责提醒，skill 负责写对。

---

## 5. 验收

连续使用几天后应看到：

- 闲聊日：git 无记忆提交，或只有极少行。
- 做了技术选型：项目里多了一份带未选方案的决策。
- 改了称呼：下一会话不提醒也能用对。
- 新开会话：只读几份 L1，不必翻旧聊天。
- 大脑仓库仍然很小；变厚的是 `decisions/`、`learned.md`、项目 `progress/`，不是某一个巨型文件。
