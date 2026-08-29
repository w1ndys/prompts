---
issue_number: 17
title: "[AI 协作规范] Vibe Coding 辅助代码注释与决策记录规范"
author: "w1ndys"
created_at: "2026-07-12 13:14:36 UTC"
updated_at: "2026-08-29 03:44:27 UTC"
labels: ["prompt"]
source_url: "https://github.com/w1ndys/prompts/issues/17"
---

# [AI 协作规范] Vibe Coding 辅助代码注释与决策记录规范

```
把下面要求加入到当前项目规范文件中，以后ai辅助编程必须严格遵循下面规则：

函数头必须包含 @param、@returns 和 ⚠️副作用说明；

内部遇到 if 判断，上方必须写 [决策理由]；

在函数最底部，用 // >>> 数据演变示例 展示 2 组输入输出的演变过程；

在文件顶部用 // 📌 影响范围 列出它引用了哪些外部变量。”
```
