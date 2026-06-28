# Feature extraction for player style clustering

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

IDENTIFIER_COLUMNS = ["player", "games_played"]

FEATURE_COLUMNS = [
    "win_rate",
    "loss_rate",
    "draw_rate",
    "avg_elo",
    "elo_change_proxy",
    "avg_game_length",
    "avg_capture_count",
    "capture_game_rate",
    "castle_rate",
    "opening_diversity",
    "top_opening_share",
    "bullet_share",
    "blitz_share",
    "rapid_share",
    "classical_share",
    "clock_game_rate",
]

PLAYER_FEATURE_QUERY = """
with player_games as (
    select
        white as player,
        white_elo as elo,
        case when result = 'white_win' then 1.0 else 0.0 end as win,
        case when result = 'black_win' then 1.0 else 0.0 end as loss,
        case when result = 'draw' then 1.0 else 0.0 end as draw,
        eco_code,
        time_control_type,
        cast(game_length as double) as game_length,
        cast(capture_count as double) as capture_count,
        cast(has_capture as integer) as has_capture,
        cast(white_castled as integer) as castled,
        cast(has_clock_data as integer) as has_clock_data
    from silver_games
    where white is not null
      and result in ('white_win', 'black_win', 'draw')

    union all

    select
        black as player,
        black_elo as elo,
        case when result = 'black_win' then 1.0 else 0.0 end as win,
        case when result = 'white_win' then 1.0 else 0.0 end as loss,
        case when result = 'draw' then 1.0 else 0.0 end as draw,
        eco_code,
        time_control_type,
        cast(game_length as double) as game_length,
        cast(capture_count as double) as capture_count,
        cast(has_capture as integer) as has_capture,
        cast(black_castled as integer) as castled,
        cast(has_clock_data as integer) as has_clock_data
    from silver_games
    where black is not null
      and result in ('white_win', 'black_win', 'draw')
),
opening_counts as (
    select
        player,
        eco_code,
        count(*) as opening_games
    from player_games
    where eco_code is not null
    group by player, eco_code
),
opening_summary as (
    select
        player,
        count(*) as opening_diversity,
        max(opening_games) as top_opening_games
    from opening_counts
    group by player
)
select
    pg.player,
    count(*) as games_played,
    avg(win) as win_rate,
    avg(loss) as loss_rate,
    avg(draw) as draw_rate,
    avg(elo) as avg_elo,
    max(elo) - min(elo) as elo_change_proxy,
    avg(game_length) as avg_game_length,
    avg(capture_count) as avg_capture_count,
    avg(has_capture) as capture_game_rate,
    avg(castled) as castle_rate,
    coalesce(max(os.opening_diversity), 0) as opening_diversity,
    coalesce(max(os.top_opening_games), 0) / count(*) as top_opening_share,
    avg(case when time_control_type = 'bullet' then 1.0 else 0.0 end) as bullet_share,
    avg(case when time_control_type = 'blitz' then 1.0 else 0.0 end) as blitz_share,
    avg(case when time_control_type = 'rapid' then 1.0 else 0.0 end) as rapid_share,
    avg(case when time_control_type = 'classical' then 1.0 else 0.0 end) as classical_share,
    avg(has_clock_data) as clock_game_rate
from player_games pg
left join opening_summary os on pg.player = os.player
group by pg.player
having count(*) >= ?
"""

def load_player_features(duckdb_path: str | Path, *, min_games: int) -> pd.DataFrame:
    """Load one model-ready row per eligible player."""

    with duckdb.connect(str(duckdb_path), read_only=True) as conn:
        return conn.execute(PLAYER_FEATURE_QUERY, [min_games]).df()

def split_identifiers_features(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return identifier columns and clustering features after validation."""

    missing = [column for column in [*IDENTIFIER_COLUMNS, *FEATURE_COLUMNS] if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required clustering columns: {', '.join(missing)}")

    clean = frame.dropna(subset=["player"]).copy()
    if clean.empty:
        raise ValueError("player style feature frame is empty")

    return clean[IDENTIFIER_COLUMNS], clean[FEATURE_COLUMNS]