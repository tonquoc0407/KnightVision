SHELL := /bin/bash
MONTH ?= 2024-01
UV ?= uv
UV_CACHE_DIR ?= $(HOME)/.cache/uv
UV_PYTHON_INSTALL_DIR ?= $(HOME)/.local/share/uv/python
UV_LINK_MODE ?= copy
UV_RUN := UV_CACHE_DIR=$(UV_CACHE_DIR) UV_PYTHON_INSTALL_DIR=$(UV_PYTHON_INSTALL_DIR) UV_LINK_MODE=$(UV_LINK_MODE) $(UV) run --python 3.11
UV_RUN_DEV := UV_CACHE_DIR=$(UV_CACHE_DIR) UV_PYTHON_INSTALL_DIR=$(UV_PYTHON_INSTALL_DIR) UV_LINK_MODE=$(UV_LINK_MODE) $(UV) run --python 3.11 --extra dev
# PySpark 3.x is incompatible with Java 21+ (Subject.getSubject removed). Use Temurin 17 when present.
JAVA17 := /usr/lib/jvm/java-17-temurin-jdk
JAVA_HOME_OVERRIDE := $(if $(wildcard $(JAVA17)),JAVA_HOME=$(JAVA17),)
PYTHON ?= env -u SPARK_HOME -u PYSPARK_PYTHON -u PYSPARK_DRIVER_PYTHON $(JAVA_HOME_OVERRIDE) $(UV_RUN) python
DBT ?= $(UV_RUN) dbt
STREAMLIT ?= $(UV_RUN) streamlit
NPM ?= npm
DASHBOARD_HOST ?= 127.0.0.1
DASHBOARD_PORT ?= 3636
API_PORT ?= 3637
DBT_DIR ?= analytics/dbt
AIRFLOW_COMPOSE ?= orchestration/docker-compose.airflow.yml
AIRFLOW_ENV_FILE := $(if $(wildcard .env),--env-file .env,)
AIRFLOW_EXEC := docker compose $(AIRFLOW_ENV_FILE) -f $(AIRFLOW_COMPOSE) exec -T airflow-scheduler
AIRFLOW_SMOKE_MONTH ?= 2024-01
AIRFLOW_SMOKE_DATE ?= 2024-02-05
AIRFLOW_SMOKE_RAW ?= data/raw/lichess_db_standard_rated_$(AIRFLOW_SMOKE_MONTH).pgn.zst
RAW_DUMP ?= data/raw/lichess_db_standard_rated_$(MONTH).pgn.zst
LANDING_GAMES ?= data/landing/games/$(MONTH)
QUALITY_DIR ?= data/quality/$(MONTH)
SAMPLE_MONTH ?= 2024-01
SAMPLE_ROOT ?= data/sample
SAMPLE_PGN ?= fixtures/sample_lichess.pgn
SAMPLE_ECO ?= fixtures/eco_sample.csv
SAMPLE_DB ?= warehouse/knightvision_sample.duckdb
SAMPLE_QUALITY_DIR ?= $(SAMPLE_ROOT)/quality
QUARANTINE_DIR ?= data/quarantine/$(MONTH)
SAMPLE_QUARANTINE_DIR ?= $(SAMPLE_ROOT)/quarantine
DUCKDB_PATH ?= warehouse/knightvision.duckdb
STOCKFISH_PATH ?=
BLUNDER_FRACTION ?= 0.01
BLUNDER_MAX_GAMES ?= 1000
BLUNDER_MAX_PLIES ?= 80
BLUNDER_DEPTH ?= 12
BLUNDER_THRESHOLD_CP ?= 200
BLUNDER_INPUT ?= data/gold/blunder_positions
SAMPLE_BLUNDER_INPUT ?= $(SAMPLE_ROOT)/gold/blunder_positions
MODEL_DUCKDB ?= warehouse/knightvision_benchmark.duckdb
MODEL_OUTPUT_DIR ?= models/blunder_predictor
OPENING_MODEL_DUCKDB ?= warehouse/knightvision_benchmark.duckdb
OPENING_MODEL_OUTPUT_DIR ?= models/opening_outcome
PLAYER_STYLE_DUCKDB ?= warehouse/knightvision_benchmark.duckdb
PLAYER_STYLE_OUTPUT_DIR ?= models/player_style_clusters
PLAYER_STYLE_MIN_GAMES ?= 10
PLAYER_STYLE_CLUSTERS ?= 5

.PHONY: help setup install dashboard-install format lint test demo download parse bronze silver quality gold blunders sample-blunders train-blunder-model train-opening-outcome cluster-player-styles warehouse dbt-run dbt-test dbt-docs sample-dbt pipeline sample-pipeline dashboard dashboard-api dashboard-web dashboard-streamlit dashboard-sample airflow-up airflow-down airflow-logs airflow-smoke airflow-notify-test clean

help:
	@printf "KnightVision targets:\n"
	@printf "  make setup                Install Python 3.11 dependencies with uv\n"
	@printf "  make demo                 Run sample pipeline and sample dbt checks\n"
	@printf "  make dashboard            Open custom dashboard on localhost:3636\n"
	@printf "  make dashboard-sample     Open custom dashboard on the sample warehouse\n"
	@printf "  make test                 Run tests with Spark env isolation\n"
	@printf "  make download MONTH=YYYY-MM\n"
	@printf "  make parse MONTH=YYYY-MM\n"
	@printf "  make pipeline MONTH=YYYY-MM\n"
	@printf "  make sample-pipeline       Run deterministic fixture pipeline\n"
	@printf "  make blunders STOCKFISH_PATH=/path/to/stockfish\n"
	@printf "  make sample-blunders STOCKFISH_PATH=/path/to/stockfish\n"
	@printf "  make train-blunder-model Train XGBoost model from benchmark Stockfish rows\n"
	@printf "  make train-opening-outcome Train XGBoost opening outcome models\n"
	@printf "  make cluster-player-styles Train unsupervised player style clusters\n"
	@printf "  make warehouse            Refresh DuckDB views over lake Parquet\n"
	@printf "  make dbt-run && make dbt-test\n"
	@printf "  make dbt-docs              Generate dbt lineage docs\n"
	@printf "  make airflow-up           Start local Airflow on localhost:8080\n"
	@printf "  make airflow-smoke        Run tiny .pgn.zst Airflow runtime proof\n"
	@printf "  make airflow-notify-test  Send a Telegram smoke notification\n"

setup:
	UV_CACHE_DIR=$(UV_CACHE_DIR) UV_PYTHON_INSTALL_DIR=$(UV_PYTHON_INSTALL_DIR) UV_LINK_MODE=$(UV_LINK_MODE) $(UV) sync --python 3.11 --extra dev

install:
	$(MAKE) setup

dashboard-install:
	$(NPM) --prefix dashboard_web install

format:
	$(UV_RUN_DEV) ruff format .

lint:
	$(UV_RUN_DEV) ruff check .

test:
	env -u SPARK_HOME -u PYSPARK_PYTHON -u PYSPARK_DRIVER_PYTHON $(UV_RUN_DEV) python -m pytest -q

demo: sample-pipeline sample-dbt

download:
	$(PYTHON) -m ingestion.downloader --month $(MONTH) --output-dir data/raw

parse:
	$(PYTHON) -m ingestion.pgn_parser --input $(RAW_DUMP) --output $(LANDING_GAMES) --batch-id $(MONTH) --metrics-output $(QUALITY_DIR)/parser_metrics.json

bronze:
	$(PYTHON) -m pipeline.bronze.ingest --input $(LANDING_GAMES) --output data/bronze/games --metrics-output $(QUALITY_DIR)/bronze_metrics.json --quarantine-output $(QUARANTINE_DIR)/bronze

silver:
	$(PYTHON) -m pipeline.silver.transform --input data/bronze/games --output data/silver/games --quarantine-output $(QUARANTINE_DIR)/silver

quality:
	$(PYTHON) -m pipeline.silver.quality_checks --bronze-batch-id $(MONTH) --silver-month $(MONTH) --bronze data/bronze/games --silver data/silver/games --metrics-output $(QUALITY_DIR)/silver_metrics.json

gold:
	$(PYTHON) -m pipeline.gold.player_stats --input data/silver/games --output data/gold/player_monthly_stats
	$(PYTHON) -m pipeline.gold.opening_perf --input data/silver/games --output data/gold/opening_performance
	$(PYTHON) -m pipeline.gold.time_pressure --input data/silver/games --output data/gold/time_pressure_analysis --blunder-input $(BLUNDER_INPUT)

blunders:
	@test -n "$(STOCKFISH_PATH)" || (printf "Set STOCKFISH_PATH=/path/to/stockfish\n" && exit 1)
	$(PYTHON) -m pipeline.gold.blunder_positions --input data/silver/games --output data/gold/blunder_positions --stockfish-path $(STOCKFISH_PATH) --fraction $(BLUNDER_FRACTION) --max-games $(BLUNDER_MAX_GAMES) --max-plies $(BLUNDER_MAX_PLIES) --depth $(BLUNDER_DEPTH) --blunder-threshold-cp $(BLUNDER_THRESHOLD_CP)
	$(PYTHON) -m pipeline.gold.time_pressure --input data/silver/games --output data/gold/time_pressure_analysis --blunder-input $(BLUNDER_INPUT)

dbt-run:
	cd $(DBT_DIR) && $(DBT) run --profiles-dir .

dbt-test:
	cd $(DBT_DIR) && $(DBT) test --profiles-dir .

dbt-docs:
	cd $(DBT_DIR) && $(DBT) docs generate --profiles-dir .

sample-dbt:
	cd $(DBT_DIR) && KNIGHTVISION_DUCKDB_PATH=../../$(SAMPLE_DB) $(DBT) run --profiles-dir .
	cd $(DBT_DIR) && KNIGHTVISION_DUCKDB_PATH=../../$(SAMPLE_DB) $(DBT) test --profiles-dir .

pipeline: download parse bronze silver quality gold warehouse dbt-run dbt-test

sample-pipeline:
	$(PYTHON) -m ingestion.pgn_parser --input $(SAMPLE_PGN) --output $(SAMPLE_ROOT)/landing/games --batch-id $(SAMPLE_MONTH) --metrics-output $(SAMPLE_QUALITY_DIR)/parser_metrics.json
	$(PYTHON) -m pipeline.bronze.ingest --input $(SAMPLE_ROOT)/landing/games --output $(SAMPLE_ROOT)/bronze/games --metrics-output $(SAMPLE_QUALITY_DIR)/bronze_metrics.json --quarantine-output $(SAMPLE_QUARANTINE_DIR)/bronze
	$(PYTHON) -m pipeline.silver.transform --input $(SAMPLE_ROOT)/bronze/games --output $(SAMPLE_ROOT)/silver/games --eco-reference $(SAMPLE_ECO) --drop-corrupt-pgn --quarantine-output $(SAMPLE_QUARANTINE_DIR)/silver
	$(PYTHON) -m pipeline.silver.quality_checks --bronze-batch-id $(SAMPLE_MONTH) --silver-month $(SAMPLE_MONTH) --bronze $(SAMPLE_ROOT)/bronze/games --silver $(SAMPLE_ROOT)/silver/games --metrics-output $(SAMPLE_QUALITY_DIR)/silver_quality.json
	$(PYTHON) -m pipeline.gold.player_stats --input $(SAMPLE_ROOT)/silver/games --output $(SAMPLE_ROOT)/gold/player_monthly_stats
	$(PYTHON) -m pipeline.gold.opening_perf --input $(SAMPLE_ROOT)/silver/games --output $(SAMPLE_ROOT)/gold/opening_performance
	$(PYTHON) -m pipeline.gold.time_pressure --input $(SAMPLE_ROOT)/silver/games --output $(SAMPLE_ROOT)/gold/time_pressure_analysis --blunder-input $(SAMPLE_BLUNDER_INPUT)
	$(PYTHON) warehouse/init_db.py --data-root $(SAMPLE_ROOT) --db-path $(SAMPLE_DB)

sample-blunders:
	@test -n "$(STOCKFISH_PATH)" || (printf "Set STOCKFISH_PATH=/path/to/stockfish\n" && exit 1)
	$(PYTHON) -m pipeline.gold.blunder_positions --input $(SAMPLE_ROOT)/silver/games --output $(SAMPLE_ROOT)/gold/blunder_positions --stockfish-path $(STOCKFISH_PATH) --fraction 1.0 --max-games 3 --max-plies 20 --depth 8 --blunder-threshold-cp $(BLUNDER_THRESHOLD_CP)
	$(PYTHON) -m pipeline.gold.time_pressure --input $(SAMPLE_ROOT)/silver/games --output $(SAMPLE_ROOT)/gold/time_pressure_analysis --blunder-input $(SAMPLE_BLUNDER_INPUT)
	$(PYTHON) warehouse/init_db.py --data-root $(SAMPLE_ROOT) --db-path $(SAMPLE_DB)

train-blunder-model:
	$(PYTHON) -m ml.blunder_predictor.train --duckdb-path $(MODEL_DUCKDB) --output-dir $(MODEL_OUTPUT_DIR)

train-opening-outcome:
	$(PYTHON) -m ml.opening_outcome.train --duckdb-path $(OPENING_MODEL_DUCKDB) --output-dir $(OPENING_MODEL_OUTPUT_DIR)

cluster-player-styles:
	$(PYTHON) -m ml.player_style_clustering.train --duckdb-path $(PLAYER_STYLE_DUCKDB) --output-dir $(PLAYER_STYLE_OUTPUT_DIR) --min-games $(PLAYER_STYLE_MIN_GAMES) --clusters $(PLAYER_STYLE_CLUSTERS)

warehouse:
	$(PYTHON) warehouse/init_db.py

dashboard:
	@test -d dashboard_web/node_modules || (printf "Installing dashboard frontend dependencies...\n" && $(MAKE) dashboard-install)
	KNIGHTVISION_DUCKDB_PATH=$(DUCKDB_PATH) DASHBOARD_HOST=$(DASHBOARD_HOST) DASHBOARD_PORT=$(DASHBOARD_PORT) API_PORT=$(API_PORT) PYTHONPATH=. $(PYTHON) -m dashboard_api.dev

dashboard-sample:
	$(MAKE) dashboard DUCKDB_PATH=$(SAMPLE_DB)

dashboard-api:
	KNIGHTVISION_DUCKDB_PATH=$(DUCKDB_PATH) PYTHONPATH=. $(UV_RUN) uvicorn dashboard_api.app:app --host $(DASHBOARD_HOST) --port $(API_PORT) --reload

dashboard-web:
	$(NPM) --prefix dashboard_web run dev -- --host $(DASHBOARD_HOST) --port $(DASHBOARD_PORT)

dashboard-streamlit:
	KNIGHTVISION_DUCKDB_PATH=$(DUCKDB_PATH) PYTHONPATH=. $(STREAMLIT) run dashboard/app.py

airflow-up:
	docker compose $(AIRFLOW_ENV_FILE) -f $(AIRFLOW_COMPOSE) up -d

airflow-down:
	docker compose $(AIRFLOW_ENV_FILE) -f $(AIRFLOW_COMPOSE) down

airflow-logs:
	docker compose $(AIRFLOW_ENV_FILE) -f $(AIRFLOW_COMPOSE) logs -f airflow-scheduler airflow-webserver

airflow-smoke:
	@set -e; \
	trap '$(MAKE) airflow-down' EXIT; \
	mkdir -p data/raw; \
	zstd -f $(SAMPLE_PGN) -o $(AIRFLOW_SMOKE_RAW); \
	$(MAKE) airflow-up; \
	for task in \
		parse_to_bronze_parquet \
		spark_bronze_ingest \
		spark_silver_transform \
		silver_quality_gate \
		spark_gold_player_stats \
		spark_gold_opening_perf \
		spark_gold_time_pressure \
		init_warehouse \
		dbt_run \
		dbt_test \
		notify_telegram; do \
		printf "\n==> Airflow smoke task: %s\n" "$$task"; \
		$(AIRFLOW_EXEC) airflow tasks test knightvision_monthly_pipeline "$$task" $(AIRFLOW_SMOKE_DATE); \
	done

airflow-notify-test:
	$(AIRFLOW_EXEC) python -m orchestration.notify --month smoke --status success --details "Airflow Telegram notification test"

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
