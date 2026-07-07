# SparkSession factory for local and standalone KnightVision jobs

from __future__ import annotations

import os


def build_spark(app_name: str = "KnightVision", *, master: str | None = None):
    from pyspark.sql import SparkSession

    os.environ.setdefault("SPARK_LOCAL_HOSTNAME", "localhost")
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")

    # /tmp is often small (tmpfs quota). Use a project-local dir when SPARK_LOCAL_DIRS isn't set.
    if not os.environ.get("SPARK_LOCAL_DIRS"):
        local_tmp = os.path.join(os.getcwd(), "data", ".spark_tmp")
        os.makedirs(local_tmp, exist_ok=True)
        os.environ["SPARK_LOCAL_DIRS"] = local_tmp

    # Default to 5 cores: balanced for 14 GB RAM with Python UDF workloads.
    # Callers can override by passing master= explicitly.
    resolved_master = master or "local[5]"

    builder = SparkSession.builder.appName(app_name).master(resolved_master)
    return (
        builder
        .config("spark.driver.memory", "5g")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        # Fewer shuffle partitions → smaller per-partition buffers in RAM
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.sql.parquet.compression.codec", "snappy")
        # Spill to disk earlier when RAM is tight
        .config("spark.memory.fraction", "0.5")
        .config("spark.memory.storageFraction", "0.3")
        # Adaptive query execution: coalesces small shuffle partitions automatically
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        # Kyro serializer uses ~30% less memory than Java default
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .getOrCreate()
    )
