from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from .nlp import CONTROLLED_ENTITIES
from .source import PassageRecord, passage_identity

_STOP_WORDS = {"a", "an", "and", "how", "is", "of", "or", "the", "to", "used", "what"}


class Store:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    source_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    language TEXT NOT NULL,
                    source_uri TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS passages (
                    passage_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL REFERENCES documents(source_id) ON DELETE CASCADE,
                    ordinal INTEGER NOT NULL,
                    start TEXT NOT NULL,
                    end TEXT NOT NULL,
                    text TEXT NOT NULL,
                    text_sha256 TEXT NOT NULL,
                    UNIQUE(source_id, ordinal)
                );
                CREATE TABLE IF NOT EXISTS vocabulary (
                    term TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    PRIMARY KEY(term, entity_type)
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS passage_fts USING fts5(
                    passage_id UNINDEXED,
                    source_id UNINDEXED,
                    title,
                    language UNINDEXED,
                    start UNINDEXED,
                    end UNINDEXED,
                    text
                );
                """
            )
            if con.execute("SELECT COUNT(*) FROM vocabulary").fetchone()[0] == 0:
                con.executemany(
                    "INSERT INTO vocabulary(term, entity_type) VALUES (?, ?)",
                    [
                        (term, entity_type)
                        for entity_type, terms in CONTROLLED_ENTITIES.items()
                        for term in terms
                    ],
                )

    def list_vocabulary(self) -> list[dict[str, str]]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT term, entity_type FROM vocabulary ORDER BY term COLLATE NOCASE, entity_type"
            ).fetchall()
        return [
            {"term": str(row["term"]), "entity_type": str(row["entity_type"])}
            for row in rows
        ]

    def replace_vocabulary(self, terms: list[dict[str, str]]) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM vocabulary")
            con.executemany(
                "INSERT INTO vocabulary(term, entity_type) VALUES (?, ?)",
                [(item["term"], item["entity_type"]) for item in terms],
            )

    def controlled_entities(self) -> dict[str, tuple[str, ...]]:
        grouped: dict[str, list[str]] = {}
        for item in self.list_vocabulary():
            grouped.setdefault(item["entity_type"], []).append(item["term"])
        return {entity_type: tuple(terms) for entity_type, terms in grouped.items()}

    def upsert_document(
        self,
        *,
        source_id: str,
        title: str,
        language: str,
        source_uri: str | None,
        metadata: dict[str, Any],
        passages: list[dict[str, str]],
    ) -> bool:
        with self._connect() as con:
            created = con.execute(
                "SELECT 1 FROM documents WHERE source_id = ?", (source_id,)
            ).fetchone() is None
            con.execute("DELETE FROM passage_fts WHERE source_id = ?", (source_id,))
            con.execute("DELETE FROM passages WHERE source_id = ?", (source_id,))
            con.execute(
                """
                INSERT INTO documents(source_id, title, language, source_uri, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    title = excluded.title,
                    language = excluded.language,
                    source_uri = excluded.source_uri,
                    metadata_json = excluded.metadata_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (source_id, title, language, source_uri, json.dumps(metadata, sort_keys=True)),
            )
            for ordinal, item in enumerate(passages):
                passage_id = passage_identity(source_id, item["start"], item["end"], item["text"])
                text_sha256 = hashlib.sha256(item["text"].encode("utf-8")).hexdigest()
                con.execute(
                    "INSERT INTO passages VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        passage_id,
                        source_id,
                        ordinal,
                        item["start"],
                        item["end"],
                        item["text"],
                        text_sha256,
                    ),
                )
                con.execute(
                    "INSERT INTO passage_fts VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        passage_id,
                        source_id,
                        title,
                        language,
                        item["start"],
                        item["end"],
                        item["text"],
                    ),
                )
        return created

    def delete_document(self, source_id: str) -> bool:
        with self._connect() as con:
            exists = con.execute(
                "SELECT 1 FROM documents WHERE source_id = ?", (source_id,)
            ).fetchone()
            if exists is None:
                return False
            con.execute("DELETE FROM passage_fts WHERE source_id = ?", (source_id,))
            con.execute("DELETE FROM documents WHERE source_id = ?", (source_id,))
        return True

    def list_documents(self) -> list[dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT d.source_id, d.title, d.language, d.source_uri, d.metadata_json,
                       COUNT(p.passage_id) AS passage_count
                FROM documents d
                LEFT JOIN passages p ON p.source_id = d.source_id
                GROUP BY d.source_id
                ORDER BY d.source_id
                """
            ).fetchall()
        return [
            {
                "source_id": row["source_id"],
                "title": row["title"],
                "language": row["language"],
                "source_uri": row["source_uri"],
                "metadata": json.loads(row["metadata_json"]),
                "passage_count": row["passage_count"],
            }
            for row in rows
        ]

    def stats(self) -> dict[str, int]:
        with self._connect() as con:
            documents = int(con.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
            passages = int(con.execute("SELECT COUNT(*) FROM passages").fetchone()[0])
        return {"documents": documents, "passages": passages}

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        tokens = [
            token
            for token in re.findall(r"\w+", query.casefold(), flags=re.UNICODE)
            if token not in _STOP_WORDS
        ]
        if not tokens:
            return []
        fts_query = " OR ".join(f'"{token}"' for token in tokens)
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT passage_id, source_id, title, language, start, end, text,
                       bm25(passage_fts) AS rank
                FROM passage_fts
                WHERE passage_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()
        return [
            {
                "passage_id": row["passage_id"],
                "source_id": row["source_id"],
                "video_id": row["source_id"],
                "title": row["title"],
                "language": row["language"],
                "start": row["start"],
                "end": row["end"],
                "text": row["text"],
                "score": -float(row["rank"]),
            }
            for row in rows
        ]

    def read_passages(self) -> list[PassageRecord]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT p.passage_id, p.source_id, d.source_uri, d.title, d.language,
                       p.start, p.end, p.text, p.text_sha256
                FROM passages p
                JOIN documents d ON d.source_id = p.source_id
                ORDER BY p.source_id, p.ordinal
                """
            ).fetchall()
        return [
            PassageRecord(
                passage_id=row["passage_id"],
                video_id=row["source_id"],
                path=row["source_uri"] or row["source_id"],
                title=row["title"],
                language=row["language"],
                start=row["start"],
                end=row["end"],
                text=row["text"],
                text_sha256=row["text_sha256"],
            )
            for row in rows
        ]
