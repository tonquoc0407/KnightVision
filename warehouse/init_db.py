# Initialize the KnightVision DuckDB warehouse over local Parquet lake data

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = ROOT / "data"
DEFAULT_DB_PATH = ROOT / "warehouse" / "knightvision.duckdb"

GOLD_TABLES = {
    "gold_player_monthly_stats": "gold/player_monthly_stats/**/*.parquet",
    "gold_opening_performance": "gold/opening_performance/**/*.parquet",
    "gold_time_pressure_analysis": "gold/time_pressure_analysis/**/*.parquet",
    "gold_blunder_positions": "gold/blunder_positions/**/*.parquet",
}

SILVER_TABLES = {
    "silver_games": "silver/games/**/*.parquet",
}

PLACEHOLDER_COLUMNS = {
    "silver_games": {
        "game_id": "varchar",
        "white": "varchar",
        "black": "varchar",
        "white_elo": "integer",
        "black_elo": "integer",
        "result": "varchar",
        "termination": "varchar",
        "result_reason": "varchar",
        "eco_code": "varchar",
        "opening_family": "varchar",
        "opening_variation": "varchar",
        "time_control_type": "varchar",
        "base_time_seconds": "integer",
        "increment_seconds": "integer",
        "game_date": "date",
        "game_length": "integer",
        "has_clock_data": "boolean",
        "clock_seconds": "integer[]",
        "has_capture": "boolean",
        "capture_count": "integer",
        "white_castled": "boolean",
        "black_castled": "boolean",
        "legal_prefix_length": "integer",
        "has_bot_player": "boolean",
        "moves_uci": "varchar[]",
        "batch_id": "varchar",
    },
    "gold_player_monthly_stats": {
        "player": "varchar",
        "year": "integer",
        "month": "integer",
        "games_played": "integer",
        "wins": "integer",
        "losses": "integer",
        "draws": "integer",
        "win_rate": "double",
        "avg_elo": "double",
        "elo_change": "double",
        "most_played_opening_white": "varchar",
        "most_played_opening_black": "varchar",
    },
    "gold_opening_performance": {
        "eco_code": "varchar",
        "opening_family": "varchar",
        "elo_bucket": "varchar",
        "time_control_type": "varchar",
        "year": "integer",
        "games_count": "integer",
        "white_win_rate": "double",
        "black_win_rate": "double",
        "draw_rate": "double",
        "avg_game_length": "double",
        "most_common_response": "varchar",
    },
    "gold_time_pressure_analysis": {
        "time_remaining_bucket": "varchar",
        "game_phase": "varchar",
        "time_control_type": "varchar",
        "year": "integer",
        "games_count": "integer",
        "evaluated_positions": "bigint",
        "blunder_count": "bigint",
        "avg_cp_loss": "double",
        "blunder_rate": "double",
    },
    "gold_blunder_positions": {
        "game_id": "varchar",
        "ply_number": "integer",
        "fen": "varchar",
        "move_uci": "varchar",
        "square": "varchar",
        "game_phase": "varchar",
        "time_control_type": "varchar",
        "year": "integer",
        "player_elo": "integer",
        "time_remaining_seconds": "integer",
        "material_balance": "integer",
        "is_in_check": "boolean",
        "eval_before_cp": "integer",
        "eval_after_cp": "integer",
        "cp_loss": "integer",
        "is_blunder": "boolean",
    },
}

def _has_parquet(data_root: Path, pattern: str) -> bool:
    return any(data_root.glob(pattern))

def create_placeholder_view(conn: duckdb.DuckDBPyConnection, view_name: str) -> None:
    columns = PLACEHOLDER_COLUMNS[view_name]
    projection = ", ".join(f"cast(null as {data_type}) as {name}" for name, data_type in columns.items())
    conn.execute(f"create or replace view {view_name} as select {projection} where false")

def duckdb_string(value: Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"

def _view_columns(conn: duckdb.DuckDBPyConnection, view_name: str) -> set[str]:
    return {row[0] for row in conn.execute(f"describe {view_name}").fetchall()}

COMPATIBILITY_COLUMNS = {
    "gold_time_pressure_analysis": {
        "evaluated_positions": "cast(0 as bigint)",
        "blunder_count": "cast(0 as bigint)",
    },
    "gold_blunder_positions": {
        "year": "cast(null as integer)",
    },
}

def compatible_projection(conn: duckdb.DuckDBPyConnection, source_view: str, target_view: str) -> str:
    columns = _view_columns(conn, source_view)
    additions = COMPATIBILITY_COLUMNS.get(target_view, {})
    projection = ["*"] + [f"{expression} as {name}" for name, expression in additions.items() if name not in columns]
    return ", ".join(projection)

def register_parquet_views(conn: duckdb.DuckDBPyConnection, data_root: Path = DEFAULT_DATA_ROOT) -> list[str]:
    """Create views for available lake tables and placeholders for missing ones."""
    data_root = data_root.resolve()
    registered: list[str] = []
    for view_name, pattern in {**SILVER_TABLES, **GOLD_TABLES}.items():
        parquet_path = data_root / pattern
        if _has_parquet(data_root, pattern):
            parquet_scan = f"read_parquet({duckdb_string(parquet_path)}, hive_partitioning = true, union_by_name = true)"
            raw_view = f"_{view_name}_raw"
            conn.execute(f"create or replace temporary view {raw_view} as select * from {parquet_scan}")
            projection = compatible_projection(conn, raw_view, view_name)
            conn.execute(
                f"""
                create or replace view {view_name} as
                select {projection}
                from {parquet_scan}
                """
            )
            registered.append(view_name)
        else:
            create_placeholder_view(conn, view_name)
    return registered

def run_schema(conn: duckdb.DuckDBPyConnection) -> None:
    schema_path = ROOT / "warehouse" / "schema.sql"
    if schema_path.exists():
        conn.execute(schema_path.read_text(encoding="utf-8"))

def initialize(db_path: Path = DEFAULT_DB_PATH, data_root: Path = DEFAULT_DATA_ROOT) -> list[str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(db_path)) as conn:
        registered = register_parquet_views(conn, data_root=data_root)
        run_schema(conn)
    return registered

def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize DuckDB views for KnightVision lake data.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    args = parser.parse_args()

    registered = initialize(args.db_path, data_root=args.data_root)
    if registered:
        print(f"Registered views: {', '.join(sorted(registered))}")
    else:
        print("No Parquet files found yet; placeholder views were created.")
    print(f"DuckDB database: {args.db_path}")
    print(f"Lake data root: {args.data_root}")

if __name__ == "__main__":
    main()