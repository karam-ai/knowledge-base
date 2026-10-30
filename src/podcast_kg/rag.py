from __future__ import annotations

from typing import Any

from rdflib import Dataset
from rdflib.namespace import RDFS

from .graph import PK, passage_uri


def build_context_packet(
    retrieved_passages: list[dict[str, Any]], dataset: Dataset
) -> dict[str, Any]:
    passages: list[dict[str, Any]] = []
    for item in retrieved_passages:
        passage = passage_uri(str(item["passage_id"]))
        entities: set[str] = set()
        for entity in dataset.objects(passage, PK.mentions):
            labels = list(dataset.objects(entity, RDFS.label))
            if labels:
                entities.add(str(labels[0]))
        title = str(item["title"])
        start = str(item["start"])
        end = str(item["end"])
        passages.append(
            {
                **item,
                "citation": f"{title}, {start}-{end}",
                "entities": sorted(entities),
            }
        )
    return {"passages": passages, "policy": "evidence-only"}
