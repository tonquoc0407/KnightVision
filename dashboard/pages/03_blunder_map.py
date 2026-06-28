from __future__ import annotations

import streamlit as st

from dashboard.components.chessboard import render_square_heatmap
from dashboard.components.layout import configure_page, format_float, format_int, metric_row, page_header, show_table
from dashboard.db import run_named_query

configure_page("Blunders")
page_header("Blunder Map", "Stockfish-evaluated position quality grouped by destination square.")

df = run_named_query("blunder_heatmap.sql")
has_evaluations = not df.empty and "evaluated_positions" in df.columns and df["evaluated_positions"].sum() > 0
has_blunders = has_evaluations and "blunders" in df.columns and df["blunders"].sum() > 0

if df.empty:
    st.info("No Stockfish-evaluated positions available yet.")
    st.stop()

if not has_evaluations:
    st.info("Blunder-position candidates exist, but cp-loss values are not available yet.")
    show_table(df)
    st.stop()

metric_row(
    [
        ("Evaluated positions", format_int(df["evaluated_positions"].sum())),
        ("200cp blunders", format_int(df["blunders"].sum())),
        ("Avg cp loss", format_float(df["avg_cp_loss"].mean())),
        ("Worst square cp loss", format_int(df["max_cp_loss"].max())),
    ]
)

if not has_blunders:
    st.info("The loaded sample has evaluated positions, but no move crosses the 200cp blunder threshold.")

left, right = st.columns([0.48, 0.52])
with left:
    value_col = st.radio(
        "Board value",
        ["avg_cp_loss", "evaluated_positions", "blunders"],
        format_func={
            "avg_cp_loss": "Average cp loss",
            "evaluated_positions": "Evaluated positions",
            "blunders": "200cp blunders",
        }.get,
        horizontal=True,
    )
    render_square_heatmap(df, value_col=value_col, value_label=value_col.replace("_", " "))

with right:
    st.subheader("Square Ranking")
    table = df.copy()
    table["avg_cp_loss"] = table["avg_cp_loss"].map(format_float)
    show_table(table)