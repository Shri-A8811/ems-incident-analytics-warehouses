# Distributed Warehouse Test Results

**Run date:** 2026-11-15
**Citus image:** `citusdata/citus:14.2.0`
**Docker Engine:** 29.6.1
**Docker Compose:** 5.2.0
**Python:** 3.12.14

## Result

All 13 automated checks passed against the live local Citus cluster.

| Check | Result |
| --- | --- |
| Source header and quoted numeric CSV parsing | Pass |
| All 31 source columns retained in staging | Pass |
| Source rows and unique incident IDs | 1,310 / 1,310 |
| Repeated full load | Pass; still 1,310 fact rows |
| Active workers | 2 |
| Fact shards | 4 total, 2 placed on each worker |
| Missing ZIP codes mapped to `UNKNOWN` | 35 incidents |
| Usable dispatch durations | 1,309 |
| Usable incident-response durations | 1,293 |
| Usable travel durations (derived rule) | 1,294 |
| Out-of-order timestamp rows flagged | 4 |
| Borough/month/initial-call-type KPI groups | Match independent CSV calculation |
| Final automated test run | 13 passed, 0 failed |

These results validate this dataset and local topology. They are not throughput, capacity, or scale benchmarks.
