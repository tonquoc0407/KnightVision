# Shared Streamlit layout helpers

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.db import db_path, warehouse_ready


def configure_page(title: str) -> None:
    st.set_page_config(page_title=f"KnightVision | {title}", layout="wide")
    st.markdown(
        """
        <style>
        :root {
            --kv-bg: #111713;
            --kv-panel: #182118;
            --kv-panel-soft: #202b20;
            --kv-border: rgba(224, 190, 116, 0.22);
            --kv-text: #f3ead5;
            --kv-muted: #b8aa8a;
            --kv-green: #769656;
            --kv-green-dark: #4f6f39;
            --kv-light-square: #f0d9b5;
            --kv-gold: #d6a84f;
            --kv-red: #bf5a45;
            --kv-blue: #6a9fb5;
        }
        html, body, [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at top left, rgba(214, 168, 79, 0.11), transparent 32rem),
                linear-gradient(135deg, #111713 0%, #172015 52%, #101510 100%);
            color: var(--kv-text);
        }
        [data-testid="stHeader"] {
            background: transparent;
        }
        [data-testid="stSidebar"] {
            background: #101610;
            border-right: 1px solid var(--kv-border);
        }
        [data-testid="stSidebar"] * {
            color: var(--kv-text);
        }
        .block-container {
            padding-top: 1.25rem;
            padding-bottom: 2.5rem;
            max-width: 1180px;
        }
        h1, h2, h3 {
            color: var(--kv-text);
            letter-spacing: 0;
        }
        p, label, span, div {
            color: inherit;
        }
        div[data-testid="stCaptionContainer"], .kv-muted {
            color: var(--kv-muted);
        }
        div[data-testid="stMetric"] {
            border: 1px solid var(--kv-border);
            border-radius: 8px;
            padding: 0.8rem 0.9rem;
            background: linear-gradient(180deg, rgba(32, 43, 32, 0.96), rgba(24, 33, 24, 0.96));
            box-shadow: 0 10px 24px rgba(0, 0, 0, 0.18);
        }
        div[data-testid="stMetric"] [data-testid="stMetricLabel"] p {
            color: var(--kv-muted);
        }
        div[data-testid="stMetricValue"] {
            color: var(--kv-light-square);
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--kv-border);
            border-radius: 8px;
            overflow: hidden;
        }
        .stAlert {
            border-radius: 8px;
            border-color: var(--kv-border);
        }
        .kv-hero {
            border: 1px solid var(--kv-border);
            border-radius: 8px;
            padding: 1.05rem 1.15rem;
            margin: 0 0 1rem;
            background:
                linear-gradient(90deg, rgba(118, 150, 86, 0.23), transparent 45%),
                repeating-linear-gradient(45deg, rgba(240, 217, 181, 0.035) 0 14px, rgba(118, 150, 86, 0.035) 14px 28px),
                var(--kv-panel);
        }
        .kv-hero h1 {
            margin: 0 0 0.25rem;
            font-size: 2.15rem;
            line-height: 1.1;
        }
        .kv-hero p {
            margin: 0;
            color: var(--kv-muted);
        }
        .kv-status {
            margin-top: 0.75rem;
            padding-top: 0.75rem;
            border-top: 1px solid var(--kv-border);
            color: var(--kv-muted);
            font-size: 0.9rem;
        }
        .kv-section {
            border: 1px solid var(--kv-border);
            border-radius: 8px;
            padding: 0.9rem 1rem 1rem;
            background: rgba(24, 33, 24, 0.72);
        }
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="base-input"] {
            background-color: rgba(16, 22, 16, 0.86);
            border-color: var(--kv-border);
        }
        button[kind="secondary"], button[kind="primary"] {
            border-radius: 8px;
            border-color: var(--kv-border);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def page_header(title: str, subtitle: str | None = None) -> None:
    status = "ready" if warehouse_ready() else "missing"
    st.markdown(
        f"""
        <div class="kv-hero">
          <h1>{title}</h1>
          <p>{subtitle or ""}</p>
          <div class="kv-status">
            <strong>Warehouse:</strong> {db_path()}<br/>
            Status: {status}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def format_int(value: object) -> str:
    if value is None or pd.isna(value):
        return "0"
    return f"{int(value):,}"

def format_float(value: object, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.{digits}f}"

def format_percent(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.1%}"

def metric_row(metrics: list[tuple[str, str]]) -> None:
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics, strict=True):
        col.metric(label, value)

def show_table(df: pd.DataFrame, *, height: int = 420) -> None:
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)