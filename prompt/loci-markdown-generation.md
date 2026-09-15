# Loci Markdown 记忆生成

完整协议在 [`docs/loci-markdown-generation.md`](../docs/loci-markdown-generation.md)。运用方式在 [`docs/loci-memory-usage.md`](../docs/loci-memory-usage.md)。常驻短规则用 [`loci-memory-system.md`](loci-memory-system.md)，写入时调用 skill https://github.com/w1ndys/skills/tree/main/markdown-memory 。不要把完整协议贴进系统提示词。

启动时只读 L1：`plan.md`、`me/preferences.md`、`projects/index.md`、当前任务快照。不要预加载 inbox、日记、旧决策、操作总账。

每一轮：先回答人，再检查可存信号。无信号不写。有信号则蒸馏（禁止存原文），按类型路由到唯一落点。当前文件就地更新并保持短；历史只追加。项目细节写在项目自己的记忆目录；大脑只保留一行索引。

决策用「背景 / 选项 / 决定 / 后续」，没选的路必须留下。新偏好当轮生效。确认只用一句人话，不报路径。写完决策后检查是否向 L1 上浮一行摘要。任何写入后在当月操作总账追加一行。

Issue: https://github.com/w1ndys/prompts/issues/29
