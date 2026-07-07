# Build `gold/player_monthly_stats` from Silver games.
from __future__ import annotations

import argparse

from pyspark.sql import functions as F

from pipeline.spark_session import build_spark


def build_player_monthly_stats(silver_df):
    white = silver_df.select(
        F.col("white").alias("player"),
        "year",
        "month",
        F.col("white_elo").alias("elo"),
        F.when(F.col("result") == "white_win", 1).otherwise(0).alias("wins"),
        F.when(F.col("result") == "black_win", 1).otherwise(0).alias("losses"),
        F.when(F.col("result") == "draw", 1).otherwise(0).alias("draws"),
        F.col("eco_code").alias("opening_white"),
        F.lit(None).cast("string").alias("opening_black"),
    )
    black = silver_df.select(
        F.col("black").alias("player"),
        "year",
        "month",
        F.col("black_elo").alias("elo"),
        F.when(F.col("result") == "black_win", 1).otherwise(0).alias("wins"),
        F.when(F.col("result") == "white_win", 1).otherwise(0).alias("losses"),
        F.when(F.col("result") == "draw", 1).otherwise(0).alias("draws"),
        F.lit(None).cast("string").alias("opening_white"),
        F.col("eco_code").alias("opening_black"),
    )
    games = white.unionByName(black)
    return games.groupBy("player", "year", "month").agg(
        F.count("*").alias("games_played"),
        F.sum("wins").alias("wins"),
        F.sum("losses").alias("losses"),
        F.sum("draws").alias("draws"),
        (F.sum("wins") / F.count("*")).alias("win_rate"),
        F.avg("elo").alias("avg_elo"),
        (F.max("elo") - F.min("elo")).alias("elo_change"),
        F.mode("opening_white").alias("most_played_opening_white"),
        F.mode("opening_black").alias("most_played_opening_black"),
    )

def run(input_path: str, output_path: str) -> None:
    spark = build_spark("KnightVision Gold Player Stats", master="local[5]")
    try:
        build_player_monthly_stats(spark.read.parquet(input_path)).write.mode("overwrite").partitionBy(
            "year", "month"
        ).parquet(output_path)
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