import os

import pytest

os.environ.setdefault("AIRFLOW_HOME", "/tmp/knightvision-airflow-test")

pytest.importorskip("airflow")
pytest.importorskip("pyspark")

from ingestion.schema import RAW_GAME_FIELDS  # noqa: E402
from pipeline.bronze.ingest import bronze_metrics  # noqa: E402


def test_monthly_dag_imports_with_expected_release_gates():
    from orchestration.dags.monthly_pipeline import dag

    task_ids = {task.task_id for task in dag.tasks}

    assert dag.dag_id == "knightvision_monthly_pipeline"
    assert "silver_quality_gate" in task_ids
    assert "init_warehouse" in task_ids
    assert "dbt_run" in task_ids
    assert "dbt_test" in task_ids
    assert "notify_telegram" in task_ids
    assert dag.get_task("init_warehouse") in dag.get_task("spark_gold_player_stats").downstream_list
    assert dag.get_task("init_warehouse") in dag.get_task("spark_gold_opening_perf").downstream_list
    assert dag.get_task("init_warehouse") in dag.get_task("spark_gold_time_pressure").downstream_list
    assert dag.get_task("dbt_run") in dag.get_task("init_warehouse").downstream_list
    assert dag.get_task("dbt_test") in dag.get_task("dbt_run").downstream_list
    assert dag.get_task("notify_telegram") in dag.get_task("dbt_test").downstream_list

def test_backfill_dag_imports():
    from orchestration.dags.backfill_pipeline import dag

    assert dag.dag_id == "knightvision_backfill_pipeline"
    assert {task.task_id for task in dag.tasks} == {"run_backfill_months"}

def test_bronze_metrics_report_dedupe_and_partition_counts(spark_session):
    rows = [
        ("g1", "alice", "bob", "1-0", "1500", "1450", "B20", "Opening", "300+0", "Normal", "2024.01.01", "12:00:00", "1. e4", None, None, "2024-01", "batch"),
        ("g1", "alice", "bob", "1-0", "1500", "1450", "B20", "Opening", "300+0", "Normal", "2024.01.01", "12:00:00", "1. e4", None, None, "2024-01", "batch"),
        (None, "carol", "dave", "0-1", "1500", "1450", "C20", "Opening", "300+0", "Normal", "2024.01.01", "12:00:00", "1. e4", None, None, "2024-01", "batch"),
    ]
    df = spark_session.createDataFrame(rows, ", ".join(f"{field} string" for field in RAW_GAME_FIELDS))
    bronze = df.dropna(subset=["game_id"]).dropDuplicates(["game_id"])

    metrics = bronze_metrics(df, bronze)

    assert metrics["input_count"] == 3
    assert metrics["missing_game_id"] == 1
    assert metrics["duplicate_game_ids"] == 1
    assert metrics["duplicate_rows_removed"] == 1
    assert metrics["output_count"] == 1
    assert metrics["partitions"] == [{"batch_id": "2024-01", "source": "batch", "count": 1}]