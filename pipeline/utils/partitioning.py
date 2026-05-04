# Partitioning helper for pipeline 
from __future__ import annotations


def month_partition_path(base_path: str, year: int, month: int) -> str:
    return f"{base_path.rstrip('/')}/year={year}/month={month}"