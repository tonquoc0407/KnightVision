# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

KnightVision is a chess analytics data platform over Lichess public database dumps. It is a data engineering portfolio project: monthly dump ingestion → PySpark medallion pipeline → DuckDB/dbt analytics → Airflow orchestration → custom React dashboard + ML case studies.

## Prerequisites

- Python 3.10 or 3.11 (3.11 preferred; the Makefile pins to it via `uv`)
- `uv` for Python dependency management
- Node.js and npm for the React dashboard frontend
- Java 11+ for PySpark
- Docker with Docker Compose for Airflow
- Optional: a UCI-compatible Stockfish binary for blunder analytics

## Common Commands

All day-to-day operations go through `make`. The Makefile wraps `uv`, Spark environment isolation (`env -u SPARK_HOME -u PYSPARK_PYTHON`), `PYTHONPATH=.`, and DuckDB path wiring.

```bash
make setup              # Install Python 3.11 deps with uv (includes dev extras)
make lint               # ruff check .
make format             # ruff format .
make test               # pytest with Spark env isolation
make demo               # Full sample pipeline end-to-end (fixtures → DuckDB → dbt)

# Run a single test file
env -u SPARK_HOME -u PYSPARK_PYTHON -u PYSPARK_DRIVER_PYTHON uv run --python 3.11 --extra dev python -m pytest tests/test_silver_transform.py -q

make dashboard          # React+FastAPI dashboard at localhost:3636 / localhost:3637
make dashboard-sample   # Same dashboard against the sample warehouse
make dashboard-streamlit  # Legacy Streamlit fallback
```

## Full Pipeline

```bash
make pipeline MONTH=2024-01   # Download → parse → bronze → silver → quality → gold → warehouse → dbt
```

Individual stages (each is a separate PySpark or Python job):

```bash
make download MONTH=2024-01
make parse MONTH=2024-01
make bronze MONTH=2024-01     # also writes quarantine to data/quarantine/<MONTH>/bronze
make silver MONTH=2024-01     # also writes quarantine to data/quarantine/<MONTH>/silver
make quality MONTH=2024-01
make gold MONTH=2024-01
make warehouse            # init_db.py — must run before dbt
make dbt-run && make dbt-test
```

Blunders (requires Stockfish):

```bash
make blunders STOCKFISH_PATH=/path/to/stockfish
make sample-blunders STOCKFISH_PATH=/path/to/stockfish   # bounded run on fixtures
```

ML models (read from `warehouse/knightvision_benchmark.duckdb`):

```bash
make train-blunder-model
make train-opening-outcome
make cluster-player-styles
```

## Architecture

### Data Flow

```
Lichess .pgn.zst → PGN parser → Landing Parquet
                              → Bronze (PySpark dedup)   → quarantine (null game_id)
                              → Silver (PySpark enrichment) → quarantine (null required cols)
                              → Gold aggregations (PySpark)
                              → DuckDB warehouse (init_db.py)
                              → dbt marts
                              → FastAPI + React dashboard / ML models
```

### Medallion Pipeline (`pipeline/`)

- `ingestion/pgn_parser.py` — Streaming parser that reads `.pgn.zst` dumps (zstandard) and writes Landing Parquet batches using pyarrow directly (no Spark). Emits `parser_metrics.json`.
- `pipeline/bronze/ingest.py` — PySpark job: deduplicates by `game_id`, drops rows missing required fields, writes hive-partitioned Parquet. `build_bronze_rejected()` captures null-`game_id` rows; `--quarantine-output` persists them with a `reject_reason` column.
- `pipeline/silver/transform.py` — PySpark job: enriches with ECO codes, normalizes results/terminations, extracts clock seconds, computes game features. UDFs live in `pipeline/silver/udfs.py`. `transform_silver(..., return_quarantine=True)` returns a `(silver, quarantine)` tuple; `--quarantine-output` persists rejected rows (`reject_reason = "null_required_column"`).
- `pipeline/silver/quality_checks.py` — Gate: Silver row count ≥ 95% of Bronze, non-null required columns, Elo in 400-3500, no duplicate `game_id`.
- `pipeline/gold/` — Four independent PySpark jobs: `player_stats.py`, `opening_perf.py`, `time_pressure.py`, `blunder_positions.py` (Stockfish-backed).
- `pipeline/spark_session.py` — Shared `build_spark()` factory; always uses `driver.host=127.0.0.1` to avoid hostname resolution issues.

### Quarantine Layer

Rejected rows are persisted as Parquet for replay/investigation, not just counted:

- Bronze quarantine: rows with null `game_id` → `data/quarantine/<MONTH>/bronze/` (sample: `data/sample/quarantine/bronze/`)
- Silver quarantine: rows failing the required-column check (`game_id`, `white`, `black`, `result`, `year`, `month`) → `data/quarantine/<MONTH>/silver/`
- Quarantine Parquet is only written when there are actual rejected rows (no empty directories)
- `quarantine_count` and `quarantine_path` are included in `bronze_metrics.json` and the silver `run()` return dict
- Makefile vars: `QUARANTINE_DIR` (default `data/quarantine/$(MONTH)`), `SAMPLE_QUARANTINE_DIR`

### Warehouse (`warehouse/`)

- `warehouse/init_db.py` — Registers Parquet lake tables as DuckDB views (via `read_parquet` with `hive_partitioning=true`), then executes `warehouse/schema.sql` to create `analytics.*` views. **Must run before dbt.** Falls back to empty placeholder views when Parquet is absent so dbt can still parse.
- `warehouse/schema.sql` — Creates the `analytics` schema with views over the raw lake tables.
- `warehouse/queries/` — Named SQL files loaded by the FastAPI backend via `Warehouse.named_records()`.

### Analytics (`analytics/dbt/`)

dbt-duckdb project. The DuckDB path comes from `KNIGHTVISION_DUCKDB_PATH` env var (default `warehouse/knightvision.duckdb`). Run from `analytics/dbt/` with `--profiles-dir .`.

Layer order: `staging/` → `intermediate/` → `dimensions/` → `marts/`. Materialization: staging/intermediate as views, dimensions/marts as tables.

### Dashboard

The primary dashboard is a React + FastAPI combo:
- `dashboard_api/app.py` — FastAPI app, `create_app()` factory pattern. All query logic is in top-level payload functions (testable without a live server). Reads DuckDB via `dashboard_api/db.py` `Warehouse` class.
- `dashboard_web/` — Vite/React frontend, proxies to `localhost:3637`.
- `dashboard_api/dev.py` — Starts both processes together for `make dashboard`.

Dashboard UI features:
- 8 tabs: Overview, Evidence, Openings, Players, Blunders, Time Pressure, ML Lab, Quality
- ML Lab tab has a `BlunderPredictor` form at the top — submits to `POST /api/ml/predict/blunder` and shows blunder probability from the loaded XGBoost model. The backend loads `models/blunder_predictor/model.json` + `preprocessing.joblib` lazily on first request and caches them. Returns `{"blunder_probability": float, "is_blunder": bool}` or `{"error": str}` when model files are absent.
- `DataTable` accepts an optional `downloadName` prop → renders an "Export CSV" button (`downloadCSV()` in `main.jsx` handles escaping + blob download). Wired on Openings, Players, player profile, Blunders, Time Pressure, and Quality tables.
- `LineChart` (custom SVG) renders the per-player Elo progression with Y-axis tick labels; viewBox is extended left (−48) to make room for the labels.
- Sidebar "Year" dropdown (populated from `/api/years`) filters Openings, Players, Blunders, and Time Pressure tabs via a `year` query param.
- Players tab has a search input (`search` param → case-insensitive `ILIKE` substring match on player name).
- Named SQL queries use the `(? is null or col = ?)` pattern for optional filters — each optional param is passed twice in the param list.

The legacy Streamlit dashboard (`dashboard/`) is still functional as a fallback.

### Orchestration (`orchestration/`)

- `orchestration/dags/monthly_pipeline.py` — Airflow DAG `knightvision_monthly_pipeline`, scheduled 5th of each month at 12:00 UTC. Task order: sensor → download → parse → bronze → silver → quality gate → (gold jobs in parallel) → warehouse init → dbt run → dbt test → [trigger_ml_retrain, notify].
- `orchestration/dags/ml_retrain_pipeline.py` — Airflow DAG `knightvision_ml_retrain_pipeline`. Triggered by `monthly_pipeline` after `dbt_test` via `TriggerDagRunOperator`. Task order: `train_blunder_model` → `train_opening_model` → `train_player_clusters` → `publish_metrics` → `notify_telegram`. Can also be run manually with custom `duckdb_path` and `output_dir` params. Writes `data/quality/ml_retrain_metrics.json` on completion.
- `orchestration/dags/backfill_pipeline.py` — Accepts `start_month`/`end_month` params.
- `orchestration/docker-compose.airflow.yml` — Custom Airflow stack with project bind-mount at `/opt/airflow/project`.
- Airflow smoke test: compress fixture to the expected filename, then test tasks individually with execution date `2024-02-05` (resolves batch month to `2024-01`).

### ML (`ml/`)

Three case studies, each with a `features.py` (DuckDB → pandas) and `train.py` (train → write to `models/`):
- `ml/blunder_predictor/` — Binary XGBoost classifier (is this a 200cp blunder?). Reads `gold_blunder_positions`.
- `ml/opening_outcome/` — Multiclass XGBoost (win/draw/loss from opening features). Reads `gold_opening_performance`.
- `ml/player_style_clustering/` — KMeans clustering. Reads `gold_player_monthly_stats`.

All three read from `warehouse/knightvision_benchmark.duckdb` by default.

## Environment Variables

Copy `.env.example` to `.env` for local overrides. Key variables:

| Variable | Default | Purpose |
|---|---|---|
| `KNIGHTVISION_DUCKDB_PATH` | `warehouse/knightvision.duckdb` | DuckDB path for dbt and dashboard |
| `STOCKFISH_PATH` | _(empty)_ | Required for blunder analytics |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | _(empty)_ | Airflow DAG notification |
| `AIRFLOW_UID` | `50000` | Container user mapping for rootless Podman |

The `.env` file is optional — all `make` targets work without it.

## Testing

Tests live in `tests/`. Spark tests use a shared `spark_session` fixture (`conftest.py`) scoped to the session.

```bash
make test   # env -u SPARK_HOME ... uv run --python 3.11 --extra dev python -m pytest -q
```

For CI-equivalent checks: `make lint && make test && make demo`.

The `test_orchestration_guardrails.py` test imports both DAG modules and asserts required task IDs (`silver_quality_gate`, `init_warehouse`, `dbt_run`, `dbt_test`, `notify_telegram`) are present.

Quarantine behavior is covered by `test_build_bronze_rejected_captures_null_game_id_rows` (tests/test_quality_checks.py) and `test_transform_silver_quarantines_rows_with_null_required_columns` (tests/test_silver_transform.py).

## Release Guardrails

CI runs: `make lint` → `make test` → `make demo` (fixture pipeline + dbt against sample warehouse). The sample warehouse is `warehouse/knightvision_sample.duckdb`; the benchmark warehouse is `warehouse/knightvision_benchmark.duckdb`.

Quality JSON artifacts are written under `data/quality/<YYYY-MM>/` for real runs and `data/sample/quality/` for fixture runs. The dashboard Evidence tab surfaces these as proof points.

## Data Conventions

- Hive partitioning: Gold Parquet is written as `year=YYYY/month=M/` partitions.
- `batch_id` is the `YYYY-MM` string carried from parser through Bronze.
- Silver retention gate: ≥ 95% of Bronze rows must survive. Failures are non-zero exit.
- `game_id`, `white`, `black`, `result` are required non-null in Silver.
- Quarantined rows carry a `reject_reason` column (`null_game_id` for Bronze, `null_required_column` for Silver).
- dbt custom tests: `assert_elo_range.sql`, `assert_no_null_game_id.sql` in `analytics/dbt/tests/`.

## Feature Roadmap Status

Prioritized feature plan (see `/home/tondaiquoc/.claude/plans/well-could-you-plan-greedy-puddle.md` for full details). Status as of 2026-06-11:

| # | Feature | Status |
|---|---------|--------|
| 9 | Elo progression chart Y-axis labels | ✅ Done |
| 3 | CSV export from dashboard tables | ✅ Done |
| 1 | Quarantine layer for rejected records | ✅ Done |
| 2 | Player search + year filtering | ✅ Done |
| 4 | ML model retraining DAG (Airflow) | ✅ Done |
| 5 | Online blunder inference API (`/api/ml/predict/blunder`) | ✅ Done |
| 6 | Statistical anomaly detection in quality checks | Planned |
| 7 | Backfill DAG parallelization (TaskGroup per month) | Planned |
| 8 | Opening recommendation engine | Planned |
| 10 | Code coverage + security scanning in CI | Planned |

Implementation notes for completed features live in the relevant sections above (Quarantine Layer, Dashboard).
