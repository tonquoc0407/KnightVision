from __future__ import annotations

import streamlit as st

from dashboard.components.charts import time_pressure_chart
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

configure_page("Time Pressure")
page_header("Time Pressure", "Clock buckets, game phases, and Stockfish quality metrics where available.")

df = run_named_query("time_pressure.sql")
if df.empty:
    st.info("No time-pressure rows available yet.")
else:
    with st.sidebar:
        st.header("Filters")
        controls = sorted(df["time_control_type"].dropna().unique().tolist())
        selected = st.multiselect("Time controls", controls, default=controls)
        metric = st.radio(
            "Chart metric",
            ["games_count", "avg_cp_loss", "evaluated_positions", "blunder_rate"],
            format_func={
                "games_count": "Clock positions",
                "avg_cp_loss": "Average cp loss",
                "evaluated_positions": "Evaluated positions",
                "blunder_rate": "Blunder rate",
            }.get,
        )

    filtered = df[df["time_control_type"].isin(selected)] if selected else df
    evaluated_positions = int(filtered["evaluated_positions"].fillna(0).sum()) if "evaluated_positions" in filtered else 0
    blunder_count = int(filtered["blunder_count"].fillna(0).sum()) if "blunder_count" in filtered else 0
    clock_positions = int(filtered["games_count"].fillna(0).sum()) if "games_count" in filtered else 0
    avg_cp_loss = filtered["avg_cp_loss"].dropna().mean() if "avg_cp_loss" in filtered else None
    blunder_rate = blunder_count / evaluated_positions if evaluated_positions else None
    metric_row(
        [
            ("Clock positions", format_int(clock_positions)),
            ("Evaluated positions", format_int(evaluated_positions)),
            ("200cp blunders", format_int(blunder_count)),
            ("Avg cp loss", format_float(avg_cp_loss)),
            ("Blunder rate", format_percent(blunder_rate)),
        ]
    )

    has_quality_metrics = "avg_cp_loss" in filtered.columns and filtered["avg_cp_loss"].notna().any()
    if metric != "games_count" and not has_quality_metrics:
        st.info("Clock bucket counts are available, but move-quality metrics require Stockfish evaluation.")
        metric = "games_count"

    st.subheader("Bucket View")
    time_pressure_chart(filtered, metric=metric)

    st.subheader("Rows")
    table = filtered.copy()
    if not table.empty:
        table["avg_cp_loss"] = table["avg_cp_loss"].map(format_float)
        table["blunder_rate"] = table["blunder_rate"].map(format_percent)
    show_table(table)