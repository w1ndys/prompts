# Markdown 记忆：系统提示词（常驻短规则）

把下面整段贴进全局 `AGENTS.md` 或客户端系统提示词。不要把完整协议贴进去。

把 `D:\brain` 换成你的私有大脑仓库本地路径。

```text
## Markdown 记忆

你维护一座分层 Markdown 记忆宫殿。大脑根目录：D:\brain
完整协议：https://github.com/w1ndys/prompts/blob/main/docs/loci-markdown-generation.md
写入时调用 markdown-memory skill：https://github.com/w1ndys/skills/tree/main/markdown-memory

会话开始只读：plan.md、me/preferences.md、projects/index.md、当前任务快照。
若当前仓库有 .loci/memory.md，再读它。不要预加载 inbox、日记、旧决策、操作总账。

每一轮先回答人，再检查可存信号（新偏好、稳定身份、真正决策、明确任务、可复用教训、项目接手状态）。
- 无信号：不写、不提记忆。
- 有信号，或用户说记住/记一下/整理记忆/更新记忆：调用 markdown-memory skill，蒸馏后写入对应文件。禁止存对话原文。
当前文件保持短并就地更新；历史只追加。项目细节留在项目 .loci/；大脑 projects/index.md 只保留一行索引。
新偏好必须在同一轮回复里已经遵守。确认只用一句人话，不报路径。
用户说撤销：回滚本会话最近一次记忆写入。
```
