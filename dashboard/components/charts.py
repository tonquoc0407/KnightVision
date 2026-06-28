# Plotly chart helpers for KnightVision dashboard pages

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

COLOR_SEQUENCE = ["#f0d9b5", "#769656", "#d6a84f", "#bf5a45", "#6a9fb5", "#9b7a42"]
PHASE_ORDER = ["opening", "middlegame", "endgame"]
TIME_BUCKET_ORDER = ["0-5s", "6-15s", "16-30s", "31-60s", "60s+"]
PLOT_LAYOUT = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(16,22,16,0.45)",
    "font": {"color": "#f3ead5"},
    "legend": {"font": {"color": "#f3ead5"}},
}

def show_empty(message: str = "No rows available for this view yet.") -> None:
    st.info(message)

def opening_outcome_chart(df: pd.DataFrame) -> None:
    if df.empty:
        show_empty()
        return
    chart_df = df.melt(
        id_vars=["eco_code", "opening_family"],
        value_vars=["white_win_rate", "black_win_rate", "draw_rate"],
        var_name="outcome",
        value_name="rate",
    )
    chart_df["outcome"] = chart_df["outcome"].map(
        {
            "white_win_rate": "White wins",
            "black_win_rate": "Black wins",
            "draw_rate": "Draws",
        }
    )
    fig = px.bar(
        chart_df,
        x="eco_code",
        y="rate",
        color="outcome",
        hover_data=["opening_family"],
        color_discrete_sequence=COLOR_SEQUENCE,
        barmode="stack",
    )
    fig.update_layout(
        **PLOT_LAYOUT,
        xaxis_title="ECO",
        yaxis_title="Result share",
        yaxis_tickformat=".0%",
        legend_title_text="",
        margin=dict(l=8, r=8, t=16, b=8),
    )
    st.plotly_chart(fig, use_container_width=True)

def player_elo_chart(df: pd.DataFrame) -> None:
    if df.empty:
        show_empty()
        return
    chart_df = df.assign(period=df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2))
    fig = px.line(
        chart_df,
        x="period",
        y="avg_elo",
        markers=True,
        hover_data=["games_played", "win_rate"],
        color_discrete_sequence=["#d6a84f"],
    )
    fig.update_traces(line=dict(width=3), marker=dict(size=8, color="#f0d9b5", line=dict(width=1, color="#d6a84f")))
    fig.update_layout(**PLOT_LAYOUT, xaxis_title="", yaxis_title="Average Elo", margin=dict(l=8, r=8, t=16, b=8))
    st.plotly_chart(fig, use_container_width=True)

def time_pressure_chart(df: pd.DataFrame, *, metric: str = "avg_cp_loss") -> None:
    if df.empty:
        show_empty()
        return
    chart_df = df.copy()
    chart_df["time_remaining_bucket"] = pd.Categorical(
        chart_df["time_remaining_bucket"],
        categories=TIME_BUCKET_ORDER,
        ordered=True,
    )
    chart_df["game_phase"] = pd.Categorical(chart_df["game_phase"], categories=PHASE_ORDER, ordered=True)
    chart_df = chart_df.sort_values(["time_remaining_bucket", "game_phase"])
    labels = {
        "games_count": "Clock positions",
        "avg_cp_loss": "Average cp loss",
        "evaluated_positions": "Evaluated positions",
        "blunder_rate": "Blunder rate",
    }
    if metric == "avg_cp_loss":
        fig = px.scatter(
            chart_df,
            x="time_remaining_bucket",
            y=metric,
            size="evaluated_positions" if "evaluated_positions" in chart_df else "games_count",
            color="game_phase",
            facet_col="time_control_type",
            color_discrete_sequence=COLOR_SEQUENCE,
        )
    else:
        fig = px.bar(
            chart_df,
            x="time_remaining_bucket",
            y=metric,
            color="game_phase",
            facet_col="time_control_type",
            color_discrete_sequence=COLOR_SEQUENCE,
            barmode="group",
        )
    fig.update_layout(
        **PLOT_LAYOUT,
        xaxis_title="Time remaining",
        yaxis_title=labels.get(metric, metric),
        legend_title_text="",
        margin=dict(l=8, r=8, t=24, b=8),
    )
    st.plotly_chart(fig, use_container_width=True)