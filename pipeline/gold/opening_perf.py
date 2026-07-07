# Build `gold/opening_performance` from Silver games

from __future__ import annotations

import argparse

from pyspark.sql import functions as F

from pipeline.spark_session import build_spark


def build_opening_performance(silver_df):
    with_response = silver_df.withColumn("most_common_response_candidate", F.element_at("moves_uci", 2))
    return with_response.groupBy("eco_code", "opening_family", "elo_bucket", "time_control_type", "year").agg(
        F.count("*").alias("games_count"),
        F.avg(F.when(F.col("result") == "white_win", 1.0).otherwise(0.0)).alias("white_win_rate"),
        F.avg(F.when(F.col("result") == "black_win", 1.0).otherwise(0.0)).alias("black_win_rate"),
        F.avg(F.when(F.col("result") == "draw", 1.0).otherwise(0.0)).alias("draw_rate"),
        F.avg("game_length").alias("avg_game_length"),
        F.mode("most_common_response_candidate").alias("most_common_response"),
    )

def run(input_path: str, output_path: str) -> None:
    spark = build_spark("KnightVision Gold Opening Performance", master="local[5]")
    try:
        build_opening_performance(spark.read.parquet(input_path)).write.mode("overwrite").partitionBy("year").parquet(
            output_path
        )
    finally:
        spark.stop()

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.input, args.output)

if __name__ == "__main__":
    main()