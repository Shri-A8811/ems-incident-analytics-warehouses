# Runbook

## First start

1. Confirm Docker Desktop is running.
2. From `realtime-warehouse`, copy `.env.example` to `.env` and adjust the Grafana local admin password if desired.
3. Run `./scripts/start.ps1`. Compose waits for Kafka, ClickHouse, and Grafana health checks; Kafka topic creation is a one-shot dependency.
4. Check `docker compose ps` and open `http://localhost:3002`.
5. Sign in with the credentials in `.env`. The EMS dashboard is provisioned under the EMS folder.
6. Start a replay with `python ./scripts/replay_csv.py --rate 1`.

## Replay controls

- `--rate N`: target N source records per second. Defaults to 1.
- `--rate 0`: send without deliberate pacing, useful for tests and short demos.
- `--limit N`: send only the first N incidents after chronological sorting.
- `--incident-id ID`: send exactly one source incident, useful for the freshness acceptance check.

Each event retains its original CSV event time. The `ingested_at` field is added downstream by Spark and is used to observe replay freshness.

## Health and logs

```powershell
docker compose ps
docker compose logs --tail 100 kafka spark clickhouse grafana
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic ems.incidents.raw
docker compose exec clickhouse clickhouse-client --query "SELECT count() FROM ems.fact_incident FINAL"
```

If Spark cannot download the Kafka connector package, check that Docker can reach Maven Central, then restart only Spark with `docker compose restart spark`.

## Clean reset

Run `./scripts/reset_demo.ps1`. It runs Compose `down --volumes` for this project only, removing this project's Kafka, ClickHouse, Spark checkpoint, and Grafana state, and starts fresh services. The shared CSV source is not modified. To stop while preserving state, use `docker compose down` instead.

## Troubleshooting

- If port 3002 is in use, change `GRAFANA_PORT` in `.env` and rerun `docker compose up -d`.
- If Kafka topic setup failed, inspect `docker compose logs kafka-init`; rerun with `docker compose up -d kafka-init`.
- If the same incident appears multiple times in physical parts, query `ems.fact_incident FINAL`; this is the current-state query form used by the dashboard.
- For a fresh replay from offset zero, use the clean reset. The Spark checkpoint intentionally resumes a prior stream and should not be deleted alone while leaving ClickHouse/Kafka state intact.
