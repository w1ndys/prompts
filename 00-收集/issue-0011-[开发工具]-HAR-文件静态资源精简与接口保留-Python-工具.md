---
issue_number: 11
title: "[开发工具] HAR 文件静态资源精简与接口保留 Python 工具"
author: "w1ndys"
created_at: "2026-05-09 09:46:55 UTC"
updated_at: "2026-08-29 03:44:42 UTC"
labels: ["prompt"]
source_url: "https://github.com/w1ndys/prompts/issues/11"
---

# [开发工具] HAR 文件静态资源精简与接口保留 Python 工具

下面是一个可直接用 `uv run` 执行的 Python 脚本，用来精简浏览器导出的 `.har` 文件，默认会：

- 过滤掉图片、CSS、JS、字体、视频等静态资源请求
- 尽量保留接口请求，例如：
  - `fetch`
  - `xhr`
  - `POST / PUT / PATCH / DELETE`
  - JSON / GraphQL / Form 请求
  - URL 中包含 `/api/`、`graphql`、`ajax` 等特征
- 删除 HAR 中大量冗余字段
- 默认脱敏 Cookie、Authorization、Token 等敏感 header
- 支持一次处理多个 HAR 文件

保存为：`slim_har.py`

```python
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qsl


STATIC_EXTENSIONS = {
    ".js", ".mjs", ".css",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp", ".avif",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp4", ".webm", ".mp3", ".wav", ".ogg",
    ".map",
}

STATIC_MIME_PREFIXES = (
    "image/",
    "font/",
    "audio/",
    "video/",
)

STATIC_MIME_TYPES = {
    "text/css",
    "application/javascript",
    "text/javascript",
    "application/x-javascript",
}

API_HINT_PATTERNS = [
    r"/api/",
    r"/apis/",
    r"/graphql",
    r"/gql",
    r"/ajax",
    r"/rest/",
    r"/rpc/",
    r"/gateway",
    r"/openapi",
    r"/v\d+/",
]

SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
    "x-csrf-token",
    "x-xsrf-token",
    "csrf-token",
    "xsrf-token",
    "token",
}


def header_list_to_dict(headers, redact=True):
    result = {}

    for item in headers or []:
        name = item.get("name", "")
        value = item.get("value", "")

        if not name:
            continue

        key_lower = name.lower()

        if redact and key_lower in SENSITIVE_HEADER_NAMES:
            result[name] = "<REDACTED>"
        else:
            result[name] = value

    return result


def get_header(headers, name):
    name_lower = name.lower()

    for item in headers or []:
        if item.get("name", "").lower() == name_lower:
            return item.get("value", "")

    return ""


def guess_mime(entry):
    response = entry.get("response", {})
    content = response.get("content", {})

    mime = content.get("mimeType") or get_header(response.get("headers", []), "content-type")
    return mime.split(";")[0].strip().lower()


def get_url_path(url):
    try:
        return urlparse(url).path
    except Exception:
        return ""


def is_static_request(entry):
    request = entry.get("request", {})
    url = request.get("url", "")
    path = get_url_path(url).lower()

    suffix = Path(path).suffix.lower()
    if suffix in STATIC_EXTENSIONS:
        return True

    mime = guess_mime(entry)

    if mime in STATIC_MIME_TYPES:
        return True

    if any(mime.startswith(prefix) for prefix in STATIC_MIME_PREFIXES):
        return True

    resource_type = entry.get("_resourceType", "").lower()
    if resource_type in {
        "stylesheet",
        "script",
        "image",
        "font",
        "media",
        "manifest",
    }:
        return True

    return False


def looks_like_api_request(entry):
    request = entry.get("request", {})
    response = entry.get("response", {})

    method = request.get("method", "GET").upper()
    url = request.get("url", "")
    path = get_url_path(url).lower()

    resource_type = entry.get("_resourceType", "").lower()

    if resource_type in {"xhr", "fetch", "websocket", "eventsource"}:
        return True

    if method not in {"GET", "HEAD", "OPTIONS"}:
        return True

    request_mime = get_header(request.get("headers", []), "content-type").lower()
    response_mime = guess_mime(entry)

    api_mime_hints = [
        "application/json",
        "application/problem+json",
        "application/graphql",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
        "text/xml",
        "application/xml",
    ]

    if any(hint in request_mime for hint in api_mime_hints):
        return True

    if any(hint in response_mime for hint in api_mime_hints):
        return True

    if any(re.search(pattern, path) for pattern in API_HINT_PATTERNS):
        return True

    status = response.get("status")
    if status in {401, 403, 422, 429, 500} and not is_static_request(entry):
        return True

    return False


def truncate_text(text, limit):
    if text is None:
        return None

    if limit <= 0:
        return text

    if len(text) <= limit:
        return text

    return text[:limit] + f"\n... <TRUNCATED {len(text) - limit} chars>"


def parse_query(url):
    try:
        return dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
    except Exception:
        return {}


def simplify_post_data(post_data, keep_body, body_limit):
    if not post_data:
        return None

    result = {
        "mimeType": post_data.get("mimeType"),
    }

    params = post_data.get("params")
    if params:
        result["params"] = [
            {
                "name": item.get("name"),
                "value": item.get("value"),
            }
            for item in params
        ]

    if keep_body and "text" in post_data:
        result["text"] = truncate_text(post_data.get("text"), body_limit)

    return result


def simplify_response_content(content, keep_body, body_limit):
    if not content:
        return None

    result = {
        "mimeType": content.get("mimeType"),
        "size": content.get("size"),
        "compression": content.get("compression"),
    }

    if keep_body and "text" in content:
        result["text"] = truncate_text(content.get("text"), body_limit)
        if content.get("encoding"):
            result["encoding"] = content.get("encoding")

    return result


def simplify_entry(entry, redact=True, keep_request_body=True, keep_response_body=False, body_limit=10000):
    request = entry.get("request", {})
    response = entry.get("response", {})
    timings = entry.get("timings", {})

    url = request.get("url", "")
    parsed = urlparse(url)

    simplified = {
        "startedDateTime": entry.get("startedDateTime"),
        "time": entry.get("time"),
        "resourceType": entry.get("_resourceType"),
        "request": {
            "method": request.get("method"),
            "url": url,
            "scheme": parsed.scheme,
            "host": parsed.netloc,
            "path": parsed.path,
            "query": parse_query(url),
            "headers": header_list_to_dict(request.get("headers", []), redact=redact),
            "postData": simplify_post_data(
                request.get("postData"),
                keep_body=keep_request_body,
                body_limit=body_limit,
            ),
        },
        "response": {
            "status": response.get("status"),
            "statusText": response.get("statusText"),
            "headers": header_list_to_dict(response.get("headers", []), redact=redact),
            "content": simplify_response_content(
                response.get("content"),
                keep_body=keep_response_body,
                body_limit=body_limit,
            ),
            "redirectURL": response.get("redirectURL"),
        },
        "timings": {
            "blocked": timings.get("blocked"),
            "dns": timings.get("dns"),
            "connect": timings.get("connect"),
            "send": timings.get("send"),
            "wait": timings.get("wait"),
            "receive": timings.get("receive"),
            "ssl": timings.get("ssl"),
        },
    }

    return simplified


def load_har(path):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("log", {}).get("entries", [])

    if not isinstance(entries, list):
        raise ValueError(f"{path} does not look like a valid HAR file")

    return data, entries


def process_har(
    input_path,
    output_path,
    redact=True,
    include_static=False,
    keep_request_body=True,
    keep_response_body=False,
    body_limit=10000,
):
    _, entries = load_har(input_path)

    simplified_entries = []

    for entry in entries:
        if not include_static:
            if is_static_request(entry):
                continue

            if not looks_like_api_request(entry):
                continue

        simplified_entries.append(
            simplify_entry(
                entry,
                redact=redact,
                keep_request_body=keep_request_body,
                keep_response_body=keep_response_body,
                body_limit=body_limit,
            )
        )

    output = {
        "source": str(input_path),
        "totalEntries": len(entries),
        "keptEntries": len(simplified_entries),
        "entries": simplified_entries,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return len(entries), len(simplified_entries)


def main():
    parser = argparse.ArgumentParser(
        description="Slim browser HAR files by keeping likely API requests and removing static resources."
    )

    parser.add_argument(
        "har_files",
        nargs="+",
        type=Path,
        help="Input HAR files",
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("slim-har-output"),
        help="Output directory. Default: slim-har-output",
    )

    parser.add_argument(
        "--include-static",
        action="store_true",
        help="Do not filter static resources. Only simplify entries.",
    )

    parser.add_argument(
        "--no-redact",
        action="store_true",
        help="Do not redact sensitive headers such as Cookie and Authorization.",
    )

    parser.add_argument(
        "--no-request-body",
        action="store_true",
        help="Remove request body text from output.",
    )

    parser.add_argument(
        "--keep-response-body",
        action="store_true",
        help="Keep response body text if it exists in HAR. Disabled by default.",
    )

    parser.add_argument(
        "--body-limit",
        type=int,
        default=10000,
        help="Max chars to keep for request/response body. 0 means unlimited. Default: 10000",
    )

    args = parser.parse_args()

    for input_path in args.har_files:
        if not input_path.exists():
            print(f"[SKIP] File not found: {input_path}")
            continue

        output_path = args.output_dir / f"{input_path.stem}.slim.json"

        total, kept = process_har(
            input_path=input_path,
            output_path=output_path,
            redact=not args.no_redact,
            include_static=args.include_static,
            keep_request_body=not args.no_request_body,
            keep_response_body=args.keep_response_body,
            body_limit=args.body_limit,
        )

        print(f"[OK] {input_path}")
        print(f"     total: {total}")
        print(f"     kept : {kept}")
        print(f"     out  : {output_path}")


if __name__ == "__main__":
    main()
```

使用方式：

```bash
uv run slim_har.py ./first.har ./second.har
```

输出目录默认是：

```bash
slim-har-output/
```

生成类似：

```text
slim-har-output/first.slim.json
slim-har-output/second.slim.json
```

如果你想保留响应体内容，可以这样：

```bash
uv run slim_har.py ./first.har ./second.har --keep-response-body
```

如果你不想脱敏 Cookie、Authorization 等 header：

```bash
uv run slim_har.py ./first.har ./second.har --no-redact
```

如果只想简化 HAR，不过滤静态资源：

```bash
uv run slim_har.py ./first.har ./second.har --include-static
```

通常分析接口调用时直接运行：

```bash
uv run slim_har.py ./a.har ./b.har
```

就够了。
