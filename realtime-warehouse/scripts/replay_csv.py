"""Replay the shared EMS snapshot to Kafka in incident-time order."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_DIR.parent / "data" / "source" / "EMS_Incident_Dispatch_Data_20261015.csv"
EXPECTED_COLUMNS = (
    "INCIDENT_ID", "INCIDENT_DATETIME", "INITIAL_CALL_TYPE", "INITIAL_SEVERITY_LEVEL_CODE",
    "FINAL_CALL_TYPE", "FINAL_SEVERITY_LEVEL_CODE", "FIRST_ASSIGNMENT_DATETIME",
    "VALID_DISPATCH_RSPNS_TIME_INDC", "DISPATCH_RESPONSE_SECONDS_QY", "FIRST_ACTIVATION_DATETIME",
    "FIRST_ON_SCENE_DATETIME", "VALID_INCIDENT_RSPNS_TIME_INDC", "INCIDENT_RESPONSE_SECONDS_QY",
    "INCIDENT_TRAVEL_TM_SECONDS_QY", "FIRST_TO_HOSP_DATETIME", "FIRST_HOSP_ARRIVAL_DATETIME",
    "INCIDENT_CLOSE_DATETIME", "HELD_INDICATOR", "INCIDENT_DISPOSITION_CODE", "BOROUGH",
    "INCIDENT_DISPATCH_AREA", "ZIPCODE", "POLICEPRECINCT", "CITYCOUNCILDISTRICT",
    "COMMUNITYDISTRICT", "COMMUNITYSCHOOLDISTRICT", "CONGRESSIONALDISTRICT", "REOPEN_INDICATOR",
    "SPECIAL_EVENT_INDICATOR", "STANDBY_INDICATOR", "TRANSFER_INDICATOR",
)


def read_rows(source: Path = SOURCE) -> list[dict[str, str]]:
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
            raise ValueError("CSV header does not match the expected 31 FDNY EMS source columns")
        rows = list(reader)
    for row in rows:
        if not row["INCIDENT_ID"]:
            raise ValueError("INCIDENT_ID must be present for keyed replay")
        row["_event_sort"] = datetime.strptime(row["INCIDENT_DATETIME"], "%m/%d/%Y %I:%M:%S %p")
    return rows


def replay(*, source: Path = SOURCE, rate: float = 1.0, limit: int | None = None, incident_id: str | None = None) -> int:
    if rate < 0:
        raise ValueError("rate must be zero (unpaced) or a positive events-per-second value")
    rows = read_rows(source)
    rows.sort(key=lambda row: (row["_event_sort"], int(row["INCIDENT_ID"])))
    if incident_id is not None:
        rows = [row for row in rows if row["INCIDENT_ID"] == incident_id]
        if not rows:
            raise ValueError(f"INCIDENT_ID {incident_id} was not found in {source}")
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be positive")
        rows = rows[:limit]

    command = [
        "docker", "compose", "exec", "-T", "kafka",
        "/opt/kafka/bin/kafka-console-producer.sh",
        "--bootstrap-server", "kafka:9092", "--topic", "ems.incidents.raw",
        "--property", "parse.key=true", "--property", "key.separator=\t",
    ]
    process = subprocess.Popen(command, cwd=PROJECT_DIR, stdin=subprocess.PIPE, text=True, encoding="utf-8")
    assert process.stdin is not None
    sent = 0
    interval = 0 if rate == 0 else 1.0 / rate
    try:
        for row in rows:
            row.pop("_event_sort")
            record = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            process.stdin.write(f"{row['INCIDENT_ID']}\t{record}\n")
            process.stdin.flush()
            sent += 1
            if interval and sent < len(rows):
                time.sleep(interval)
    except (BrokenPipeError, OSError):
        process.stdin.close()
        return process.wait()
    process.stdin.close()
    result = process.wait()
    if result:
        raise subprocess.CalledProcessError(result, command)
    print(f"Replayed {sent} incident(s) to ems.incidents.raw")
    return sent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rate", type=float, default=1.0, help="events per second; 0 sends without pacing")
    parser.add_argument("--limit", type=int, help="replay only the first N events in chronological order")
    parser.add_argument("--incident-id", help="replay exactly one source incident (useful for freshness checks)")
    parser.add_argument("--source", type=Path, default=SOURCE)
    args = parser.parse_args()
    try:
        replay(source=args.source, rate=args.rate, limit=args.limit, incident_id=args.incident_id)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Replay failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
