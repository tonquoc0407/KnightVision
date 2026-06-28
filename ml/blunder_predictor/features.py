# Feature extraction for the Stockfish blunder predictor

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

TARGET_COLUMN = "is_blunder"
NUMERIC_FEATURES = [
    "player_elo",
    "time_remaining_seconds",
    "ply_number",
    "material_balance",
    "is_in_check",
    "year",
]
CATEGORICAL_FEATURES = ["game_phase", "time_control_type", "square"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES

FEATURE_QUERY = """
select
    cast(is_blunder as integer) as is_blunder,
    cast(player_elo as double) as player_elo,
    cast(time_remaining_seconds as double) as time_remaining_seconds,
    cast(ply_number as double) as ply_number,
    cast(material_balance as double) as material_balance,
    cast(is_in_check as integer) as is_in_check,
    cast(year as double) as year,
    cast(game_phase as varchar) as game_phase,
    cast(time_control_type as varchar) as time_control_type,
    cast(square as varchar) as square
from analytics.blunder_positions
where is_blunder is not null
  and cp_loss is not null
"""

def load_training_frame(duckdb_path: str | Path) -> pd.DataFrame:
    """Load model-ready rows from the KnightVision DuckDB warehouse."""

    with duckdb.connect(str(duckdb_path), read_only=True) as conn:
        return conn.execute(FEATURE_QUERY).df()

def split_features_target(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Return X/y after validating the expected training columns."""

    missing = [column for column in [TARGET_COLUMN, *FEATURE_COLUMNS] if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required training columns: {', '.join(missing)}")

    clean = frame.dropna(subset=[TARGET_COLUMN]).copy()
    if clean.empty:
        raise ValueError("training frame contains no labeled rows")

    clean[TARGET_COLUMN] = clean[TARGET_COLUMN].astype(int)
    return clean[FEATURE_COLUMNS], clean[TARGET_COLUMN]