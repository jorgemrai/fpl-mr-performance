.PHONY: install ingest export test test-web dev build sql

FORCE ?=
HISTORY ?=
INGEST_FLAGS := $(if $(FORCE),--force) $(if $(HISTORY),--history)

install:
	uv sync
	cd web && npm ci

ingest:
	uv run python -m pipeline.ingest $(INGEST_FLAGS)

export:
	uv run python -m pipeline.export

test:
	uv run pytest -q

test-web:
	cd web && npm test

dev:
	cd web && npm run dev

build:
	cd web && npm run build

# Exploración ad-hoc de snapshots con DuckDB
sql:
	uv run python -c "import duckdb; print(duckdb.sql(\"SELECT gw, count(*) n FROM read_parquet('data/snapshots/gw*.parquet', filename=true) GROUP BY gw ORDER BY gw\"))"
