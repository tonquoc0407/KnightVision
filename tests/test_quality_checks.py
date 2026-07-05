import pytest

pytest.importorskip("pyspark")

from pyspark.sql import functions as F  # noqa: E402

from pipeline.bronze.ingest import build_bronze_rejected  # noqa: E402
from pipeline.silver.quality_checks import (  # noqa: E402
    _prev_month_str,
    detect_anomalies,
    filter_partitions,
    validate_silver_quality,
)


def test_prev_month_str_handles_year_boundary():
    assert _prev_month_str("2024-01") == "2023-12"
    assert _prev_month_str("2024-06") == "2024-05"
    assert _prev_month_str("2025-12") == "2025-11"


def test_detect_anomalies_clean_months_returns_empty():
    base = {
        "silver_count": 1000,
        "result_counts": {"white_win": 450, "black_win": 420, "draw": 130},
        "elo_mean": 1500.0,
        "elo_stddev": 200.0,
    }
    assert detect_anomalies(base, base) == []


def test_detect_anomalies_volume_spike():
    current = {"silver_count": 2000, "result_counts": {}, "elo_mean": None}
    prev = {"silver_count": 1000, "result_counts": {}, "elo_mean": None}
    anomalies = detect_anomalies(current, prev)
    assert any(a["check"] == "volume" for a in anomalies)


def test_detect_anomalies_result_distribution_drift():
    current = {"silver_count": 1000, "result_counts": {"white_win": 700, "black_win": 200, "draw": 100}, "elo_mean": None}
    prev = {"silver_count": 1000, "result_counts": {"white_win": 450, "black_win": 420, "draw": 130}, "elo_mean": None}
    anomalies = detect_anomalies(current, prev)
    checks = {a["check"] for a in anomalies}
    assert "result_distribution" in checks


def test_detect_anomalies_elo_shift():
    # z = |1900 - 1450| / 150 = 3.0 > 2.0 threshold
    current = {"silver_count": 1000, "result_counts": {}, "elo_mean": 1900.0, "elo_stddev": 150.0}
    prev = {"silver_count": 1000, "result_counts": {}, "elo_mean": 1450.0, "elo_stddev": 150.0}
    anomalies = detect_anomalies(current, prev)
    assert any(a["check"] == "elo_distribution" for a in anomalies)


def test_detect_anomalies_no_prev_data_skips_elo():
    current = {"silver_count": 1000, "result_counts": {}, "elo_mean": 1500.0}
    prev = {"silver_count": 1000, "result_counts": {}, "elo_mean": None, "elo_stddev": None}
    anomalies = detect_anomalies(current, prev)
    assert not any(a["check"] == "elo_distribution" for a in anomalies)


def test_validate_silver_quality_passes(spark_session):
    bronze = spark_session.createDataFrame(
        [("g1", "2024-01"), ("g2", "2024-01")],
        "game_id string, batch_id string",
    )
    silver = spark_session.createDataFrame(
        [
            ("g1", "alice", "bob", "white_win", 1500, 1450, "2024-01-01", 2024, 1, ["e2e4"], 1),
            ("g2", "carol", "dave", "draw", None, 1600, "2024-01-02", 2024, 1, [], 0),
        ],
        "game_id string, white string, black string, result string, white_elo int, black_elo int, game_date string, year int, month int, moves_uci array<string>, game_length int",
    ).withColumn("game_date", F.to_date("game_date"))

    metrics = validate_silver_quality(bronze, silver)

    assert metrics["bronze_count"] == 2
    assert metrics["silver_count"] == 2
    assert metrics["retention"] == 1.0
    assert metrics["null_counts"] == {"game_id": 0, "white": 0, "black": 0, "result": 0}
    assert metrics["duplicate_game_ids"] == 0
    assert metrics["result_counts"] == {"draw": 1, "white_win": 1}
    assert metrics["partitions"] == [{"year": 2024, "month": 1, "count": 2}]

def test_validate_silver_quality_rejects_invalid_result(spark_session):
    bronze = spark_session.createDataFrame([("g1", "2024-01")], "game_id string, batch_id string")
    silver = spark_session.createDataFrame(
        [("g1", "alice", "bob", "1-0", 1500, 1450, "2024-01-01", 2024, 1, ["e2e4"], 1)],
        "game_id string, white string, black string, result string, white_elo int, black_elo int, game_date string, year int, month int, moves_uci array<string>, game_length int",
    ).withColumn("game_date", F.to_date("game_date"))

    with pytest.raises(ValueError, match="invalid normalized results"):
        validate_silver_quality(bronze, silver)

def test_validate_silver_quality_rejects_missing_required_columns(spark_session):
    bronze = spark_session.createDataFrame([("g1", "2024-01")], "game_id string, batch_id string")
    silver = spark_session.createDataFrame(
        [("g1", "alice", "bob", "white_win")],
        "game_id string, white string, black string, result string",
    )

    with pytest.raises(ValueError, match="silver is missing required columns"):
        validate_silver_quality(bronze, silver)

def test_validate_silver_quality_rejects_duplicate_game_ids(spark_session):
    bronze = spark_session.createDataFrame([("g1", "2024-01")], "game_id string, batch_id string")
    silver = spark_session.createDataFrame(
        [
            ("g1", "alice", "bob", "white_win", 1500, 1450, "2024-01-01", 2024, 1, ["e2e4"], 1),
            ("g1", "alice", "bob", "white_win", 1500, 1450, "2024-01-01", 2024, 1, ["e2e4"], 1),
        ],
        "game_id string, white string, black string, result string, white_elo int, black_elo int, game_date string, year int, month int, moves_uci array<string>, game_length int",
    ).withColumn("game_date", F.to_date("game_date"))

    with pytest.raises(ValueError, match="duplicated game_id"):
        validate_silver_quality(bronze, silver, min_retention=1.0)

def test_build_bronze_rejected_captures_null_game_id_rows(spark_session):
    df = spark_session.createDataFrame(
        [("g1", "alice", "bob"), (None, "carol", "dave"), ("g2", "erin", "frank")],
        "game_id string, white string, black string",
    )
    rejected = build_bronze_rejected(df)
    rows = rejected.collect()
    assert len(rows) == 1
    assert rows[0]["game_id"] is None
    assert rows[0]["reject_reason"] == "null_game_id"

def test_filter_partitions_uses_explicit_bronze_and_silver_selectors(spark_session):
    bronze = spark_session.createDataFrame(
        [("g1", "real-lichess-api-2026-04"), ("g2", "2024-01")],
        "game_id string, batch_id string",
    )
    silver = spark_session.createDataFrame(
        [
            ("g1", "alice", "bob", "white_win", 1500, 1450, "2026-04-01", 2026, 4, ["e2e4"], 1),
            ("g2", "alice", "bob", "white_win", 1500, 1450, "2024-01-01", 2024, 1, ["e2e4"], 1),
        ],
        "game_id string, white string, black string, result string, white_elo int, black_elo int, game_date string, year int, month int, moves_uci array<string>, game_length int",
    ).withColumn("game_date", F.to_date("game_date"))

    bronze_filtered, silver_filtered = filter_partitions(
        bronze,
        silver,
        bronze_batch_id="real-lichess-api-2026-04",
        silver_month="2026-04",
    )

    assert bronze_filtered.count() == 1
    assert silver_filtered.count() == 1
    assert bronze_filtered.first()["batch_id"] == "real-lichess-api-2026-04"
    assert silver_filtered.first()["year"] == 2026
    assert silver_filtered.first()["month"] == 4