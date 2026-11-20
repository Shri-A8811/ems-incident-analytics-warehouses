# Dataset source and acquisition record

## Source

- **Dataset:** EMS Incident Dispatch Data
- **Publisher:** Fire Department of New York City (FDNY), published on NYC Open Data
- **Official dataset page:** <https://data.cityofnewyork.us/Public-Safety/EMS-Incident-Dispatch-Data/76xm-jjuj>
- **Socrata API:** <https://data.cityofnewyork.us/resource/76xm-jjuj.json>
- **FDNY field and code descriptions:** [official dataset attachment](https://data.cityofnewyork.us/api/views/76xm-jjuj/files/1f3c87df-ffa3-4bda-a63c-45aeac003a26?download=true&filename=EMS_incident_dispatch_data_description.xlsx), saved as `docs/reference/EMS_incident_dispatch_data_description.xlsx` on 2026-10-28. The call type and disposition sheets were also extracted to CSV files beside the workbook.
- **API dataset identifier:** `76xm-jjuj`
- **Extraction date:** 2026-10-28 (Asia/Calcutta)
- **Source data last updated:** Metadata `rowsUpdatedAt` value was `1791384138` (Unix epoch seconds), retrieved from the official Socrata metadata API on 2026-10-28.

## Selected period and extraction

- **Start, inclusive:** 2024-01-01 00:00:00
- **End, exclusive:** 2026-07-01 00:00:00
- **Filter:** `incident_datetime >= '2024-01-01T00:00:00' AND incident_datetime < '2026-07-01T00:00:00'`
- **Expected matching rows from API count query:** 4,035,659
- **Downloaded rows:** 4,035,659, verified by `verify_dataset.py`.
- **Fields:** All 31 fields exposed by the source at extraction time; see `data_dictionary.csv`.
- **Filters applied:** Only the incident timestamp range above. No sampling, category filters, cleaning, enrichment or derived fields were applied.
- **File format:** UTF-8 CSV pages of up to 500,000 records each, with a header per page.
- **Raw location:** `data/raw/ems_incident_dispatch_2024-01_to_2026-06_part*.csv`
- **Field selection / ordering:** Source default field set; source API order is retained to avoid an expensive server-side sort. Pages were fetched consecutively by offset.

## Verification record

The completed verification is saved in `verification_summary.json`. Results from streaming all nine files:

- **Downloaded rows:** 4,035,659, matching the API count query.
- **Raw CSV size:** 1,181,995,248 bytes across nine files (about 1.10 GiB).
- **Page sizes:** Eight pages of 500,000 rows and a final page of 35,659 rows.
- **Source fields:** 31; all nine pages have the same header.
- **Unique nonblank incident IDs:** 4,035,659; duplicate IDs: 0.
- **Incident timestamp coverage:** 2024-01-01 00:00:03 through 2026-06-30 23:59:34.
- **Missing or invalid incident timestamps:** 0; out-of-range timestamps: 0.
- **Rows with missing or extra CSV fields / malformed row widths:** 0.
- **Usability check:** Passed for the acquisition milestone. The verifier also records field-level blank counts; these are source missingness observations, not cleaning decisions.

The API count is an independent expected-count check. The verifier streams the raw files and records the actual row count, unique incident IDs, date coverage, field list and field-level blank counts.

The official attachment contains the field descriptions, call-type descriptions and incident-disposition descriptions. Extracted lookup CSVs are stored beside the workbook for use in the profile. It does not provide a complete severity-code mapping.

## Important provenance note

These are historical dispatch records from a public dataset. They are not a live feed. Any later streaming implementation must label chronological replay as a real-time simulation, as required by the assignment.
