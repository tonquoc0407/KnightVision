# Build `gold/time_pressure_analysis` from Silver games with clock data

from __future__ import annotations

import argparse
from pathlib import Path

from pyspark.sql import functions as F

from pipeline.spark_session import build_spark


def bucket_time_remaining(seconds_col):
    return (
        F.when(seconds_col <= 5, F.lit("0-5s"))
        .when(seconds_col <= 15, F.lit("6-15s"))
        .when(seconds_col <= 30, F.lit("16-30s"))
        .when(seconds_col <= 60, F.lit("31-60s"))
        .otherwise(F.lit("60s+"))
    )

def phase_from_ply(ply_col):
    return F.when(ply_col <= 20, F.lit("opening")).when(ply_col <= 60, F.lit("middlegame")).otherwise(F.lit("endgame"))

def _has_parquet(path: str | None) -> bool:
    if not path:
        return False
    return any(Path(path).glob("**/*.parquet"))

def build_time_pressure_analysis(silver_df, blunder_df=None):
    with_clock = silver_df.filter(F.col("has_clock_data") & (F.size("clock_seconds") > 0))
    move_clock = with_clock.select(
        "time_control_type",
        "year",
        F.posexplode("clock_seconds").alias("ply_index", "time_remaining_seconds"),
    ).withColumn("ply_number", F.col("ply_index") + F.lit(1))

    clock_counts = (
        move_clock.withColumn("time_remaining_bucket", bucket_time_remaining(F.col("time_remaining_seconds")))
        .withColumn("game_phase", phase_from_ply(F.col("ply_number")))
        .groupBy("time_remaining_bucket", "game_phase", "time_control_type", "year")
        .agg(F.count("*").alias("games_count"))
    )

    if blunder_df is None:
        return (
            clock_counts.withColumn("evaluated_positions", F.lit(0).cast("long"))
            .withColumn("blunder_count", F.lit(0).cast("long"))
            .withColumn("avg_cp_loss", F.lit(None).cast("double"))
            .withColumn("blunder_rate", F.lit(None).cast("double"))
            .select(
                "time_remaining_bucket",
                "game_phase",
                "time_control_type",
                "year",
                "games_count",
                "evaluated_positions",
                "blunder_count",
                "avg_cp_loss",
                "blunder_rate",
            )
        )

    if "year" not in blunder_df.columns:
        blunder_df = blunder_df.withColumn("year", F.lit(None).cast("integer"))

    evaluated = (
        blunder_df.filter(F.col("time_remaining_seconds").isNotNull())
        .withColumn("time_remaining_bucket", bucket_time_remaining(F.col("time_remaining_seconds")))
        .groupBy("time_remaining_bucket", "game_phase", "time_control_type", "year")
        .agg(
            F.count("*").alias("evaluated_positions"),
            F.sum(F.when(F.col("is_blunder"), F.lit(1)).otherwise(F.lit(0))).cast("long").alias("blunder_count"),
            F.avg("cp_loss").cast("double").alias("avg_cp_loss"),
        )
        .withColumn(
            "blunder_rate",
            F.when(F.col("evaluated_positions") > 0, F.col("blunder_count") / F.col("evaluated_positions")).otherwise(
                F.lit(None).cast("double")
            ),
        )
    )

    return (
        clock_counts.join(
            evaluated,
            on=["time_remaining_bucket", "game_phase", "time_control_type", "year"],
            how="left",
        )
        .withColumn("evaluated_positions", F.coalesce(F.col("evaluated_positions"), F.lit(0)).cast("long"))
        .withColumn("blunder_count", F.coalesce(F.col("blunder_count"), F.lit(0)).cast("long"))
        .select(
            "time_remaining_bucket",
            "game_phase",
            "time_control_type",
            "year",
            "games_count",
            "evaluated_positions",
            "blunder_count",
            "avg_cp_loss",
            "blunder_rate",
        )
    )

def run(input_path: str, output_path: str, *, blunder_input: str | None = None) -> None:
    spark = build_spark("KnightVision Gold Time Pressure", master="local[5]")
    try:
        blunder_df = spark.read.parquet(blunder_input) if _has_parquet(blunder_input) else None
        build_time_pressure_analysis(spark.read.parquet(input_path), blunder_df=blunder_df).write.mode("overwrite").partitionBy(
            "year"
        ).parquet(output_path)
    finally:
        spark.stop()

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--blunder-input", help="Optional gold/blunder_positions path for cp-loss and blunder metrics.")
    args = parser.parse_args()
    run(args.input, args.output, blunder_input=args.blunder_input)

if __name__ == "__main__":
    main()