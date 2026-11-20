# Data quality report - EMS Incident Dispatch Data

## Scope

This report profiles the untouched source files for incidents created from 2024-01-01 through 2026-06-30. The official FDNY source says each row represents an incident and provides definitions for the timing fields, response-validity flags, call types and dispositions. The official field-description workbook is saved under `docs/reference/` and is cited in `docs/dataset_source.md`.

The profile covers **4,035,659 rows** and all 31 source fields. It does not alter the raw data. Detailed counts are in `raw_profile_summary.json`, `missing_values.csv`, `numeric_summary.csv`, `timing_by_validity_flag.csv`, and `unmapped_documented_codes.csv`.

## Findings and decisions

| Check | Observed result | Treatment in curated copy |
|---|---|---|
| Missing incident IDs / repeated IDs | 0 blank IDs; 0 repeated IDs | Keep all incidents. No duplicate removal needed. Since the ID is the row key and every ID is unique, exact duplicate rows are also 0. |
| Missing incident creation timestamp | 0 | No action needed. |
| Invalid nonblank timestamps | 0 across the 7 timestamp fields | Keep original timestamps. |
| Event timestamps out of order | 14,941 incidents have at least one out-of-order pair; most are activation after on-scene (14,039 pair occurrences) | Keep the records and add `timestamp_order_issue`; do not swap or invent event times. |
| Missing assignment, activation or on-scene time | 97,784; 106,099; and 261,338 rows | Preserve blanks. Do not remove the incident. |
| Missing hospital times | 1,592,750 missing first-to-hospital and 1,603,431 missing hospital-arrival timestamps | Preserve blanks. These events do not apply to every dispatch. |
| Missing incident response seconds | 262,484 rows (6.50%); all have validity flag `N` | Preserve missing values and the source flag. Use only flag `Y` for response-time summaries. |
| Dispatch response marked invalid | 98,709 rows have flag `N`; every such row has `0` seconds | Set this measure to missing in the curated copy. Keep the `N` flag and original zero in the untouched raw files. |
| Valid dispatch response zeros | 36,058 rows with flag `Y` | Keep zero values. The source timestamps reconcile exactly to the recorded measure. |
| Other numerical fields | 0 nonnumeric values and 0 negative values in the 3 duration measures and 5 numeric district fields | No correction needed. Zero durations are retained and reported. |
| Source codebook coverage | 8 initial-call codes (39 rows) and 2 disposition codes (90 rows) do not appear in the attached official code list; all final-call codes are listed | Preserve the codes. Label them as not in the attached codebook. Do not call them invalid or silently replace them. |
| Categorical whitespace | No surrounding whitespace found in observed category values | No trimming needed. |
| Unknown borough | 15 rows use the source value `UNKNOWN` | Keep the source value. Map to an Unknown location member later if needed. |
| Extreme durations | Durations are right-skewed and have high maxima; all valid recorded durations match their source timestamp differences exactly | Keep values and add statistical IQR flags. Do not cap or delete a value based only on a statistical outlier rule. |

## Timing measures and outlier flags

Response-time statistics below use rows whose source validity indicator is `Y`. The IQR threshold is Q3 + 1.5 x IQR. It is a review flag, not an operational definition of a long response.

| Measure | Valid rows | Mean (s) | Median (s) | Min (s) | Max (s) | IQR threshold (s) | Rows flagged |
|---|---:|---:|---:|---:|---:|---:|---:|
| Dispatch response | 3,936,950 | 346.0 | 31 | 0 | 32,390 | 214.0 | 644,575 |
| Incident response | 3,773,175 | 976.5 | 571 | 0 | 32,396 | 1,771.0 | 393,796 |
| Travel time | 3,774,262 | 647.2 | 493 | 0 | 90,337 | 1,354.5 | 251,995 |

The full numerical profile also includes sample variance, sample standard deviation, Q1, Q3, IQR, skewness and excess kurtosis in `timing_by_validity_flag.csv` (dispatch/incident response) and `numeric_summary.csv` (all source values and travel time). For the valid dispatch population: variance 1,789,257 seconds squared, standard deviation 1,337.6 seconds, Q1 14, Q3 94, IQR 80, skewness 9.07 and excess kurtosis 118.62. For valid incident response: variance 2,416,762 seconds squared, standard deviation 1,554.6 seconds, Q1 381, Q3 937, IQR 556, skewness 7.05 and excess kurtosis 75.28. For travel time: variance 513,987 seconds squared, standard deviation 716.9 seconds, Q1 332, Q3 741, IQR 409, skewness 9.93 and excess kurtosis 252.87.

The source defines dispatch response as incident creation to first assignment, incident response as creation to first on-scene, and travel time as first assignment to first on-scene. Every checked duration matches the corresponding timestamp difference exactly. Negative durations were not found. The high IQR counts reflect strongly right-skewed distributions and are retained for review.

## Source code notes

- The source validity fields use `Y` and `N` only. For dispatch response, all 98,709 `N` rows carry zero seconds. The `Y` rows include 36,058 genuine zero-valued records.
- The official description file defines the call type and disposition codes, but does not document the severity-code meanings. Severity codes remain categorical source values; no numeric ordering or severity bands are inferred here.
- Call type is the classification entered for dispatch/resource allocation. The FDNY description cautions that it does not necessarily represent the patient's actual condition.
- The 39 initial-call and 90 disposition values absent from the attached codebook remain unchanged and are listed in `unmapped_documented_codes.csv`.

## Curated output rules

1. Keep every incident row and all 31 source columns.
2. Keep the raw pages unchanged.
3. Convert the eight numeric source fields to numeric values in the curated CSV; keep identifiers and category codes as text.
4. Set `dispatch_response_seconds_qy` to blank only when `valid_dispatch_rspns_time_indc = 'N'`.
5. Preserve all other source blanks and category values.
6. Add `timestamp_order_issue` and three upper-IQR outlier flags. Keep the underlying values unchanged.
7. Do not create a long-response label or response-time band in this milestone. Those thresholds belong to later modelling/feature-engineering work.

## Row-count reconciliation

The curation step does not drop rows: source and curated record counts must both equal 4,035,659. `curation_summary.json` records the final reconciliation and number of values changed to missing.
