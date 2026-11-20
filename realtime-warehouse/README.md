# EMS Realtime Data Warehouse

This is a separate local replay-and-streaming warehouse for the FDNY EMS Incident Dispatch CSV. It uses Kafka for event transport, Spark Structured Streaming for parsing and validity flags, ClickHouse for analytics, and Grafana for dashboards. The source incident timestamps remain event time; replay/stream ingestion time is stored separately. The 1,310-row snapshot is for correctness and demonstration, not performance claims.

## Scope and data rules

- Kafka raw topic records preserve all 31 CSV columns; a ClickHouse staging table keeps those source values as text. The replay tool checks the exact source header and keys every record by `INCIDENT_ID`.
- The replay is sorted by `INCIDENT_DATETIME` before sending. `--rate` controls events per second; `0` means unpaced.
- Spark derives a date and typed measures, while preserving dispatch/incident response validity flags and separate initial/final call-type and severity values.
- All incidents are kept for volume. Dispatch and incident-response durations are usable only when their FDNY flag is `Y` and the number is present and nonnegative. Travel has no FDNY validity flag; this warehouse treats a present, nonnegative travel value as usable and records that rule explicitly.
- `ReplacingMergeTree` stores versions ordered by `INCIDENT_ID`. Dashboard queries use `FINAL` so repeated replay does not inflate current-state counts before background merges.
- Grafana refresh is set to 5 seconds. The live stack test replays one known incident and checks its fresh version through the provisioned dashboard data source within 10 seconds.

## Prerequisites

- Docker Desktop Linux engine and Docker Compose v2
- Python 3.10 or later on the host (standard library only)
- Internet access from Docker while pulling the pinned images and Spark's Kafka connector package

## Start

In PowerShell from this folder:

```powershell
Copy-Item .env.example .env
.\scripts\start.ps1
```

Open Grafana at `http://localhost:3002`. The initial admin login is in `.env` (the example is only for local learning; change it before sharing the machine). Services do not publish Kafka or ClickHouse ports to the host.

## Replay

Send the complete 1,310-row source snapshot chronologically at one row per second:

```powershell
python .\scripts\replay_csv.py --rate 1
```

Use another speed, limit a demonstration, or send one test event:

```powershell
python .\scripts\replay_csv.py --rate 5
python .\scripts\replay_csv.py --rate 0 --limit 25
python .\scripts\replay_csv.py --rate 0 --incident-id 123456789
```

`--incident-id` must exist in the supplied source snapshot. Replaying the CSV is safe for live counts: the same incident ID is a replacement version in ClickHouse, and dashboard SQL reads with `FINAL`.

## Component and live checks

Unit/source-contract checks (no containers required):

```powershell
python -m unittest discover -s tests -v
```

After starting the stack, run service/topic checks, replay-to-dashboard freshness, and duplicate replay checks:

```powershell
$env:RUN_STACK_TESTS = '1'
python -m unittest tests.test_stack -v
Remove-Item Env:\RUN_STACK_TESTS
```

The freshness check is local to this Compose environment. It is a repeatable acceptance target, not a general latency claim.

## Reset demo data

The project-scoped reset removes this warehouse's Kafka log, ClickHouse tables, Spark checkpoint, and Grafana state, then recreates the services:

```powershell
.\scripts\reset_demo.ps1
```

To stop without deleting state, run `docker compose down`.

## Further documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Data dictionary](docs/DATA_DICTIONARY.md)
- [Runbook](docs/RUNBOOK.md)
- [Test results](docs/TEST_RESULTS.md)
- [Technical references](docs/TECH_REFERENCES.md)
