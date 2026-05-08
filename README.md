# KnightVision

KnightVision is a chess analytics data platform over the Lichess public database. It is organized as a portfolio-grade data engineering project: monthly dump ingestion, PySpark medallion processing, DuckDB/dbt analytics, Airflow orchestration, custom dashboarding, and ML case studies.

The original web-app direction is intentionally out of scope. This repository is focused on backend, data engineering, and analytics work.

## Architecture

```mermaid
flowchart LR
    L[Lichess .pgn.zst dumps] --> P[Streaming PGN parser]
    P --> A[Landing Parquet]
    A --> B[Bronze: dedupe and raw metadata]
    B --> S[Silver: clean chess features]
    S --> G[Gold aggregations]
    S --> E[Stockfish sampled evaluations]
    E --> G
    G --> W[DuckDB warehouse]
    S --> W
    W --> D[dbt marts and tests]
    D --> U[Custom React dashboard]
    W --> M[ML case studies]
    G --> M
    D --> O[Airflow release gates]
```

Airflow coordinates the monthly workflow:

```mermaid
sequenceDiagram
    participant Sensor as Lichess sensor
    participant Raw as Downloader
    participant Parser as PGN parser
    participant Spark as PySpark jobs
    participant Quality as Silver quality gate
    participant DuckDB as DuckDB init
    participant Dbt as dbt
    participant Notify as Telegram notify

    Sensor->>Raw: monthly dump is available
    Raw->>Parser: rated .pgn.zst file
    Parser->>Spark: landing Parquet
    Spark->>Quality: Bronze and Silver outputs
    Quality->>Spark: approved for Gold
    Spark->>DuckDB: Gold Parquet outputs
    DuckDB->>Dbt: registered lake views
    Dbt->>Notify: run and test status
```

## Repository Layout

```text
ingestion/              # Downloader, PGN parser, optional Kafka producer
pipeline/               # PySpark Bronze/Silver/Gold jobs and quality checks
warehouse/              # DuckDB initialization, schema, dashboard queries
analytics/dbt/          # dbt-duckdb project
orchestration/          # Airflow DAGs, sensor plugin, Airflow compose file
dashboard_api/          # FastAPI backend for the custom local dashboard
dashboard_web/          # React/Vite dashboard frontend
dashboard/              # Legacy Streamlit dashboard fallback
notebooks/              # EDA, feature engineering, ML exploration
models/                 # Saved model artifacts
data/                   # Local raw/lake/warehouse artifacts, ignored by git
docs/                   # Operational and portfolio documentation
tests/                  # Unit and integration tests
```

## Feature Overview

See [docs/FEATURES.md](docs/FEATURES.md) for the full list of implemented platform, analytics, dashboard, Stockfish, orchestration, and ML features. See [docs/MODEL_CARDS.md](docs/MODEL_CARDS.md) for model-card summaries of the three ML case studies.

## Local Setup

Prerequisites:

- Python 3.10 or 3.11
- `uv`
- Node.js and npm for the custom React dashboard
- Java 11+ for Spark
- Docker with Docker Compose for Airflow
- Enough disk space for selected Lichess monthly dumps (about 30-100GB for the full rated dump, smaller for bounded benchmarks)
- Optional: a UCI-compatible Stockfish binary for blunder analytics

Install dependencies:

```bash
make setup
```

Optional local overrides live in [.env.example](.env.example). Copy it to `.env` only if you want to centralize values like `KNIGHTVISION_DUCKDB_PATH`, `STOCKFISH_PATH`, or Telegram settings; the normal `make` targets work without it.

Run the local demo pipeline and dbt checks:

```bash
make demo
```

This parses `fixtures/sample_lichess.pgn`, builds the Bronze/Silver/Gold lake under `data/sample`, initializes `warehouse/knightvision_sample.duckdb`, and runs dbt against that sample warehouse.

Run a real monthly flow (! CAUTION WITH LARGE MONTHLY DUMPS !):

```bash
make pipeline MONTH=2024-01
```

Run individual stages:

```bash
make download MONTH=2024-01
make parse MONTH=2024-01
make bronze MONTH=2024-01
make silver MONTH=2024-01
make quality MONTH=2024-01
make gold MONTH=2024-01
make warehouse
make dbt-run
make dbt-test
```

Initialize the DuckDB warehouse:

```bash
make warehouse
```

Run the dashboard on the main warehouse:

```bash
make dashboard
```

The custom dashboard opens at `http://localhost:3636`. It starts a React/Vite frontend on port `3636` and a FastAPI dashboard API on port `3637`.

The dashboard includes Overview, Evidence, Openings, Players, Blunders, Time Pressure, ML Lab, and Quality tabs. Use the warehouse selector in the sidebar to switch between the main, sample, real sample, and benchmark DuckDB files when they exist locally.

Run the dashboard on the deterministic sample warehouse:

```bash
make dashboard-sample
```

The Makefile wraps the longer `uv`, Python 3.11, Spark environment cleanup, `PYTHONPATH`, dashboard ports, and DuckDB path commands. If you need to override them, use variables such as `PYTHON=python`, `DUCKDB_PATH=warehouse/knightvision_benchmark.duckdb`, `DASHBOARD_PORT=3636`, or `MONTH=2026-04`.

The old Streamlit dashboard is still available as a fallback:

```bash
make dashboard-streamlit
```

## Airflow

Start the local Airflow stack:

```bash
make airflow-up
```

The Airflow UI is available at `http://localhost:8080`.

Default local credentials:

- Username: `airflow`
- Password: `airflow`

Useful commands:

```bash
make airflow-logs
make airflow-down
make airflow-smoke
make airflow-notify-test
```

The monthly DAG is `knightvision_monthly_pipeline`. It runs on the 5th of each month at 12:00 UTC and defaults to processing the previous month. For manual runs, pass a `month` value such as:

```json
{"month": "2024-01"}
```

For a tiny Airflow runtime smoke test without downloading a full monthly archive, compress the fixture to the filename the DAG expects, then run task tests with execution date `2024-02-05` so the DAG resolves the batch month as `2024-01`:

```bash
mkdir -p data/raw
zstd -f fixtures/sample_lichess.pgn -o data/raw/lichess_db_standard_rated_2024-01.pgn.zst
make airflow-up
docker compose --env-file .env -f orchestration/docker-compose.airflow.yml exec airflow-scheduler airflow tasks test knightvision_monthly_pipeline parse_to_bronze_parquet 2024-02-05
```

Then run the downstream task IDs in order: `spark_bronze_ingest`, `spark_silver_transform`, `silver_quality_gate`, `spark_gold_player_stats`, `spark_gold_opening_perf`, `spark_gold_time_pressure`, `init_warehouse`, `dbt_run`, and `dbt_test`.

The same proof is wrapped by:

```bash
make airflow-smoke
```

The DAG notification task is disabled by default because the DAG param `notify` defaults to `false`. To test Telegram delivery explicitly after setting `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`, run:

```bash
make airflow-up
make airflow-notify-test
make airflow-down
```

The backfill DAG is `knightvision_backfill_pipeline`. It accepts:

```json
{"start_month": "2024-01", "end_month": "2024-03"}
```

## Data Quality

Silver quality gates are documented in [docs/DATA_QUALITY.md](docs/DATA_QUALITY.md). The minimum operational checks are:

- Silver row count is at least 95% of Bronze row count.
- `game_id`, `white`, `black`, and normalized `result` are non-null.
- Elo values, when present, are in the 400-3500 range.
- Bronze/Silver partitions fail when empty unless `--allow-empty` is passed.
- Required Silver columns and duplicate `game_id` values are checked.
- Parser, Bronze, and Silver diagnostics are written under `data/quality/<month>/` for normal runs.
- Sample diagnostics are written under `data/sample/quality/`.
- dbt tests enforce mart-level uniqueness, accepted values, and relationship checks.

## Current Analytical Scope

Implemented analytics cover parsed Lichess games, Bronze deduplication, Silver normalization/enrichment, opening performance, player monthly stats, clock-based time-pressure buckets, and Stockfish-backed blunder-position generation. When Stockfish rows are present, time-pressure output also includes evaluated position counts, blunder counts, average centipawn loss, and blunder rate by bucket.

Blunder analytics require an external UCI-compatible Stockfish binary and a bounded sampling run. Use `make blunders STOCKFISH_PATH=/path/to/stockfish` for the main lake, or `make sample-blunders STOCKFISH_PATH=/path/to/stockfish` after `make sample-pipeline`. See [docs/STOCKFISH_BLUNDER_ANALYTICS.md](docs/STOCKFISH_BLUNDER_ANALYTICS.md).

The benchmark proof includes a 1,000-game Stockfish sample from the 100 MB monthly prefix. It produced 19,739 evaluated positions and 623 standard 200cp blunders.

Machine learning case studies are documented in [docs/MACHINE_LEARNING.md](docs/MACHINE_LEARNING.md). The current ML layer includes:

- Blunder Prediction Under Time Pressure.
- Opening Outcome Prediction.
- Player Style Clustering.

## Portfolio Metrics

Latest deterministic fixture proof:

| Metric | Value |
|---|---:|
| Fixture month | 2024-01 |
| Fixture games | 3 |
| Bronze rows | 3 |
| Silver rows | 3 |
| Silver retention | 100% |
| Gold player monthly rows | 6 |
| Gold opening rows | 3 |
| Gold time-pressure rows | 3 |
| dbt models built | 12 |
| dbt tests passed | 7 |
| Dashboard query rows | opening 3, player profile 1, time pressure 3 |
| Runtime | Not formally benchmarked |

Latest real Lichess API proof:

| Metric | Value |
|---|---:|
| Source | Lichess public API PGN export for `DrNykterstein` |
| Raw PGN file | `data/raw/real_sample/lichess_user_DrNykterstein_20.pgn` |
| Raw PGN size | 56,033 bytes |
| Raw PGN games | 20 |
| Landing rows | 20 |
| Bronze rows | 20 |
| Silver rows | 20 |
| Silver retention | 100% |
| Gold player monthly rows | 7 |
| Gold opening rows | 18 |
| Gold time-pressure rows | 14 |
| dbt models built | 12 |
| dbt tests passed | 7 |
| Dashboard query rows | opening 10, player profile 3, time pressure 14, blunder 0 |
| Warm parser runtime | 0.47s |
| Spark/dbt stage runtime sum | about 70s |
| Machine | AMD Ryzen 5 6600H, 6 cores / 12 threads, 14 GiB RAM, Java 17 |

Real API proof command source:

```bash
curl -L -H 'Accept: application/x-chess-pgn' \
  'https://lichess.org/api/games/user/DrNykterstein?max=20&clocks=true&opening=true&evals=false' \
  -o data/raw/real_sample/lichess_user_DrNykterstein_20.pgn
```

The real API proof is still small. A bounded real monthly `.pgn.zst` benchmark now exists on a 100 MB prefix of the April 2026 standard archive, but a full uninterrupted monthly dump run is still unmeasured.

| Monthly prefix benchmark | Value |
|---|---:|
| Source | `lichess_db_standard_rated_2026-04.pgn.zst` 100 MB prefix |
| Raw games parsed | 322,789 |
| Bronze rows | 322,789 |
| Silver rows | 322,164 |
| Silver retention | 99.81% |
| Parser runtime | 15.98s |
| Bronze runtime | 14.30s |
| Silver runtime | 257.85s |
| Silver quality runtime | 9.21s |
| dbt run runtime | 5.36s |
| dbt test runtime | 3.26s |
| Gold runtimes | player 9.77s, opening 7.76s, time pressure 7.37s |
| Benchmark warehouse views | silver 322,164, player stats 141,946, opening 9,069, time pressure 56 |

## Development

Release guardrails are documented in [docs/RELEASE_GUARDRAILS.md](docs/RELEASE_GUARDRAILS.md). The CI workflow in `.github/workflows/release-guardrails.yml` runs lint, pytest, the deterministic sample pipeline, and dbt parse/run/test against the sample DuckDB warehouse.

Run checks:

```bash
make lint
make test
```

Generate dbt lineage docs:

```bash
KNIGHTVISION_DUCKDB_PATH=../../warehouse/knightvision_sample.duckdb make dbt-docs
```

Format code:

```bash
make format
```

Generated data under `data/`, dbt artifacts, local virtual environments, and Airflow runtime volumes are ignored by git.
