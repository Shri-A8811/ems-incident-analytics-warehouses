# EMS Incident Analytics Warehouses

This repository contains three implementations built from FDNY EMS Incident Dispatch data:

1. `batch-warehouse/` — the traditional Dockerized PostgreSQL warehouse, with ETL, OLAP queries, and Power BI/browser dashboards.
2. `distributed-warehouse/` — a local Citus coordinator with two workers.
3. `realtime-warehouse/` — Kafka, Spark Structured Streaming, ClickHouse, and Grafana using a paced replay.

Each warehouse has separate code, run instructions, and documentation. The batch warehouse's raw/curated source files and local database files are intentionally excluded from Git because of their size. Follow `batch-warehouse/docs/dataset_source.md` and `batch-warehouse/README.md` to obtain and prepare the data locally. Credentials belong in a local `.env` file and must not be committed.
