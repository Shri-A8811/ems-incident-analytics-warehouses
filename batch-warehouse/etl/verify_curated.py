"""Check the saved curated CSV and reconcile it to the raw row count."""
from __future__ import annotations

import csv
import gzip
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURATED = ROOT / "data" / "curated" / "ems_incident_dispatch_curated_2024-01_to_2026-06.csv.gz"
EXPECTED_ROWS = 4_035_659


def main() -> None:
    rows = malformed = 0
    blanks: Counter[str] = Counter()
    dispatch_flag_counts: Counter[str] = Counter()
    incident_flag_counts: Counter[str] = Counter()
    dispatch_n_nonblank = dispatch_y_blank = dispatch_y_zero = 0
    response_n_nonblank = response_y_blank = 0
    quality_flag_counts: Counter[str] = Counter()
    header: list[str] | None = None
    with gzip.open(CURATED, "rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        header = reader.fieldnames
        for record in reader:
            rows += 1
            if None in record or any(v is None for k, v in record.items() if k):
                malformed += 1
            for field, value in record.items():
                if field and value == "":
                    blanks[field] += 1
            dflag = record["valid_dispatch_rspns_time_indc"]
            rflag = record["valid_incident_rspns_time_indc"]
            dispatch_flag_counts[dflag] += 1
            incident_flag_counts[rflag] += 1
            dispatch_value = record["dispatch_response_seconds_qy"]
            response_value = record["incident_response_seconds_qy"]
            if dflag == "N" and dispatch_value != "":
                dispatch_n_nonblank += 1
            if dflag == "Y" and dispatch_value == "":
                dispatch_y_blank += 1
            if dflag == "Y" and dispatch_value != "" and float(dispatch_value) == 0:
                dispatch_y_zero += 1
            if rflag == "N" and response_value != "":
                response_n_nonblank += 1
            if rflag == "Y" and response_value == "":
                response_y_blank += 1
            for field in ("timestamp_order_issue", "dispatch_response_iqr_outlier",
                          "incident_response_iqr_outlier", "incident_travel_tm_iqr_outlier"):
                quality_flag_counts[field] += record[field] == "True"

    checks = {
        "expected_rows": EXPECTED_ROWS,
        "curated_rows": rows,
        "row_count_matches_raw": rows == EXPECTED_ROWS,
        "field_count": len(header or []),
        "fields": header,
        "malformed_rows": malformed,
        "dispatch_flag_counts": dict(dispatch_flag_counts),
        "incident_response_flag_counts": dict(incident_flag_counts),
        "dispatch_n_rows_with_measure": dispatch_n_nonblank,
        "dispatch_y_rows_missing_measure": dispatch_y_blank,
        "dispatch_y_zero_count": dispatch_y_zero,
        "incident_response_n_rows_with_measure": response_n_nonblank,
        "incident_response_y_rows_missing_measure": response_y_blank,
        "quality_flag_counts": dict(quality_flag_counts),
        "blank_counts_by_field": dict(blanks),
        "usable": rows == EXPECTED_ROWS and malformed == 0 and dispatch_n_nonblank == 0
        and dispatch_y_blank == 0 and response_n_nonblank == 0 and response_y_blank == 0,
    }
    (ROOT / "reports" / "curated_verification_summary.json").write_text(
        json.dumps(checks, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(checks, indent=2))
    if not checks["usable"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
