from __future__ import annotations

import hashlib
from pathlib import Path

from pyshacl import validate

from podcast_kg.ai import build_extraction_prompt, parse_extraction_response
from podcast_kg.graph import build_dataset
from podcast_kg.nlp import extract_entities
from podcast_kg.source import PassageRecord, passage_identity


def record() -> PassageRecord:
    text = "Palantir uses an ontology with RDF, OWL and SPARQL."
    return PassageRecord(
        passage_id=passage_identity("episode-1", "00:00:00", "00:00:20", text),
        video_id="episode-1",
        path="https://example.org/episode-1",
        title="Synthetic episode",
        language="en",
        start="00:00:00",
        end="00:00:20",
        text=text,
        text_sha256=hashlib.sha256(text.encode()).hexdigest(),
    )


def test_graph_conforms_to_public_ontology_and_shapes() -> None:
    item = record()
    mentions = extract_entities(item)
    dataset = build_dataset([item], mentions, run_id="test")
    root = Path(__file__).parents[1]

    conforms, _, report = validate(
        data_graph=dataset,
        shacl_graph=str(root / "shapes" / "podcast.shacl.ttl"),
        ont_graph=str(root / "ontology" / "podcast.ttl"),
        inference="rdfs",
    )

    assert conforms, report
    assert {mention.surface for mention in mentions} >= {"Palantir", "RDF", "OWL", "SPARQL"}


def test_claim_parser_keeps_model_output_unverified() -> None:
    prompt = build_extraction_prompt("Palantir uses an ontology.", passage_id="p1")
    claims = parse_extraction_response(
        '{"claims":[{"text":"Palantir uses an ontology.",'
        '"claim_type":"reported_fact","subject":"Palantir",'
        '"predicate":"uses","object":"ontology","confidence":0.8}]}'
    )

    assert "Do not add facts" in prompt
    assert claims[0].verification_status == "unverified"
