from __future__ import annotations

import json
from typing import Any


def build_grounded_prompt(question: str, context_packet: dict[str, Any]) -> str:
    evidence = json.dumps(context_packet, ensure_ascii=False, indent=2)
    return (
        "You answer questions about a podcast corpus. Only use the supplied evidence. "
        "Treat speaker statements as attributed claims, not verified facts. If the evidence "
        "is insufficient, say so. Cite passage_id and timestamp for every substantive claim.\n\n"
        f"Question:\n{question}\n\nEvidence:\n{evidence}\n"
    )
