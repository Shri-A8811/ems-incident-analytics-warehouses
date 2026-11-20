# Distributed Warehouse Runbook

Commands below assume Windows PowerShell and the working directory `distributed-warehouse`.

## Start

```powershell
Copy-Item .env.example .env
docker compose up -d --wait
docker compose ps
```

The coordinator is local-only on `127.0.0.1:55432`; workers are internal to the Compose network. The Compose environment is for local learning, not deployment on a shared or public host.

## Load / reload

```powershell
python .\etl\load_ems.py
```

The loader validates the exact source header, truncates and reloads raw staging, runs the SQL transformation, and upserts facts by `INCIDENT_ID`. It requires the cluster to be running and the source CSV to remain under the shared `data\source` folder.

Expected summary for the supplied snapshot:

```text
Staged 1310 source rows; fact_incident currently contains 1310 incidents.
```

## Test

Source/header tests without the database:

```powershell
python -m unittest discover -s tests -v
```

All integration checks with the Citus cluster:

```powershell
$env:RUN_DB_TESTS = '1'
python -m unittest discover -s tests -v
Remove-Item Env:\RUN_DB_TESTS
```

## Inspect

```powershell
Get-Content .\scripts\check_cluster.sql | docker compose exec -T coordinator psql -U postgres -d postgres
Get-Content .\sql\20_analytics.sql | docker compose exec -T coordinator psql -U postgres -d postgres
```

## Stop and restart

Stop services while keeping database volumes:

```powershell
docker compose stop
```

Restart the same cluster and data:

```powershell
docker compose up -d --wait
```

## Clean reset

This removes the containers, network, and **only this Compose project's** database volumes:

```powershell
docker compose down -v
```

Start again with `docker compose up -d --wait`, then reload the source CSV.
