# Contributing

Contributions are welcome through issues and pull requests.

## Development

```bash
uv sync --extra dev
uv run pytest -W ignore::DeprecationWarning -W ignore::UserWarning
uv run uvicorn podcast_kg.api:app --reload
```

Keep changes small, add tests before implementation, and preserve passage-level provenance. Do not commit transcript corpora, generated databases, generated graphs, credentials, access tokens, or copyrighted material without redistribution rights.

## Pull requests

1. Explain the user-visible change.
2. Include or update tests.
3. Run `bash scripts/ci.sh` when Docker is available.
4. Document schema or API changes.
5. Mark AI-extracted claims as unverified unless independent evidence is attached.
