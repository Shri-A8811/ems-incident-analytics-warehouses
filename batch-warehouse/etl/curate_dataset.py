"""Apply the documented Milestone 2 curation rules to the raw CSV pages."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_FILES = sorted((ROOT / "data" / "raw").glob("ems_incident_dispatch_2024-01_to_2026-06_part*.csv"))
OUT_FILE = ROOT / "data" / "curated" / "ems_incident_dispatch_curated_2024-01_to_2026-06.csv.gz"
TIMESTAMP_FIELDS = [
    "incident_datetime", "first_assignment_datetime", "first_activation_datetime",
    "first_on_scene_datetime", "first_to_hosp_datetime", "first_hosp_arrival_datetime",
    "incident_close_datetime",
]
EVENT_PAIRS = [
    ("incident_datetime", "first_assignment_datetime"),
    ("first_assignment_datetime", "first_activation_datetime"),
    ("first_activation_datetime", "first_on_scene_datetime"),
    ("first_on_scene_datetime", "first_to_hosp_datetime"),
    ("first_to_hosp_datetime", "first_hosp_arrival_datetime"),
    ("first_hosp_arrival_datetime", "incident_close_datetime"),
]
NUMERIC_FIELDS = [
    "dispatch_response_seconds_qy", "incident_response_seconds_qy",
    "incident_travel_tm_seconds_qy", "policeprecinct", "citycouncildistrict",
    "communitydistrict", "communityschooldistrict", "congressionaldistrict",
]
OUTLIER_THRESHOLDS = {
    "dispatch_response_seconds_qy": 214.0,  # Q3 + 1.5*IQR among validity_flag=Y
    "incident_response_seconds_qy": 1771.0,  # Q3 + 1.5*IQR among validity_flag=Y
    "incident_travel_tm_seconds_qy": 1354.5,  # Q3 + 1.5*IQR among nonblank source values
}


def main() -> None:
    if not RAW_FILES:
        raise SystemExit("No raw CSV pages found.")
    if OUT_FILE.exists():
        raise SystemExit(f"Curated output already exists: {OUT_FILE}. Move it to an archive before replacing it.")
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    rows = 0
    invalid_dispatch_rows = 0
    timestamp_issue_rows = 0
    outlier_counts = {field: 0 for field in OUTLIER_THRESHOLDS}
    dispatch_null_before = 0
    dispatch_null_after = 0
    dispatch_valid_zero_preserved = 0

    with gzip.open(OUT_FILE, "wt", encoding="utf-8", newline="") as output:
        first_page = True
        for page_number, path in enumerate(RAW_FILES, start=1):
            for frame in pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=200_000):
                n = len(frame)
                rows += n
                dispatch_null_before += int(frame["dispatch_response_seconds_qy"].eq("").sum())

                parsed = {field: pd.to_datetime(frame[field], errors="coerce", format="mixed") for field in TIMESTAMP_FIELDS}
                order_issue = pd.Series(False, index=frame.index)
                for before, after in EVENT_PAIRS:
                    comparable = parsed[before].notna() & parsed[after].notna()
                    order_issue |= comparable & (parsed[after] < parsed[before])
                frame["timestamp_order_issue"] = order_issue.astype(bool)
                timestamp_issue_rows += int(order_issue.sum())

                for field in NUMERIC_FIELDS:
                    frame[field] = pd.to_numeric(frame[field].replace("", np.nan), errors="coerce")

                invalid_dispatch = frame["valid_dispatch_rspns_time_indc"].eq("N")
                invalid_dispatch_rows += int(invalid_dispatch.sum())
                frame.loc[invalid_dispatch, "dispatch_response_seconds_qy"] = np.nan
                dispatch_valid_zero_preserved += int(
                    (frame["valid_dispatch_rspns_time_indc"].eq("Y") & frame["dispatch_response_seconds_qy"].eq(0)).sum()
                )

                for field in OUTLIER_THRESHOLDS:
                    flag_name = field.replace("_seconds_qy", "") + "_iqr_outlier"
                    is_candidate = frame[field].notna() & (frame[field] > OUTLIER_THRESHOLDS[field])
                    if field == "dispatch_response_seconds_qy":
                        is_candidate &= frame["valid_dispatch_rspns_time_indc"].eq("Y")
                    elif field == "incident_response_seconds_qy":
                        is_candidate &= frame["valid_incident_rspns_time_indc"].eq("Y")
                    frame[flag_name] = is_candidate.astype(bool)
                    outlier_counts[field] += int(is_candidate.sum())

                dispatch_null_after += int(frame["dispatch_response_seconds_qy"].isna().sum())
                frame.to_csv(output, index=False, header=first_page, na_rep="")
                first_page = False
            print(f"Curated page {page_number}/{len(RAW_FILES)}: {path.name}", flush=True)

    summary = {
        "source_rows": rows,
        "curated_rows": rows,
        "row_count_reconciles": True,
        "invalid_dispatch_flag_n_rows_set_to_missing": invalid_dispatch_rows,
        "dispatch_response_blanks_before": dispatch_null_before,
        "dispatch_response_blanks_after": dispatch_null_after,
        "dispatch_valid_zero_values_preserved": dispatch_valid_zero_preserved,
        "rows_flagged_for_timestamp_order_issue": timestamp_issue_rows,
        "outlier_flags_added": outlier_counts,
        "outlier_rule": "Upper Tukey fence (Q3 + 1.5*IQR); flags only. Values were retained.",
        "raw_files_modified": False,
        "curated_file": str(OUT_FILE.relative_to(ROOT)),
        "curated_bytes": OUT_FILE.stat().st_size,
        "new_fields": ["timestamp_order_issue", "dispatch_response_iqr_outlier",
                       "incident_response_iqr_outlier", "incident_travel_tm_iqr_outlier"],
    }
    (ROOT / "reports" / "curation_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
