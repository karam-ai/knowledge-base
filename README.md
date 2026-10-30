# Podcast Knowledge Graph API

A standalone, open-source HTTP service for timestamped podcast evidence, RDF/OWL knowledge graphs, read-only SPARQL and citation-preserving RAG context.

The application owns its SQLite database and generated N-Quads graph. Consumers communicate through the API; they do not need access to an Obsidian vault, transcript folder or internal database file.

## Why this exists

Podcast and document intelligence systems need more than generic vector search. This project preserves:

- source and passage identity;
- start/end timestamps;
- passage-level provenance;
- normalized entity mentions;
- RDF named graphs;
- read-only SPARQL access;
- evidence packets suitable for grounded RAG.

Model-extracted statements must remain attributed and unverified until independently checked.

## Architecture

```text
Client / importer / application
             |
             | HTTP JSON
             v
        FastAPI service
      /       |        \
 ingestion  search   SPARQL/RAG
      |         \        /
      v          \      /
 app-owned       RDF/OWL graph
 SQLite + FTS5   N-Quads + SHACL
```

The repository contains no private transcript corpus and no generated graph from the author's private knowledge base. `examples/sample-document.json` is synthetic CC0 sample data.

## API

Interactive OpenAPI documentation is available at `/docs` after the server starts.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Process health |
| `GET` | `/v1/stats` | Document, passage and graph status |
| `GET` | `/v1/documents` | List document metadata |
| `GET` | `/v1/vocabulary` | List the controlled entity vocabulary |
| `PUT` | `/v1/vocabulary` | Replace the controlled vocabulary |
| `POST` | `/v1/documents` | Create or replace a document and its passages |
| `DELETE` | `/v1/documents/{source_id}` | Delete one document |
| `POST` | `/v1/search` | SQLite FTS5 evidence retrieval |
| `POST` | `/v1/graph/rebuild` | Rebuild the RDF named-graph dataset |
| `POST` | `/v1/sparql` | Read-only `SELECT` or `ASK` SPARQL |
| `POST` | `/v1/rag/context` | Search plus graph-enriched evidence packet |
| `GET` | `/v1/exports/passages.jsonl` | Download passages for Spark/Databricks |
| `GET` | `/v1/exports/graph.nq` | Download the generated N-Quads graph |

When `PODCAST_KG_API_KEY` is configured, mutating endpoints require `X-API-Key`. Production deployments should also use TLS and stronger gateway authentication.

## Quick start with Docker

```bash
cp .env.example .env
# Replace the sample secret in .env before remote deployment.
docker compose up --build
```

The API listens only on `127.0.0.1:8000` in the supplied Compose configuration.

Load the synthetic sample and exercise the API:

```bash
python examples/api_client.py --api-key "$PODCAST_KG_API_KEY"
```

Then open `http://127.0.0.1:8000/docs`.

## Local Python development

```bash
uv sync --extra dev
export PODCAST_KG_DATA_DIR="$PWD/data"
uv run uvicorn podcast_kg.api:app --reload
```

In another shell:

```bash
curl -X POST http://127.0.0.1:8000/v1/documents \
  -H 'Content-Type: application/json' \
  --data @examples/sample-document.json

curl -X POST http://127.0.0.1:8000/v1/graph/rebuild

curl -X POST http://127.0.0.1:8000/v1/rag/context \
  -H 'Content-Type: application/json' \
  -d '{"question":"How is ontology used?","limit":5}'
```

Read-only SPARQL example:

```bash
curl -X POST http://127.0.0.1:8000/v1/sparql \
  -H 'Content-Type: application/json' \
  -d '{"query":"PREFIX pkg: <https://github.com/karam-ai/knowledge-base/ontology#> SELECT (COUNT(?p) AS ?count) WHERE { ?p a pkg:Passage }"}'
```

SPARQL update operations such as `INSERT`, `DELETE`, `LOAD` and `CLEAR` are rejected.

## Importing an existing FTS corpus

The optional adapter reads a compatible `transcript_fts` SQLite database locally and sends documents through the public API:

```bash
python examples/import_sqlite_fts.py \
  --db /path/to/podcasts.sqlite3 \
  --url http://127.0.0.1:8000 \
  --api-key "$PODCAST_KG_API_KEY"
```

The server never mounts or reads the source database. Filesystem paths are excluded by default; use `--include-source-path` only when deliberate disclosure is acceptable.

## Data model

A document contains a stable `source_id`, title, language, optional public source URI, metadata and one or more timestamped passages. Passage identifiers are deterministic SHA-256 values over:

```text
source_id + start + end + text
```

The generated RDF dataset uses episode-level named graphs and PROV-O links. The ontology is in `ontology/podcast.ttl`; SHACL constraints are in `shapes/podcast.shacl.ttl`.

## Graph-assisted RAG

`POST /v1/rag/context` performs lexical retrieval and attaches graph entities to each passage. The response includes passage IDs, timestamps, text, citation labels and an `evidence-only` policy. It does not call an external language model or silently convert podcast statements into verified facts.

## Deployment and data tooling

- `Dockerfile` and `compose.yaml`: local/container deployment.
- `deploy/k8s/`: non-root Kubernetes Deployment, Service and persistent storage.
- `.github/workflows/ci.yml`: GitHub Actions.
- `azure-pipelines.yml`: Azure DevOps.
- `databricks/podcast_graph_job.py`: standard PySpark entity/triple transformation.
- `databricks.yml`: Azure Databricks Asset Bundle definition.
- `go/cmd/kgcheck`: small Go SPARQL health client.

Before Kubernetes deployment, create the API-key secret outside Git:

```bash
kubectl -n podcast-kg create secret generic podcast-kg-api \
  --from-literal=api-key='replace-with-a-long-random-secret'
```

## Tests

```bash
uv run pytest -W ignore::DeprecationWarning -W ignore::UserWarning
bash scripts/ci.sh
```

The API tests cover ingestion, idempotent replacement, optional API-key protection, search, graph rebuilding, RAG context, exports, SPARQL restrictions and deletion.

## Privacy and content rights

- Do not commit private transcript corpora, app data, N-Quads exports or SQLite databases.
- Only ingest content you are permitted to process.
- Treat passage and graph exports as potentially sensitive.
- Use encrypted storage and encrypted backups when required.
- The bundled controlled-vocabulary extractor is intentionally conservative; it is not general-purpose NER.

See [SECURITY.md](SECURITY.md) for deployment guidance.

## Current limitations

- SQLite is intended for a single service instance; horizontal write scaling requires a different storage adapter.
- The API-key option is not a replacement for enterprise identity, authorization or tenancy.
- Graph rebuilds are synchronous.
- The project does not currently execute corpus-wide LLM claim extraction.
- Kubernetes and Databricks definitions require a real cluster/workspace before they can be called production-verified.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

MIT. See [LICENSE](LICENSE).
