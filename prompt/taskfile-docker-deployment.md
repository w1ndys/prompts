---
issue: 4
title: "[部署运维] Taskfile 与脚本化 Docker 部署规范"
source: https://github.com/w1ndys/prompts/issues/4
state: closed
---

```
增加或修改taskfile文件用于开发运维，要有silent: true，包含环境部署，服务启动，部署到生产环境服务器
task deploy 改成支持 cli 参数，示例命令如下  task deploy HOST=1.2.3.4 PORT=22 USER=root DIR=/srv/app
host默认为thinkpad，端口默认22，user默认是w1ndys，dir默认是/opt/当前项目名
如果没有其他要求，默认通过docker compose部署到生产服务器
所有shell操作通过taskfile调用外部的shell脚本实现
部署方式应为：本地拉取需要拉取的镜像，本地构建镜像，打包镜像和必要的运维配置文件，上传到目标服务器，在目标服务器load镜像，删除悬空镜像
```
