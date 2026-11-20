# Data Dictionary and Measurement Rules

## Source snapshot

Source: `data/source/EMS_Incident_Dispatch_Data_20261015.csv`, FDNY EMS Incident Dispatch Data. It contains 1,310 rows with unique incident IDs and 31 source columns. The source file is retained unchanged.

## Raw staging table

`stg_ems_incident` contains all 31 source columns, mapped to lowercase field names and stored as `TEXT`. This preserves source codes, blank values, number formatting such as quoted thousands separators, and timestamp strings. The table's primary key is `incident_id`.

| Source fields | Meaning / use |
| --- | --- |
| `INCIDENT_ID`, `INCIDENT_DATETIME` | Stable incident identifier and incident time; the incident date populates `dim_date`. |
| `INITIAL_CALL_TYPE`, `FINAL_CALL_TYPE` | Source call type before and after review; both map to `dim_call_type` with separate fact keys. |
| `INITIAL_SEVERITY_LEVEL_CODE`, `FINAL_SEVERITY_LEVEL_CODE` | Source severity before and after review; both map to `dim_severity` with separate fact keys. |
| `FIRST_ASSIGNMENT_DATETIME`, `FIRST_ACTIVATION_DATETIME`, `FIRST_ON_SCENE_DATETIME` | Dispatch and response timeline inputs used for the quality-order flag. |
| `VALID_DISPATCH_RSPNS_TIME_INDC`, `DISPATCH_RESPONSE_SECONDS_QY` | Source dispatch-duration validity flag and dispatch duration. |
| `VALID_INCIDENT_RSPNS_TIME_INDC`, `INCIDENT_RESPONSE_SECONDS_QY` | Source incident-response validity flag and incident-response duration. |
| `INCIDENT_TRAVEL_TM_SECONDS_QY` | Travel duration. No travel-specific validity flag is present in the source. |
| `FIRST_TO_HOSP_DATETIME`, `FIRST_HOSP_ARRIVAL_DATETIME`, `INCIDENT_CLOSE_DATETIME` | Later incident timeline fields retained in staging and used in the timestamp-order check. |
| `HELD_INDICATOR`, `INCIDENT_DISPOSITION_CODE` | Source hold flag and disposition code; disposition values remain source codes. |
| `BOROUGH`, `INCIDENT_DISPATCH_AREA`, `ZIPCODE`, `POLICEPRECINCT`, `CITYCOUNCILDISTRICT`, `COMMUNITYDISTRICT`, `COMMUNITYSCHOOLDISTRICT`, `CONGRESSIONALDISTRICT` | Geography attributes combined in `dim_geography`. Blank values map to `UNKNOWN` in the curated dimension. |
| `REOPEN_INDICATOR`, `SPECIAL_EVENT_INDICATOR`, `STANDBY_INDICATOR`, `TRANSFER_INDICATOR` | Additional source indicators retained in staging for future analytics. |

## Curated dimensions

| Table | Key | Attributes |
| --- | --- | --- |
| `dim_date` | `date_key` (`DATE`) | Year, quarter, month, day, ISO day of week. Derived from `incident_datetime`. |
| `dim_geography` | `geography_key` | Borough, dispatch area, ZIP code, police precinct, city council, community, school, and congressional districts. |
| `dim_call_type` | `call_type_key` | Original call type code. Codes are preserved without invented descriptions. |
| `dim_severity` | `severity_key` | Original severity code. Codes are preserved without invented descriptions. |
| `dim_disposition` | `disposition_code` | Original disposition code, including nonnumeric source values. |

## Fact table

`fact_incident` has one row per `incident_id` and is hash-distributed on that key.

| Field | Definition |
| --- | --- |
| `date_key`, `geography_key` | Dimension links for incident date and location. |
| `initial_call_type_key`, `final_call_type_key` | Separate role-playing links to the call type dimension. |
| `initial_severity_key`, `final_severity_key` | Separate role-playing links to the severity dimension. |
| `disposition_code` | Source disposition code linked to its dimension. |
| `incident_count` | Constant 1, suitable for additive incident volume. |
| `dispatch_response_seconds` | Dispatch response duration as an integer number of seconds. |
| `dispatch_response_valid_flag` | Source validity flag (`Y`/`N`). |
| `dispatch_response_usable` | Derived true only when the source flag is `Y` and the duration is nonmissing and nonnegative. |
| `incident_response_seconds` | Incident response duration as an integer number of seconds. |
| `incident_response_valid_flag` | Source validity flag (`Y`/`N`). |
| `incident_response_usable` | Derived true only when the source flag is `Y` and the duration is nonmissing and nonnegative. |
| `incident_travel_seconds` | Travel duration as an integer number of seconds. |
| `incident_travel_usable` | Project-derived true when the travel duration is present and nonnegative; this is not an FDNY validity flag. |
| `timestamp_order_ok` | True when no consecutive present timestamps in the retained response/transport/close sequence run backwards. |

## Reporting rules

- Incident counts include all loaded incidents.
- Dispatch and incident-response averages filter to their respective `*_usable` flags. Their valid-value counts are reported beside the averages.
- Travel averages use the separate project-derived `incident_travel_usable` rule and report their own count.
- Values are stored and reported in seconds. Convert to minutes in a presentation layer only if clearly labeled.
- The source timestamps have no timezone suffix; the warehouse derives a date key and does not reinterpret them as UTC.
