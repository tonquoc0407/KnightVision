# Helper for loading ECO reference data.
from __future__ import annotations


def load_eco_reference(spark, path: str):
    return spark.read.option("header", True).csv(path)