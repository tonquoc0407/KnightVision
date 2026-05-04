from __future__ import annotations

import streamlit as st

from dashboard.components.charts import player_elo_chart
from dashboard.components.layout import (
    configure_page,
    format_float,
    format_int,
    format_percent,
    metric_row,
    page_header,
    show_table,
)
from dashboard.db import run_named_query, run_query

configure_page("Players")
page_header("Player Deep Dive", "Monthly player records from the Gold player profile table.")

players = run_query(
    """
    select
        player,
        sum(games_played) as games,
        round(avg(avg_elo), 1) as avg_elo,
        round(avg(win_rate), 4) as win_rate
    from analytics.player_profiles
    group by 1
    order by games desc, player
    """
)

if players.empty:
    st.info("No player rows available.")
    st.stop()

with st.sidebar:
    st.header("Player")
    selected_player = st.selectbox("Player", players["player"].tolist())

df = run_named_query("player_profile.sql", [selected_player])

if df.empty:
    st.info("No profile rows found for the selected player.")
else:
    metric_row(
        [
            ("Games", format_int(df["games_played"].sum())),
            ("Avg Elo", format_float(df["avg_elo"].mean(), digits=0)),
            ("Win Rate", format_percent(df["win_rate"].mean())),
            ("Months", format_int(len(df))),
        ]
    )
    st.subheader("Rating Trend")
    player_elo_chart(df)

    st.subheader("Monthly Rows")
    table = df.copy()
    table["win_rate"] = table["win_rate"].map(format_percent)
    table["avg_elo"] = table["avg_elo"].map(lambda value: format_float(value, digits=0))
    table["elo_change"] = table["elo_change"].map(lambda value: format_float(value, digits=0))
    show_table(table, height=300)

st.subheader("Player Comparison")
comparison = players.copy()
comparison["win_rate"] = comparison["win_rate"].map(format_percent)
comparison["avg_elo"] = comparison["avg_elo"].map(lambda value: format_float(value, digits=0))
show_table(comparison, height=300)