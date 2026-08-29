# 📚 Prompts 与文档收集库

这个仓库用于保存可复用的 Prompt、技术文档和开发方法。推荐直接在 GitHub 新建 Issue，内容会自动归档为 Markdown 文件。

## 自动归档规则

`.github/workflows/issue-to-markdown.yml` 监听 Issue 的创建、标签变更和编辑事件。只有同时满足以下条件时才会生成文件：

- Issue 带有固定标签 `prompt`；
- Issue 作者是仓库所有者（当前为 `w1ndys`）。

生成文件位于 `00-收集/`，文件名格式为 `issue-编号-标题.md`。重复编辑同一个 Issue 会删除旧文件并生成新文件，因此不会留下过期标题。

Issue 表单会自动申请 `prompt` 标签；首次使用前请在仓库的 **Settings → Issues → Labels** 中创建同名标签（颜色可自选）。

## 修改规则

工作流顶部的 `REQUIRED_LABEL`、`REQUIRED_AUTHOR` 和 `TARGET_DIR` 是唯一配置入口。修改标签或目标目录时，同时更新 job 中 `if` 表达式里的固定标签值。

工作流使用 `GITHUB_TOKEN` 提交归档文件，需要在仓库 **Settings → Actions → General → Workflow permissions** 中允许 **Read and write permissions**。

## 本地测试

可以用一份 Issue 事件 JSON 测试转换脚本：

```bash
GITHUB_EVENT_PATH=/path/to/event.json python3 scripts/issue_to_markdown.py
```
