---
issue_number: 10
title: "[容器化部署] Docker 镜像本地构建、上传与远程加载部署"
author: "w1ndys"
created_at: "2026-04-25 14:49:16 UTC"
updated_at: "2026-08-29 03:44:45 UTC"
labels: ["prompt"]
source_url: "https://github.com/w1ndys/prompts/issues/10"
---

# [容器化部署] Docker 镜像本地构建、上传与远程加载部署

```
把部署链路改为“本地构建镜像、导出压缩包、上传服务器、远端 load （需要先删除已有同名镜像）后 compose up”，并尽量复用现有 Taskfile 和 scripts/task 结构，避免引入重复入口
```
