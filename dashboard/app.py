from __future__ import annotations

import streamlit as st

from dashboard.components.charts import opening_outcome_chart, time_pressure_chart
from dashboard.components.layout import (
    configure_page,
    format_float,
    format_int,
    format_percent,
    metric_row,
    page_header,
    show_table,
)
from dashboard.db import run_named_query, run_query, warehouse_ready

configure_page("Overview")

page_header("KnightVision", "Lichess archive analytics from the local DuckDB warehouse.")

if not warehouse_ready():
    st.stop()

overview = run_query(
    """
    select
        (select coalesce(sum(games_count), 0) from analytics.opening_stats) as games,
        (select count(*) from analytics.player_profiles) as player_rows,
        (select count(*) from analytics.opening_stats) as opening_rows,
        (select coalesce(sum(games_count), 0) from analytics.time_pressure) as clock_positions,
        (select count(*) from analytics.blunder_positions) as evaluated_positions,
        (select coalesce(sum(case when is_blunder then 1 else 0 end), 0) from analytics.blunder_positions) as blunders
    """
)

row = overview.iloc[0] if not overview.empty else {}
metric_row(
    [
        ("Games", format_int(row.get("games"))),
        ("Player rows", format_int(row.get("player_rows"))),
        ("Opening groups", format_int(row.get("opening_rows"))),
        ("Clock positions", format_int(row.get("clock_positions"))),
        ("Stockfish positions", format_int(row.get("evaluated_positions"))),
        ("200cp blunders", format_int(row.get("blunders"))),
    ]
)

st.divider()

left, right = st.columns([0.55, 0.45])

opening_df = run_named_query("opening_stats.sql", [None, None, None, None, 12])
time_df = run_named_query("time_pressure.sql")

with left:
    st.subheader("Opening Outcomes")
    opening_outcome_chart(opening_df)

with right:
    st.subheader("Time Pressure")
    if time_df.empty:
        st.info("No clock rows available.")
    else:
        time_pressure_chart(time_df, metric="games_count")

st.subheader("Top Opening Groups")
summary = opening_df[
    [
        "eco_code",
        "opening_family",
        "time_control_type",
        "games_count",
        "white_win_rate",
        "black_win_rate",
        "draw_rate",
        "avg_game_length",
    ]
].copy()
if not summary.empty:
    summary["white_win_rate"] = summary["white_win_rate"].map(format_percent)
    summary["black_win_rate"] = summary["black_win_rate"].map(format_percent)
    summary["draw_rate"] = summary["draw_rate"].map(format_percent)
    summary["avg_game_length"] = summary["avg_game_length"].map(format_float)
show_table(summary)