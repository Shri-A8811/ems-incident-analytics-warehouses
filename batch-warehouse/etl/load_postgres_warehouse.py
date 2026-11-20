"""Initial and incremental batch ETL for the assignment's PostgreSQL warehouse."""
import argparse
import csv
import gzip
import io
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/curated/ems_incident_dispatch_curated_2024-01_to_2026-06.csv.gz"
SCHEMA = ROOT / "sql/create_ems_dw.sql"
CALLS = ROOT / "docs/reference/call_type_descriptions.csv"
DISPOSITIONS = ROOT / "docs/reference/incident_disposition_codes.csv"
FIELDS = (
    "incident_id", "incident_datetime", "initial_call_type", "initial_severity_level_code",
    "final_call_type", "final_severity_level_code", "first_assignment_datetime",
    "valid_dispatch_rspns_time_indc", "dispatch_response_seconds_qy",
    "first_activation_datetime", "first_on_scene_datetime", "valid_incident_rspns_time_indc",
    "incident_response_seconds_qy", "incident_travel_tm_seconds_qy",
    "first_to_hosp_datetime", "first_hosp_arrival_datetime", "incident_close_datetime",
    "held_indicator", "incident_disposition_code", "borough", "incident_dispatch_area",
    "zipcode", "policeprecinct", "citycouncildistrict", "communitydistrict",
    "communityschooldistrict", "congressionaldistrict", "reopen_indicator",
    "special_event_indicator", "standby_indicator", "transfer_indicator",
    "timestamp_order_issue", "dispatch_response_iqr_outlier",
    "incident_response_iqr_outlier", "incident_travel_tm_iqr_outlier",
)
COPY_FIELDS = ("load_batch_id",) + FIELDS + ("source_extract_name",)
COPY_SQL = (
    "COPY ems_dw.stg_ems_incident (" + ",".join(COPY_FIELDS) +
    ") FROM STDIN WITH (FORMAT CSV)"
)
DATES = (
    ("incident_datetime", "incident"), ("first_assignment_datetime", "assignment"),
    ("first_activation_datetime", "activation"), ("first_on_scene_datetime", "scene"),
    ("first_to_hosp_datetime", "to_hospital"),
    ("first_hosp_arrival_datetime", "hospital_arrival"),
    ("incident_close_datetime", "close"),
)

def read_env():
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

def connection():
    read_env()
    return psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"), port=os.getenv("PGPORT", "5435"),
        dbname=os.getenv("PGDATABASE", "ems_dw"), user=os.getenv("PGUSER", "ems_admin"),
        password=os.environ["POSTGRES_PASSWORD"],
    )

def codebook(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["code"]: r["description"] for r in csv.DictReader(f)}

def period(mode):
    if mode == "initial":
        return "initial_2024-01_to_2026-05", "2024-01-01", "2026-06-01"
    if mode == "incremental":
        return "incremental_2026-06", "2026-06-01", "2026-07-01"
    return "full_2024-01_to_2026-06", "2024-01-01", "2026-07-01"

def copy_stage(cur, batch_id, start, end):
    cur.execute("TRUNCATE ems_dw.stg_ems_incident")
    input_count = 0
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    with gzip.open(SOURCE, "rt", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if set(FIELDS) - set(reader.fieldnames or []):
            raise ValueError("Curated CSV does not contain the expected source fields.")
        for row in reader:
            timestamp = row["incident_datetime"]
            day = timestamp[:10] if timestamp else ""
            if not start <= day < end:
                continue
            writer.writerow([batch_id] + [row[f] for f in FIELDS] + [SOURCE.name])
            input_count += 1
            if input_count % 25000 == 0:
                buf.seek(0)
                cur.copy_expert(COPY_SQL, buf)
                buf.seek(0)
                buf.truncate(0)
            if input_count % 500000 == 0:
                print(f"Staged {input_count:,} incidents for {batch_id}", flush=True)
    if buf.tell():
        buf.seek(0)
        cur.copy_expert(COPY_SQL, buf)
    return input_count

def load_dimensions(cur, callbook, dispositionbook):
    # Generate a contiguous calendar around the incident range. The one-day
    # padding covers event timestamps that pass midnight after incident start.
    cur.execute(f"""
        INSERT INTO ems_dw.dim_date
        (date_key,full_date,year_number,quarter_number,month_number,month_name,
         day_of_month,day_of_week_number,day_name,is_weekend)
        SELECT (extract(year from g.d)::int*10000+extract(month from g.d)::int*100+
                extract(day from g.d)::int), g.d, extract(year from g.d)::smallint,
               extract(quarter from g.d)::smallint, extract(month from g.d)::smallint,
               to_char(g.d,'FMMonth'), extract(day from g.d)::smallint,
               extract(isodow from g.d)::smallint, to_char(g.d,'FMDay'),
               extract(isodow from g.d)::int >= 6
        FROM (
          SELECT generate_series(min(NULLIF(incident_datetime,'')::timestamp::date)-1,
                                 max(NULLIF(incident_datetime,'')::timestamp::date)+1,
                                 interval '1 day')::date AS d
          FROM ems_dw.stg_ems_incident
        ) g
        ON CONFLICT (full_date) DO NOTHING
    """)
    cur.execute("""
        INSERT INTO ems_dw.dim_time
        (time_key,time_value,hour_number,minute_number,second_number,time_band)
        SELECT s+1, (time '00:00:00' + s*interval '1 second')::time,
               (s/3600)::smallint, ((s/60)%60)::smallint, (s%60)::smallint,
               CASE WHEN s/3600 < 6 THEN 'overnight'
                    WHEN s/3600 < 12 THEN 'morning'
                    WHEN s/3600 < 18 THEN 'afternoon'
                    ELSE 'evening' END
        FROM generate_series(0,86399) AS g(s)
        ON CONFLICT (time_key) DO NOTHING
    """)
    cur.execute("""
        INSERT INTO ems_dw.dim_location
        (location_signature,borough,incident_dispatch_area,zipcode,police_precinct,city_council_district,
         community_district,community_school_district,congressional_district)
        SELECT DISTINCT jsonb_build_array(NULLIF(borough,''),NULLIF(incident_dispatch_area,''),
               NULLIF(zipcode,''),NULLIF(policeprecinct,'')::numeric::integer,
               NULLIF(citycouncildistrict,'')::numeric::integer,NULLIF(communitydistrict,'')::numeric::integer,
               NULLIF(communityschooldistrict,'')::numeric::integer,
               NULLIF(congressionaldistrict,'')::numeric::integer)::text,
               NULLIF(borough,''),NULLIF(incident_dispatch_area,''),
               NULLIF(zipcode,''),NULLIF(policeprecinct,'')::numeric::integer,
               NULLIF(citycouncildistrict,'')::numeric::integer,NULLIF(communitydistrict,'')::numeric::integer,
               NULLIF(communityschooldistrict,'')::numeric::integer,
               NULLIF(congressionaldistrict,'')::numeric::integer
        FROM ems_dw.stg_ems_incident
        ON CONFLICT (location_signature) DO NOTHING
    """)
    for table, field, mapping in (
        ("dim_call_type", "initial_call_type", callbook),
        ("dim_call_type", "final_call_type", callbook),
        ("dim_disposition", "incident_disposition_code", dispositionbook),
    ):
        cur.execute(f"SELECT DISTINCT NULLIF({field},'') FROM ems_dw.stg_ems_incident")
        codes = {r[0] for r in cur.fetchall() if r[0] is not None}
        col = "source_call_type_code" if table == "dim_call_type" else "source_disposition_code"
        desc = "call_type_description" if table == "dim_call_type" else "source_description"
        values = [(c, mapping.get(c)) for c in codes]
        if values:
            cur.executemany(
                f"INSERT INTO ems_dw.{table} ({col},{desc}) VALUES (%s,%s) "
                f"ON CONFLICT ({col}) DO UPDATE SET {desc}=COALESCE(ems_dw.{table}.{desc},EXCLUDED.{desc})",
                values,
            )
    for field in ("initial_severity_level_code", "final_severity_level_code"):
        cur.execute(f"SELECT DISTINCT NULLIF({field},'') FROM ems_dw.stg_ems_incident")
        codes = [(r[0],) for r in cur.fetchall() if r[0] is not None]
        if codes:
            cur.executemany(
                "INSERT INTO ems_dw.dim_severity(source_severity_code) VALUES (%s) "
                "ON CONFLICT (source_severity_code) DO NOTHING", codes,
            )

def insert_facts(cur):
    parsed = """
    WITH p AS (
      SELECT s.*,
       NULLIF(incident_datetime,'')::timestamp AS incident_ts,
       NULLIF(first_assignment_datetime,'')::timestamp AS assignment_ts,
       NULLIF(first_activation_datetime,'')::timestamp AS activation_ts,
       NULLIF(first_on_scene_datetime,'')::timestamp AS scene_ts,
       NULLIF(first_to_hosp_datetime,'')::timestamp AS to_hospital_ts,
       NULLIF(first_hosp_arrival_datetime,'')::timestamp AS hospital_arrival_ts,
       NULLIF(incident_close_datetime,'')::timestamp AS close_ts
      FROM ems_dw.stg_ems_incident s
    )
    """
    join_bits = []
    select_keys = []
    for field, role in DATES:
        ts = role + "_ts"
        select_keys.append(
            f"COALESCE(to_char(p.{ts},'YYYYMMDD')::integer,0) AS {role}_date_key"
        )
        select_keys.append(
            f"COALESCE(extract(hour from p.{ts})::int*3600+"
            f"extract(minute from p.{ts})::int*60+extract(second from p.{ts})::int+1,0) "
            f"AS {role}_time_key"
        )
    sql = parsed + """
    INSERT INTO ems_dw.fact_ems_incident (
      incident_id,incident_date_key,assignment_date_key,activation_date_key,scene_date_key,
      to_hospital_date_key,hospital_arrival_date_key,close_date_key,
      incident_time_key,assignment_time_key,activation_time_key,scene_time_key,
      to_hospital_time_key,hospital_arrival_time_key,close_time_key,location_key,
      initial_call_type_key,final_call_type_key,initial_severity_key,final_severity_key,
      disposition_key,incident_datetime,first_assignment_datetime,first_activation_datetime,
      first_on_scene_datetime,first_to_hosp_datetime,first_hosp_arrival_datetime,
      incident_close_datetime,dispatch_response_seconds,incident_response_seconds,
      incident_travel_seconds,valid_dispatch_response,valid_incident_response,held_indicator,
      reopen_indicator,special_event_indicator,standby_indicator,transfer_indicator,
      timestamp_order_issue,dispatch_response_iqr_outlier,incident_response_iqr_outlier,
      incident_travel_iqr_outlier,source_extract_name
    )
    SELECT p.incident_id,
      COALESCE(to_char(p.incident_ts,'YYYYMMDD')::integer,0),
      COALESCE(to_char(p.assignment_ts,'YYYYMMDD')::integer,0),
      COALESCE(to_char(p.activation_ts,'YYYYMMDD')::integer,0),
      COALESCE(to_char(p.scene_ts,'YYYYMMDD')::integer,0),
      COALESCE(to_char(p.to_hospital_ts,'YYYYMMDD')::integer,0),
      COALESCE(to_char(p.hospital_arrival_ts,'YYYYMMDD')::integer,0),
      COALESCE(to_char(p.close_ts,'YYYYMMDD')::integer,0),
      COALESCE(extract(hour from p.incident_ts)::int*3600+extract(minute from p.incident_ts)::int*60+extract(second from p.incident_ts)::int+1,0),
      COALESCE(extract(hour from p.assignment_ts)::int*3600+extract(minute from p.assignment_ts)::int*60+extract(second from p.assignment_ts)::int+1,0),
      COALESCE(extract(hour from p.activation_ts)::int*3600+extract(minute from p.activation_ts)::int*60+extract(second from p.activation_ts)::int+1,0),
      COALESCE(extract(hour from p.scene_ts)::int*3600+extract(minute from p.scene_ts)::int*60+extract(second from p.scene_ts)::int+1,0),
      COALESCE(extract(hour from p.to_hospital_ts)::int*3600+extract(minute from p.to_hospital_ts)::int*60+extract(second from p.to_hospital_ts)::int+1,0),
      COALESCE(extract(hour from p.hospital_arrival_ts)::int*3600+extract(minute from p.hospital_arrival_ts)::int*60+extract(second from p.hospital_arrival_ts)::int+1,0),
      COALESCE(extract(hour from p.close_ts)::int*3600+extract(minute from p.close_ts)::int*60+extract(second from p.close_ts)::int+1,0),
      l.location_key,ci.call_type_key,cf.call_type_key,si.severity_key,sf.severity_key,di.disposition_key,
      p.incident_ts,p.assignment_ts,p.activation_ts,p.scene_ts,p.to_hospital_ts,p.hospital_arrival_ts,p.close_ts,
      NULLIF(p.dispatch_response_seconds_qy,'')::numeric,
      NULLIF(p.incident_response_seconds_qy,'')::numeric,
      NULLIF(p.incident_travel_tm_seconds_qy,'')::numeric,
      NULLIF(p.valid_dispatch_rspns_time_indc,''),NULLIF(p.valid_incident_rspns_time_indc,''),
      NULLIF(p.held_indicator,''),NULLIF(p.reopen_indicator,''),NULLIF(p.special_event_indicator,''),
      NULLIF(p.standby_indicator,''),NULLIF(p.transfer_indicator,''),
      lower(p.timestamp_order_issue)::boolean,lower(p.dispatch_response_iqr_outlier)::boolean,
      lower(p.incident_response_iqr_outlier)::boolean,lower(p.incident_travel_tm_iqr_outlier)::boolean,
      p.source_extract_name
    FROM p
    JOIN ems_dw.dim_location l ON l.location_signature = jsonb_build_array(
      NULLIF(p.borough,''),NULLIF(p.incident_dispatch_area,''),NULLIF(p.zipcode,''),
      NULLIF(p.policeprecinct,'')::numeric::integer,
      NULLIF(p.citycouncildistrict,'')::numeric::integer,
      NULLIF(p.communitydistrict,'')::numeric::integer,
      NULLIF(p.communityschooldistrict,'')::numeric::integer,
      NULLIF(p.congressionaldistrict,'')::numeric::integer)::text
    LEFT JOIN ems_dw.dim_call_type ci ON ci.source_call_type_code=NULLIF(p.initial_call_type,'')
    LEFT JOIN ems_dw.dim_call_type cf ON cf.source_call_type_code=NULLIF(p.final_call_type,'')
    LEFT JOIN ems_dw.dim_severity si ON si.source_severity_code=NULLIF(p.initial_severity_level_code,'')
    LEFT JOIN ems_dw.dim_severity sf ON sf.source_severity_code=NULLIF(p.final_severity_level_code,'')
    LEFT JOIN ems_dw.dim_disposition di ON di.source_disposition_code=NULLIF(p.incident_disposition_code,'')
    ON CONFLICT (incident_id) DO NOTHING
    """
    cur.execute(sql)
    return cur.rowcount

def refresh_hourly(cur, start, end, incremental):
    start_key = int(start.replace("-", ""))
    end_key = int(end.replace("-", ""))
    if incremental:
        cur.execute(
            "DELETE FROM ems_dw.fact_borough_hourly_ems_performance "
            "WHERE date_key >= %s AND date_key < %s", (start_key, end_key))
    else:
        cur.execute("TRUNCATE ems_dw.fact_borough_hourly_ems_performance")
    cur.execute("""
      INSERT INTO ems_dw.fact_borough_hourly_ems_performance
      (date_key,hour_time_key,location_key,incident_count,valid_dispatch_count,
       dispatch_response_seconds_sum,valid_incident_response_count,
       incident_response_seconds_sum,travel_time_count,travel_time_seconds_sum)
      SELECT incident_date_key,
        (extract(hour from incident_datetime)::int*3600+1),
        location_key,count(*),
        count(*) FILTER (WHERE valid_dispatch_response='Y' AND dispatch_response_seconds IS NOT NULL),
        COALESCE(sum(dispatch_response_seconds) FILTER
          (WHERE valid_dispatch_response='Y' AND dispatch_response_seconds IS NOT NULL),0),
        count(*) FILTER (WHERE valid_incident_response='Y' AND incident_response_seconds IS NOT NULL),
        COALESCE(sum(incident_response_seconds) FILTER
          (WHERE valid_incident_response='Y' AND incident_response_seconds IS NOT NULL),0),
        count(incident_travel_seconds),COALESCE(sum(incident_travel_seconds),0)
      FROM ems_dw.fact_ems_incident
      WHERE incident_datetime IS NOT NULL
        AND incident_date_key >= %s AND incident_date_key < %s
      GROUP BY incident_date_key,extract(hour from incident_datetime)::int,location_key
    """, (start_key, end_key))

def validate_foreign_keys(cur, batch_id):
    references = (
        ("incident_date_key", "dim_date", "date_key"),
        ("assignment_date_key", "dim_date", "date_key"),
        ("activation_date_key", "dim_date", "date_key"),
        ("scene_date_key", "dim_date", "date_key"),
        ("to_hospital_date_key", "dim_date", "date_key"),
        ("hospital_arrival_date_key", "dim_date", "date_key"),
        ("close_date_key", "dim_date", "date_key"),
        ("incident_time_key", "dim_time", "time_key"),
        ("assignment_time_key", "dim_time", "time_key"),
        ("activation_time_key", "dim_time", "time_key"),
        ("scene_time_key", "dim_time", "time_key"),
        ("to_hospital_time_key", "dim_time", "time_key"),
        ("hospital_arrival_time_key", "dim_time", "time_key"),
        ("close_time_key", "dim_time", "time_key"),
        ("location_key", "dim_location", "location_key"),
        ("initial_call_type_key", "dim_call_type", "call_type_key"),
        ("final_call_type_key", "dim_call_type", "call_type_key"),
        ("initial_severity_key", "dim_severity", "severity_key"),
        ("final_severity_key", "dim_severity", "severity_key"),
        ("disposition_key", "dim_disposition", "disposition_key"),
    )
    conditions = [
        f"(f.{fact_col} IS NOT NULL AND f.{fact_col} NOT IN "
        f"(SELECT {dim_col} FROM ems_dw.{table}))"
        for fact_col, table, dim_col in references
    ]
    cur.execute("SELECT count(*) FROM ems_dw.fact_ems_incident f "
                "JOIN ems_dw.stg_ems_incident s ON s.incident_id=f.incident_id "
                "WHERE s.load_batch_id=%s AND (" + " OR ".join(conditions) + ")",
                (batch_id,))
    return cur.fetchone()[0]

def run(mode, resume_staged=False):
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    batch_id, start, end = period(mode)
    conn = connection()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA.read_text(encoding="utf-8"))
            if mode == "incremental":
                cur.execute("SELECT count(*) FROM ems_dw.etl_batch_audit WHERE load_mode='initial' AND status='success'")
                if cur.fetchone()[0] == 0:
                    raise RuntimeError("Run --mode initial successfully before the incremental period.")
            cur.execute("SELECT count(*) FROM ems_dw.fact_ems_incident")
            before = cur.fetchone()[0]
            cur.execute("INSERT INTO ems_dw.etl_batch_audit "
                "(load_batch_id,load_mode,period_start,period_end_exclusive,status) "
                "VALUES (%s,%s,%s,%s,'running') ON CONFLICT (load_batch_id) DO UPDATE SET "
                "status='running',started_at=now(),finished_at=NULL,notes=NULL",
                (batch_id, mode, start, end))
            if resume_staged:
                cur.execute("SELECT count(*) FROM ems_dw.stg_ems_incident WHERE load_batch_id=%s",
                            (batch_id,))
                staged = cur.fetchone()[0]
                if staged == 0:
                    raise RuntimeError("No committed staging rows found for this batch to resume.")
            else:
                staged = copy_stage(cur, batch_id, start, end)
            cur.execute("UPDATE ems_dw.etl_batch_audit SET staged_row_count=%s WHERE load_batch_id=%s",
                        (staged, batch_id))
            conn.commit()
            cur.execute("SET LOCAL work_mem='256MB'")
            index_names = (
                "ix_fact_ems_incident_date", "ix_fact_ems_incident_location",
                "ix_fact_ems_incident_call_type_initial",
                "ix_fact_ems_incident_call_type_final",
            )
            if mode != "incremental":
                for index in index_names:
                    cur.execute(f"DROP INDEX IF EXISTS ems_dw.{index}")
            load_dimensions(cur, codebook(CALLS), codebook(DISPOSITIONS))
            # Bulk ETL bypasses per-row FK trigger lookups for speed. The same
            # transaction performs a full set-based orphan check immediately
            # after inserting, before commit; constraints remain enabled later.
            if mode != "incremental":
                cur.execute("SET LOCAL session_replication_role = replica")
            inserted = insert_facts(cur)
            if mode != "incremental":
                cur.execute("SET LOCAL session_replication_role = origin")
            orphan_count = validate_foreign_keys(cur, batch_id)
            if orphan_count:
                raise RuntimeError(f"Post-load foreign-key validation found {orphan_count:,} orphan rows.")
            if mode != "incremental":
                cur.execute("CREATE INDEX ix_fact_ems_incident_date ON ems_dw.fact_ems_incident(incident_date_key)")
                cur.execute("CREATE INDEX ix_fact_ems_incident_location ON ems_dw.fact_ems_incident(location_key)")
                cur.execute("CREATE INDEX ix_fact_ems_incident_call_type_initial ON ems_dw.fact_ems_incident(initial_call_type_key)")
                cur.execute("CREATE INDEX ix_fact_ems_incident_call_type_final ON ems_dw.fact_ems_incident(final_call_type_key)")
            refresh_hourly(cur, start, end, mode == "incremental")
            cur.execute("SELECT count(*),count(DISTINCT incident_id) FROM ems_dw.fact_ems_incident")
            after, distinct_ids = cur.fetchone()
            if after != distinct_ids:
                raise RuntimeError("Fact incident IDs are not unique.")
            cur.execute("SELECT count(*) FROM ems_dw.stg_ems_incident WHERE load_batch_id=%s", (batch_id,))
            staged_db = cur.fetchone()[0]
            if staged_db != staged:
                raise RuntimeError(f"Stage row count mismatch: read {staged:,}, stored {staged_db:,}")
            cur.execute("SELECT count(*) FROM ems_dw.fact_ems_incident "
                "WHERE valid_dispatch_response='Y' AND dispatch_response_seconds IS NULL")
            missing_valid_dispatch = cur.fetchone()[0]
            if missing_valid_dispatch:
                raise RuntimeError(f"{missing_valid_dispatch} valid dispatch rows lack a duration")
            cur.execute("SELECT count(*) FROM ems_dw.fact_ems_incident")
            final_count = cur.fetchone()[0]
            cur.execute("""
              UPDATE ems_dw.etl_batch_audit SET inserted_fact_count=%s,
                fact_row_count_after=%s,finished_at=now(),status='success',
                notes=%s WHERE load_batch_id=%s
            """, (inserted, final_count,
                  f"Fact rows before load: {before}; rows added: {inserted}; "
                  f"stage rows: {staged}; valid dispatch blanks: {missing_valid_dispatch}",
                  batch_id))
        conn.commit()
        print(f"Batch: {batch_id}")
        print(f"Mode: {mode}; source period: {start} through {end} (end exclusive)")
        print(f"Staged rows: {staged:,}; new fact rows: {inserted:,}; total fact rows: {final_count:,}")
        print(f"Distinct incident IDs: {distinct_ids:,}; valid dispatch rows missing duration: {missing_valid_dispatch}")
        print("Foreign-key orphan rows: 0")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("initial","incremental","full"), default="initial")
    parser.add_argument("--resume-staged", action="store_true",
                        help="reuse the selected batch's previously committed staging rows")
    args = parser.parse_args()
    run(args.mode, args.resume_staged)
