from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


_SRT_TIMING = re.compile(
    r"^(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
    r"(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})(?:\s+.*)?$"
)


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


def parse_srt_transcript(transcript: str) -> list[dict[str, str]]:
    """Convert an SRT transcript into timestamped passage dictionaries."""
    normalized = transcript.replace("\r\n", "\n").replace("\r", "\n").strip()
    passages: list[dict[str, str]] = []
    for block in re.split(r"\n\s*\n", normalized):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timing_index = next(
            (index for index, line in enumerate(lines) if _SRT_TIMING.match(line)),
            None,
        )
        if timing_index is None:
            continue
        timing = _SRT_TIMING.match(lines[timing_index])
        if timing is None:
            continue
        text = " ".join(lines[timing_index + 1 :]).strip()
        if not text:
            continue
        passages.append(
            {
                "start": timing.group("start").replace(",", "."),
                "end": timing.group("end").replace(",", "."),
                "text": text,
            }
        )
    if not passages:
        raise ValueError("The transcript contains no valid SRT subtitle passages")
    return passages
