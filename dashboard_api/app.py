"""FastAPI app for the custom KnightVision dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from dashboard_api import artifacts
from dashboard_api.artifacts import MODELS_DIR
from dashboard_api.db import ROOT, WAREHOUSE_CHOICES, Warehouse, db_path_for

QUALITY_ROOTS = [ROOT / "data" / "sample" / "quality", ROOT / "data" / "quality"]


def _warehouse(source: str | None = None) -> Warehouse:
    return Warehouse(db_path_for(source))


def _count_table(warehouse: Warehouse, table: str) -> int:
    return int(warehouse.scalar(f"select count(*) from {table}", default=0) or 0)


def _quality_files() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for root in QUALITY_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {"error": "invalid json"}
            results.append({"path": path.relative_to(ROOT).as_posix(), "payload": payload})
    return results[-20:]


def _quality_status(payload: dict[str, Any]) -> str:
    failure_fields = [
        "parse_errors",
        "missing_game_id",
        "missing_players",
        "missing_result",
        "invalid_results",
        "bad_elo",
        "bad_partitions",
        "bad_move_lengths",
        "duplicate_game_ids",
    ]
    if any((payload.get(field) or 0) > 0 for field in failure_fields):
        return "warn"
    if payload.get("retention") is not None and payload["retention"] < 0.95:
        return "warn"
    return "pass"


def _quality_kind(path: str) -> str:
    name = Path(path).name
    if "parser" in name:
        return "parser"
    if "bronze" in name:
        return "bronze"
    if "silver" in name:
        return "silver"
    return "quality"


def quality_summary_payload() -> dict[str, Any]:
    files = _quality_files()
    cards = []
    for item in files:
        payload = item["payload"]
        cards.append(
            {
                "path": item["path"],
                "kind": _quality_kind(item["path"]),
                "status": _quality_status(payload),
                "primary_count": payload.get("rows_written")
                or payload.get("output_count")
                or payload.get("silver_count")
                or payload.get("games_seen"),
                "retention": payload.get("retention"),
                "clock_coverage": payload.get("clock_coverage"),
                "suspicious_rows": payload.get("suspicious_rows"),
                "rows_removed": payload.get("rows_removed"),
                "duplicate_game_ids": payload.get("duplicate_game_ids"),
                "payload": payload,
            }
        )
    return {
        "files": files,
        "cards": cards,
        "pass_count": sum(1 for card in cards if card["status"] == "pass"),
        "warn_count": sum(1 for card in cards if card["status"] == "warn"),
    }


def warehouse_sources_payload() -> dict[str, Any]:
    active_env = str(db_path_for())
    return {
        "active_env_path": active_env,
        "sources": [
            {
                "key": key,
                "label": key.replace("_", " ").title(),
                "path": str(path.relative_to(ROOT)),
                "exists": path.exists(),
                "size_mb": round(path.stat().st_size / 1024 / 1024, 2) if path.exists() else 0,
            }
            for key, path in WAREHOUSE_CHOICES.items()
        ],
    }


def health_payload(source: str | None = None) -> dict[str, Any]:
    warehouse = _warehouse(source)
    counts = {}
    if warehouse.ready:
        for table in [
            "analytics.opening_stats",
            "analytics.player_profiles",
            "analytics.time_pressure",
            "analytics.blunder_positions",
        ]:
            counts[table] = _count_table(warehouse, table)
    return {
        "status": "ready" if warehouse.ready else "missing_warehouse",
        "duckdb_path": str(warehouse.path),
        "source": source or "env",
        "sources": warehouse_sources_payload()["sources"],
        "counts": counts,
        "ml_artifacts": artifacts.summary(),
    }


def overview_payload(source: str | None = None) -> dict[str, Any]:
    warehouse = _warehouse(source)
    row = warehouse.records(
        """
        select
            (select count(*) from analytics.player_profiles) as player_profile_rows,
            (select count(*) from analytics.opening_stats) as opening_rows,
            (select count(*) from analytics.time_pressure) as time_pressure_rows,
            (select count(*) from analytics.blunder_positions) as evaluated_positions,
            (select coalesce(sum(case when is_blunder then 1 else 0 end), 0) from analytics.blunder_positions) as blunders
        """
    )
    return {"warehouse_ready": warehouse.ready, "summary": row[0] if row else {}, "quality": quality_summary_payload()["cards"]}


def openings_payload(
    eco: str | None = None,
    opening: str | None = None,
    limit: int = 50,
    source: str | None = None,
) -> dict[str, Any]:
    records = _warehouse(source).named_records("opening_stats.sql", [eco, eco, opening, opening, limit])
    return {"rows": records, "count": len(records)}


def players_payload(limit: int = 50, source: str | None = None) -> dict[str, Any]:
    rows = _warehouse(source).records(
        """
        select
            player,
            sum(games_played) as games_played,
            round(avg(win_rate), 4) as avg_win_rate,
            round(avg(avg_elo), 1) as avg_elo,
            any_value(most_played_opening_white) as white_opening,
            any_value(most_played_opening_black) as black_opening
        from analytics.player_profiles
        group by 1
        order by games_played desc, player
        limit ?
        """,
        [limit],
    )
    return {"rows": rows, "count": len(rows)}


def player_profile_payload(player: str, source: str | None = None) -> dict[str, Any]:
    return {"player": player, "rows": _warehouse(source).named_records("player_profile.sql", [player])}


def time_pressure_payload(source: str | None = None) -> dict[str, Any]:
    rows = _warehouse(source).named_records("time_pressure.sql")
    return {"rows": rows, "count": len(rows)}


def blunder_heatmap_payload(source: str | None = None) -> dict[str, Any]:
    rows = _warehouse(source).named_records("blunder_heatmap.sql")
    totals = {
        "evaluated_positions": sum(row.get("evaluated_positions") or 0 for row in rows),
        "blunders": sum(row.get("blunders") or 0 for row in rows),
        "max_cp_loss": max((row.get("max_cp_loss") or 0 for row in rows), default=0),
    }
    return {"rows": rows, "count": len(rows), "totals": totals}


def evidence_payload() -> dict[str, Any]:
    quality = quality_summary_payload()
    source_rows = []
    for source in warehouse_sources_payload()["sources"]:
        health = health_payload(source["key"])
        source_rows.append(
            {
                **source,
                "status": health["status"],
                "opening_rows": health["counts"].get("analytics.opening_stats", 0),
                "player_rows": health["counts"].get("analytics.player_profiles", 0),
                "time_pressure_rows": health["counts"].get("analytics.time_pressure", 0),
                "blunder_rows": health["counts"].get("analytics.blunder_positions", 0),
            }
        )
    return {
        "sources": source_rows,
        "quality": quality,
        "ml": artifacts.summary(),
        "proof_points": [
            {
                "label": "Fixture pipeline",
                "status": "pass" if any("sample/quality/silver_quality" in card["path"] for card in quality["cards"]) else "warn",
                "evidence": "Deterministic PGN fixture through Bronze, Silver, Gold, DuckDB, dbt, and dashboard queries.",
            },
            {
                "label": "Real API sample",
                "status": "pass" if any("real_sample" in card["path"] for card in quality["cards"]) else "warn",
                "evidence": "Public Lichess user export processed through the local warehouse path.",
            },
            {
                "label": "Monthly prefix benchmark",
                "status": "pass" if any("benchmark" in card["path"] for card in quality["cards"]) else "warn",
                "evidence": "Bounded monthly .pgn.zst prefix with hundreds of thousands of parsed games.",
            },
            {
                "label": "ML artifacts",
                "status": "pass" if artifacts.summary()["available_count"] >= 3 else "warn",
                "evidence": "Blunder prediction, opening outcome, and player style clustering artifacts are present.",
            },
        ],
    }


def create_app() -> FastAPI:
    app = FastAPI(title="KnightVision Dashboard API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3636", "http://127.0.0.1:3636"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if MODELS_DIR.exists():
        app.mount("/model-artifacts", StaticFiles(directory=MODELS_DIR), name="model-artifacts")

    @app.get("/api/sources")
    def sources() -> dict[str, Any]:
        return warehouse_sources_payload()

    @app.get("/api/health")
    def health(source: str | None = None) -> dict[str, Any]:
        return health_payload(source)

    @app.get("/api/overview")
    def overview(source: str | None = None) -> dict[str, Any]:
        return overview_payload(source)

    @app.get("/api/openings")
    def openings(
        eco: str | None = None,
        opening: str | None = None,
        limit: int = Query(default=50, ge=1, le=500),
        source: str | None = None,
    ) -> dict[str, Any]:
        return openings_payload(eco=eco, opening=opening, limit=limit, source=source)

    @app.get("/api/players")
    def players(limit: int = Query(default=50, ge=1, le=500), source: str | None = None) -> dict[str, Any]:
        return players_payload(limit=limit, source=source)

    @app.get("/api/players/{player}")
    def player_profile(player: str, source: str | None = None) -> dict[str, Any]:
        return player_profile_payload(player, source=source)

    @app.get("/api/time-pressure")
    def time_pressure(source: str | None = None) -> dict[str, Any]:
        return time_pressure_payload(source)

    @app.get("/api/blunders/heatmap")
    def blunder_heatmap(source: str | None = None) -> dict[str, Any]:
        return blunder_heatmap_payload(source)

    @app.get("/api/ml/summary")
    def ml_summary() -> dict[str, Any]:
        return artifacts.summary()

    @app.get("/api/ml/blunder")
    def ml_blunder() -> dict[str, Any]:
        return artifacts.blunder_artifacts()

    @app.get("/api/ml/opening-outcome")
    def ml_opening_outcome() -> dict[str, Any]:
        return artifacts.opening_outcome_artifacts()

    @app.get("/api/ml/player-style")
    def ml_player_style() -> dict[str, Any]:
        return artifacts.player_style_artifacts()

    @app.get("/api/data-quality")
    def data_quality() -> dict[str, Any]:
        return quality_summary_payload()

    @app.get("/api/evidence")
    def evidence() -> dict[str, Any]:
        return evidence_payload()

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("dashboard_api.app:app", host="127.0.0.1", port=3637, reload=True)
