# Schemas used by the raw Lichess ingestion layer

from __future__ import annotations

RAW_GAME_FIELDS = [
    "game_id",
    "white",
    "black",
    "result",
    "white_elo",
    "black_elo",
    "eco",
    "opening",
    "time_control",
    "termination",
    "utc_date",
    "utc_time",
    "moves",
    "clock_annotations",
    "ingested_at",
    "batch_id",
    "source",
]

def pyarrow_schema():
    # Return the raw game schema as a PyArrow schema.

    # PyArrow is imported lazily so parser unit tests can run without the full
    # ingestion dependency set installed.
    
    import pyarrow as pa

    return pa.schema(
        [
            ("game_id", pa.string()),
            ("white", pa.string()),
            ("black", pa.string()),
            ("result", pa.string()),
            ("white_elo", pa.string()),
            ("black_elo", pa.string()),
            ("eco", pa.string()),
            ("opening", pa.string()),
            ("time_control", pa.string()),
            ("termination", pa.string()),
            ("utc_date", pa.string()),
            ("utc_time", pa.string()),
            ("moves", pa.string()),
            ("clock_annotations", pa.string()),
            ("ingested_at", pa.timestamp("us")),
            ("batch_id", pa.string()),
            ("source", pa.string()),
        ]
    )

def spark_raw_schema():
    

    from pyspark.sql import types as T

    return T.StructType(
        [
            T.StructField("game_id", T.StringType()),
            T.StructField("white", T.StringType()),
            T.StructField("black", T.StringType()),
            T.StructField("result", T.StringType()),
            T.StructField("white_elo", T.StringType()),
            T.StructField("black_elo", T.StringType()),
            T.StructField("eco", T.StringType()),
            T.StructField("opening", T.StringType()),
            T.StructField("time_control", T.StringType()),
            T.StructField("termination", T.StringType()),
            T.StructField("utc_date", T.StringType()),
            T.StructField("utc_time", T.StringType()),
            T.StructField("moves", T.StringType()),
            T.StructField("clock_annotations", T.StringType()),
            T.StructField("ingested_at", T.TimestampType()),
            T.StructField("batch_id", T.StringType()),
            T.StructField("source", T.StringType()),
        ]
    )