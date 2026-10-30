from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field


class ClaimCandidate(BaseModel):
    text: str
    claim_type: Literal[
        "reported_fact", "opinion", "prediction", "advice", "speculation"
    ]
    subject: str
    predicate: str
    object: str
    confidence: float = Field(ge=0.0, le=1.0)
    verification_status: Literal["unverified"] = "unverified"


class ExtractionResponse(BaseModel):
    claims: list[ClaimCandidate]


def build_extraction_prompt(text: str, passage_id: str) -> str:
    return f"""Extract explicit claims from one podcast passage as JSON.
Do not add facts, infer missing speakers, or convert opinions into verified facts.
Every result remains unverified until independently checked.

Passage ID: {passage_id}
Passage text: {text}

Return exactly this schema:
{{
  "claims": [
    {{
      "text": "verbatim or close paraphrase",
      "claim_type": "reported_fact|opinion|prediction|advice|speculation",
      "subject": "subject stated in the passage",
      "predicate": "short relationship",
      "object": "object stated in the passage",
      "confidence": 0.0
    }}
  ]
}}
"""


def parse_extraction_response(raw: str) -> list[ClaimCandidate]:
    payload = json.loads(raw)
    return ExtractionResponse.model_validate(payload).claims
