import pytest

pytest.importorskip("pyspark")

from pyspark.sql import functions as F  # noqa: E402

from pipeline.silver.quality_checks import filter_partitions, validate_silver_quality  # noqa: E402


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