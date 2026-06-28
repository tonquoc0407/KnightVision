"""Framework-neutral DuckDB access for the custom dashboard."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "warehouse" / "knightvision.duckdb"
QUERY_DIR = ROOT / "warehouse" / "queries"
WAREHOUSE_CHOICES = {
    "main": ROOT / "warehouse" / "knightvision.duckdb",
    "sample": ROOT / "warehouse" / "knightvision_sample.duckdb",
    "real_sample": ROOT / "warehouse" / "knightvision_real_sample.duckdb",
    "benchmark": ROOT / "warehouse" / "knightvision_benchmark.duckdb",
}


def db_path() -> Path:
    configured = os.getenv("KNIGHTVISION_DUCKDB_PATH")
    return Path(configured).expanduser() if configured else DEFAULT_DB_PATH


def db_path_for(key: str | None = None) -> Path:
    if key and key in WAREHOUSE_CHOICES:
        return WAREHOUSE_CHOICES[key]
    return db_path()


def read_query(name: str) -> str:
    return (QUERY_DIR / name).read_text(encoding="utf-8")


def _clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, float) and math.isfinite(value):
        return round(value, 6)
    return value


def frame_to_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        records.append({key: _clean_value(value) for key, value in row.items()})
    return records


class Warehouse:
    """Read-only helper around the active KnightVision DuckDB warehouse."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or db_path()

    @property
    def ready(self) -> bool:
        return self.path.exists()

    def query(self, sql: str, params: list[Any] | None = None) -> pd.DataFrame:
        if not self.ready:
            return pd.DataFrame()
        try:
            with duckdb.connect(str(self.path), read_only=True) as connection:
                return connection.execute(sql, params or []).df()
        except duckdb.Error:
            return pd.DataFrame()

    def records(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        return frame_to_records(self.query(sql, params))

    def named_records(self, name: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        return self.records(read_query(name), params)

    def scalar(self, sql: str, params: list[Any] | None = None, default: Any = None) -> Any:
        frame = self.query(sql, params)
        if frame.empty:
            return default
        return _clean_value(frame.iat[0, 0])
