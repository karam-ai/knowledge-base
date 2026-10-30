#!/usr/bin/env bash
set -euo pipefail

uv sync --extra dev --locked
uv run pytest -W ignore::DeprecationWarning -W ignore::UserWarning
uv run python -m compileall -q src examples databricks
uv build

if command -v go >/dev/null 2>&1; then
  (cd go && go test ./... && go build ./cmd/kgcheck)
fi

docker build -t podcast-knowledge-graph-api:ci .
docker compose config >/dev/null
