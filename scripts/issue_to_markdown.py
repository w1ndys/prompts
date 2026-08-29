#!/usr/bin/env python3
"""将符合条件的 GitHub Issue 保存为仓库中的 Markdown 文件。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LABEL = "prompt"
DEFAULT_AUTHOR = "w1ndys"
DEFAULT_TARGET_DIR = "00-收集"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--event",
        default=os.environ.get("GITHUB_EVENT_PATH"),
        help="GitHub 事件 JSON 文件路径，默认读取 GITHUB_EVENT_PATH",
    )
    return parser.parse_args()


def load_issue(event_path: str | None) -> dict:
    if not event_path:
        raise ValueError("未提供事件文件，请设置 GITHUB_EVENT_PATH 或使用 --event")

    with Path(event_path).open(encoding="utf-8") as event_file:
        payload = json.load(event_file)

    issue = payload.get("issue", payload)
    if not isinstance(issue, dict) or "number" not in issue:
        raise ValueError("事件 JSON 中没有有效的 issue 对象")
    return issue


def normalized(value: str) -> str:
    return value.strip().casefold()


def has_required_label(issue: dict, required_label: str) -> bool:
    labels = issue.get("labels") or []
    return any(
        isinstance(label, dict)
        and normalized(str(label.get("name", ""))) == normalized(required_label)
        for label in labels
    )


def issue_author(issue: dict) -> str:
    author = issue.get("user") or issue.get("author") or {}
    return str(author.get("login", ""))


def safe_slug(title: str) -> str:
    """生成适合文件名的短标题，保留中文等 Unicode 字符。"""
    slug = re.sub(r"\s+", "-", title.strip())
    slug = re.sub(r'[\\/:*?"<>|#%\x00-\x1f\x7f]', "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip(" .-")
    return (slug or "未命名")[:80]


def format_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    except ValueError:
        return value


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_markdown(issue: dict) -> str:
    number = int(issue["number"])
    title = str(issue.get("title") or "未命名 Issue").strip()
    author = issue_author(issue) or "unknown"
    labels = [
        str(label.get("name", ""))
        for label in issue.get("labels", [])
        if isinstance(label, dict) and label.get("name")
    ]
    body = str(issue.get("body") or "").rstrip()
    body = body or "（Issue 没有正文）"
    url = issue.get("html_url") or f"https://github.com/w1ndys/prompts/issues/{number}"

    frontmatter = {
        "issue_number": number,
        "title": title,
        "author": author,
        "created_at": format_date(issue.get("created_at")),
        "updated_at": format_date(issue.get("updated_at")),
        "labels": labels,
        "source_url": url,
    }
    metadata = [
        f"{key}: {yaml_string(value) if isinstance(value, str) else json.dumps(value, ensure_ascii=False)}"
        for key, value in frontmatter.items()
    ]
    return "---\n" + "\n".join(metadata) + f"\n---\n\n# {title}\n\n{body}\n"


def remove_previous_versions(target_dir: Path, number: int) -> None:
    pattern = re.compile(r"^issue-(\d+)-.*\.md$")
    for path in target_dir.glob("issue-*.md"):
        match = pattern.match(path.name)
        if match and int(match.group(1)) == number:
            path.unlink()


def main() -> int:
    args = parse_args()
    required_label = os.environ.get("REQUIRED_LABEL", DEFAULT_LABEL)
    required_author = os.environ.get("REQUIRED_AUTHOR", DEFAULT_AUTHOR)
    target_value = os.environ.get("TARGET_DIR", DEFAULT_TARGET_DIR)
    target_path = Path(target_value)

    # 目标目录必须位于仓库内，避免错误配置把 Issue 内容写到任意路径。
    if target_path.is_absolute() or ".." in target_path.parts:
        raise ValueError("TARGET_DIR 必须是仓库内的相对路径")
    target_dir = REPO_ROOT / target_path

    issue = load_issue(args.event)
    number = int(issue["number"])
    author = issue_author(issue)
    if not has_required_label(issue, required_label):
        print(f"跳过 Issue #{number}：缺少标签 {required_label!r}")
        return 0
    if normalized(author) != normalized(required_author):
        print(f"跳过 Issue #{number}：作者 @{author} 不是 @{required_author}")
        return 0

    target_dir.mkdir(parents=True, exist_ok=True)
    remove_previous_versions(target_dir, number)
    output_path = target_dir / f"issue-{number:04d}-{safe_slug(str(issue.get('title') or '未命名'))}.md"
    output_path.write_text(render_markdown(issue), encoding="utf-8")
    print(f"已生成 {output_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"错误：{error}", file=sys.stderr)
        raise SystemExit(1)
