WITH parsed AS (
    SELECT
        incident_id::BIGINT AS incident_id,
        to_timestamp(incident_datetime, 'MM/DD/YYYY HH12:MI:SS AM')::DATE AS date_key,
        COALESCE(NULLIF(BTRIM(borough), ''), 'UNKNOWN') AS borough,
        COALESCE(NULLIF(BTRIM(incident_dispatch_area), ''), 'UNKNOWN') AS dispatch_area,
        COALESCE(NULLIF(BTRIM(zipcode), ''), 'UNKNOWN') AS zipcode,
        COALESCE(NULLIF(BTRIM(policeprecinct), ''), 'UNKNOWN') AS police_precinct,
        COALESCE(NULLIF(BTRIM(citycouncildistrict), ''), 'UNKNOWN') AS city_council_district,
        COALESCE(NULLIF(BTRIM(communitydistrict), ''), 'UNKNOWN') AS community_district,
        COALESCE(NULLIF(BTRIM(communityschooldistrict), ''), 'UNKNOWN') AS community_school_district,
        COALESCE(NULLIF(BTRIM(congressionaldistrict), ''), 'UNKNOWN') AS congressional_district,
        COALESCE(NULLIF(BTRIM(initial_call_type), ''), 'UNKNOWN') AS initial_call_type,
        COALESCE(NULLIF(BTRIM(final_call_type), ''), 'UNKNOWN') AS final_call_type,
        COALESCE(NULLIF(BTRIM(initial_severity_level_code), ''), 'UNKNOWN') AS initial_severity,
        COALESCE(NULLIF(BTRIM(final_severity_level_code), ''), 'UNKNOWN') AS final_severity,
        COALESCE(NULLIF(BTRIM(incident_disposition_code), ''), 'UNKNOWN') AS disposition_code,
        NULLIF(REPLACE(BTRIM(dispatch_response_seconds_qy), ',', ''), '')::INTEGER AS dispatch_seconds,
        NULLIF(BTRIM(valid_dispatch_rspns_time_indc), '') AS dispatch_valid_flag,
        NULLIF(REPLACE(BTRIM(incident_response_seconds_qy), ',', ''), '')::INTEGER AS incident_response_seconds,
        NULLIF(BTRIM(valid_incident_rspns_time_indc), '') AS incident_valid_flag,
        NULLIF(REPLACE(BTRIM(incident_travel_tm_seconds_qy), ',', ''), '')::INTEGER AS travel_seconds,
        to_timestamp(incident_datetime, 'MM/DD/YYYY HH12:MI:SS AM')::TIMESTAMP AS incident_ts,
        to_timestamp(first_assignment_datetime, 'MM/DD/YYYY HH12:MI:SS AM')::TIMESTAMP AS assignment_ts,
        to_timestamp(NULLIF(first_activation_datetime, ''), 'MM/DD/YYYY HH12:MI:SS AM')::TIMESTAMP AS activation_ts,
        to_timestamp(NULLIF(first_on_scene_datetime, ''), 'MM/DD/YYYY HH12:MI:SS AM')::TIMESTAMP AS on_scene_ts,
        to_timestamp(NULLIF(first_to_hosp_datetime, ''), 'MM/DD/YYYY HH12:MI:SS AM')::TIMESTAMP AS to_hospital_ts,
        to_timestamp(NULLIF(first_hosp_arrival_datetime, ''), 'MM/DD/YYYY HH12:MI:SS AM')::TIMESTAMP AS hospital_arrival_ts,
        to_timestamp(incident_close_datetime, 'MM/DD/YYYY HH12:MI:SS AM')::TIMESTAMP AS close_ts
    FROM stg_ems_incident
), normalized AS (
    SELECT *,
        dispatch_valid_flag = 'Y' AND dispatch_seconds IS NOT NULL AND dispatch_seconds >= 0
            AS dispatch_usable,
        incident_valid_flag = 'Y' AND incident_response_seconds IS NOT NULL AND incident_response_seconds >= 0
            AS incident_response_usable,
        travel_seconds IS NOT NULL AND travel_seconds >= 0 AS travel_usable,
        (assignment_ts IS NULL OR incident_ts IS NULL OR assignment_ts >= incident_ts)
        AND (activation_ts IS NULL OR assignment_ts IS NULL OR activation_ts >= assignment_ts)
        AND (on_scene_ts IS NULL OR activation_ts IS NULL OR on_scene_ts >= activation_ts)
        AND (to_hospital_ts IS NULL OR on_scene_ts IS NULL OR to_hospital_ts >= on_scene_ts)
        AND (hospital_arrival_ts IS NULL OR to_hospital_ts IS NULL OR hospital_arrival_ts >= to_hospital_ts)
        AND (close_ts IS NULL OR hospital_arrival_ts IS NULL OR close_ts >= hospital_arrival_ts)
            AS timestamp_order_ok
    FROM parsed
)
INSERT INTO dim_date (date_key, year, quarter, month, day, day_of_week)
SELECT DISTINCT
    date_key,
    EXTRACT(YEAR FROM date_key)::SMALLINT,
    EXTRACT(QUARTER FROM date_key)::SMALLINT,
    EXTRACT(MONTH FROM date_key)::SMALLINT,
    EXTRACT(DAY FROM date_key)::SMALLINT,
    EXTRACT(ISODOW FROM date_key)::SMALLINT
FROM normalized
ON CONFLICT (date_key) DO NOTHING;

WITH parsed AS (
    SELECT
        COALESCE(NULLIF(BTRIM(borough), ''), 'UNKNOWN') AS borough,
        COALESCE(NULLIF(BTRIM(incident_dispatch_area), ''), 'UNKNOWN') AS dispatch_area,
        COALESCE(NULLIF(BTRIM(zipcode), ''), 'UNKNOWN') AS zipcode,
        COALESCE(NULLIF(BTRIM(policeprecinct), ''), 'UNKNOWN') AS police_precinct,
        COALESCE(NULLIF(BTRIM(citycouncildistrict), ''), 'UNKNOWN') AS city_council_district,
        COALESCE(NULLIF(BTRIM(communitydistrict), ''), 'UNKNOWN') AS community_district,
        COALESCE(NULLIF(BTRIM(communityschooldistrict), ''), 'UNKNOWN') AS community_school_district,
        COALESCE(NULLIF(BTRIM(congressionaldistrict), ''), 'UNKNOWN') AS congressional_district
    FROM stg_ems_incident
)
INSERT INTO dim_geography (
    borough, dispatch_area, zipcode, police_precinct, city_council_district,
    community_district, community_school_district, congressional_district
)
SELECT DISTINCT borough, dispatch_area, zipcode, police_precinct, city_council_district,
       community_district, community_school_district, congressional_district
FROM parsed
ON CONFLICT ON CONSTRAINT uq_dim_geography DO NOTHING;

INSERT INTO dim_call_type (call_type_code)
SELECT DISTINCT COALESCE(NULLIF(BTRIM(initial_call_type), ''), 'UNKNOWN')
FROM stg_ems_incident
UNION
SELECT DISTINCT COALESCE(NULLIF(BTRIM(final_call_type), ''), 'UNKNOWN')
FROM stg_ems_incident
ON CONFLICT (call_type_code) DO NOTHING;

INSERT INTO dim_severity (severity_level_code)
SELECT DISTINCT COALESCE(NULLIF(BTRIM(initial_severity_level_code), ''), 'UNKNOWN')
FROM stg_ems_incident
UNION
SELECT DISTINCT COALESCE(NULLIF(BTRIM(final_severity_level_code), ''), 'UNKNOWN')
FROM stg_ems_incident
ON CONFLICT (severity_level_code) DO NOTHING;

INSERT INTO dim_disposition (disposition_code)
SELECT DISTINCT COALESCE(NULLIF(BTRIM(incident_disposition_code), ''), 'UNKNOWN')
FROM stg_ems_incident
ON CONFLICT (disposition_code) DO NOTHING;

WITH parsed AS (
    SELECT
        incident_id::BIGINT AS incident_id,
        to_timestamp(incident_datetime, 'MM/DD/YYYY HH12:MI:SS AM')::DATE AS date_key,
        COALESCE(NULLIF(BTRIM(borough), ''), 'UNKNOWN') AS borough,
        COALESCE(NULLIF(BTRIM(incident_dispatch_area), ''), 'UNKNOWN') AS dispatch_area,
        COALESCE(NULLIF(BTRIM(zipcode), ''), 'UNKNOWN') AS zipcode,
        COALESCE(NULLIF(BTRIM(policeprecinct), ''), 'UNKNOWN') AS police_precinct,
        COALESCE(NULLIF(BTRIM(citycouncildistrict), ''), 'UNKNOWN') AS city_council_district,
        COALESCE(NULLIF(BTRIM(communitydistrict), ''), 'UNKNOWN') AS community_district,
        COALESCE(NULLIF(BTRIM(communityschooldistrict), ''), 'UNKNOWN') AS community_school_district,
        COALESCE(NULLIF(BTRIM(congressionaldistrict), ''), 'UNKNOWN') AS congressional_district,
        COALESCE(NULLIF(BTRIM(initial_call_type), ''), 'UNKNOWN') AS initial_call_type,
        COALESCE(NULLIF(BTRIM(final_call_type), ''), 'UNKNOWN') AS final_call_type,
        COALESCE(NULLIF(BTRIM(initial_severity_level_code), ''), 'UNKNOWN') AS initial_severity,
        COALESCE(NULLIF(BTRIM(final_severity_level_code), ''), 'UNKNOWN') AS final_severity,
        COALESCE(NULLIF(BTRIM(incident_disposition_code), ''), 'UNKNOWN') AS disposition_code,
        NULLIF(REPLACE(BTRIM(dispatch_response_seconds_qy), ',', ''), '')::INTEGER AS dispatch_seconds,
        NULLIF(BTRIM(valid_dispatch_rspns_time_indc), '') AS dispatch_valid_flag,
        NULLIF(REPLACE(BTRIM(incident_response_seconds_qy), ',', ''), '')::INTEGER AS incident_response_seconds,
        NULLIF(BTRIM(valid_incident_rspns_time_indc), '') AS incident_valid_flag,
        NULLIF(REPLACE(BTRIM(incident_travel_tm_seconds_qy), ',', ''), '')::INTEGER AS travel_seconds,
        to_timestamp(incident_datetime, 'MM/DD/YYYY HH12:MI:SS AM')::TIMESTAMP AS incident_ts,
        to_timestamp(first_assignment_datetime, 'MM/DD/YYYY HH12:MI:SS AM')::TIMESTAMP AS assignment_ts,
        to_timestamp(NULLIF(first_activation_datetime, ''), 'MM/DD/YYYY HH12:MI:SS AM')::TIMESTAMP AS activation_ts,
        to_timestamp(NULLIF(first_on_scene_datetime, ''), 'MM/DD/YYYY HH12:MI:SS AM')::TIMESTAMP AS on_scene_ts,
        to_timestamp(NULLIF(first_to_hosp_datetime, ''), 'MM/DD/YYYY HH12:MI:SS AM')::TIMESTAMP AS to_hospital_ts,
        to_timestamp(NULLIF(first_hosp_arrival_datetime, ''), 'MM/DD/YYYY HH12:MI:SS AM')::TIMESTAMP AS hospital_arrival_ts,
        to_timestamp(incident_close_datetime, 'MM/DD/YYYY HH12:MI:SS AM')::TIMESTAMP AS close_ts
    FROM stg_ems_incident
), normalized AS (
    SELECT *,
        dispatch_valid_flag = 'Y' AND dispatch_seconds IS NOT NULL AND dispatch_seconds >= 0 AS dispatch_usable,
        incident_valid_flag = 'Y' AND incident_response_seconds IS NOT NULL AND incident_response_seconds >= 0 AS incident_response_usable,
        travel_seconds IS NOT NULL AND travel_seconds >= 0 AS travel_usable,
        (assignment_ts IS NULL OR incident_ts IS NULL OR assignment_ts >= incident_ts)
        AND (activation_ts IS NULL OR assignment_ts IS NULL OR activation_ts >= assignment_ts)
        AND (on_scene_ts IS NULL OR activation_ts IS NULL OR on_scene_ts >= activation_ts)
        AND (to_hospital_ts IS NULL OR on_scene_ts IS NULL OR to_hospital_ts >= on_scene_ts)
        AND (hospital_arrival_ts IS NULL OR to_hospital_ts IS NULL OR hospital_arrival_ts >= to_hospital_ts)
        AND (close_ts IS NULL OR hospital_arrival_ts IS NULL OR close_ts >= hospital_arrival_ts) AS timestamp_order_ok
    FROM parsed
)
INSERT INTO fact_incident (
    incident_id, date_key, geography_key,
    initial_call_type_key, final_call_type_key,
    initial_severity_key, final_severity_key, disposition_code, incident_count,
    dispatch_response_seconds, dispatch_response_valid_flag, dispatch_response_usable,
    incident_response_seconds, incident_response_valid_flag, incident_response_usable,
    incident_travel_seconds, incident_travel_usable, timestamp_order_ok
)
SELECT
    p.incident_id, p.date_key, g.geography_key,
    ict.call_type_key, fct.call_type_key, ise.severity_key, fse.severity_key,
    p.disposition_code, 1,
    p.dispatch_seconds, COALESCE(p.dispatch_valid_flag, 'N'), p.dispatch_usable,
    p.incident_response_seconds, COALESCE(p.incident_valid_flag, 'N'), p.incident_response_usable,
    p.travel_seconds, p.travel_usable, p.timestamp_order_ok
FROM normalized AS p
JOIN dim_geography AS g USING (
    borough, dispatch_area, zipcode, police_precinct, city_council_district,
    community_district, community_school_district, congressional_district
)
JOIN dim_call_type AS ict ON ict.call_type_code = p.initial_call_type
JOIN dim_call_type AS fct ON fct.call_type_code = p.final_call_type
JOIN dim_severity AS ise ON ise.severity_level_code = p.initial_severity
JOIN dim_severity AS fse ON fse.severity_level_code = p.final_severity
ON CONFLICT (incident_id) DO UPDATE SET
    date_key = EXCLUDED.date_key,
    geography_key = EXCLUDED.geography_key,
    initial_call_type_key = EXCLUDED.initial_call_type_key,
    final_call_type_key = EXCLUDED.final_call_type_key,
    initial_severity_key = EXCLUDED.initial_severity_key,
    final_severity_key = EXCLUDED.final_severity_key,
    disposition_code = EXCLUDED.disposition_code,
    dispatch_response_seconds = EXCLUDED.dispatch_response_seconds,
    dispatch_response_valid_flag = EXCLUDED.dispatch_response_valid_flag,
    dispatch_response_usable = EXCLUDED.dispatch_response_usable,
    incident_response_seconds = EXCLUDED.incident_response_seconds,
    incident_response_valid_flag = EXCLUDED.incident_response_valid_flag,
    incident_response_usable = EXCLUDED.incident_response_usable,
    incident_travel_seconds = EXCLUDED.incident_travel_seconds,
    incident_travel_usable = EXCLUDED.incident_travel_usable,
    timestamp_order_ok = EXCLUDED.timestamp_order_ok;
