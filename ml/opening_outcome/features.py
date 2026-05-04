# Feature extraction for opening outcome prediction

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

TARGET_COLUMN = "result"
RESULT_LABELS = ["white_win", "black_win", "draw"]

PRE_GAME_NUMERIC_FEATURES = [
    "white_elo",
    "black_elo",
    "elo_diff",
    "abs_elo_diff",
    "base_time_seconds",
    "increment_seconds",
    "year",
    "month",
]
PRE_GAME_CATEGORICAL_FEATURES = [
    "eco_code",
    "opening_family",
    "opening_variation",
    "time_control_type",
]
POST_GAME_NUMERIC_FEATURES = [
    *PRE_GAME_NUMERIC_FEATURES,
    "game_length",
    "has_clock_data",
    "has_capture",
    "capture_count",
    "white_castled",
    "black_castled",
    "legal_prefix_length",
]
POST_GAME_CATEGORICAL_FEATURES = PRE_GAME_CATEGORICAL_FEATURES

FEATURE_SETS = {
    "pre_game": {
        "numeric": PRE_GAME_NUMERIC_FEATURES,
        "categorical": PRE_GAME_CATEGORICAL_FEATURES,
    },
    "post_game": {
        "numeric": POST_GAME_NUMERIC_FEATURES,
        "categorical": POST_GAME_CATEGORICAL_FEATURES,
    },
}

FEATURE_QUERY = """
select
    cast(result as varchar) as result,
    cast(white_elo as double) as white_elo,
    cast(black_elo as double) as black_elo,
    cast(white_elo - black_elo as double) as elo_diff,
    cast(abs(white_elo - black_elo) as double) as abs_elo_diff,
    cast(base_time_seconds as double) as base_time_seconds,
    cast(increment_seconds as double) as increment_seconds,
    cast(year as double) as year,
    cast(month as double) as month,
    cast(eco_code as varchar) as eco_code,
    cast(opening_family as varchar) as opening_family,
    cast(opening_variation as varchar) as opening_variation,
    cast(time_control_type as varchar) as time_control_type,
    cast(game_length as double) as game_length,
    cast(has_clock_data as integer) as has_clock_data,
    cast(has_capture as integer) as has_capture,
    cast(capture_count as double) as capture_count,
    cast(white_castled as integer) as white_castled,
    cast(black_castled as integer) as black_castled,
    cast(legal_prefix_length as double) as legal_prefix_length
from silver_games
where result in ('white_win', 'black_win', 'draw')
  and white_elo is not null
  and black_elo is not null
"""

def load_training_frame(duckdb_path: str | Path) -> pd.DataFrame:
    """Load model-ready game rows from the KnightVision DuckDB warehouse."""

    with duckdb.connect(str(duckdb_path), read_only=True) as conn:
        return conn.execute(FEATURE_QUERY).df()

def feature_columns(feature_set: str) -> list[str]:
    """Return ordered feature columns for a supported feature set."""

    if feature_set not in FEATURE_SETS:
        raise ValueError(f"unknown feature set: {feature_set}")
    spec = FEATURE_SETS[feature_set]
    return [*spec["numeric"], *spec["categorical"]]

def split_features_target(frame: pd.DataFrame, *, feature_set: str) -> tuple[pd.DataFrame, pd.Series]:
    """Return X/y after validating expected training columns."""

    columns = feature_columns(feature_set)
    missing = [column for column in [TARGET_COLUMN, *columns] if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required training columns: {', '.join(missing)}")

    clean = frame.dropna(subset=[TARGET_COLUMN]).copy()
    clean = clean[clean[TARGET_COLUMN].isin(RESULT_LABELS)]
    if clean.empty:
        raise ValueError("training frame contains no labeled outcome rows")

    return clean[columns], clean[TARGET_COLUMN].astype(str)