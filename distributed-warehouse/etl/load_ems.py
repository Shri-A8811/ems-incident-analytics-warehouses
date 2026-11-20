"""Idempotently stage and transform the FDNY EMS CSV into the Citus warehouse."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import re
import subprocess
import sys
from typing import TextIO

SOURCE_COLUMNS = (
    "INCIDENT_ID",
    "INCIDENT_DATETIME",
    "INITIAL_CALL_TYPE",
    "INITIAL_SEVERITY_LEVEL_CODE",
    "FINAL_CALL_TYPE",
    "FINAL_SEVERITY_LEVEL_CODE",
    "FIRST_ASSIGNMENT_DATETIME",
    "VALID_DISPATCH_RSPNS_TIME_INDC",
    "DISPATCH_RESPONSE_SECONDS_QY",
    "FIRST_ACTIVATION_DATETIME",
    "FIRST_ON_SCENE_DATETIME",
    "VALID_INCIDENT_RSPNS_TIME_INDC",
    "INCIDENT_RESPONSE_SECONDS_QY",
    "INCIDENT_TRAVEL_TM_SECONDS_QY",
    "FIRST_TO_HOSP_DATETIME",
    "FIRST_HOSP_ARRIVAL_DATETIME",
    "INCIDENT_CLOSE_DATETIME",
    "HELD_INDICATOR",
    "INCIDENT_DISPOSITION_CODE",
    "BOROUGH",
    "INCIDENT_DISPATCH_AREA",
    "ZIPCODE",
    "POLICEPRECINCT",
    "CITYCOUNCILDISTRICT",
    "COMMUNITYDISTRICT",
    "COMMUNITYSCHOOLDISTRICT",
    "CONGRESSIONALDISTRICT",
    "REOPEN_INDICATOR",
    "SPECIAL_EVENT_INDICATOR",
    "STANDBY_INDICATOR",
    "TRANSFER_INDICATOR",
)

DEFAULT_SOURCE = Path(__file__).resolve().parents[2] / "data" / "source" / "EMS_Incident_Dispatch_Data_20261015.csv"
PROJECT_DIR = Path(__file__).resolve().parents[1]


def validate_header(stream: TextIO) -> csv.DictReader:
    reader = csv.DictReader(stream)
    if tuple(reader.fieldnames or ()) != SOURCE_COLUMNS:
        raise ValueError("CSV header does not match the expected FDNY EMS source columns and order")
    return reader


def run_psql(*args: str, capture_output: bool = False) -> str:
    command = [
        "docker", "compose", "exec", "-T", "coordinator", "psql",
        "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres",
        *args,
    ]
    result = subprocess.run(
        command,
        cwd=PROJECT_DIR,
        check=True,
        text=True,
        capture_output=capture_output,
    )
    return result.stdout if capture_output else ""


def load_csv(source_path: Path) -> tuple[int, int]:
    source_path = source_path.resolve()
    shared_source_dir = DEFAULT_SOURCE.parent.resolve()
    if source_path.parent != shared_source_dir:
        raise ValueError(f"Source CSV must be inside the shared source folder: {shared_source_dir}")
    if "'" in source_path.name:
        raise ValueError("CSV filename cannot contain a single quote")
    with source_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = validate_header(stream)
        source_row_count = sum(1 for _ in reader)
    container_path = f"/opt/ems/source/{source_path.name}"
    run_psql("-c", "TRUNCATE TABLE stg_ems_incident")
    copy_command = f"\\copy stg_ems_incident FROM '{container_path}' WITH (FORMAT csv, HEADER true)"
    copy_result = run_psql("-c", copy_command, capture_output=True)
    copy_match = re.search(r"COPY\s+(\d+)", copy_result)
    if not copy_match:
        raise RuntimeError(f"Could not read COPY row count from psql output: {copy_result!r}")
    staged_count = int(copy_match.group(1))
    if staged_count != source_row_count:
        raise RuntimeError(f"Staged row count {staged_count} does not match source count {source_row_count}")
    run_psql("-f", "/opt/ems/sql/10_transform.sql")
    run_psql(
        "-c",
        "INSERT INTO etl_batch (source_file, staged_row_count, fact_row_count) "
        f"SELECT '{source_path.name}', {staged_count}, COUNT(*) FROM fact_incident",
    )
    fact_count_text = run_psql("-A", "-t", "-c", "SELECT COUNT(*) FROM fact_incident", capture_output=True)
    fact_count = int(fact_count_text.strip())
    return staged_count, fact_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", nargs="?", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    try:
        staged_count, fact_count = load_csv(args.csv_path)
    except subprocess.CalledProcessError as exc:
        print(f"ETL command failed with exit code {exc.returncode}", file=sys.stderr)
        raise SystemExit(exc.returncode) from exc
    print(f"Staged {staged_count} source rows; fact_incident currently contains {fact_count} incidents.")


if __name__ == "__main__":
    main()
