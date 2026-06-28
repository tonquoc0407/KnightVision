# SparkSession factory for local and standalone KnightVision jobs

from __future__ import annotations

import os


def build_spark(app_name: str = "KnightVision", *, master: str | None = None):
    from pyspark.sql import SparkSession

    os.environ.setdefault("SPARK_LOCAL_HOSTNAME", "localhost")
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    builder = SparkSession.builder.appName(app_name)
    if master:
        builder = builder.master(master)
    return (
        builder.config("spark.driver.memory", "8g")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.sql.shuffle.partitions", "32")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .getOrCreate()
    )