from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.models.param import Param
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator

try:
    from lichess_sensor import LichessDumpSensor
except ImportError:  # Airflow loads plugins differently in some local test runners.
    from orchestration.plugins.lichess_sensor import LichessDumpSensor

DEFAULT_ARGS = {
    "owner": "knightvision",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}

BATCH_MONTH = "{{ params.month or dag_run.conf.get('month') or macros.ds_format(macros.ds_add(ds, -5), '%Y-%m-%d', '%Y-%m') }}"
BATCH_RAW_DUMP = f"data/raw/lichess_db_standard_rated_{BATCH_MONTH}.pgn.zst"
BATCH_LANDING_DIR = f"data/landing/games/{BATCH_MONTH}"
BATCH_QUALITY_DIR = f"data/quality/{BATCH_MONTH}"

with DAG(
    dag_id="knightvision_monthly_pipeline",
    description="Monthly Lichess dump ingestion, Spark transforms, dbt marts, and quality gates.",
    start_date=pendulum.datetime(2024, 1, 5, 12, 0, tz="UTC"),
    schedule="0 12 5 * *",
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["knightvision", "lichess", "spark", "dbt"],
    params={
        "month": Param("", type="string", description="Override month in YYYY-MM format for manual runs."),
        "source": Param("batch", enum=["batch", "stream"]),
        "notify": Param(False, type="boolean"),
    },
) as dag:
    start = EmptyOperator(task_id="start")

    lichess_dump_sensor = LichessDumpSensor(
        task_id="lichess_dump_sensor",
        month=BATCH_MONTH,
        poke_interval=60 * 30,
        timeout=60 * 60 * 12,
        mode="reschedule",
    )

    download_dump = BashOperator(
        task_id="download_dump",
        bash_command=(
            "python -m ingestion.downloader "
            f"--month {BATCH_MONTH} "
            "--output-dir data/raw"
        ),
    )

    parse_to_bronze_parquet = BashOperator(
        task_id="parse_to_bronze_parquet",
        bash_command=(
            "python -m ingestion.pgn_parser "
            f"--input {BATCH_RAW_DUMP} "
            f"--output {BATCH_LANDING_DIR} "
            f"--batch-id {BATCH_MONTH} "
            "--source {{ params.source }} "
            f"--metrics-output {BATCH_QUALITY_DIR}/parser_metrics.json"
        ),
        execution_timeout=timedelta(hours=8),
    )

    spark_bronze_ingest = BashOperator(
        task_id="spark_bronze_ingest",
        bash_command=(
            "python -m pipeline.bronze.ingest "
            f"--input {BATCH_LANDING_DIR} "
            "--output data/bronze/games "
            f"--metrics-output {BATCH_QUALITY_DIR}/bronze_metrics.json"
        ),
        execution_timeout=timedelta(hours=4),
    )

    spark_silver_transform = BashOperator(
        task_id="spark_silver_transform",
        bash_command=(
            "python -m pipeline.silver.transform "
            "--input data/bronze/games "
            "--output data/silver/games"
        ),
        execution_timeout=timedelta(hours=6),
    )

    silver_quality_gate = BashOperator(
        task_id="silver_quality_gate",
        bash_command=(
            "python -m pipeline.silver.quality_checks "
            f"--bronze-batch-id {BATCH_MONTH} "
            f"--silver-month {BATCH_MONTH} "
            "--bronze data/bronze/games "
            "--silver data/silver/games "
            f"--metrics-output {BATCH_QUALITY_DIR}/silver_metrics.json"
        ),
    )

    spark_gold_player_stats = BashOperator(
        task_id="spark_gold_player_stats",
        bash_command=(
            "python -m pipeline.gold.player_stats "
            "--input data/silver/games "
            "--output data/gold/player_monthly_stats"
        ),
        execution_timeout=timedelta(hours=3),
    )

    spark_gold_opening_perf = BashOperator(
        task_id="spark_gold_opening_perf",
        bash_command=(
            "python -m pipeline.gold.opening_perf "
            "--input data/silver/games "
            "--output data/gold/opening_performance"
        ),
        execution_timeout=timedelta(hours=3),
    )

    spark_gold_time_pressure = BashOperator(
        task_id="spark_gold_time_pressure",
        bash_command=(
            "python -m pipeline.gold.time_pressure "
            "--input data/silver/games "
            "--output data/gold/time_pressure_analysis"
        ),
        execution_timeout=timedelta(hours=3),
    )

    init_warehouse = BashOperator(
        task_id="init_warehouse",
        bash_command="python warehouse/init_db.py",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd analytics/dbt && dbt run --profiles-dir .",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd analytics/dbt && dbt test --profiles-dir .",
    )

    notify_telegram = BashOperator(
        task_id="notify_telegram",
        bash_command=(
            "if [ '{{ params.notify }}' = 'True' ]; then "
            "python -m orchestration.notify "
            f"--month {BATCH_MONTH} "
            "--status success; "
            "else echo 'Telegram notification disabled'; fi"
        ),
        trigger_rule="all_done",
    )

    finish = EmptyOperator(task_id="finish")

    start >> lichess_dump_sensor >> download_dump >> parse_to_bronze_parquet
    parse_to_bronze_parquet >> spark_bronze_ingest >> spark_silver_transform >> silver_quality_gate
    silver_quality_gate >> [spark_gold_player_stats, spark_gold_opening_perf, spark_gold_time_pressure]
    [spark_gold_player_stats, spark_gold_opening_perf, spark_gold_time_pressure] >> init_warehouse >> dbt_run >> dbt_test
    dbt_test >> notify_telegram >> finish
