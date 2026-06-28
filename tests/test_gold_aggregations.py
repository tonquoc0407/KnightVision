import pytest

pytest.importorskip("pyspark")

from pipeline.gold.opening_perf import build_opening_performance  # noqa: E402
from pipeline.gold.time_pressure import build_time_pressure_analysis  # noqa: E402


def test_opening_performance_aggregation(spark_session):
    df = spark_session.createDataFrame(
        [
            ("B20", "Sicilian Defense", "1400-1600", "blitz", 2024, "white_win", 40, ["e2e4", "c7c5"]),
            ("B20", "Sicilian Defense", "1400-1600", "blitz", 2024, "black_win", 60, ["e2e4", "c7c5"]),
        ],
        "eco_code string, opening_family string, elo_bucket string, time_control_type string, year int, result string, game_length int, moves_uci array<string>",
    )
    rows = build_opening_performance(df).collect()
    assert len(rows) == 1
    assert rows[0]["games_count"] == 2
    assert rows[0]["white_win_rate"] == 0.5
    assert rows[0]["most_common_response"] == "c7c5"

def test_time_pressure_aggregation_uses_clock_buckets_and_phases(spark_session):
    df = spark_session.createDataFrame(
        [
            ("g1", True, [5, 12, 45, 120], "blitz", 2024),
            ("g2", True, [6], "blitz", 2024),
            ("g3", False, [], "rapid", 2024),
        ],
        "game_id string, has_clock_data boolean, clock_seconds array<int>, time_control_type string, year int",
    )
    rows = {
        (row["time_remaining_bucket"], row["game_phase"], row["time_control_type"]): row["games_count"]
        for row in build_time_pressure_analysis(df).collect()
    }
    assert rows[("0-5s", "opening", "blitz")] == 1
    assert rows[("6-15s", "opening", "blitz")] == 2
    assert rows[("31-60s", "opening", "blitz")] == 1
    assert rows[("60s+", "opening", "blitz")] == 1

def test_time_pressure_aggregation_joins_stockfish_metrics(spark_session):
    silver = spark_session.createDataFrame(
        [
            ("g1", True, [5, 12, 45], "blitz", 2024),
            ("g2", True, [6], "blitz", 2024),
        ],
        "game_id string, has_clock_data boolean, clock_seconds array<int>, time_control_type string, year int",
    )
    blunders = spark_session.createDataFrame(
        [
            ("g1", 1, "opening", "blitz", 2024, 5, 260, True),
            ("g1", 2, "opening", "blitz", 2024, 12, 40, False),
            ("g1", 3, "opening", "blitz", 2024, 45, 80, False),
            ("g2", 1, "opening", "blitz", 2024, 6, 220, True),
        ],
        "game_id string, ply_number int, game_phase string, time_control_type string, year int, time_remaining_seconds int, cp_loss int, is_blunder boolean",
    )

    rows = {
        row["time_remaining_bucket"]: row.asDict()
        for row in build_time_pressure_analysis(silver, blunder_df=blunders).collect()
    }

    assert rows["0-5s"]["games_count"] == 1
    assert rows["0-5s"]["evaluated_positions"] == 1
    assert rows["0-5s"]["blunder_count"] == 1
    assert rows["0-5s"]["avg_cp_loss"] == 260.0
    assert rows["0-5s"]["blunder_rate"] == 1.0
    assert rows["6-15s"]["games_count"] == 2
    assert rows["6-15s"]["evaluated_positions"] == 2
    assert rows["6-15s"]["blunder_count"] == 1
    assert rows["6-15s"]["avg_cp_loss"] == 130.0
    assert rows["6-15s"]["blunder_rate"] == 0.5