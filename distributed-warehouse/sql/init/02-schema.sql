CREATE TABLE stg_ems_incident (
    incident_id TEXT PRIMARY KEY,
    incident_datetime TEXT,
    initial_call_type TEXT,
    initial_severity_level_code TEXT,
    final_call_type TEXT,
    final_severity_level_code TEXT,
    first_assignment_datetime TEXT,
    valid_dispatch_rspns_time_indc TEXT,
    dispatch_response_seconds_qy TEXT,
    first_activation_datetime TEXT,
    first_on_scene_datetime TEXT,
    valid_incident_rspns_time_indc TEXT,
    incident_response_seconds_qy TEXT,
    incident_travel_tm_seconds_qy TEXT,
    first_to_hosp_datetime TEXT,
    first_hosp_arrival_datetime TEXT,
    incident_close_datetime TEXT,
    held_indicator TEXT,
    incident_disposition_code TEXT,
    borough TEXT,
    incident_dispatch_area TEXT,
    zipcode TEXT,
    policeprecinct TEXT,
    citycouncildistrict TEXT,
    communitydistrict TEXT,
    communityschooldistrict TEXT,
    congressionaldistrict TEXT,
    reopen_indicator TEXT,
    special_event_indicator TEXT,
    standby_indicator TEXT,
    transfer_indicator TEXT
);

CREATE TABLE etl_batch (
    batch_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_file TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    staged_row_count INTEGER NOT NULL,
    fact_row_count INTEGER NOT NULL
);

CREATE TABLE dim_date (
    date_key DATE PRIMARY KEY,
    year SMALLINT NOT NULL,
    quarter SMALLINT NOT NULL,
    month SMALLINT NOT NULL,
    day SMALLINT NOT NULL,
    day_of_week SMALLINT NOT NULL
);
SELECT create_reference_table('dim_date');

CREATE TABLE dim_geography (
    geography_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    borough TEXT NOT NULL,
    dispatch_area TEXT NOT NULL,
    zipcode TEXT NOT NULL,
    police_precinct TEXT NOT NULL,
    city_council_district TEXT NOT NULL,
    community_district TEXT NOT NULL,
    community_school_district TEXT NOT NULL,
    congressional_district TEXT NOT NULL,
    CONSTRAINT uq_dim_geography UNIQUE (
        borough, dispatch_area, zipcode, police_precinct,
        city_council_district, community_district,
        community_school_district, congressional_district
    )
);
SELECT create_reference_table('dim_geography');

CREATE TABLE dim_call_type (
    call_type_key INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    call_type_code TEXT NOT NULL UNIQUE
);
SELECT create_reference_table('dim_call_type');

CREATE TABLE dim_severity (
    severity_key INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    severity_level_code TEXT NOT NULL UNIQUE
);
SELECT create_reference_table('dim_severity');

CREATE TABLE dim_disposition (
    disposition_code TEXT PRIMARY KEY
);
SELECT create_reference_table('dim_disposition');

CREATE TABLE fact_incident (
    incident_id BIGINT NOT NULL,
    date_key DATE NOT NULL REFERENCES dim_date(date_key),
    geography_key BIGINT NOT NULL REFERENCES dim_geography(geography_key),
    initial_call_type_key INTEGER NOT NULL REFERENCES dim_call_type(call_type_key),
    final_call_type_key INTEGER NOT NULL REFERENCES dim_call_type(call_type_key),
    initial_severity_key INTEGER NOT NULL REFERENCES dim_severity(severity_key),
    final_severity_key INTEGER NOT NULL REFERENCES dim_severity(severity_key),
    disposition_code TEXT NOT NULL REFERENCES dim_disposition(disposition_code),
    incident_count SMALLINT NOT NULL DEFAULT 1 CHECK (incident_count = 1),
    dispatch_response_seconds INTEGER,
    dispatch_response_valid_flag TEXT NOT NULL,
    dispatch_response_usable BOOLEAN NOT NULL,
    incident_response_seconds INTEGER,
    incident_response_valid_flag TEXT NOT NULL,
    incident_response_usable BOOLEAN NOT NULL,
    incident_travel_seconds INTEGER,
    incident_travel_usable BOOLEAN NOT NULL,
    timestamp_order_ok BOOLEAN NOT NULL,
    PRIMARY KEY (incident_id)
);
SELECT create_distributed_table('fact_incident', 'incident_id', shard_count => 4);

CREATE VIEW vw_incident_response_by_borough_month_initial_call AS
SELECT
    g.borough,
    date_trunc('month', f.date_key)::date AS incident_month,
    ct.call_type_code AS initial_call_type,
    COUNT(*) AS incident_count,
    COUNT(*) FILTER (WHERE f.dispatch_response_usable) AS valid_dispatch_count,
    ROUND(AVG(f.dispatch_response_seconds) FILTER (WHERE f.dispatch_response_usable), 2)
        AS avg_dispatch_response_seconds,
    COUNT(*) FILTER (WHERE f.incident_response_usable) AS valid_incident_response_count,
    ROUND(AVG(f.incident_response_seconds) FILTER (WHERE f.incident_response_usable), 2)
        AS avg_incident_response_seconds,
    COUNT(*) FILTER (WHERE f.incident_travel_usable) AS valid_travel_count,
    ROUND(AVG(f.incident_travel_seconds) FILTER (WHERE f.incident_travel_usable), 2)
        AS avg_incident_travel_seconds
FROM fact_incident AS f
JOIN dim_geography AS g USING (geography_key)
JOIN dim_call_type AS ct ON ct.call_type_key = f.initial_call_type_key
GROUP BY g.borough, date_trunc('month', f.date_key)::date, ct.call_type_code;
