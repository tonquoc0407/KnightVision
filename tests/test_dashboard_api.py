from __future__ import annotations

from pathlib import Path

import duckdb

from dashboard_api.app import (
    _elo_to_bucket,
    blunder_heatmap_payload,
    evidence_payload,
    health_payload,
    openings_payload,
    overview_payload,
    player_profile_payload,
    players_payload,
    predict_blunder_payload,
    recommendations_payload,
    time_pressure_payload,
    years_payload,
)


def create_dashboard_db(path: Path) -> None:
    with duckdb.connect(str(path)) as connection:
        connection.execute("create schema analytics")
        connection.execute(
            """
            create table analytics.player_profiles (
                player varchar,
                year integer,
                month integer,
                games_played integer,
                wins integer,
                losses integer,
                draws integer,
                win_rate double,
                avg_elo double,
                elo_change double,
                most_played_opening_white varchar,
                most_played_opening_black varchar
            )
            """
        )
        connection.execute(
            """
            insert into analytics.player_profiles values
            ('alice', 2024, 1, 12, 7, 4, 1, 0.5833, 1820, 14, 'Sicilian Defense', 'French Defense'),
            ('bob', 2024, 1, 6, 2, 3, 1, 0.3333, 1710, -8, 'Queen''s Gambit', 'Caro-Kann Defense')
            """
        )
        connection.execute(
            """
            create table analytics.opening_stats (
                eco_code varchar,
                opening_family varchar,
                elo_bucket varchar,
                time_control_type varchar,
                year integer,
                games_count integer,
                white_win_rate double,
                black_win_rate double,
                draw_rate double,
                avg_game_length double,
                most_common_response varchar
            )
            """
        )
        connection.execute(
            """
            insert into analytics.opening_stats values
            ('B20', 'Sicilian Defense', '1600-1999', 'blitz', 2024, 20, 0.45, 0.50, 0.05, 42.1, 'c5'),
            ('D06', 'Queen''s Gambit', '1600-1999', 'rapid', 2024, 10, 0.55, 0.35, 0.10, 51.3, 'd5'),
            ('E60', 'King''s Indian', '1600-1800', 'blitz', 2024, 15, 0.52, 0.38, 0.10, 45.0, 'Nf6'),
            ('C50', 'Italian Game', '1600-1800', 'rapid', 2024, 8, 0.48, 0.42, 0.10, 38.0, 'e5')
            """
        )
        connection.execute(
            """
            create table analytics.time_pressure (
                time_remaining_bucket varchar,
                game_phase varchar,
                time_control_type varchar,
                year integer,
                games_count integer,
                evaluated_positions integer,
                blunder_count integer,
                avg_cp_loss double,
                blunder_rate double
            )
            """
        )
        connection.execute("insert into analytics.time_pressure values ('0-5s', 'middlegame', 'blitz', 2024, 5, 3, 1, 212.0, 0.3333)")
        connection.execute(
            """
            create table analytics.blunder_positions (
                square varchar,
                evaluated_positions integer,
                year integer,
                cp_loss integer,
                is_blunder boolean
            )
            """
        )
        connection.execute("insert into analytics.blunder_positions values ('f3', 1, 2024, 250, true), ('e4', 1, 2024, 40, false)")


def test_health_and_overview_use_active_warehouse(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "dashboard.duckdb"
    create_dashboard_db(db_path)
    monkeypatch.setenv("KNIGHTVISION_DUCKDB_PATH", str(db_path))

    health = health_payload()
    overview = overview_payload()

    assert health["status"] == "ready"
    assert "sources" in health
    assert health["counts"]["analytics.player_profiles"] == 2
    assert overview["summary"]["opening_rows"] == 4
    assert overview["summary"]["blunders"] == 1


def test_query_endpoints_return_stable_shapes(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "dashboard.duckdb"
    create_dashboard_db(db_path)
    monkeypatch.setenv("KNIGHTVISION_DUCKDB_PATH", str(db_path))

    assert openings_payload(opening="sicilian")["rows"][0]["eco_code"] == "B20"
    assert players_payload()["rows"][0]["player"] == "alice"
    assert player_profile_payload("alice")["rows"][0]["avg_elo"] == 1820
    assert time_pressure_payload()["rows"][0]["blunder_rate"] == 0.3333
    assert blunder_heatmap_payload()["totals"]["blunders"] == 1


def test_player_search_and_year_filters(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "dashboard.duckdb"
    create_dashboard_db(db_path)
    monkeypatch.setenv("KNIGHTVISION_DUCKDB_PATH", str(db_path))

    search_rows = players_payload(search="ali")["rows"]
    assert [row["player"] for row in search_rows] == ["alice"]

    assert players_payload(year=2024)["count"] == 2
    assert players_payload(year=2025)["count"] == 0
    assert openings_payload(year=2024)["count"] == 4
    assert openings_payload(year=2025)["count"] == 0
    assert time_pressure_payload(year=2024)["count"] == 1
    assert time_pressure_payload(year=2025)["count"] == 0
    assert blunder_heatmap_payload(year=2025)["totals"]["blunders"] == 0
    assert years_payload()["years"] == [2024]


def test_missing_warehouse_returns_empty_state(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("KNIGHTVISION_DUCKDB_PATH", str(tmp_path / "missing.duckdb"))

    assert health_payload()["status"] == "missing_warehouse"
    assert openings_payload() == {"rows": [], "count": 0}


def test_predict_blunder_returns_valid_response_shape():
    result = predict_blunder_payload()
    if "error" in result:
        assert isinstance(result["error"], str)
    else:
        assert 0.0 <= result["blunder_probability"] <= 1.0
        assert isinstance(result["is_blunder"], bool)


def test_elo_to_bucket_conversion():
    assert _elo_to_bucket(1500) == "1400-1600"
    assert _elo_to_bucket(1700) == "1600-1800"
    assert _elo_to_bucket(1600) == "1600-1800"
    assert _elo_to_bucket(2200) == "2200+"
    assert _elo_to_bucket(2800) == "2200+"
    assert _elo_to_bucket(400) == "400-600"


def test_recommendations_payload_returns_rows_for_matching_bucket(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "dashboard.duckdb"
    create_dashboard_db(db_path)
    monkeypatch.setenv("KNIGHTVISION_DUCKDB_PATH", str(db_path))

    result = recommendations_payload(player_elo=1700, time_control="blitz", goal="win")
    assert result["elo_bucket"] == "1600-1800"
    assert result["count"] == 1
    assert result["rows"][0]["eco_code"] == "E60"
    assert result["goal"] == "win"


def test_recommendations_payload_draw_goal_sorts_by_draw_rate(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "dashboard.duckdb"
    create_dashboard_db(db_path)
    monkeypatch.setenv("KNIGHTVISION_DUCKDB_PATH", str(db_path))

    result = recommendations_payload(player_elo=1700, goal="draw")
    assert result["goal"] == "draw"
    assert result["count"] >= 1


def test_recommendations_payload_no_elo_returns_all(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "dashboard.duckdb"
    create_dashboard_db(db_path)
    monkeypatch.setenv("KNIGHTVISION_DUCKDB_PATH", str(db_path))

    result = recommendations_payload()
    assert result["elo_bucket"] is None
    assert result["count"] == 4


def test_evidence_payload_contains_sources_and_proof_points():
    evidence = evidence_payload()

    assert evidence["sources"]
    assert {row["key"] for row in evidence["sources"]} >= {"main", "sample", "benchmark"}
    assert evidence["proof_points"]
    assert "available_count" in evidence["ml"]
