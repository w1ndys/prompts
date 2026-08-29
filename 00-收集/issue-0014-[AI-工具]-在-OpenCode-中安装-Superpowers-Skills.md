---
issue_number: 14
title: "[AI 工具] 在 OpenCode 中安装 Superpowers Skills"
author: "w1ndys"
created_at: "2026-06-16 06:30:42 UTC"
updated_at: "2026-08-29 03:44:35 UTC"
labels: ["prompt"]
source_url: "https://github.com/w1ndys/prompts/issues/14"
---

# [AI 工具] 在 OpenCode 中安装 Superpowers Skills

```
# 安装 superpowers：优先 git clone，失败则通过 HTTPS tarball 降级下载到本地
git clone --depth 1 https://github.com/obra/superpowers.git ~/.config/opencode/node_modules/superpowers 2>/dev/null || {
  mkdir -p ~/.config/opencode/node_modules/superpowers && curl -sL --connect-timeout 30 --max-time 120 https://github.com/obra/superpowers/archive/refs/heads/main.tar.gz | tar xz -C ~/.config/opencode/node_modules/superpowers --strip-components=1
}

# 将 superpowers 的 14 个 skills 复制到 opencode 自动扫描的 ~/.claude/skills/ 目录，无需修改配置文件
cp -r ~/.config/opencode/node_modules/superpowers/skills/* ~/.claude/skills/

# 重启 opencode 后，输入 "Tell me about your superpowers" 验证是否安装成功

```
