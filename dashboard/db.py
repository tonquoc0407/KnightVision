# DuckDB access helpers for the KnightVision dashboard

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "warehouse" / "knightvision.duckdb"
QUERY_DIR = ROOT / "warehouse" / "queries"


def db_path() -> Path:
    configured = os.getenv("KNIGHTVISION_DUCKDB_PATH")
    return Path(configured).expanduser() if configured else DEFAULT_DB_PATH


@st.cache_resource
def get_connection(path: str) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(path, read_only=True)


def warehouse_ready() -> bool:
    return db_path().exists()


def read_query(name: str) -> str:
    return (QUERY_DIR / name).read_text(encoding="utf-8")


def run_query(sql: str, params: list[Any] | None = None) -> pd.DataFrame:
    if not warehouse_ready():
        st.warning(f"DuckDB warehouse not found: {db_path()}")
        return pd.DataFrame()
    try:
        return get_connection(str(db_path())).execute(sql, params or []).df()
    except duckdb.Error as exc:
        st.warning(f"Query unavailable: {exc}")
        return pd.DataFrame()


def run_named_query(name: str, params: list[Any] | None = None) -> pd.DataFrame:
    return run_query(read_query(name), params)
