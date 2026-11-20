# Data dictionary

## Topics

| Topic | Key | Value | Purpose |
|---|---|---|---|
| `ems.incidents.raw` | `INCIDENT_ID` | JSON object with all 31 original CSV columns as strings | Immutable source-shaped replay event |
| `ems.incidents.processed` | `incident_id` | JSONEachRow analytics record | Spark-typed/enriched event consumed by ClickHouse |

## ClickHouse `ems.fact_incident`

| Column | Meaning |
|---|---|
| `incident_id` | FDNY `INCIDENT_ID`; replacing key and incident grain |
| `incident_datetime` | Original source event datetime text; not adjusted to replay time |
| `event_date` | Calendar date parsed from the original incident datetime |
| `borough` | Source borough; blank values become `UNKNOWN` |
| `initial_call_type`, `final_call_type` | Separate original call type roles, with blanks mapped to `UNKNOWN` |
| `initial_severity`, `final_severity` | Separate initial/final severity values, with blanks mapped to `UNKNOWN` |
| `disposition_code` | Source incident disposition; blank becomes `UNKNOWN` |
| `incident_count` | Always 1 per source incident version |
| `dispatch_seconds` | Parsed dispatch response seconds; nullable |
| `dispatch_valid_flag` | Original `VALID_DISPATCH_RSPNS_TIME_INDC` |
| `dispatch_usable` | Source flag is `Y`, value present, and value is nonnegative |
| `incident_response_seconds` | Parsed incident response seconds; nullable |
| `incident_valid_flag` | Original `VALID_INCIDENT_RSPNS_TIME_INDC` |
| `incident_response_usable` | Source flag is `Y`, value present, and value is nonnegative |
| `travel_seconds` | Parsed incident travel seconds; nullable |
| `travel_usable` | Project rule: travel value is present and nonnegative |
| `timestamp_order_ok` | Source event/assignment/activation/on-scene/hospital/close times have no adjacent out-of-order pair |
| `ingested_at` | Spark processing timestamp in UTC; distinct from incident event time |

## ClickHouse `ems.stg_ems_incident`

This staging table has all 31 source columns, stored as `String` with their original names and values. `raw_ingested_at` is an additional ClickHouse ingestion timestamp. It uses `ReplacingMergeTree(raw_ingested_at)` ordered by source `INCIDENT_ID`, so replaying an incident maintains one current staged source row while leaving its source-shaped values unchanged.

Invalid numeric values become null only in the typed fact; source originals remain available in staging.

## Metrics

- Incident volume: `count()` after `FINAL`; invalid/missing durations do not remove incidents.
- Dispatch response average: `avgIf(dispatch_seconds, dispatch_usable)`; denominator is `countIf(dispatch_usable)`.
- Incident response average: `avgIf(incident_response_seconds, incident_response_usable)`; denominator is `countIf(incident_response_usable)`.
- Travel average: `avgIf(travel_seconds, travel_usable)`; denominator is `countIf(travel_usable)`.
