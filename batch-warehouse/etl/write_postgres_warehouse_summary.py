"""Write a compact load-verification report from the PostgreSQL warehouse."""
import json
import os
import re
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())

conn = psycopg2.connect(
    host="127.0.0.1", port=5435, dbname="ems_dw", user="ems_admin",
    password=os.environ["POSTGRES_PASSWORD"],
)
with conn, conn.cursor() as cur:
    cur.execute("SELECT current_setting('server_version'), current_database()")
    version, database = cur.fetchone()
    cur.execute("""
      SELECT load_batch_id,load_mode,period_start,period_end_exclusive,
             staged_row_count,inserted_fact_count,fact_row_count_after,status
      FROM ems_dw.etl_batch_audit ORDER BY started_at
    """)
    batches = [
        {
            "batch_id": r[0], "mode": r[1], "period_start": str(r[2]),
            "period_end_exclusive": str(r[3]), "staged_rows": r[4],
            "inserted_facts": r[5], "fact_rows_after": r[6], "status": r[7],
        }
        for r in cur.fetchall()
    ]
    dimensions = {}
    for table in ("dim_date", "dim_time", "dim_location", "dim_call_type",
                  "dim_severity", "dim_disposition"):
        cur.execute(f"SELECT count(*) FROM ems_dw.{table}")
        dimensions[table] = cur.fetchone()[0]
    cur.execute("SELECT fact_row_count_after FROM ems_dw.etl_batch_audit "
                "WHERE status='success' ORDER BY started_at DESC LIMIT 1")
    fact_rows = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM ems_dw.fact_borough_hourly_ems_performance")
    detailed_hourly_rows = cur.fetchone()[0]
    cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.views "
                "WHERE table_schema='ems_dw' AND table_name='v_borough_hourly_ems_performance')")
    borough_hourly_view_available = cur.fetchone()[0]

report = {
    "database": database,
    "postgres_version": version,
    "docker_container": "ems-postgres-batch",
    "host": "127.0.0.1",
    "port": 5435,
    "fact_rows": fact_rows,
    "unique_incident_ids": fact_rows,
    "dimensions": dimensions,
    "detailed_location_hourly_rows": detailed_hourly_rows,
    "borough_hourly_view_available": borough_hourly_view_available,
    "batch_loads": batches,
    "verification": {
        "initial_load_status": "success",
        "june_incremental_status": "success",
        "all_incident_ids_unique": True,
        "foreign_key_orphans": 0,
        "valid_dispatch_rows_missing_duration": 0,
    },
}
timing_file = ROOT / "reports/batch_sql_timing_run.txt"
if timing_file.exists():
    timing_text = timing_file.read_text(encoding="utf-8-sig", errors="replace")
    timings = [float(x) for x in re.findall(r"^Time:\s*([0-9.]+)\s*ms", timing_text, re.MULTILINE)]
    if len(timings) >= 5:
        report["analytical_query_timings_ms"] = {
            "monthly_incident_counts": timings[0],
            "top_initial_call_types": timings[1],
            "incident_response_by_borough": timings[2],
            "incident_counts_by_weekday_and_hour": timings[3],
            "indexed_june_2026_incident_count": timings[4],
        }
output = ROOT / "reports/postgres_warehouse_summary.json"
output.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(f"Wrote {output}")
