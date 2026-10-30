"""Azure Databricks-compatible passage, entity, and RDF triple pipeline.

This uses standard PySpark APIs and does not require dbutils, so the same script
can run on a local Spark installation for development.
"""

from __future__ import annotations

import argparse

CONTROLLED_TERMS = [
    ("palantir", "Organization"),
    ("openai", "Organization"),
    ("microsoft", "Organization"),
    ("pwc", "Organization"),
    ("sparql", "Technology"),
    ("rdf", "Technology"),
    ("owl", "Technology"),
    ("rag", "Technology"),
    ("python", "Technology"),
    ("docker", "Technology"),
    ("kubernetes", "Technology"),
    ("azure databricks", "Technology"),
    ("knowledge graph", "Topic"),
    ("ontology", "Topic"),
    ("semantic data layer", "Topic"),
]


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="JSONL/Parquet passage export")
    parser.add_argument("--input-format", choices=("json", "parquet"), default="json")
    parser.add_argument("--output", required=True, help="Delta/Parquet output directory")
    parser.add_argument("--output-format", choices=("delta", "parquet"), default="delta")
    return parser.parse_args()


def main() -> None:
    from pyspark.sql import SparkSession, functions as F, types as T

    args = arguments()
    spark = SparkSession.builder.appName("podcast-knowledge-graph").getOrCreate()
    passages = spark.read.format(args.input_format).load(args.input)
    passages = passages.select(
        "passage_id", "video_id", "path", "title", "language", "start", "end", "text", "text_sha256"
    ).dropDuplicates(["passage_id"])

    term_schema = T.ArrayType(
        T.StructType(
            [
                T.StructField("normalized", T.StringType(), False),
                T.StructField("entity_type", T.StringType(), False),
            ]
        )
    )
    terms = F.array(
        *[
            F.struct(F.lit(term).alias("normalized"), F.lit(entity_type).alias("entity_type"))
            for term, entity_type in CONTROLLED_TERMS
        ]
    ).cast(term_schema)
    mentions = (
        passages.withColumn("candidate", F.explode(terms))
        .where(F.instr(F.lower(F.col("text")), F.col("candidate.normalized")) > 0)
        .select(
            "passage_id",
            "video_id",
            F.col("candidate.normalized").alias("normalized"),
            F.col("candidate.entity_type").alias("entity_type"),
        )
        .withColumn(
            "entity_id",
            F.sha2(F.concat_ws("\u001f", "entity_type", "normalized"), 256),
        )
        .dropDuplicates(["passage_id", "entity_id"])
    )
    entities = mentions.select("entity_id", "normalized", "entity_type").dropDuplicates(["entity_id"])
    triples = mentions.select(
        F.concat(F.lit("urn:podcast:passage:"), F.col("passage_id")).alias("subject"),
        F.lit("https://github.com/karam-ai/knowledge-base/ontology#mentions").alias("predicate"),
        F.concat(F.lit("urn:podcast:entity:"), F.col("entity_type"), F.lit(":"), F.col("entity_id")).alias("object"),
        F.lit("iri").alias("object_type"),
        F.concat(F.lit("urn:podcast:episode:"), F.col("video_id")).alias("named_graph"),
        "passage_id",
    )

    writer_options = {"mode": "overwrite", "format": args.output_format}
    for name, frame in {
        "podcast_passages": passages,
        "podcast_entities": entities,
        "podcast_entity_mentions": mentions,
        "podcast_rdf_triples": triples,
    }.items():
        frame.write.mode(writer_options["mode"]).format(writer_options["format"]).save(
            f"{args.output.rstrip('/')}/{name}"
        )
    spark.stop()


if __name__ == "__main__":
    main()
