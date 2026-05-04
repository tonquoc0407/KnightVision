from __future__ import annotations

import streamlit as st

from dashboard.components.charts import opening_outcome_chart
from dashboard.components.layout import (
    configure_page,
    format_float,
    format_int,
    format_percent,
    metric_row,
    page_header,
    show_table,
)
from dashboard.db import run_named_query

configure_page("Openings")
page_header("Opening Explorer", "Opening performance by ECO, rating bucket, time control, and year.")

with st.sidebar:
    st.header("Filters")
    eco = st.text_input("ECO code", placeholder="B20")
    opening = st.text_input("Opening family", placeholder="Sicilian")
    limit = st.number_input("Rows", min_value=10, max_value=500, value=50, step=10)

df = run_named_query(
    "opening_stats.sql",
    [eco or None, eco or None, opening or None, opening or None, int(limit)],
)

metric_row(
    [
        ("Groups", format_int(len(df))),
        ("Games", format_int(df["games_count"].sum() if not df.empty else 0)),
        ("ECO codes", format_int(df["eco_code"].nunique() if not df.empty else 0)),
        ("Avg length", format_float(df["avg_game_length"].mean() if not df.empty else None)),
    ]
)

st.subheader("Outcome Mix")
opening_outcome_chart(df)

st.subheader("Opening Rows")
table = df.copy()
if not table.empty:
    table["white_win_rate"] = table["white_win_rate"].map(format_percent)
    table["black_win_rate"] = table["black_win_rate"].map(format_percent)
    table["draw_rate"] = table["draw_rate"].map(format_percent)
    table["avg_game_length"] = table["avg_game_length"].map(format_float)
show_table(table)