"""Stream-validate the raw FDNY EMS CSV pages without altering them."""
from __future__ import annotations

import csv
import glob
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILES = sorted(glob.glob(str(ROOT / "data" / "raw" / "ems_incident_dispatch_2024-01_to_2026-06_part*.csv")))
START = datetime.fromisoformat("2024-01-01T00:00:00")
END = datetime.fromisoformat("2026-07-01T00:00:00")
REQUIRED = {"incident_id", "incident_datetime", "borough", "initial_call_type", "incident_response_seconds_qy"}
EXPECTED_ROWS_AT_EXTRACTION = 4_035_659


def parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def main() -> None:
    if not FILES:
        raise SystemExit("No raw CSV pages found. Run ./download_fdny_ems.ps1 first.")
    canonical_header = None
    rows = invalid_width = missing_datetime = invalid_datetime = out_of_range = 0
    ids: set[str] = set()
    duplicate_ids = 0
    first_dt = last_dt = None
    null_counts: Counter[str] = Counter()
    for path in FILES:
        with open(path, "r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            header = reader.fieldnames or []
            if canonical_header is None:
                canonical_header = header
                missing = REQUIRED - set(header)
                if missing:
                    raise SystemExit(f"Required fields missing: {sorted(missing)}")
            elif header != canonical_header:
                raise SystemExit(f"Header mismatch in {path}")
            for record in reader:
                rows += 1
                if None in record or any(value is None for key, value in record.items() if key):
                    invalid_width += 1
                for key, value in record.items():
                    if key and (value is None or value == ""):
                        null_counts[key] += 1
                incident_id = record.get("incident_id") or ""
                if incident_id in ids:
                    duplicate_ids += 1
                elif incident_id:
                    ids.add(incident_id)
                raw_dt = record.get("incident_datetime") or ""
                if not raw_dt:
                    missing_datetime += 1
                    continue
                parsed = parse_dt(raw_dt)
                if parsed is None:
                    invalid_datetime += 1
                    continue
                first_dt = parsed if first_dt is None or parsed < first_dt else first_dt
                last_dt = parsed if last_dt is None or parsed > last_dt else last_dt
                if not START <= parsed < END:
                    out_of_range += 1
    result = {
        "files": len(FILES), "rows": rows, "unique_nonblank_incident_ids": len(ids),
        "duplicate_incident_ids": duplicate_ids, "fields": canonical_header,
        "first_incident_datetime": first_dt.isoformat() if first_dt else None,
        "last_incident_datetime": last_dt.isoformat() if last_dt else None,
        "missing_incident_datetime": missing_datetime, "invalid_incident_datetime": invalid_datetime,
        "out_of_range_incident_datetime": out_of_range, "rows_with_invalid_width": invalid_width,
        "blank_counts_by_field": dict(null_counts), "usable": rows == EXPECTED_ROWS_AT_EXTRACTION and invalid_width == 0 and
        missing_datetime == 0 and invalid_datetime == 0 and out_of_range == 0 and duplicate_ids == 0,
    }
    rendered = json.dumps(result, indent=2)
    (ROOT / "docs" / "verification_summary.json").write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if rows == 0 or invalid_width or missing_datetime or invalid_datetime or out_of_range or duplicate_ids:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
