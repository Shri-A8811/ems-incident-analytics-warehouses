# Milestone 6 — OLAP analysis

## Purpose

Show how users can summarize EMS demand at different levels, focus on selected parts of the data, and compare categories using the PostgreSQL warehouse.

## Prepared work

`sql/olap_analysis.sql` contains executable examples for all required operations:

- Roll-up: month and borough detail to larger totals.
- Drill-down: borough totals to monthly detail for one borough.
- Slice: one year of incidents.
- Dice: a date range, selected boroughs, and selected call types.
- Pivot: boroughs presented as separate columns by year.
- `CUBE`: all subtotal combinations for year, borough, and initial call type.
- `GROUPING SETS`: selected monthly, yearly, and grand totals.

Response-time averages use only source-valid, non-null measurements and show the corresponding valid sample count.

## Verification status

All seven OLAP sections ran successfully against PostgreSQL 16.15 with `ON_ERROR_STOP=1`; the command exited successfully and no SQL errors were found. The fact table contained 4,035,659 incidents. Query output and timings are saved in `reports/olap_query_results.txt`.

| Operation | Result rows | Run time |
|---|---:|---:|
| Roll-up | 195 | 92.196 sec |
| Drill-down (Brooklyn, month) | 30 | 209.107 sec |
| Slice (2025) | 66 | 39.305 sec |
| Dice (2025, Brooklyn/Queens, INJURY/SICK) | 48 | 21.338 sec |
| Pivot (year by borough) | 3 | 40.669 sec in full run; corrected rerun 26.177 sec |
| CUBE (year, borough, initial call type) | 2,451 | 100.689 sec |
| GROUPING SETS | 195 | 88.579 sec |

During review, the source's Staten Island category was found to be named `RICHMOND / STATEN ISLAND`. The pivot query now uses the actual source label. Its corrected standalone output is saved in `reports/olap_pivot_results.txt` and supersedes the pivot block in the full run log. The corrected pivot accounts for all 4,035,659 incidents across the three years, including the small other/missing category.

**Milestone 6 is complete.**

## How to run

1. Start Docker Desktop.
2. In PowerShell, open `D:\EDA Project` and run:

   ```powershell
   docker compose --env-file .env up -d postgres
   Get-Content sql/olap_analysis.sql | docker exec -i ems-postgres-batch psql -U ems_admin -d ems_dw -v ON_ERROR_STOP=1
   ```

3. The execution evidence is already saved in `reports/olap_query_results.txt`; the corrected pivot is in `reports/olap_pivot_results.txt`. The Dice example uses common source call-type codes `INJURY` and `SICK`.

The CUBE query returns 2,451 rows because it includes subtotal combinations across years, boroughs, and call types.
