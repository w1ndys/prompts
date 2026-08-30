---
issue: 6
title: "[前端规范] Vue 3 + Tailwind CSS 组件与布局开发规范"
source: https://github.com/w1ndys/prompts/issues/6
state: open
---

```
为了防止项目随着功能增加而失控，建议遵循以下“后端友好型”规范：

1. 组件拆分原则 (Atomic Design)
Base Components: 按钮、输入框、标签等。不包含业务逻辑，样式高度封装。

Business Components: 复杂的表单、列表项、侧边栏。

Views: 页面级容器，只负责组合组件和获取数据。

2. Tailwind 编写策略
顺序规范： 建议按照：布局(flex/grid/pos) -> 尺寸(w/h) -> 间距(m/p) -> 装饰(bg/border/rounded) -> 交互(hover/focus) 的顺序写类名。

禁止任意值： 尽量不要使用 w-[123px] 这种写法，优先从 Tailwind 的预设配置（如 w-32）中选择。如果必须自定义，请修改 tailwind.config.js。

3. 布局红线
垂直居中： 一律使用 flex items-center justify-center。

元素间距： 父容器使用 flex flex-col gap-4，而不是给每个子元素写 mb-4。这样在删除某个中间元素时，布局不会错位。
```
