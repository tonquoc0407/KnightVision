# Silver games transformation job

from __future__ import annotations

import argparse

from pyspark.sql import functions as F
from pyspark.sql import types as T

from pipeline.silver.udfs import (
    elo_bucket,
    has_bot_player,
    move_feature_summary,
    normalize_result,
    normalize_termination,
    parse_clock_seconds,
    parse_elo,
    parse_moves,
    parse_time_control,
    result_reason,
)
from pipeline.spark_session import build_spark
from pipeline.utils.eco_loader import load_eco_reference


def _coalesce_existing(df, candidates: list[str]):
    existing = [F.col(column) for column in candidates if column in df.columns]
    return F.coalesce(*existing) if existing else F.lit(None).cast("string")

def prepare_eco_reference(eco_df):
    if eco_df is None:
        return None
    eco_code = _coalesce_existing(eco_df, ["eco", "ECO", "eco_code", "code"]).alias("eco_ref_code")
    opening_name = _coalesce_existing(eco_df, ["name", "Name", "opening", "Opening"]).alias("eco_ref_name")
    prepared = eco_df.select(eco_code, opening_name).dropna(subset=["eco_ref_code"]).dropDuplicates(["eco_ref_code"])
    return prepared.withColumn(
        "eco_ref_family",
        F.split(F.col("eco_ref_name"), ":").getItem(0),
    ).withColumn(
        "eco_ref_variation",
        F.when(F.instr(F.col("eco_ref_name"), ":") > 0, F.trim(F.split(F.col("eco_ref_name"), ":", 2).getItem(1))).otherwise(
            F.col("eco_ref_name")
        ),
    )

_SILVER_REQUIRED = ["game_id", "white", "black", "result", "year", "month"]

def transform_silver(
    df,
    *,
    eco_reference_df=None,
    exclude_bots: bool = False,
    exclude_unrated: bool = False,
    drop_corrupt_pgn: bool = False,
    return_quarantine: bool = False,
):
    parse_time_control_udf = F.udf(
        parse_time_control,
        T.StructType(
            [
                T.StructField("base_seconds", T.IntegerType()),
                T.StructField("increment_seconds", T.IntegerType()),
                T.StructField("estimated_total", T.IntegerType()),
                T.StructField("time_control_type", T.StringType()),
            ]
        ),
    )
    parse_elo_udf = F.udf(parse_elo, T.IntegerType())
    normalize_result_udf = F.udf(normalize_result, T.StringType())
    normalize_termination_udf = F.udf(normalize_termination, T.StringType())
    result_reason_udf = F.udf(result_reason, T.StringType())
    parse_moves_udf = F.udf(parse_moves, T.ArrayType(T.StringType()))
    parse_clock_seconds_udf = F.udf(parse_clock_seconds, T.ArrayType(T.IntegerType()))
    elo_bucket_udf = F.udf(elo_bucket, T.StringType())
    has_bot_player_udf = F.udf(has_bot_player, T.BooleanType())
    move_features_udf = F.udf(
        move_feature_summary,
        T.StructType(
            [
                T.StructField("has_capture", T.BooleanType()),
                T.StructField("capture_count", T.IntegerType()),
                T.StructField("white_castled", T.BooleanType()),
                T.StructField("black_castled", T.BooleanType()),
                T.StructField("legal_prefix_length", T.IntegerType()),
            ]
        ),
    )

    enriched = (
        df.withColumn("white_elo_int", parse_elo_udf("white_elo"))
        .withColumn("black_elo_int", parse_elo_udf("black_elo"))
        .withColumn("tc", parse_time_control_udf("time_control"))
        .withColumn("moves_uci", parse_moves_udf("moves"))
        .withColumn("clock_seconds", parse_clock_seconds_udf("clock_annotations"))
        .withColumn("move_features", move_features_udf("moves_uci"))
        .withColumn("game_date", F.to_date("utc_date", "yyyy.MM.dd"))
        .withColumn("result_norm", normalize_result_udf("result"))
        .withColumn("termination_norm", normalize_termination_udf("termination"))
        .withColumn("result_reason", result_reason_udf("termination"))
        .withColumn("game_length", F.size("moves_uci"))
        .withColumn("has_clock_data", F.size("clock_seconds") > 0)
        .withColumn("year", F.year("game_date"))
        .withColumn("month", F.month("game_date"))
        .withColumn("elo_bucket", elo_bucket_udf("white_elo_int", "black_elo_int"))
        .withColumn("has_bot_player", has_bot_player_udf("white", "black"))
    )

    if exclude_bots:
        enriched = enriched.filter(~F.col("has_bot_player"))
    if exclude_unrated:
        enriched = enriched.filter(F.col("white_elo_int").isNotNull() & F.col("black_elo_int").isNotNull())
    if drop_corrupt_pgn:
        enriched = enriched.filter((F.col("moves").isNull()) | (F.size("moves_uci") > 0))

    selected = enriched.select(
        "game_id",
        "white",
        "black",
        F.col("white_elo_int").alias("white_elo"),
        F.col("black_elo_int").alias("black_elo"),
        F.col("result_norm").alias("result"),
        F.col("termination_norm").alias("termination"),
        "result_reason",
        F.col("eco").alias("eco_code"),
        F.col("opening").alias("opening_variation"),
        F.split(F.col("opening"), ":").getItem(0).alias("opening_family"),
        F.col("tc.time_control_type").alias("time_control_type"),
        F.col("tc.base_seconds").alias("base_time_seconds"),
        F.col("tc.increment_seconds").alias("increment_seconds"),
        "game_date",
        "game_length",
        "has_clock_data",
        "clock_seconds",
        F.col("move_features.has_capture").alias("has_capture"),
        F.col("move_features.capture_count").alias("capture_count"),
        F.col("move_features.white_castled").alias("white_castled"),
        F.col("move_features.black_castled").alias("black_castled"),
        F.col("move_features.legal_prefix_length").alias("legal_prefix_length"),
        "has_bot_player",
        "moves_uci",
        "batch_id",
        "year",
        "month",
        "elo_bucket",
    )

    eco_ref = prepare_eco_reference(eco_reference_df)
    if eco_ref is not None:
        selected = (
            selected.join(eco_ref, selected.eco_code == eco_ref.eco_ref_code, "left")
            .withColumn("opening_family", F.coalesce(F.col("eco_ref_family"), F.col("opening_family")))
            .withColumn("opening_variation", F.coalesce(F.col("eco_ref_variation"), F.col("opening_variation")))
            .drop("eco_ref_code", "eco_ref_name", "eco_ref_family", "eco_ref_variation")
        )

    reject_mask = (
        F.col("game_id").isNull()
        | F.col("white").isNull()
        | F.col("black").isNull()
        | F.col("result").isNull()
        | F.col("year").isNull()
        | F.col("month").isNull()
    )
    silver = selected.filter(~reject_mask)
    if return_quarantine:
        quarantine = selected.filter(reject_mask).withColumn("reject_reason", F.lit("null_required_column"))
        return silver, quarantine
    return silver

def run(
    input_path: str,
    output_path: str,
    *,
    eco_reference_path: str | None = None,
    exclude_bots: bool = False,
    exclude_unrated: bool = False,
    drop_corrupt_pgn: bool = False,
    quarantine_output: str | None = None,
) -> dict[str, object]:
    spark = build_spark("KnightVision Silver Transform", master="local[*]")
    try:
        eco_reference_df = load_eco_reference(spark, eco_reference_path) if eco_reference_path else None
        silver, quarantine = transform_silver(
            spark.read.parquet(input_path),
            eco_reference_df=eco_reference_df,
            exclude_bots=exclude_bots,
            exclude_unrated=exclude_unrated,
            drop_corrupt_pgn=drop_corrupt_pgn,
            return_quarantine=True,
        )
        silver.write.mode("overwrite").partitionBy("year", "month").parquet(output_path)

        quarantine_count = 0
        if quarantine_output:
            quarantine_count = quarantine.count()
            if quarantine_count > 0:
                quarantine.write.mode("overwrite").parquet(quarantine_output)

        return {"quarantine_count": quarantine_count, "quarantine_path": quarantine_output}
    finally:
        spark.stop()

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--eco-reference")
    parser.add_argument("--exclude-bots", action="store_true")
    parser.add_argument("--exclude-unrated", action="store_true")
    parser.add_argument("--drop-corrupt-pgn", action="store_true")
    parser.add_argument("--quarantine-output", help="Optional Parquet path for quarantined rows (null required columns).")
    args = parser.parse_args()
    metrics = run(
        args.input,
        args.output,
        eco_reference_path=args.eco_reference,
        exclude_bots=args.exclude_bots,
        exclude_unrated=args.exclude_unrated,
        drop_corrupt_pgn=args.drop_corrupt_pgn,
        quarantine_output=args.quarantine_output,
    )
    print(f"Silver transform complete: quarantine_count={metrics['quarantine_count']}")

if __name__ == "__main__":
    main()