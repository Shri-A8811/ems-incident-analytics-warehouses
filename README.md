# EMS Incident Analytics Warehouses

This workspace contains two new, independent warehouses built from the FDNY EMS Incident Dispatch dataset. The existing traditional warehouse is not part of this workspace and remains unchanged.

## Build order

1. `distributed-warehouse/` — local Citus coordinator with two workers. Built and integration-checked against the source snapshot.
2. `realtime-warehouse/` — Kafka, Spark Structured Streaming, ClickHouse, and Grafana with a paced replay of the same source CSV. Built and checked after the distributed warehouse.

The shared source snapshot is in `data/source/`. Each warehouse will keep its own code, tests, run instructions, and documentation.
