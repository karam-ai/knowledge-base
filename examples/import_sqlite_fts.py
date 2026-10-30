#!/usr/bin/env python3
"""Import an existing SQLite FTS corpus through the public HTTP API.

The server never reads the source database or Obsidian vault directly. This adapter is
run by the data owner and sends only selected document fields over the API.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any


def post(url: str, path: str, payload: dict[str, Any], api_key: str | None) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(
        f"{url.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API error {exc.code}: {detail}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Import transcript_fts through the API")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key")
    parser.add_argument("--include-source-path", action="store_true")
    parser.add_argument("--limit-documents", type=int)
    args = parser.parse_args()

    uri = f"file:{args.db.resolve()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    rows = con.execute(
        "SELECT video_id, path, title, language, start, end, text "
        "FROM transcript_fts ORDER BY video_id, start, end"
    )
    grouped: dict[str, list[tuple[str, str, str, str, str, str]]] = defaultdict(list)
    for video_id, path, title, language, start, end, text in rows:
        grouped[str(video_id)].append(
            (str(path), str(title), str(language), str(start), str(end), str(text))
        )
    con.close()

    selected = sorted(grouped.items())
    if args.limit_documents is not None:
        selected = selected[: args.limit_documents]
    for index, (source_id, passages) in enumerate(selected, start=1):
        path, title, language, *_ = passages[0]
        payload = {
            "source_id": source_id,
            "title": title,
            "language": language,
            "source_uri": f"file://{path}" if args.include_source_path else None,
            "metadata": {"import_adapter": "transcript_fts"},
            "passages": [
                {"start": start, "end": end, "text": text}
                for _, _, _, start, end, text in passages
            ],
        }
        result = post(args.url, "/v1/documents", payload, args.api_key)
        print(f"[{index}/{len(selected)}] {source_id}: {result['passage_count']} passages")

    result = post(args.url, "/v1/graph/rebuild", {}, args.api_key)
    print("Graph rebuilt:", result)


if __name__ == "__main__":
    main()
