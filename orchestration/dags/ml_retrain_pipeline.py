"""ML model retraining DAG for KnightVision."""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.models.param import Param
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator

DEFAULT_ARGS = {
    "owner": "knightvision",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=15),
}

PROJECT_ROOT = "/opt/airflow/project"
PROJECT_PREFIX = f"cd {PROJECT_ROOT} && PYTHONPATH={PROJECT_ROOT} "
DEFAULT_DUCKDB_PATH = "warehouse/knightvision.duckdb"
DEFAULT_MODELS_DIR = "models"

with DAG(
    dag_id="knightvision_ml_retrain_pipeline",
    description="Monthly ML model retraining: blunder predictor, opening outcome, and player style clustering.",
    start_date=pendulum.datetime(2024, 1, 5, 12, 0, tz="UTC"),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["knightvision", "ml", "training"],
    params={
        "duckdb_path": Param(DEFAULT_DUCKDB_PATH, type="string", description="DuckDB warehouse path."),
        "output_dir": Param(DEFAULT_MODELS_DIR, type="string", description="Root directory for trained model artifacts."),
        "notify": Param(False, type="boolean"),
    },
) as dag:
    start = EmptyOperator(task_id="start")

    train_blunder_model = BashOperator(
        task_id="train_blunder_model",
        bash_command=(
            PROJECT_PREFIX
            + "python -m ml.blunder_predictor.train "
            "--duckdb-path {{ params.duckdb_path }} "
            "--output-dir {{ params.output_dir }}/blunder_predictor"
        ),
        execution_timeout=timedelta(minutes=30),
    )

    train_opening_model = BashOperator(
        task_id="train_opening_model",
        bash_command=(
            PROJECT_PREFIX
            + "python -m ml.opening_outcome.train "
            "--duckdb-path {{ params.duckdb_path }} "
            "--output-dir {{ params.output_dir }}/opening_outcome"
        ),
        execution_timeout=timedelta(minutes=30),
    )

    train_player_clusters = BashOperator(
        task_id="train_player_clusters",
        bash_command=(
            PROJECT_PREFIX
            + "python -m ml.player_style_clustering.train "
            "--duckdb-path {{ params.duckdb_path }} "
            "--output-dir {{ params.output_dir }}/player_style_clustering"
        ),
        execution_timeout=timedelta(minutes=30),
    )

    publish_metrics = BashOperator(
        task_id="publish_metrics",
        bash_command=(
            PROJECT_PREFIX
            + r"""MODELS_OUTPUT_DIR="{{ params.output_dir }}" python - <<'PYEOF'
import json, os, pathlib, datetime

models_dir = pathlib.Path(os.environ["MODELS_OUTPUT_DIR"])
names = ["blunder_predictor", "opening_outcome", "player_style_clustering"]
summary = {
    "retrained_at": datetime.datetime.utcnow().isoformat(),
    "artifacts": {
        name: sorted(p.name for p in (models_dir / name).glob("*") if not p.name.startswith("."))
        if (models_dir / name).exists() else []
        for name in names
    },
}
out = pathlib.Path("data/quality/ml_retrain_metrics.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
PYEOF
"""
        ),
    )

    notify_telegram = BashOperator(
        task_id="notify_telegram",
        bash_command=(
            "if [ '{{ params.notify }}' = 'True' ]; then "
            + PROJECT_PREFIX
            + "python -m orchestration.notify "
            "--month {{ macros.ds_format(ds, '%Y-%m-%d', '%Y-%m') }} "
            "--status ml_retrain_success; "
            "else echo 'Telegram notification disabled'; fi"
        ),
        trigger_rule="all_done",
    )

    finish = EmptyOperator(task_id="finish")

    (
        start
        >> train_blunder_model
        >> train_opening_model
        >> train_player_clusters
        >> publish_metrics
        >> notify_telegram
        >> finish
    )
