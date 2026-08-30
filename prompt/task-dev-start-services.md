---
issue: 7
title: "[开发运维] Task dev 一键启动前后端并清理端口占用"
source: https://github.com/w1ndys/prompts/issues/7
state: closed
---

```
修改 task 运维命令，如果现在开发服务器是分前后端两条命令分别执行，就修改成同时启动，先启动后端，再启动前端，实现 task dev 同时启动两个命令
如果现有的启动命令启动前没有检测端口，需要增加一个步骤，先杀死目标端口已存在的进程，再启动，防止端口冲突启动失败  ，注意只杀死仅监听状态的进程，远程的不需要，可以使用命令 `lsof -ti:PORT -sTCP:LISTEN：`
```
