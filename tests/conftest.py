import os

import pytest


@pytest.fixture(scope="session")
def spark_session():
    pyspark = pytest.importorskip("pyspark")
    os.environ.setdefault("SPARK_LOCAL_HOSTNAME", "localhost")
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    spark = (
        pyspark.sql.SparkSession.builder.master("local[1]")
        .appName("KnightVisionTests")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .getOrCreate()
    )
    yield spark
    spark.stop()