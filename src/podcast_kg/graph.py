from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

from rdflib import Dataset, Literal, Namespace, URIRef
from rdflib.namespace import PROV, RDF, RDFS, XSD

from .nlp import EntityMention
from .source import PassageRecord

PK = Namespace("https://github.com/karam-ai/knowledge-base/ontology#")
SCHEMA = Namespace("https://schema.org/")


def episode_uri(video_id: str) -> URIRef:
    return URIRef(f"urn:podcast:episode:{quote(video_id, safe='')}")


def passage_uri(passage_id: str) -> URIRef:
    return URIRef(f"urn:podcast:passage:{passage_id}")


def entity_uri(entity_type: str, normalized: str) -> URIRef:
    digest = hashlib.sha256(f"{entity_type}\x1f{normalized}".encode()).hexdigest()[:24]
    return URIRef(f"urn:podcast:entity:{entity_type.casefold()}:{digest}")


def build_dataset(
    records: list[PassageRecord], mentions: list[EntityMention], run_id: str
) -> Dataset:
    dataset = Dataset(default_union=True)
    dataset.bind("pk", PK)
    dataset.bind("schema", SCHEMA)
    dataset.bind("prov", PROV)
    dataset.bind("rdf", RDF)
    by_passage: dict[str, list[EntityMention]] = defaultdict(list)
    for mention in mentions:
        by_passage[mention.passage_id].append(mention)
    run = URIRef(f"urn:podcast:run:{quote(run_id, safe='')}")
    for record in records:
        graph = dataset.graph(episode_uri(record.video_id))
        episode = episode_uri(record.video_id)
        passage = passage_uri(record.passage_id)
        source = URIRef(f"urn:podcast:source:{quote(record.path, safe='')}")
        graph.add((episode, RDF.type, PK.Episode))
        graph.add((episode, SCHEMA.name, Literal(record.title)))
        graph.add((episode, SCHEMA.inLanguage, Literal(record.language)))
        graph.add((episode, PK.videoId, Literal(record.video_id)))
        graph.add((episode, PK.hasPassage, passage))
        graph.add((passage, RDF.type, PK.Passage))
        graph.add((passage, PK.startTimestamp, Literal(record.start)))
        graph.add((passage, PK.endTimestamp, Literal(record.end)))
        graph.add((passage, PK.text, Literal(record.text)))
        graph.add((passage, PK.textSha256, Literal(record.text_sha256)))
        graph.add((passage, PK.sourcePath, Literal(record.path)))
        graph.add((passage, PROV.wasDerivedFrom, source))
        graph.add((passage, PROV.wasGeneratedBy, run))
        graph.add((run, RDF.type, PK.ExtractionRun))
        for mention in by_passage.get(record.passage_id, []):
            entity = entity_uri(mention.entity_type, mention.normalized)
            graph.add((passage, PK.mentions, entity))
            graph.add((entity, RDF.type, PK[mention.entity_type]))
            graph.add((entity, RDFS.label, Literal(mention.surface)))
            graph.add((entity, PK.normalizedLabel, Literal(mention.normalized)))
            mention_node = URIRef(
                f"urn:podcast:mention:{record.passage_id}:{mention.start_char}:{mention.end_char}"
            )
            graph.add((mention_node, RDF.type, PK.EntityMention))
            graph.add((mention_node, PK.inPassage, passage))
            graph.add((mention_node, PK.refersTo, entity))
            graph.add((mention_node, PK.mentionSurface, Literal(mention.surface)))
            graph.add((mention_node, PK.startChar, Literal(mention.start_char, datatype=XSD.integer)))
            graph.add((mention_node, PK.endChar, Literal(mention.end_char, datatype=XSD.integer)))
            graph.add((mention_node, PK.confidence, Literal(mention.confidence, datatype=XSD.decimal)))
            graph.add((mention_node, PK.extractor, Literal(mention.extractor)))
            graph.add((mention_node, PROV.wasGeneratedBy, run))
    return dataset


def load_dataset(path: Path) -> Dataset:
    dataset = Dataset(default_union=True)
    dataset.parse(path, format="nquads")
    return dataset
