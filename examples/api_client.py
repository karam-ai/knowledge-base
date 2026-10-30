#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def request(
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}", data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = response.read()
            return {} if not raw else json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"API error {exc.code}: {detail}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Exercise the Podcast Knowledge Graph API")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key")
    parser.add_argument(
        "--document",
        type=Path,
        default=Path(__file__).with_name("sample-document.json"),
    )
    args = parser.parse_args()

    document = json.loads(args.document.read_text(encoding="utf-8"))
    print("ingest", request(args.url, "POST", "/v1/documents", document, args.api_key))
    print("rebuild", request(args.url, "POST", "/v1/graph/rebuild", api_key=args.api_key))
    print(
        "search",
        request(args.url, "POST", "/v1/search", {"query": "ontology", "limit": 5}),
    )
    print(
        "rag",
        request(
            args.url,
            "POST",
            "/v1/rag/context",
            {"question": "How is ontology used?", "limit": 5},
        ),
    )


if __name__ == "__main__":
    main()
