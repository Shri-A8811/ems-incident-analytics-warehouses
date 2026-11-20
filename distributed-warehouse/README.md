# EMS Distributed Data Warehouse

This project builds the distributed warehouse for the FDNY EMS Incident Dispatch dataset using a local Citus cluster: one coordinator and two worker nodes. The source snapshot contains 1,310 incidents and is intentionally kept at its original size. This is an architecture and correctness demonstration, not a performance benchmark.

## Scope

- Keep all 31 original source columns in `stg_ems_incident` as raw text.
- Build one `fact_incident` row per `INCIDENT_ID`, with date, geography, call type, severity, and disposition dimensions.
- Retain separate initial/final call type and severity keys.
- Store dispatch, incident-response, and travel durations in seconds.
- Use the source validity flags for dispatch and incident-response averages. Travel time has no separate source validity flag, so its project-defined usability rule is nonmissing and nonnegative.
- Count every incident for volume. Show each valid measurement count next to the corresponding average.
- Keep source values unchanged in staging; map missing dimension values to `UNKNOWN`; flag out-of-order timestamp sequences without deleting or correcting incidents.
- Hash-distribute the fact table by `INCIDENT_ID` into four shards and replicate the small dimensions.

## Prerequisites

- Docker Desktop with the Linux container engine running
- Docker Compose v2
- Python 3.10 or newer
- Docker CLI access to the local engine

Docker CLI and Compose were present during initial setup, but the engine was unavailable. Start Docker Desktop and wait for the engine to finish starting before running the commands below.

## Start the cluster

From this directory in PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up -d --wait
docker compose ps
```

The coordinator is available at `127.0.0.1:55432`. The two workers are internal to the Compose network. This Compose setup is for local development only and uses trust authentication inside its isolated network.

## Load the source snapshot

```powershell
python .\etl\load_ems.py
```

The loader stages the full CSV snapshot, transforms dimensions, and upserts facts by `INCIDENT_ID`. Repeating the load should leave one fact row per source incident.

## Verify

Run unit and source-contract tests:

```powershell
python -m unittest discover -s tests -v
```

After the cluster is running, add database integration checks:

```powershell
$env:RUN_DB_TESTS = '1'
python -m unittest tests.test_integration -v
Remove-Item Env:\RUN_DB_TESTS
```

Inspect worker and shard placement and row quality:

```powershell
Get-Content .\scripts\check_cluster.sql | docker compose exec -T coordinator psql -U postgres -d postgres
Get-Content .\sql\20_analytics.sql | docker compose exec -T coordinator psql -U postgres -d postgres
```

## Reset

To reset the database volumes and return to a clean cluster, run:

```powershell
docker compose down -v
```

This permanently removes this project's local Citus database volumes. Then run `docker compose up -d --wait` and load the CSV again.

## Documentation map

- `docs/ARCHITECTURE.md`: cluster, data flow, and star-schema design
- `docs/DATA_DICTIONARY.md`: source columns, curated fields, KPI and quality rules
- `docs/RUNBOOK.md`: start, load, verify, stop, and reset instructions
- `docs/TEST_RESULTS.md`: recorded component and integration test evidence
- `sql/init/`: cluster registration and schema creation on first initialization
- `sql/10_transform.sql`: idempotent dimension/fact transformation
- `sql/20_analytics.sql`: reporting queries
- `etl/load_ems.py`: standard-library CSV validation and psql-based staging/transformation orchestration
- `tests/`: unit, source-contract, and opt-in Citus integration checks
- `scripts/check_cluster.sql`: worker, shard, and data-quality checks

## Data-quality notes

- The source has 1,310 unique incident IDs.
- There are 1,309 usable dispatch durations, 1,293 usable incident-response durations, and 1,294 present nonnegative travel-duration values.
- Timestamp-order issues are flagged, not dropped; missing intermediate timestamps do not by themselves make an incident out of order.
- Travel time has no dedicated source validity indicator. Its usability is derived as nonmissing and nonnegative and is identified as a project rule, not an FDNY flag.
- Disposition and severity codes are preserved as source codes; this project does not assign undocumented human-readable meanings.

## References

- [FDNY EMS Incident Dispatch Data](https://data.cityofnewyork.us/Public-Safety/EMS-Incident-Dispatch-Data/76xm-jjuj)
- [Citus Docker image and cluster example](https://github.com/citusdata/docker)
- [Citus node registration documentation](https://docs.citusdata.com/en/stable/develop/api_udf.html#citus-add-node)
