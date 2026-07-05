"""Parallel historical backfill DAG for KnightVision."""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.models.param import Param
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="knightvision_backfill_pipeline",
    description="Parallel historical backfill: runs up to max_parallel_months concurrently, writes per-month status JSON.",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["knightvision", "backfill", "lichess"],
    params={
        "start_month": Param("2024-01", type="string", description="First month to backfill (YYYY-MM)."),
        "end_month": Param("2024-03", type="string", description="Last month to backfill (YYYY-MM), inclusive."),
        "max_parallel_months": Param(3, type="integer", description="Maximum months processed concurrently."),
    },
    default_args={
        "owner": "knightvision",
        "retries": 1,
        "retry_delay": timedelta(minutes=15),
    },
) as dag:
    run_backfill = BashOperator(
        task_id="run_backfill_months",
        execution_timeout=timedelta(hours=72),
        bash_command=r"""
set -euo pipefail
python - <<'PY'
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

start  = "{{ dag_run.conf.get('start_month',        params.start_month) }}"
end    = "{{ dag_run.conf.get('end_month',           params.end_month) }}"
max_par = int("{{ dag_run.conf.get('max_parallel_months', params.max_parallel_months) }}")

STATUS_DIR = pathlib.Path("data/backfill_status")
STATUS_DIR.mkdir(parents=True, exist_ok=True)


def parse_month(value: str) -> date:
    year, month = value.split("-")
    return date(int(year), int(month), 1)


def next_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def month_range(start: str, end: str) -> list[str]:
    months = []
    current = parse_month(start)
    last = parse_month(end)
    while current <= last:
        months.append(current.strftime("%Y-%m"))
        current = next_month(current)
    return months


def run_month(month: str) -> dict:
    status_path = STATUS_DIR / f"{month}.json"
    started_at = datetime.utcnow().isoformat()
    print(f"[backfill] starting {month}", flush=True)
    try:
        result = subprocess.run(
            ["make", "pipeline", f"MONTH={month}"],
            capture_output=True,
            text=True,
            check=True,
        )
        status = {
            "month": month,
            "status": "success",
            "started_at": started_at,
            "finished_at": datetime.utcnow().isoformat(),
        }
        print(f"[backfill] {month} succeeded", flush=True)
    except subprocess.CalledProcessError as exc:
        status = {
            "month": month,
            "status": "failed",
            "started_at": started_at,
            "finished_at": datetime.utcnow().isoformat(),
            "error": exc.stderr[-2000:] if exc.stderr else str(exc),
        }
        print(f"[backfill] {month} FAILED: {exc}", flush=True, file=sys.stderr)
    status_path.write_text(json.dumps(status, indent=2))
    return status


months = month_range(start, end)
print(f"[backfill] {len(months)} months from {start} to {end}, max_parallel={max_par}", flush=True)

failed = []
with ThreadPoolExecutor(max_workers=max_par) as pool:
    futures = {pool.submit(run_month, m): m for m in months}
    for future in as_completed(futures):
        result = future.result()
        if result["status"] != "success":
            failed.append(result["month"])

if failed:
    print(f"[backfill] FAILED months: {failed}", flush=True, file=sys.stderr)
    sys.exit(1)

print(f"[backfill] all {len(months)} months completed successfully", flush=True)
PY
""",
    )
