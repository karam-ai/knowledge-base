from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .source import PassageRecord


@dataclass(frozen=True)
class EntityMention:
    passage_id: str
    surface: str
    normalized: str
    entity_type: str
    start_char: int
    end_char: int
    confidence: float
    extractor: str = "controlled-vocabulary-v1"


CONTROLLED_ENTITIES: dict[str, tuple[str, ...]] = {
    "Person": (
        "Joe Lonsdale",
        "Roman Yampolskiy",
    ),
    "Organization": (
        "Palantir",
        "OpenAI",
        "Microsoft",
        "Google",
        "PwC",
        "ASN Bank",
    ),
    "Technology": (
        "SPARQL",
        "RDF",
        "OWL",
        "RAG",
        "Python",
        "Docker",
        "Kubernetes",
        "GitHub Actions",
        "Azure DevOps",
        "Azure Databricks",
        "LangChain",
        "Ollama",
    ),
    "Topic": (
        "knowledge graph",
        "ontology",
        "semantic data layer",
        "natural language processing",
        "NLP",
        "metadata extraction",
        "entity resolution",
    ),
}


def normalize_label(value: str) -> str:
    folded = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(folded.split())


def extract_entities(
    record: PassageRecord,
    controlled_entities: dict[str, tuple[str, ...]] | None = None,
) -> list[EntityMention]:
    """Extract conservative entities with deterministic, reviewable rules."""
    vocabulary = CONTROLLED_ENTITIES if controlled_entities is None else controlled_entities
    found: dict[tuple[int, int, str], EntityMention] = {}
    for entity_type, terms in vocabulary.items():
        for term in terms:
            for match in re.finditer(rf"(?<!\w){re.escape(term)}(?!\w)", record.text, re.I):
                surface = match.group(0)
                found[(match.start(), match.end(), entity_type)] = EntityMention(
                    passage_id=record.passage_id,
                    surface=surface,
                    normalized=normalize_label(surface),
                    entity_type=entity_type,
                    start_char=match.start(),
                    end_char=match.end(),
                    confidence=1.0,
                )
    return sorted(found.values(), key=lambda item: (item.start_char, item.end_char))
