"""Load curated FDNY incident data into the local SQLite star schema."""
import argparse
import csv
import gzip
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/curated/ems_incident_dispatch_curated_2024-01_to_2026-06.csv.gz"
DB = ROOT / "data/warehouse/ems_dispatch_dw.sqlite"
SCHEMA = ROOT / "sql/create_ems_dw_sqlite.sql"
FACT_COLUMNS = """incident_id,incident_date_key,location_key,initial_call_type_key,
final_call_type_key,initial_severity_key,final_severity_key,disposition_key,
incident_datetime,first_assignment_datetime,first_activation_datetime,first_on_scene_datetime,
first_to_hosp_datetime,first_hosp_arrival_datetime,incident_close_datetime,
dispatch_response_seconds,incident_response_seconds,incident_travel_seconds,
valid_dispatch_response,valid_incident_response,held_indicator,reopen_indicator,
special_event_indicator,standby_indicator,transfer_indicator,timestamp_order_issue,
dispatch_response_iqr_outlier,incident_response_iqr_outlier,incident_travel_iqr_outlier,
source_extract_name,loaded_at"""
TIMESTAMPS = ("incident_datetime", "first_assignment_datetime", "first_activation_datetime",
              "first_on_scene_datetime", "first_to_hosp_datetime", "first_hosp_arrival_datetime",
              "incident_close_datetime")
LOCATION_FIELDS = ("borough", "incident_dispatch_area", "zipcode", "policeprecinct",
                   "citycouncildistrict", "communitydistrict", "communityschooldistrict",
                   "congressionaldistrict")

def null(v):
    return v if v not in (None, "") else None

def num(v):
    return int(float(v)) if null(v) is not None else None

def real(v):
    return float(v) if null(v) is not None else None

def flag(v):
    return 1 if v == "True" else 0

def read_codebook(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["code"]: r["description"] for r in csv.DictReader(f)}

def load(replace=False):
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    DB.parent.mkdir(parents=True, exist_ok=True)
    if DB.exists() and not replace:
        raise FileExistsError(f"{DB} already exists; use --replace to rebuild")
    temp = DB.with_suffix(".building.sqlite")
    if temp.exists():
        temp.unlink()
    calls = read_codebook(ROOT / "docs/reference/call_type_descriptions.csv")
    dispositions = read_codebook(ROOT / "docs/reference/incident_disposition_codes.csv")
    loaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn = sqlite3.connect(temp)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    try:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        conn.execute("BEGIN")
        conn.execute("INSERT INTO dim_date(date_key) VALUES (0)")
        conn.execute("INSERT INTO dim_location(location_key) VALUES (0)")
        dates, locations, call_ids, severity_ids, disp_ids = {}, {}, {}, {}, {}
        batch, count = [], 0

        def member(value, cache, table, code_col, desc_col=None, descriptions=None):
            value = null(value)
            if value is None:
                return None
            if value not in cache:
                if desc_col:
                    cur = conn.execute(f"INSERT INTO {table}({code_col},{desc_col}) VALUES (?,?)",
                                       (value, (descriptions or {}).get(value)))
                else:
                    cur = conn.execute(f"INSERT INTO {table}({code_col}) VALUES (?)", (value,))
                cache[value] = cur.lastrowid
            return cache[value]

        with gzip.open(SOURCE, "rt", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            required = {"incident_id", *TIMESTAMPS, *LOCATION_FIELDS, "initial_call_type",
                "final_call_type", "initial_severity_level_code", "final_severity_level_code",
                "incident_disposition_code", "dispatch_response_seconds_qy",
                "incident_response_seconds_qy", "incident_travel_tm_seconds_qy",
                "timestamp_order_issue", "dispatch_response_iqr_outlier",
                "incident_response_iqr_outlier", "incident_travel_tm_iqr_outlier"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"Missing columns: {sorted(missing)}")

            for r in reader:
                stamp = null(r["incident_datetime"])
                day = stamp[:10] if stamp else None
                if day and day not in dates:
                    d = date.fromisoformat(day)
                    key = d.year * 10000 + d.month * 100 + d.day
                    conn.execute("INSERT INTO dim_date VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (key, d.isoformat(), d.year, (d.month-1)//3+1, d.month,
                         d.strftime("%B"), d.day, d.isoweekday(), d.strftime("%A"),
                         int(d.isoweekday() >= 6)))
                    dates[day] = key
                date_key = dates.get(day, 0)

                loc = tuple(null(r[x]) for x in LOCATION_FIELDS)
                if all(x is None for x in loc):
                    location_key = 0
                else:
                    loc = (loc[:3] + tuple(num(x) for x in loc[3:]))
                    if loc not in locations:
                        cur = conn.execute("INSERT INTO dim_location "
                            "(borough,incident_dispatch_area,zipcode,police_precinct,"
                            "city_council_district,community_district,community_school_district,"
                            "congressional_district) VALUES (?,?,?,?,?,?,?,?)", loc)
                        locations[loc] = cur.lastrowid
                    location_key = locations[loc]

                initial_call = member(r["initial_call_type"], call_ids, "dim_call_type",
                    "source_call_type_code", "call_type_description", calls)
                final_call = member(r["final_call_type"], call_ids, "dim_call_type",
                    "source_call_type_code", "call_type_description", calls)
                initial_severity = member(r["initial_severity_level_code"], severity_ids,
                    "dim_severity", "source_severity_code")
                final_severity = member(r["final_severity_level_code"], severity_ids,
                    "dim_severity", "source_severity_code")
                disposition = member(r["incident_disposition_code"], disp_ids, "dim_disposition",
                    "source_disposition_code", "source_description", dispositions)
                values = (r["incident_id"], date_key, location_key, initial_call, final_call,
                    initial_severity, final_severity, disposition,
                    *(null(r[x]) for x in TIMESTAMPS),
                    real(r["dispatch_response_seconds_qy"]), real(r["incident_response_seconds_qy"]),
                    real(r["incident_travel_tm_seconds_qy"]),
                    null(r["valid_dispatch_rspns_time_indc"]), null(r["valid_incident_rspns_time_indc"]),
                    null(r["held_indicator"]), null(r["reopen_indicator"]),
                    null(r["special_event_indicator"]), null(r["standby_indicator"]),
                    null(r["transfer_indicator"]), flag(r["timestamp_order_issue"]),
                    flag(r["dispatch_response_iqr_outlier"]), flag(r["incident_response_iqr_outlier"]),
                    flag(r["incident_travel_tm_iqr_outlier"]), SOURCE.name, loaded_at)
                batch.append(values)
                count += 1
                if len(batch) == 20000:
                    conn.executemany("INSERT INTO fact_ems_incident (" + FACT_COLUMNS +
                                     ") VALUES (" + ",".join(["?"]*31) + ")", batch)
                    batch.clear()
                    if count % 500000 == 0:
                        print(f"Loaded {count:,} incidents", flush=True)
            if batch:
                conn.executemany("INSERT INTO fact_ems_incident (" + FACT_COLUMNS +
                                 ") VALUES (" + ",".join(["?"]*31) + ")", batch)

        # Create indices after bulk loading for a faster import.
        for statement in (
            "CREATE INDEX IF NOT EXISTS ix_fact_incident_date ON fact_ems_incident(incident_date_key)",
            "CREATE INDEX IF NOT EXISTS ix_fact_location ON fact_ems_incident(location_key)",
            "CREATE INDEX IF NOT EXISTS ix_fact_initial_call_type ON fact_ems_incident(initial_call_type_key)",
            "CREATE INDEX IF NOT EXISTS ix_fact_final_call_type ON fact_ems_incident(final_call_type_key)",
        ):
            conn.execute(statement)
        conn.commit()
        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            raise RuntimeError(f"Warehouse has foreign-key errors: {fk_errors[:5]}")
        result = {
            "database": str(DB), "source_file": str(SOURCE), "loaded_rows": count,
            "fact_rows": conn.execute("SELECT COUNT(*) FROM fact_ems_incident").fetchone()[0],
            "dimension_rows": {
                table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("dim_date", "dim_location", "dim_call_type", "dim_severity", "dim_disposition")
            },
            "foreign_key_errors": len(fk_errors),
            "unique_incident_ids": conn.execute("SELECT COUNT(DISTINCT incident_id) FROM fact_ems_incident").fetchone()[0],
            "dispatch_invalid_rows": conn.execute("SELECT COUNT(*) FROM fact_ems_incident WHERE valid_dispatch_response='N'").fetchone()[0],
            "dispatch_valid_rows": conn.execute("SELECT COUNT(*) FROM fact_ems_incident WHERE valid_dispatch_response='Y'").fetchone()[0],
            "valid_dispatch_rows_missing_measure": conn.execute("SELECT COUNT(*) FROM fact_ems_incident WHERE valid_dispatch_response='Y' AND dispatch_response_seconds IS NULL").fetchone()[0],
            "timestamp_order_issue_rows": conn.execute("SELECT COUNT(*) FROM fact_ems_incident WHERE timestamp_order_issue=1").fetchone()[0],
            "loaded_at_utc": loaded_at
        }
        if result["fact_rows"] != count or result["unique_incident_ids"] != count:
            raise RuntimeError("Incident row-count or uniqueness reconciliation failed")
        if result["valid_dispatch_rows_missing_measure"] != 0:
            raise RuntimeError("Valid dispatch rows unexpectedly lack a measure")
        report = ROOT / "reports/warehouse_load_summary.json"
        report.write_text(json.dumps(result, indent=2), encoding="utf-8")
        conn.close()
        if DB.exists():
            DB.unlink()
        temp.replace(DB)
        print(json.dumps(result, indent=2))
    except Exception:
        conn.rollback()
        conn.close()
        if temp.exists():
            temp.unlink()
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replace", action="store_true", help="rebuild existing database")
    load(parser.parse_args())
