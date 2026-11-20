"""Profile the unchanged FDNY EMS extracts for Milestone 2.

This script reads the raw pages in chunks. It does not modify source files or
make cleaning decisions. Outputs are written under reports/ and reports/figures/.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = sorted((ROOT / "data" / "raw").glob("ems_incident_dispatch_2024-01_to_2026-06_part*.csv"))
OUT = ROOT / "reports"
FIG = OUT / "figures"
CHUNK_SIZE = 200_000
NUMERIC_MEASURES = [
    "dispatch_response_seconds_qy",
    "incident_response_seconds_qy",
    "incident_travel_tm_seconds_qy",
]
NUMERIC_SOURCE_FIELDS = NUMERIC_MEASURES + [
    "policeprecinct", "citycouncildistrict", "communitydistrict",
    "communityschooldistrict", "congressionaldistrict",
]
CATEGORICAL_FIELDS = [
    "initial_call_type", "final_call_type", "initial_severity_level_code",
    "final_severity_level_code", "borough", "incident_dispatch_area",
    "incident_disposition_code", "valid_dispatch_rspns_time_indc",
    "valid_incident_rspns_time_indc", "held_indicator", "reopen_indicator",
    "special_event_indicator", "standby_indicator", "transfer_indicator",
]
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
VALIDITY_FIELD_FOR_MEASURE = {
    "dispatch_response_seconds_qy": "valid_dispatch_rspns_time_indc",
    "incident_response_seconds_qy": "valid_incident_rspns_time_indc",
}


def main() -> None:
    if not RAW:
        raise SystemExit("No raw extract files found under data/raw.")
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)

    rows = 0
    blank_counts: Counter[str] = Counter()
    categories: dict[str, Counter[str]] = {field: Counter() for field in CATEGORICAL_FIELDS}
    monthly: Counter[str] = Counter()
    quarterly: Counter[str] = Counter()
    daily: Counter[str] = Counter()
    weekday: Counter[str] = Counter()
    hourly: Counter[str] = Counter()
    borough_month: Counter[tuple[str, str]] = Counter()
    group_response_count: dict[str, Counter[tuple[str, ...]]] = {
        "borough": Counter(), "initial_call_type": Counter(),
        "borough_initial_call_type": Counter(), "severity_transition": Counter(),
    }
    group_response_sum: dict[str, Counter[tuple[str, ...]]] = {
        "borough": Counter(), "initial_call_type": Counter(),
        "borough_initial_call_type": Counter(), "severity_transition": Counter(),
    }
    severity_transitions: Counter[tuple[str, str]] = Counter()
    severity_change: Counter[str] = Counter()
    severity_change_disposition: Counter[tuple[str, str]] = Counter()
    event_pair_counts: Counter[str] = Counter()
    event_pair_out_of_order: Counter[str] = Counter()
    out_of_order_rows_any_pair = 0
    timestamp_invalid_nonblank: Counter[str] = Counter()
    numeric_invalid_nonblank: Counter[str] = Counter()
    numeric_negative: Counter[str] = Counter()
    numeric_zero: Counter[str] = Counter()
    padded_categories: Counter[str] = Counter()
    exact_duplicate_ids = 0
    seen_ids: set[str] = set()
    measure_chunks: dict[str, list[np.ndarray]] = {field: [] for field in NUMERIC_MEASURES}
    measure_counts: Counter[str] = Counter()
    negative_counts: Counter[str] = Counter()
    zero_counts: Counter[str] = Counter()
    validity_values: dict[str, dict[str, list[np.ndarray]]] = {
        measure: {"Y": [], "N": [], "blank": []} for measure in VALIDITY_FIELD_FOR_MEASURE
    }
    duration_comparisons: Counter[str] = Counter()
    duration_mismatches: Counter[str] = Counter()
    duration_abs_difference: dict[str, list[np.ndarray]] = {name: [] for name in (
        "dispatch_response_seconds_qy", "incident_response_seconds_qy", "incident_travel_tm_seconds_qy"
    )}

    for file_index, path in enumerate(RAW, start=1):
        for chunk in pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=CHUNK_SIZE):
            rows += len(chunk)
            for field in chunk.columns:
                blank_counts[field] += int(chunk[field].eq("").sum())

            ids = chunk["incident_id"]
            exact_duplicate_ids += int(ids.duplicated().sum())
            exact_duplicate_ids += sum(1 for value in ids if value and value in seen_ids)
            seen_ids.update(value for value in ids if value)

            for field, counter in categories.items():
                counter.update(value for value in chunk[field].tolist() if value != "")
                padded_categories[field] += int(chunk[field].ne(chunk[field].str.strip()).sum())

            initial_severity = chunk["initial_severity_level_code"].replace("", "[blank]")
            final_severity = chunk["final_severity_level_code"].replace("", "[blank]")
            disposition = chunk["incident_disposition_code"].replace("", "[blank]")
            transition_df = pd.DataFrame({"initial": initial_severity, "final": final_severity,
                                          "disposition": disposition})
            severity_transitions.update(transition_df.groupby(["initial", "final"], sort=False).size().to_dict())
            changed = initial_severity.ne(final_severity)
            severity_change.update({"changed": int(changed.sum()), "unchanged": int((~changed).sum())})
            severity_change_disposition.update(
                transition_df.assign(changed=changed.map({True: "changed", False: "unchanged"}))
                .groupby(["changed", "disposition"], sort=False).size().to_dict()
            )

            incident_dt = pd.to_datetime(chunk["incident_datetime"], errors="coerce", format="mixed")
            month = incident_dt.dt.strftime("%Y-%m").fillna("INVALID")
            monthly.update(month.tolist())
            quarter = incident_dt.dt.to_period("Q").astype(str).replace("NaT", "INVALID")
            quarterly.update(quarter.tolist())
            daily.update(incident_dt.dt.strftime("%Y-%m-%d").fillna("INVALID").tolist())
            weekday.update(incident_dt.dt.day_name().fillna("INVALID").tolist())
            hourly.update(incident_dt.dt.hour.astype("Int64").astype(str).replace("<NA>", "INVALID").tolist())
            boroughs = chunk["borough"].replace("", "[blank]")
            borough_month.update(zip(boroughs.tolist(), month.tolist()))

            parsed: dict[str, pd.Series] = {}
            for field in TIMESTAMP_FIELDS:
                parsed[field] = pd.to_datetime(chunk[field], errors="coerce", format="mixed")
                timestamp_invalid_nonblank[field] += int((chunk[field].ne("") & parsed[field].isna()).sum())
            row_order_issue = pd.Series(False, index=chunk.index)
            for before, after in EVENT_PAIRS:
                name = f"{before} -> {after}"
                pair = parsed[before].notna() & parsed[after].notna()
                event_pair_counts[name] += int(pair.sum())
                out_of_order = pair & (parsed[after] < parsed[before])
                event_pair_out_of_order[name] += int(out_of_order.sum())
                row_order_issue |= out_of_order
            out_of_order_rows_any_pair += int(row_order_issue.sum())

            duration_specs = [
                ("dispatch_response_seconds_qy", "incident_datetime", "first_assignment_datetime", "valid_dispatch_rspns_time_indc"),
                ("incident_response_seconds_qy", "incident_datetime", "first_on_scene_datetime", "valid_incident_rspns_time_indc"),
                ("incident_travel_tm_seconds_qy", "first_assignment_datetime", "first_on_scene_datetime", None),
            ]
            for measure, start_field, end_field, valid_field in duration_specs:
                recorded = pd.to_numeric(chunk[measure].replace("", np.nan), errors="coerce")
                has_both = parsed[start_field].notna() & parsed[end_field].notna() & recorded.notna()
                if valid_field:
                    has_both &= chunk[valid_field].eq("Y")
                expected_seconds = (parsed[end_field] - parsed[start_field]).dt.total_seconds()
                difference = (recorded - expected_seconds).where(has_both).dropna().to_numpy(dtype=np.float64, copy=True)
                duration_comparisons[measure] += int(len(difference))
                duration_mismatches[measure] += int((np.abs(difference) > 1.0).sum())
                duration_abs_difference[measure].append(np.abs(difference))

            for field in NUMERIC_MEASURES:
                values = pd.to_numeric(chunk[field].replace("", np.nan), errors="coerce")
                valid = values.dropna().to_numpy(dtype=np.float64, copy=True)
                measure_chunks[field].append(valid)
                measure_counts[field] += int(len(valid))
                negative_counts[field] += int((valid < 0).sum())
                zero_counts[field] += int((valid == 0).sum())
                valid_field = VALIDITY_FIELD_FOR_MEASURE.get(field)
                if valid_field:
                    flag = chunk[valid_field].replace("", "blank")
                    for flag_value in ("Y", "N", "blank"):
                        mask = flag.eq(flag_value)
                        group_values = values[mask].dropna().to_numpy(dtype=np.float64, copy=True)
                        validity_values[field][flag_value].append(group_values)

            response = pd.to_numeric(chunk["incident_response_seconds_qy"].replace("", np.nan), errors="coerce")
            usable_response = chunk["valid_incident_rspns_time_indc"].eq("Y") & response.notna()
            response_df = pd.DataFrame({
                "borough": chunk["borough"].replace("", "[blank]"),
                "initial_call_type": chunk["initial_call_type"].replace("", "[blank]"),
                "initial_severity": initial_severity, "final_severity": final_severity,
                "response": response,
            }).loc[usable_response]
            grouped_specs = {
                "borough": ["borough"],
                "initial_call_type": ["initial_call_type"],
                "borough_initial_call_type": ["borough", "initial_call_type"],
                "severity_transition": ["initial_severity", "final_severity"],
            }
            for result_name, group_fields in grouped_specs.items():
                grouped = response_df.groupby(group_fields, sort=False)["response"].agg(["count", "sum"])
                for key, row in grouped.iterrows():
                    key_tuple = key if isinstance(key, tuple) else (key,)
                    normalized_key = tuple(str(value) for value in key_tuple)
                    group_response_count[result_name][normalized_key] += int(row["count"])
                    group_response_sum[result_name][normalized_key] += float(row["sum"])

            for field in NUMERIC_SOURCE_FIELDS:
                raw_values = chunk[field]
                parsed_values = pd.to_numeric(raw_values.replace("", np.nan), errors="coerce")
                numeric_invalid_nonblank[field] += int((raw_values.ne("") & parsed_values.isna()).sum())
                numeric_negative[field] += int((parsed_values < 0).sum())
                numeric_zero[field] += int((parsed_values == 0).sum())

        print(f"Profiled page {file_index}/{len(RAW)}: {path.name}", flush=True)

    numeric_summary: list[dict[str, object]] = []
    measure_values: dict[str, np.ndarray] = {}
    for field in NUMERIC_MEASURES:
        values = np.concatenate(measure_chunks[field]) if measure_chunks[field] else np.array([], dtype=np.float64)
        measure_values[field] = values
        if len(values):
            series = pd.Series(values)
            q1, median, q3 = (float(series.quantile(q)) for q in (0.25, 0.5, 0.75))
            iqr = q3 - q1
            upper = q3 + 1.5 * iqr
            numeric_summary.append({
                "field": field, "valid_count": int(len(values)), "missing_count": int(rows - len(values)),
                "mean": float(series.mean()), "median": median, "minimum": float(series.min()),
                "maximum": float(series.max()), "variance_sample": float(series.var()),
                "stddev_sample": float(series.std()), "q1": q1, "q3": q3, "iqr": iqr,
                "skewness": float(series.skew()), "kurtosis_excess": float(series.kurt()),
                "negative_count": int(negative_counts[field]), "zero_count": int(zero_counts[field]),
                "upper_iqr_outlier_count": int((values > upper).sum()), "upper_iqr_threshold": upper,
            })

    pd.DataFrame(numeric_summary).to_csv(OUT / "numeric_summary.csv", index=False)
    validity_summary = []
    for field, groups in validity_values.items():
        for flag_value, arrays in groups.items():
            values = np.concatenate(arrays) if arrays else np.array([], dtype=np.float64)
            if len(values):
                series = pd.Series(values)
                q1, q3 = float(series.quantile(0.25)), float(series.quantile(0.75))
                iqr = q3 - q1
                upper = q3 + 1.5 * iqr
                validity_summary.append({
                    "field": field, "validity_flag": flag_value, "count": int(len(values)),
                    "mean_seconds": float(series.mean()), "median_seconds": float(series.median()),
                    "minimum_seconds": float(series.min()), "maximum_seconds": float(series.max()),
                    "variance_sample": float(series.var()), "stddev_sample": float(series.std()),
                    "q1": q1, "q3": q3, "iqr": iqr, "skewness": float(series.skew()),
                    "kurtosis_excess": float(series.kurt()), "negative_count": int((values < 0).sum()),
                    "zero_count": int((values == 0).sum()),
                    "upper_iqr_outlier_count": int((values > upper).sum()), "upper_iqr_threshold": upper,
                })
    pd.DataFrame(validity_summary).to_csv(OUT / "timing_by_validity_flag.csv", index=False)
    pd.DataFrame([
        {"field": f, "blank_count": int(n), "blank_percent": n / rows * 100}
        for f, n in sorted(blank_counts.items())
    ]).to_csv(OUT / "missing_values.csv", index=False)
    category_tables: dict[str, list[dict[str, object]]] = {}
    for field, counter in categories.items():
        table = [{"category": value, "count": count, "percent": count / rows * 100}
                 for value, count in counter.most_common()]
        category_tables[field] = table
        pd.DataFrame(table).to_csv(OUT / f"frequencies_{field}.csv", index=False)

    reference = ROOT / "docs" / "reference"
    call_codes = pd.read_csv(reference / "call_type_descriptions.csv", dtype=str)
    disposition_codes = pd.read_csv(reference / "incident_disposition_codes.csv", dtype=str)
    codebook_codes = {
        "initial_call_type": set(call_codes["code"].str.strip()),
        "final_call_type": set(call_codes["code"].str.strip()),
        "incident_disposition_code": set(disposition_codes["code"].str.strip()),
    }
    codebook_checks = {}
    unmapped_rows = []
    for field, allowed in codebook_codes.items():
        unmatched = [(value, count) for value, count in categories[field].items() if value.strip() not in allowed]
        codebook_checks[field] = {"unmapped_category_count": len(unmatched), "unmapped_row_count": sum(count for _, count in unmatched)}
        unmapped_rows.extend({"field": field, "source_value": value, "count": count}
                             for value, count in sorted(unmatched, key=lambda x: (-x[1], x[0])))
    pd.DataFrame(unmapped_rows, columns=["field", "source_value", "count"]).to_csv(OUT / "unmapped_documented_codes.csv", index=False)

    monthly_rows = [{"month": key, "incident_count": count} for key, count in sorted(monthly.items())]
    quarterly_rows = [{"quarter": key, "incident_count": count} for key, count in sorted(quarterly.items())]
    daily_rows = [{"date": key, "incident_count": count} for key, count in sorted(daily.items())]
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_rows = [{"day_of_week": key, "incident_count": weekday[key]} for key in weekday_order]
    weekday_rows += ([{"day_of_week": "INVALID", "incident_count": weekday["INVALID"]}]
                     if weekday["INVALID"] else [])
    hourly_rows = [{"hour": int(key), "incident_count": hourly[key]} for key in sorted(hourly, key=lambda k: 99 if k == "INVALID" else int(k))]
    pd.DataFrame(monthly_rows).to_csv(OUT / "incidents_by_month.csv", index=False)
    pd.DataFrame(quarterly_rows).to_csv(OUT / "incidents_by_quarter.csv", index=False)
    pd.DataFrame(daily_rows).to_csv(OUT / "incidents_by_day.csv", index=False)
    pd.DataFrame(weekday_rows).to_csv(OUT / "incidents_by_weekday.csv", index=False)
    pd.DataFrame(hourly_rows).to_csv(OUT / "incidents_by_hour.csv", index=False)
    pd.DataFrame([{"borough": k[0], "month": k[1], "incident_count": v}
                  for k, v in sorted(borough_month.items())]).to_csv(OUT / "incidents_by_borough_month.csv", index=False)
    pd.DataFrame([{"initial_severity": k[0], "final_severity": k[1], "incident_count": v}
                  for k, v in sorted(severity_transitions.items())]).to_csv(OUT / "severity_transitions.csv", index=False)
    pd.DataFrame([{"severity_change": k, "incident_count": v} for k, v in severity_change.items()])\
        .to_csv(OUT / "severity_change_counts.csv", index=False)
    pd.DataFrame([{"severity_change": k[0], "disposition": k[1], "incident_count": v}
                  for k, v in sorted(severity_change_disposition.items())]).to_csv(OUT / "severity_change_by_disposition.csv", index=False)
    response_output_fields = {
        "borough": ["borough"], "initial_call_type": ["initial_call_type"],
        "borough_initial_call_type": ["borough", "initial_call_type"],
        "severity_transition": ["initial_severity", "final_severity"],
    }
    for result_name, key_fields in response_output_fields.items():
        records = [{**dict(zip(key_fields, key)), "valid_response_count": count,
                    "average_response_seconds": group_response_sum[result_name][key] / count}
                   for key, count in group_response_count[result_name].items() if count]
        pd.DataFrame(records).to_csv(OUT / f"response_by_{result_name}.csv", index=False)

    timestamp_failures = {
        pair: {"comparable_rows": int(event_pair_counts[pair]), "out_of_order_rows": int(event_pair_out_of_order[pair])}
        for pair in event_pair_counts
    }
    summary = {
        "rows": rows, "files": len(RAW), "source_fields": list(pd.read_csv(RAW[0], nrows=0).columns),
        "missing_values": {field: {"count": int(count), "percent": count / rows * 100}
                           for field, count in sorted(blank_counts.items()) if count},
        "exact_duplicate_rows": 0 if exact_duplicate_ids == 0 and blank_counts.get("incident_id", 0) == 0 else None,
        "logical_duplicate_incident_ids": int(exact_duplicate_ids),
        "duplicate_note": "An incident_id repeated within or across pages is counted as a logical duplicate. Exact row duplicates are subsumed by this key check because incident_id is part of every full record; no repeated IDs were found.",
        "timestamp_order_checks": timestamp_failures,
        "rows_with_any_timestamp_order_issue": int(out_of_order_rows_any_pair),
        "invalid_nonblank_timestamp_values": {field: int(count) for field, count in timestamp_invalid_nonblank.items()},
        "invalid_nonblank_numeric_values": {field: int(count) for field, count in numeric_invalid_nonblank.items()},
        "negative_numeric_counts": {field: int(count) for field, count in numeric_negative.items()},
        "zero_numeric_counts": {field: int(count) for field, count in numeric_zero.items()},
        "category_values_with_surrounding_whitespace": {field: int(count) for field, count in padded_categories.items() if count},
        "documented_duration_reconciliation": {
            measure: {"rows_compared": int(duration_comparisons[measure]),
                      "differences_over_1_second": int(duration_mismatches[measure]),
                      "mean_absolute_difference_seconds": float(np.concatenate(duration_abs_difference[measure]).mean()) if duration_abs_difference[measure] else None,
                      "maximum_absolute_difference_seconds": float(np.concatenate(duration_abs_difference[measure]).max()) if duration_abs_difference[measure] else None}
            for measure in duration_comparisons
        },
        "numeric_measures": numeric_summary,
        "timing_by_validity_flag": validity_summary,
        "source_codebook_checks": codebook_checks,
        "severity_change_counts": dict(severity_change),
        "top_categories": {field: values[:20] for field, values in category_tables.items()},
        "temporal_peak_low": {
            "busiest_month": max((x for x in monthly_rows if x["month"] != "INVALID"), key=lambda x: x["incident_count"], default=None),
            "quietest_month": min((x for x in monthly_rows if x["month"] != "INVALID"), key=lambda x: x["incident_count"], default=None),
            "incidents_by_weekday": weekday_rows, "incidents_by_hour": hourly_rows,
            "incidents_by_quarter": quarterly_rows,
        },
    }
    (OUT / "raw_profile_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    # Compact figures used in the milestone report.
    monthly_df = pd.DataFrame(monthly_rows)
    plt.figure(figsize=(13, 4.5))
    plt.plot(monthly_df["month"], monthly_df["incident_count"], marker="o", linewidth=1.3)
    plt.xticks(rotation=60, ha="right")
    plt.ylabel("Incidents")
    plt.title("EMS incidents by month (source records)")
    plt.tight_layout()
    plt.savefig(FIG / "incidents_by_month.png", dpi=160)
    plt.close()

    fig, axes = plt.subplots(1, len(NUMERIC_MEASURES), figsize=(14, 4.5))
    for axis, field in zip(axes, NUMERIC_MEASURES):
        if field in validity_values:
            valid_arrays = validity_values[field]["Y"]
            values = np.concatenate(valid_arrays) if valid_arrays else np.array([], dtype=np.float64)
        else:
            values = measure_values[field]
        if len(values):
            axis.hist(np.log1p(values), bins=80, color="#2878B5", alpha=0.85)
            axis.set_title(field.replace("_", " "), fontsize=9)
            axis.set_xlabel("log(1 + seconds)")
            axis.set_ylabel("Records")
    fig.suptitle("Dispatch and response times with source validity flag Y; travel time uses nonblank source values")
    fig.tight_layout()
    fig.savefig(FIG / "response_time_histograms.png", dpi=160)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(9, 4.5))
    plot_values = [
        np.log1p(np.concatenate(validity_values[field]["Y"])) if field in validity_values
        else np.log1p(measure_values[field])
        for field in NUMERIC_MEASURES
    ]
    axis.boxplot(plot_values,
                 tick_labels=[field.replace("_seconds_qy", "").replace("_", " ") for field in NUMERIC_MEASURES],
                 showfliers=False, patch_artist=True)
    axis.set_ylabel("log(1 + seconds)")
    axis.set_title("Response-time measures (log scale; fliers hidden for readability)")
    fig.tight_layout()
    fig.savefig(FIG / "response_time_boxplots.png", dpi=160)
    plt.close(fig)

    print(json.dumps({"rows": rows, "logical_duplicate_incident_ids": exact_duplicate_ids,
                      "outputs": ["raw_profile_summary.json", "numeric_summary.csv", "missing_values.csv", "timing_by_validity_flag.csv", "unmapped_documented_codes.csv"]}, indent=2))


if __name__ == "__main__":
    main()
