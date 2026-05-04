from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.models.param import Param
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="knightvision_backfill_pipeline",
    description="Sequential historical backfill wrapper around the monthly KnightVision pipeline.",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["knightvision", "backfill", "lichess"],
    params={
        "start_month": Param("2024-01", type="string"),
        "end_month": Param("2024-03", type="string"),
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

from datetime import date
import subprocess

start = "{{ dag_run.conf.get('start_month', params.start_month) }}"
end = "{{ dag_run.conf.get('end_month', params.end_month) }}"

def parse_month(value: str) -> date:
    year, month = value.split("-")
    return date(int(year), int(month), 1)

def next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)

current = parse_month(start)
last = parse_month(end)

while current <= last:
    month = current.strftime("%Y-%m")
    print(f"Running KnightVision backfill month {month}", flush=True)
    subprocess.run(["make", "pipeline", f"MONTH={month}"], check=True)
    current = next_month(current)
PY
""",
    )