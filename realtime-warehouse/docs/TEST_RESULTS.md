# Test results

## Unit and source-contract checks

- `python -m unittest discover -s tests -v`: 4 source-contract tests passed. Six Docker integration tests are opt-in and are skipped by this command.
- Python syntax compilation, `docker compose config --quiet`, and dashboard JSON parsing passed.

## Live local-stack checks

- `RUN_STACK_TESTS=1 python -m unittest tests.test_stack -v`: 6 checks passed on the local Compose stack.
- The replay staged 1,310 unique IDs across all 31 source columns and produced 1,310 current facts.
- Fact quality totals matched the independent source calculation: 1,309 usable dispatch durations, 1,293 usable incident-response durations, 1,294 usable travel durations, and 4 timestamp-order issues.
- Every grouped KPI result by event date, borough, and initial call type (incident count, valid denominator, and average for dispatch, incident response, and travel) matched a separate Python calculation over the source CSV.
- Replaying a known incident twice left one current staging row and one current fact row for that `INCIDENT_ID`.
- Grafana loaded the provisioned six-panel dashboard with a 5-second refresh, including monthly dispatch/incident-response averages and their valid denominators. The exact freshness-panel query returned the replayed incident through Grafana's ClickHouse datasource 2.20 seconds after it was sent, below the 10-second local acceptance target.

This is a correctness demonstration on one local machine and a small historical snapshot, not a throughput or production-availability benchmark.
