```
# 安装 superpowers：优先 git clone，失败则通过 HTTPS tarball 降级下载到本地
git clone --depth 1 https://github.com/obra/superpowers.git ~/.config/opencode/node_modules/superpowers 2>/dev/null || {
  mkdir -p ~/.config/opencode/node_modules/superpowers && curl -sL --connect-timeout 30 --max-time 120 https://github.com/obra/superpowers/archive/refs/heads/main.tar.gz | tar xz -C ~/.config/opencode/node_modules/superpowers --strip-components=1
}

# 将 superpowers 的 14 个 skills 复制到 opencode 自动扫描的 ~/.claude/skills/ 目录，无需修改配置文件
cp -r ~/.config/opencode/node_modules/superpowers/skills/* ~/.claude/skills/

# 重启 opencode 后，输入 "Tell me about your superpowers" 验证是否安装成功

```

---

## Issue 评论

### 评论 1

作者：[@w1ndys](https://github.com/w1ndys) · [原评论](https://github.com/w1ndys/prompts/issues/14#issuecomment-4715797401)

https://github.com/obra/superpowers
