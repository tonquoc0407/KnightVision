import os

import pytest

# PySpark 3.x (Hadoop 3.3.x) is incompatible with Java 21+: Subject.getSubject was
# removed in Java 21. Force Java 17 (Temurin) when available so PySpark starts its
# JVM subprocess with a compatible runtime.
_JAVA17 = "/usr/lib/jvm/java-17-temurin-jdk"
if os.path.isdir(_JAVA17):
    os.environ["JAVA_HOME"] = _JAVA17


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