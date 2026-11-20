# Curated dataset notes

The curated copy is `data/curated/ems_incident_dispatch_curated_2024-01_to_2026-06.csv.gz`. It contains all **4,035,659** incident rows, all **31 source fields**, and four quality flags. The source files in `data/raw/` were not changed.

## Changes

| Field / check | Rule |
|---|---|
| Numeric source fields | Parse the three seconds measures and five numeric district fields as numeric values. Keep incident IDs and category codes as text. |
| `dispatch_response_seconds_qy` | Set to missing only for the 98,709 rows where `valid_dispatch_rspns_time_indc = 'N'`. The source value is `0` on all of these rows. The original zero remains in raw data. Keep 36,058 zero values where the validity flag is `Y`. |
| `timestamp_order_issue` | `True` if any adjacent pair of recorded operational timestamps is out of order; otherwise `False`. This flags 14,941 rows. No timestamp is changed. |
| `dispatch_response_iqr_outlier` | `True` for a valid dispatch response above 214 seconds. This is the upper Tukey fence Q3 + 1.5 x IQR, calculated among rows with a `Y` validity flag. |
| `incident_response_iqr_outlier` | `True` for a valid incident response above 1,771 seconds. This is the upper Tukey fence among rows with a `Y` validity flag. |
| `incident_travel_tm_iqr_outlier` | `True` for travel time above 1,354.5 seconds. This is the upper Tukey fence among nonblank source values. |
| Other blanks, unknowns and code values | Preserve them. No rows are removed, and no missing values are imputed. Values absent from the attached official codebook are retained unchanged. |

The IQR flags help inspect the right-tailed distributions; they are not operational response-time bands. The values are retained. `reports/curation_summary.json` and `reports/curated_verification_summary.json` show the before/after row-count reconciliation and validation results.

## Loading

```python
import pandas as pd

for chunk in pd.read_csv(
    "data/curated/ems_incident_dispatch_curated_2024-01_to_2026-06.csv.gz",
    compression="gzip",
    chunksize=200_000,
):
    # use chunk for later analysis or warehouse loading
    pass
```
