from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class PassageRecord:
    passage_id: str
    video_id: str
    path: str
    title: str
    language: str
    start: str
    end: str
    text: str
    text_sha256: str


def passage_identity(source_id: str, start: str, end: str, text: str) -> str:
    payload = "\x1f".join((source_id, start, end, text))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
