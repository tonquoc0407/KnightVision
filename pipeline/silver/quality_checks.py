# Data quality checks for the Bronze -> Silver boundary

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pyspark.sql import functions as F

from pipeline.spark_session import build_spark

ACCEPTED_RESULTS = {"white_win", "black_win", "draw"}
NON_NULL_COLUMNS = ["game_id", "white", "black", "result"]
REQUIRED_COLUMNS = {
    "game_id",
    "white",
    "black",
    "result",
    "white_elo",
    "black_elo",
    "game_date",
    "year",
    "month",
    "moves_uci",
    "game_length",
}

def require_columns(df, required: set[str], label: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {', '.join(missing)}")

def validate_silver_quality(
    bronze_df,
    silver_df,
    *,
    min_retention: float = 0.95,
    allow_empty: bool = False,
) -> dict[str, float]:
    require_columns(bronze_df, {"game_id"}, "bronze")
    require_columns(silver_df, REQUIRED_COLUMNS, "silver")

    bronze_count = bronze_df.count()
    silver_count = silver_df.count()
    if not allow_empty and bronze_count == 0:
        raise ValueError("bronze contains 0 rows")
    if not allow_empty and silver_count == 0:
        raise ValueError("silver contains 0 rows")

    retention = 1.0 if bronze_count == 0 else silver_count / bronze_count
    if retention < min_retention:
        raise ValueError(f"silver retention {retention:.2%} is below {min_retention:.2%}")

    null_counts: dict[str, int] = {}
    for column in NON_NULL_COLUMNS:
        nulls = silver_df.filter(silver_df[column].isNull()).count()
        null_counts[column] = nulls
        if nulls:
            raise ValueError(f"silver column {column} contains {nulls} nulls")

    invalid_results = silver_df.filter(~silver_df.result.isin(sorted(ACCEPTED_RESULTS))).count()
    if invalid_results:
        raise ValueError(f"silver contains {invalid_results} invalid normalized results")

    bad_elo = silver_df.filter(
        ((silver_df.white_elo.isNotNull()) & ~silver_df.white_elo.between(400, 3500))
        | ((silver_df.black_elo.isNotNull()) & ~silver_df.black_elo.between(400, 3500))
    ).count()
    if bad_elo:
        raise ValueError(f"silver contains {bad_elo} out-of-range Elo values")

    bad_partitions = silver_df.filter(
        (silver_df.game_date.isNotNull())
        & ((silver_df.year != F.year("game_date")) | (silver_df.month != F.month("game_date")))
    ).count()
    if bad_partitions:
        raise ValueError(f"silver contains {bad_partitions} rows with year/month not matching game_date")

    bad_move_lengths = silver_df.filter(
        (silver_df.moves_uci.isNotNull()) & (silver_df.game_length != F.size("moves_uci"))
    ).count()
    if bad_move_lengths:
        raise ValueError(f"silver contains {bad_move_lengths} rows with game_length != size(moves_uci)")

    duplicate_game_ids = silver_df.groupBy("game_id").count().filter(F.col("count") > 1).count()
    if duplicate_game_ids:
        raise ValueError(f"silver contains {duplicate_game_ids} duplicated game_id values")

    clock_rows = silver_df.filter(F.col("has_clock_data") == F.lit(True)).count() if "has_clock_data" in silver_df.columns else 0
    clock_coverage = 0.0 if silver_count == 0 else clock_rows / silver_count
    result_counts = {row["result"]: row["count"] for row in silver_df.groupBy("result").count().collect()}
    partition_counts = [
        row.asDict()
        for row in silver_df.groupBy("year", "month").count().orderBy("year", "month").collect()
    ]

    metrics = {
        "bronze_count": bronze_count,
        "silver_count": silver_count,
        "retention": retention,
        "null_counts": null_counts,
        "invalid_results": invalid_results,
        "bad_elo": bad_elo,
        "bad_partitions": bad_partitions,
        "bad_move_lengths": bad_move_lengths,
        "duplicate_game_ids": duplicate_game_ids,
        "clock_rows": clock_rows,
        "clock_coverage": clock_coverage,
        "result_counts": result_counts,
        "partitions": partition_counts,
    }
    return metrics

def filter_partitions(
    bronze_df,
    silver_df,
    *,
    bronze_batch_id: str | None = None,
    silver_month: str | None = None,
):
    if bronze_batch_id:
        bronze_df = bronze_df.filter(F.col("batch_id") == bronze_batch_id)
    if silver_month:
        year, month_num = silver_month.split("-", 1)
        silver_df = silver_df.filter((F.col("year") == int(year)) & (F.col("month") == int(month_num)))
    return bronze_df, silver_df

def run(
    bronze_path: str,
    silver_path: str,
    *,
    bronze_batch_id: str | None = None,
    silver_month: str | None = None,
    month: str | None = None,
    allow_empty: bool = False,
) -> dict[str, float]:
    spark = build_spark("KnightVision Silver Quality Gate", master="local[*]")
    try:
        bronze_df = spark.read.parquet(bronze_path)
        silver_df = spark.read.parquet(silver_path)
        if month and not silver_month:
            silver_month = month
        if month and not bronze_batch_id:
            bronze_batch_id = month
        bronze_df, silver_df = filter_partitions(
            bronze_df,
            silver_df,
            bronze_batch_id=bronze_batch_id,
            silver_month=silver_month,
        )
        return validate_silver_quality(bronze_df, silver_df, allow_empty=allow_empty)
    finally:
        spark.stop()

def main() -> None:
    parser = argparse.ArgumentParser(description="Run Bronze-to-Silver data quality checks.")
    parser.add_argument("--bronze", required=True, help="Bronze games Parquet path.")
    parser.add_argument("--silver", required=True, help="Silver games Parquet path.")
    parser.add_argument("--bronze-batch-id", help="Optional Bronze batch_id filter.")
    parser.add_argument("--silver-month", help="Optional YYYY-MM Silver partition filter.")
    parser.add_argument("--month", help="Legacy alias for both batch_id and silver month.")
    parser.add_argument("--allow-empty", action="store_true", help="Allow empty Bronze/Silver dataframes.")
    parser.add_argument("--metrics-output", type=Path, help="Optional JSON path for quality metrics.")
    args = parser.parse_args()

    metrics = run(
        args.bronze,
        args.silver,
        bronze_batch_id=args.bronze_batch_id,
        silver_month=args.silver_month,
        month=args.month,
        allow_empty=args.allow_empty,
    )
    if args.metrics_output:
        args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
        args.metrics_output.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    print(
        "Silver quality gate passed: "
        f"bronze_count={metrics['bronze_count']}, "
        f"silver_count={metrics['silver_count']}, "
        f"retention={metrics['retention']:.2%}"
    )

if __name__ == "__main__":
    main()