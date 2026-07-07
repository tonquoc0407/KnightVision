# Bronze ingestion job: raw Parquet to deduplicated Bronze games

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pyspark.sql import functions as F

from ingestion.schema import spark_raw_schema
from pipeline.spark_session import build_spark


def bronze_metrics(df, bronze) -> dict[str, object]:
    input_count = df.count()
    missing_game_id = df.filter(F.col("game_id").isNull()).count()
    duplicate_game_id_groups = df.groupBy("game_id").count().filter(F.col("game_id").isNotNull() & (F.col("count") > 1))
    duplicate_game_ids = duplicate_game_id_groups.count()
    duplicate_rows = duplicate_game_id_groups.agg(F.coalesce(F.sum(F.col("count") - 1), F.lit(0))).first()[0]
    output_count = bronze.count()
    by_partition = [
        row.asDict()
        for row in bronze.groupBy("batch_id", "source").count().orderBy("batch_id", "source").collect()
    ]
    return {
        "input_count": input_count,
        "missing_game_id": missing_game_id,
        "duplicate_game_ids": duplicate_game_ids,
        "duplicate_rows_removed": int(duplicate_rows or 0),
        "output_count": output_count,
        "rows_removed": input_count - output_count,
        "partitions": by_partition,
    }

def build_bronze_rejected(df):
    """Return rows rejected by bronze ingestion: those with a null game_id."""
    return df.filter(F.col("game_id").isNull()).withColumn("reject_reason", F.lit("null_game_id"))

def ingest_bronze(spark, input_path: str, output_path: str):
    df = spark.read.schema(spark_raw_schema()).parquet(input_path)
    bronze = df.dropna(subset=["game_id"]).dropDuplicates(["game_id"])
    bronze.write.mode("overwrite").partitionBy("batch_id", "source").parquet(output_path)
    return bronze

def run(
    input_path: str,
    output_path: str,
    *,
    metrics_output: Path | None = None,
    quarantine_output: str | None = None,
) -> dict[str, object]:
    spark = build_spark("KnightVision Bronze Ingest", master="local[5]")
    try:
        df = spark.read.schema(spark_raw_schema()).parquet(input_path)
        bronze = df.dropna(subset=["game_id"]).dropDuplicates(["game_id"])
        metrics = bronze_metrics(df, bronze)

        quarantine_count = metrics["missing_game_id"]
        if quarantine_output and quarantine_count > 0:
            build_bronze_rejected(df).write.mode("overwrite").parquet(quarantine_output)
        metrics["quarantine_count"] = quarantine_count
        metrics["quarantine_path"] = quarantine_output

        bronze.write.mode("overwrite").partitionBy("batch_id", "source").parquet(output_path)
        if metrics_output:
            metrics_output.parent.mkdir(parents=True, exist_ok=True)
            metrics_output.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
        return metrics
    finally:
        spark.stop()

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--metrics-output", type=Path, help="Optional JSON path for Bronze diagnostics.")
    parser.add_argument("--quarantine-output", help="Optional Parquet path for quarantined rows (null game_id).")
    args = parser.parse_args()

    metrics = run(args.input, args.output, metrics_output=args.metrics_output, quarantine_output=args.quarantine_output)
    print(
        "Bronze ingest complete: "
        f"input_count={metrics['input_count']}, "
        f"output_count={metrics['output_count']}, "
        f"missing_game_id={metrics['missing_game_id']}, "
        f"duplicate_rows_removed={metrics['duplicate_rows_removed']}, "
        f"quarantine_count={metrics['quarantine_count']}"
    )

if __name__ == "__main__":
    main()