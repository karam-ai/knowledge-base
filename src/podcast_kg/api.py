from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from rdflib import Dataset

from .config import Settings
from .graph import build_dataset, load_dataset
from .nlp import extract_entities
from .rag import build_context_packet
from .source import parse_srt_transcript
from .storage import Store

READ_QUERY = re.compile(
    r"^(?:\s*(?:PREFIX\s+[^\n]+|BASE\s+[^\n]+)\s*)*(SELECT|ASK)\b",
    re.IGNORECASE,
)


class PassageInput(BaseModel):
    start: str = Field(min_length=1, max_length=64)
    end: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=200_000)


class DocumentInput(BaseModel):
    source_id: str = Field(min_length=1, max_length=512, pattern=r"^[^\x00]+$")
    title: str = Field(min_length=1, max_length=2_000)
    language: str = Field(min_length=2, max_length=32)
    source_uri: str | None = Field(default=None, max_length=4_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    passages: list[PassageInput] = Field(min_length=1, max_length=50_000)


class TranscriptInput(BaseModel):
    source_id: str = Field(min_length=1, max_length=512, pattern=r"^[^\x00]+$")
    title: str = Field(min_length=1, max_length=2_000)
    language: str = Field(min_length=2, max_length=32)
    source_uri: str | None = Field(default=None, max_length=4_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    format: Literal["srt"] = "srt"
    transcript: str = Field(min_length=1, max_length=10_000_000)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    limit: int = Field(default=10, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def query_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value


class RagRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
    limit: int = Field(default=5, ge=1, le=50)

    @field_validator("question")
    @classmethod
    def question_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value


class VocabularyTerm(BaseModel):
    term: str = Field(min_length=1, max_length=500)
    entity_type: Literal["Person", "Organization", "Technology", "Topic"]


class VocabularyInput(BaseModel):
    terms: list[VocabularyTerm] = Field(min_length=1, max_length=10_000)


class SparqlRequest(BaseModel):
    query: str = Field(min_length=1, max_length=20_000)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = Store(settings.db_path)
    graph_cache: Dataset | None = None

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        settings.ensure_data_dir()
        store.initialize()
        yield

    app = FastAPI(
        title="Podcast Knowledge Graph API",
        summary="Standalone ingestion, RDF/SPARQL and evidence-grounded retrieval service",
        description=(
            "Ingest timestamped podcast passages, search evidence, rebuild an RDF/OWL graph, "
            "query it with read-only SPARQL, and create graph-enriched RAG context."
        ),
        version="0.1.0",
        license_info={"name": "MIT"},
        lifespan=lifespan,
    )

    def authorize_write(
        x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    ) -> None:
        if settings.api_key is not None and x_api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="A valid X-API-Key header is required")

    def invalidate_graph() -> None:
        nonlocal graph_cache
        graph_cache = None
        settings.graph_path.unlink(missing_ok=True)

    def rebuild_graph() -> dict[str, int | str]:
        nonlocal graph_cache
        records = store.read_passages()
        vocabulary = store.controlled_entities()
        mentions = [
            mention
            for record in records
            for mention in extract_entities(record, vocabulary)
        ]
        dataset = build_dataset(records, mentions, run_id="api-rebuild")
        settings.graph_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=settings.graph_path.parent, suffix=".nq", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
        try:
            dataset.serialize(temporary_path, format="nquads")
            os.replace(temporary_path, settings.graph_path)
        finally:
            temporary_path.unlink(missing_ok=True)
        graph_cache = dataset
        entities = {
            str(mention.normalized) + "\x1f" + mention.entity_type for mention in mentions
        }
        return {
            "status": "rebuilt",
            "documents": store.stats()["documents"],
            "passages": len(records),
            "mentions": len(mentions),
            "entities": len(entities),
            "graph_path": str(settings.graph_path),
        }

    def dataset() -> Dataset:
        nonlocal graph_cache
        if graph_cache is None:
            if not settings.graph_path.exists():
                raise HTTPException(
                    status_code=503,
                    detail="Knowledge graph is not available; call POST /v1/graph/rebuild",
                )
            graph_cache = load_dataset(settings.graph_path)
        return graph_cache

    @app.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "podcast-knowledge-graph-api"}

    @app.get("/v1/stats", tags=["operations"])
    def stats() -> dict[str, int | bool]:
        values = store.stats()
        return {**values, "graph_available": settings.graph_path.exists()}

    @app.get("/v1/vocabulary", tags=["vocabulary"])
    def list_vocabulary() -> dict[str, object]:
        return {"terms": store.list_vocabulary()}

    @app.put(
        "/v1/vocabulary",
        tags=["vocabulary"],
        dependencies=[Depends(authorize_write)],
    )
    def replace_vocabulary(vocabulary: VocabularyInput) -> dict[str, int | str]:
        unique = {
            (item.term.strip(), item.entity_type)
            for item in vocabulary.terms
            if item.term.strip()
        }
        terms = [
            {"term": term, "entity_type": entity_type}
            for term, entity_type in sorted(unique, key=lambda item: (item[0].casefold(), item[1]))
        ]
        if not terms:
            raise HTTPException(status_code=422, detail="Vocabulary must contain a non-blank term")
        store.replace_vocabulary(terms)
        invalidate_graph()
        return {"status": "replaced", "term_count": len(terms)}

    @app.get("/v1/documents", tags=["documents"])
    def list_documents() -> dict[str, object]:
        return {"documents": store.list_documents()}

    @app.post(
        "/v1/transcripts",
        tags=["documents"],
        dependencies=[Depends(authorize_write)],
    )
    def ingest_transcript(
        transcript: TranscriptInput,
        response: Response,
    ) -> dict[str, object]:
        try:
            passages = parse_srt_transcript(transcript.transcript)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        created = store.upsert_document(
            source_id=transcript.source_id,
            title=transcript.title,
            language=transcript.language,
            source_uri=transcript.source_uri,
            metadata=transcript.metadata,
            passages=passages,
        )
        invalidate_graph()
        response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return {
            "source_id": transcript.source_id,
            "created": created,
            "passage_count": len(passages),
            "transcript_format": transcript.format,
            "graph_status": "rebuild-required",
        }

    @app.post("/v1/documents", tags=["documents"], dependencies=[Depends(authorize_write)])
    def ingest_document(
        document: DocumentInput,
        response: Response,
    ) -> dict[str, object]:
        created = store.upsert_document(
            source_id=document.source_id,
            title=document.title,
            language=document.language,
            source_uri=document.source_uri,
            metadata=document.metadata,
            passages=[item.model_dump() for item in document.passages],
        )
        invalidate_graph()
        response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return {
            "source_id": document.source_id,
            "created": created,
            "passage_count": len(document.passages),
            "graph_status": "rebuild-required",
        }

    @app.delete(
        "/v1/documents/{source_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["documents"],
        dependencies=[Depends(authorize_write)],
    )
    def delete_document(source_id: str) -> Response:
        if not store.delete_document(source_id):
            raise HTTPException(status_code=404, detail="Document not found")
        invalidate_graph()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/v1/search", tags=["retrieval"])
    def search(request: SearchRequest) -> dict[str, object]:
        return {"passages": store.search(request.query, request.limit)}

    @app.post(
        "/v1/graph/rebuild",
        tags=["graph"],
        dependencies=[Depends(authorize_write)],
    )
    def graph_rebuild() -> dict[str, int | str]:
        return rebuild_graph()

    @app.get("/v1/exports/passages.jsonl", tags=["exports"])
    def export_passages() -> Response:
        content = "\n".join(
            json.dumps(asdict(record), ensure_ascii=False, sort_keys=True)
            for record in store.read_passages()
        )
        if content:
            content += "\n"
        return Response(
            content=content,
            media_type="application/x-ndjson",
            headers={"Content-Disposition": 'attachment; filename="passages.jsonl"'},
        )

    @app.get("/v1/exports/graph.nq", tags=["exports"])
    def export_graph() -> FileResponse:
        dataset()
        return FileResponse(
            settings.graph_path,
            media_type="application/n-quads",
            filename="podcast.nq",
        )

    @app.post("/v1/rag/context", tags=["retrieval"])
    def rag_context(request: RagRequest) -> dict[str, object]:
        retrieved = store.search(request.question, request.limit)
        return build_context_packet(retrieved, dataset())

    @app.post("/v1/sparql", tags=["graph"])
    def sparql(request: SparqlRequest) -> dict[str, object]:
        match = READ_QUERY.match(request.query)
        if not match:
            raise HTTPException(
                status_code=400,
                detail="Only read-only SELECT and ASK queries are allowed",
            )
        try:
            result = dataset().query(request.query)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid SPARQL query: {exc}") from exc
        if match.group(1).upper() == "ASK":
            return {"boolean": bool(result.askAnswer)}
        columns = [str(item) for item in result.vars]
        rows = [
            {
                column: str(value)
                for column, value in zip(columns, row)
                if value is not None
            }
            for row in result
        ]
        return {"columns": columns, "rows": rows}

    return app


app = create_app()
