# EMS Dispatch Data Warehouse

This project implements the TY B.Tech Integrated Data Warehouse, OLAP and Data Mining assignment using the official FDNY EMS Incident Dispatch Data published through NYC Open Data.

## Current milestone

**Milestones 1–7 are complete.** Milestone 1 acquired and documented the source. Milestone 2 profiled and curated the data, reconciled row counts, and produced initial EDA tables and charts. Milestone 3 designed the dimensional model. Milestone 4 created a local SQLite prototype. Milestone 5 built the Dockerized PostgreSQL batch warehouse and loaded January 2024–May 2026 initially, then June 2026 incrementally. The nine raw CSV pages remain unchanged. Milestone 6 implemented and ran the required OLAP operations (roll-up, drill-down, slice, dice, pivot, CUBE, and GROUPING SETS). Milestone 7 created a browser dashboard, a Power BI report, and ten evidence-based findings from the warehouse. See `dashboards/index.html`, `dashboards/EMS_Dispatch_PowerBI_Dashboard.pbix`, `reports/dashboard_findings.md`, and `reports/dashboard_milestone7_status.md`. The eight dashboard summary CSVs are imported into the Power BI report.

## Project layout

```text
data/raw/       Original source CSV pages
data/curated/   Curated compressed CSV; raw pages are unchanged
docs/           Source documentation and data dictionary
notebooks/      Data quality, EDA and curation notebooks
sql/            PostgreSQL and SQLite warehouse table-creation SQL
etl/            Profiling, curation, verification and warehouse loader scripts
dashboards/     Browser dashboard, chart images, Power BI report and summary CSVs
models/         Warehouse model documentation
reports/        Reserved for project reports
```

## Reproducibility

Run `python etl/profile_raw_data.py` to recreate the profile tables and figures from the raw pages. Run `python etl/curate_dataset.py` to create the curated compressed CSV, and `python etl/verify_curated.py` to check the curated output and row-count reconciliation. The curated script will not overwrite an existing output. See `reports/data_quality_report.md` for every cleaning decision and `reports/eda_report.md` for the first findings.

To download a fresh source extract, run `./download_fdny_ems.ps1` from PowerShell. It will not overwrite existing raw files. See `docs/dataset_source.md` for source, scope and field notes. Python packages used for profiling and curation are listed in `requirements.txt`.

Start PostgreSQL with: docker compose --env-file .env up -d postgres. It listens at 127.0.0.1:5435, database ems_dw, user ems_admin. The password is in the local ignored .env file. The batch loader is etl/load_postgres_warehouse.py; its two completed loads are recorded in reports/postgres_warehouse_summary.json. For a borough/hour roll-up, query ems_dw.v_borough_hourly_ems_performance.

Assignment-ready sample analytical SQL is in sql/postgres_analytical_queries.sql; recorded runtimes and the indexed June query plan are in reports/batch_sql_timing_run.txt.

## Assignment scope

The overall assignment includes data curation and EDA, dimensional modelling, batch/distributed/streaming warehouses, OLAP, dashboards, predictive models, architecture evaluation and recommendations. Work proceeds one milestone at a time. See `models/warehouse_model.md` for the Milestone 3 star schema and `sql/create_ems_dw.sql` for its PostgreSQL DDL.
