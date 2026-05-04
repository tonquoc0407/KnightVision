import pytest

pytest.importorskip("pyspark")

from pipeline.silver.transform import transform_silver  # noqa: E402


def test_transform_silver_enriches_and_joins_eco_reference(spark_session):
    raw = spark_session.createDataFrame(
        [
            (
                "g1",
                "alice",
                "bob",
                "1500",
                "1450",
                "1-0",
                "B20",
                "Raw Opening",
                "300+0",
                "Normal",
                "2024.01.01",
                "1. e4 { [%clk 0:05:00] } c5 { [%clk 0:04:59] } 1-0",
                "0:05:00 0:04:59",
                "2024-01",
            ),
            (
                "g2",
                "helperBOT",
                "carol",
                "?",
                "?",
                "0-1",
                "C20",
                "Fallback Family: Variation",
                "60+0",
                "Time forfeit",
                "2024.01.01",
                "1. e4 e5 0-1",
                None,
                "2024-01",
            ),
        ],
        "game_id string, white string, black string, white_elo string, black_elo string, result string, eco string, opening string, time_control string, termination string, utc_date string, moves string, clock_annotations string, batch_id string",
    )
    eco = spark_session.createDataFrame(
        [("B20", "Sicilian Defense: Modern Variations")],
        "eco string, name string",
    )

    rows = {row["game_id"]: row for row in transform_silver(raw, eco_reference_df=eco).collect()}

    assert rows["g1"]["opening_family"] == "Sicilian Defense"
    assert rows["g1"]["opening_variation"] == "Modern Variations"
    assert rows["g1"]["clock_seconds"] == [300, 299]
    assert rows["g1"]["has_capture"] is False
    assert rows["g1"]["result_reason"] == "checkmate_or_resignation"
    assert rows["g2"]["opening_family"] == "Fallback Family"
    assert rows["g2"]["has_bot_player"] is True
    assert rows["g2"]["result_reason"] == "timeout"

def test_transform_silver_filters_bots_unrated_and_corrupt_games(spark_session):
    raw = spark_session.createDataFrame(
        [
            ("g1", "alice", "bob", "1500", "1450", "1-0", "B20", "Opening", "300+0", "Normal", "2024.01.01", "1. e4 c5 1-0", None, "2024-01"),
            ("g2", "helperBOT", "carol", "1500", "1450", "1-0", "B20", "Opening", "300+0", "Normal", "2024.01.01", "1. e4 c5 1-0", None, "2024-01"),
            ("g3", "dave", "erin", "?", "?", "1-0", "B20", "Opening", "300+0", "Normal", "2024.01.01", "1. e4 c5 1-0", None, "2024-01"),
            ("g4", "frank", "grace", "1500", "1450", "1-0", "B20", "Opening", "300+0", "Normal", "2024.01.01", "not-a-move 1-0", None, "2024-01"),
        ],
        "game_id string, white string, black string, white_elo string, black_elo string, result string, eco string, opening string, time_control string, termination string, utc_date string, moves string, clock_annotations string, batch_id string",
    )

    rows = transform_silver(raw, exclude_bots=True, exclude_unrated=True, drop_corrupt_pgn=True).select("game_id").collect()

    assert [row["game_id"] for row in rows] == ["g1"]