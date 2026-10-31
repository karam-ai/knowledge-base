from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from podcast_kg.api import create_app
from podcast_kg.config import Settings


def client_for(tmp_path: Path, api_key: str | None = None) -> TestClient:
    settings = Settings(data_dir=tmp_path / "data", api_key=api_key)
    return TestClient(create_app(settings))


def sample_document() -> dict[str, object]:
    return {
        "source_id": "sample-episode-1",
        "title": "Semantic systems",
        "language": "en",
        "source_uri": "https://example.org/episodes/semantic-systems",
        "metadata": {"speaker": "Example Speaker", "license": "CC0-1.0"},
        "passages": [
            {
                "start": "00:01:00",
                "end": "00:01:30",
                "text": "Joe Lonsdale explained that Palantir uses an ontology to connect data.",
            },
            {
                "start": "00:01:31",
                "end": "00:02:00",
                "text": "OpenAI services can be integrated with Azure Databricks and Python.",
            },
        ],
    }


def test_standalone_api_ingest_search_graph_rag_and_delete(tmp_path: Path) -> None:
    with client_for(tmp_path) as client:
        health = client.get("/health")
        ingested = client.post("/v1/documents", json=sample_document())
        listed = client.get("/v1/documents")
        search = client.post("/v1/search", json={"query": "How is ontology used?", "limit": 5})
        rebuilt = client.post("/v1/graph/rebuild")
        rag = client.post(
            "/v1/rag/context",
            json={"question": "How is the ontology used?", "limit": 3},
        )
        sparql = client.post(
            "/v1/sparql",
            json={
                "query": "PREFIX pkg: <https://github.com/karam-ai/knowledge-base/ontology#> "
                "SELECT (COUNT(?p) AS ?count) WHERE { ?p a pkg:Passage }"
            },
        )
        stats = client.get("/v1/stats")
        passage_export = client.get("/v1/exports/passages.jsonl")
        graph_export = client.get("/v1/exports/graph.nq")
        deleted = client.delete("/v1/documents/sample-episode-1")
        final_stats = client.get("/v1/stats")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ingested.status_code == 201
    assert ingested.json()["passage_count"] == 2
    assert listed.json()["documents"][0]["source_id"] == "sample-episode-1"
    assert search.json()["passages"][0]["start"] == "00:01:00"
    assert rebuilt.json()["passages"] == 2
    assert rag.json()["policy"] == "evidence-only"
    assert "Palantir" in rag.json()["passages"][0]["entities"]
    assert rag.json()["passages"][0]["citation"] == "Semantic systems, 00:01:00-00:01:30"
    assert sparql.json()["rows"] == [{"count": "2"}]
    assert stats.json()["documents"] == 1
    assert stats.json()["passages"] == 2
    assert passage_export.headers["content-type"].startswith("application/x-ndjson")
    assert len(passage_export.text.splitlines()) == 2
    assert graph_export.headers["content-type"].startswith("application/n-quads")
    assert "pkg:Passage" not in graph_export.text
    assert deleted.status_code == 204
    assert final_stats.json()["documents"] == 0


def test_timestamped_transcript_endpoint_ingests_srt(tmp_path: Path) -> None:
    payload = {
        "source_id": "new-podcast-episode",
        "title": "New podcast episode",
        "language": "en",
        "source_uri": "https://example.org/podcasts/new-episode",
        "metadata": {"podcast": "Example Podcast"},
        "format": "srt",
        "transcript": (
            "1\n"
            "00:00:05,000 --> 00:00:12,500\n"
            "The guest explains the knowledge graph.\n\n"
            "2\n"
            "00:00:13,000 --> 00:00:20,000\n"
            "FastAPI exposes the transcript through an API.\n"
        ),
    }

    with client_for(tmp_path) as client:
        ingested = client.post("/v1/transcripts", json=payload)
        search = client.post(
            "/v1/search", json={"query": "FastAPI transcript", "limit": 5}
        )

    assert ingested.status_code == 201
    assert ingested.json() == {
        "source_id": "new-podcast-episode",
        "created": True,
        "passage_count": 2,
        "transcript_format": "srt",
        "graph_status": "rebuild-required",
    }
    assert search.json()["passages"][0]["start"] == "00:00:13.000"
    assert search.json()["passages"][0]["end"] == "00:00:20.000"
    assert "FastAPI exposes" in search.json()["passages"][0]["text"]


def test_transcript_endpoint_rejects_non_srt_text(tmp_path: Path) -> None:
    payload = {
        "source_id": "invalid-transcript",
        "title": "Invalid transcript",
        "language": "en",
        "format": "srt",
        "transcript": "This text has no SRT timestamps.",
    }

    with client_for(tmp_path) as client:
        response = client.post("/v1/transcripts", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "The transcript contains no valid SRT subtitle passages"
    )


def test_document_upsert_is_idempotent(tmp_path: Path) -> None:
    with client_for(tmp_path) as client:
        first = client.post("/v1/documents", json=sample_document())
        second = client.post("/v1/documents", json=sample_document())
        stats = client.get("/v1/stats")

    assert first.status_code == 201
    assert second.status_code == 200
    assert stats.json()["documents"] == 1
    assert stats.json()["passages"] == 2


def test_write_endpoints_support_optional_api_key(tmp_path: Path) -> None:
    with client_for(tmp_path, api_key="test-secret") as client:
        unauthorized = client.post("/v1/documents", json=sample_document())
        authorized = client.post(
            "/v1/documents",
            json=sample_document(),
            headers={"X-API-Key": "test-secret"},
        )
        readable = client.get("/v1/stats")

    assert unauthorized.status_code == 401
    assert authorized.status_code == 201
    assert readable.status_code == 200


def test_vocabulary_is_configurable_through_api(tmp_path: Path) -> None:
    document = {
        "source_id": "custom-vocabulary",
        "title": "Custom vocabulary",
        "language": "en",
        "passages": [
            {
                "start": "00:00:00",
                "end": "00:00:10",
                "text": "GraphQL can expose a typed application schema.",
            }
        ],
    }
    with client_for(tmp_path) as client:
        replaced = client.put(
            "/v1/vocabulary",
            json={"terms": [{"term": "GraphQL", "entity_type": "Technology"}]},
        )
        listed = client.get("/v1/vocabulary")
        client.post("/v1/documents", json=document)
        client.post("/v1/graph/rebuild")
        rag = client.post(
            "/v1/rag/context", json={"question": "GraphQL", "limit": 3}
        )

    assert replaced.json()["term_count"] == 1
    assert listed.json()["terms"] == [
        {"term": "GraphQL", "entity_type": "Technology"}
    ]
    assert rag.json()["passages"][0]["entities"] == ["GraphQL"]


def test_sparql_is_read_only_and_graph_must_exist(tmp_path: Path) -> None:
    with client_for(tmp_path) as client:
        missing = client.post("/v1/sparql", json={"query": "ASK { ?s ?p ?o }"})
        blocked = client.post("/v1/sparql", json={"query": "DELETE WHERE { ?s ?p ?o }"})

    assert missing.status_code == 503
    assert blocked.status_code == 400


def test_validation_rejects_empty_or_oversized_input(tmp_path: Path) -> None:
    document = sample_document()
    document["passages"] = []
    with client_for(tmp_path) as client:
        empty_document = client.post("/v1/documents", json=document)
        empty_search = client.post("/v1/search", json={"query": "   ", "limit": 3})
        huge_limit = client.post("/v1/search", json={"query": "ontology", "limit": 101})

    assert empty_document.status_code == 422
    assert empty_search.status_code == 422
    assert huge_limit.status_code == 422
