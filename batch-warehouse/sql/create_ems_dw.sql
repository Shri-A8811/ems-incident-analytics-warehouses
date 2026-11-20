-- PostgreSQL batch warehouse schema for the EMS Dispatch assignment.
CREATE SCHEMA IF NOT EXISTS ems_dw;

CREATE TABLE IF NOT EXISTS ems_dw.dim_date (
    date_key integer PRIMARY KEY, -- YYYYMMDD; 0 is unknown
    full_date date UNIQUE,
    year_number smallint,
    quarter_number smallint,
    month_number smallint,
    month_name varchar(12),
    day_of_month smallint,
    day_of_week_number smallint,
    day_name varchar(12),
    is_weekend boolean
);

CREATE TABLE IF NOT EXISTS ems_dw.dim_time (
    time_key integer PRIMARY KEY, -- seconds after midnight + 1; 0 is unknown
    time_value time UNIQUE,
    hour_number smallint,
    minute_number smallint,
    second_number smallint,
    time_band varchar(12)
);

CREATE TABLE IF NOT EXISTS ems_dw.dim_location (
    location_key bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    borough text,
    incident_dispatch_area text,
    zipcode text,
    police_precinct integer,
    city_council_district integer,
    community_district integer,
    community_school_district integer,
    congressional_district integer,
    location_signature text UNIQUE
);
ALTER TABLE ems_dw.dim_location
    ADD COLUMN IF NOT EXISTS location_signature text;
UPDATE ems_dw.dim_location SET location_signature =
    jsonb_build_array(borough,incident_dispatch_area,zipcode,police_precinct,
      city_council_district,community_district,community_school_district,
      congressional_district)::text
WHERE location_signature IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_location_signature
    ON ems_dw.dim_location(location_signature);

CREATE TABLE IF NOT EXISTS ems_dw.dim_call_type (
    call_type_key bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_call_type_code text NOT NULL UNIQUE,
    call_type_description text
);

CREATE TABLE IF NOT EXISTS ems_dw.dim_severity (
    severity_key bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_severity_code text NOT NULL UNIQUE,
    source_description text
);

CREATE TABLE IF NOT EXISTS ems_dw.dim_disposition (
    disposition_key bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_disposition_code text NOT NULL UNIQUE,
    source_description text
);

CREATE TABLE IF NOT EXISTS ems_dw.stg_ems_incident (
    load_batch_id text NOT NULL,
    incident_id text NOT NULL,
    incident_datetime text,
    initial_call_type text,
    initial_severity_level_code text,
    final_call_type text,
    final_severity_level_code text,
    first_assignment_datetime text,
    valid_dispatch_rspns_time_indc text,
    dispatch_response_seconds_qy text,
    first_activation_datetime text,
    first_on_scene_datetime text,
    valid_incident_rspns_time_indc text,
    incident_response_seconds_qy text,
    incident_travel_tm_seconds_qy text,
    first_to_hosp_datetime text,
    first_hosp_arrival_datetime text,
    incident_close_datetime text,
    held_indicator text,
    incident_disposition_code text,
    borough text,
    incident_dispatch_area text,
    zipcode text,
    policeprecinct text,
    citycouncildistrict text,
    communitydistrict text,
    communityschooldistrict text,
    congressionaldistrict text,
    reopen_indicator text,
    special_event_indicator text,
    standby_indicator text,
    transfer_indicator text,
    timestamp_order_issue text,
    dispatch_response_iqr_outlier text,
    incident_response_iqr_outlier text,
    incident_travel_tm_iqr_outlier text,
    source_extract_name text NOT NULL,
    staged_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (load_batch_id, incident_id)
);

CREATE TABLE IF NOT EXISTS ems_dw.fact_ems_incident (
    incident_key bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id text NOT NULL UNIQUE,
    incident_date_key integer NOT NULL REFERENCES ems_dw.dim_date(date_key),
    assignment_date_key integer NOT NULL REFERENCES ems_dw.dim_date(date_key),
    activation_date_key integer NOT NULL REFERENCES ems_dw.dim_date(date_key),
    scene_date_key integer NOT NULL REFERENCES ems_dw.dim_date(date_key),
    to_hospital_date_key integer NOT NULL REFERENCES ems_dw.dim_date(date_key),
    hospital_arrival_date_key integer NOT NULL REFERENCES ems_dw.dim_date(date_key),
    close_date_key integer NOT NULL REFERENCES ems_dw.dim_date(date_key),
    incident_time_key integer NOT NULL REFERENCES ems_dw.dim_time(time_key),
    assignment_time_key integer NOT NULL REFERENCES ems_dw.dim_time(time_key),
    activation_time_key integer NOT NULL REFERENCES ems_dw.dim_time(time_key),
    scene_time_key integer NOT NULL REFERENCES ems_dw.dim_time(time_key),
    to_hospital_time_key integer NOT NULL REFERENCES ems_dw.dim_time(time_key),
    hospital_arrival_time_key integer NOT NULL REFERENCES ems_dw.dim_time(time_key),
    close_time_key integer NOT NULL REFERENCES ems_dw.dim_time(time_key),
    location_key bigint NOT NULL REFERENCES ems_dw.dim_location(location_key),
    initial_call_type_key bigint REFERENCES ems_dw.dim_call_type(call_type_key),
    final_call_type_key bigint REFERENCES ems_dw.dim_call_type(call_type_key),
    initial_severity_key bigint REFERENCES ems_dw.dim_severity(severity_key),
    final_severity_key bigint REFERENCES ems_dw.dim_severity(severity_key),
    disposition_key bigint REFERENCES ems_dw.dim_disposition(disposition_key),
    incident_datetime timestamp,
    first_assignment_datetime timestamp,
    first_activation_datetime timestamp,
    first_on_scene_datetime timestamp,
    first_to_hosp_datetime timestamp,
    first_hosp_arrival_datetime timestamp,
    incident_close_datetime timestamp,
    dispatch_response_seconds numeric,
    incident_response_seconds numeric,
    incident_travel_seconds numeric,
    valid_dispatch_response char(1),
    valid_incident_response char(1),
    held_indicator text,
    reopen_indicator text,
    special_event_indicator text,
    standby_indicator text,
    transfer_indicator text,
    timestamp_order_issue boolean NOT NULL,
    dispatch_response_iqr_outlier boolean NOT NULL,
    incident_response_iqr_outlier boolean NOT NULL,
    incident_travel_iqr_outlier boolean NOT NULL,
    source_extract_name text NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_valid_dispatch_flag CHECK
      (valid_dispatch_response IS NULL OR valid_dispatch_response IN ('Y','N')),
    CONSTRAINT ck_valid_incident_flag CHECK
      (valid_incident_response IS NULL OR valid_incident_response IN ('Y','N'))
);

CREATE TABLE IF NOT EXISTS ems_dw.fact_borough_hourly_ems_performance (
    date_key integer NOT NULL REFERENCES ems_dw.dim_date(date_key),
    hour_time_key integer NOT NULL REFERENCES ems_dw.dim_time(time_key),
    location_key bigint NOT NULL REFERENCES ems_dw.dim_location(location_key),
    incident_count bigint NOT NULL,
    valid_dispatch_count bigint NOT NULL,
    dispatch_response_seconds_sum numeric NOT NULL,
    valid_incident_response_count bigint NOT NULL,
    incident_response_seconds_sum numeric NOT NULL,
    travel_time_count bigint NOT NULL,
    travel_time_seconds_sum numeric NOT NULL,
    refreshed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (date_key, hour_time_key, location_key)
);

CREATE TABLE IF NOT EXISTS ems_dw.etl_batch_audit (
    load_batch_id text PRIMARY KEY,
    load_mode text NOT NULL,
    period_start date NOT NULL,
    period_end_exclusive date NOT NULL,
    staged_row_count bigint NOT NULL DEFAULT 0,
    inserted_fact_count bigint NOT NULL DEFAULT 0,
    fact_row_count_after bigint NOT NULL DEFAULT 0,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    status text NOT NULL,
    notes text
);

CREATE INDEX IF NOT EXISTS ix_fact_ems_incident_date
    ON ems_dw.fact_ems_incident (incident_date_key);
CREATE INDEX IF NOT EXISTS ix_fact_ems_incident_location
    ON ems_dw.fact_ems_incident (location_key);
CREATE INDEX IF NOT EXISTS ix_fact_ems_incident_call_type_initial
    ON ems_dw.fact_ems_incident (initial_call_type_key);
CREATE INDEX IF NOT EXISTS ix_fact_ems_incident_call_type_final
    ON ems_dw.fact_ems_incident (final_call_type_key);

INSERT INTO ems_dw.dim_date (date_key) VALUES (0) ON CONFLICT DO NOTHING;
INSERT INTO ems_dw.dim_time (time_key) VALUES (0) ON CONFLICT DO NOTHING;
INSERT INTO ems_dw.dim_location (location_key,location_signature) OVERRIDING SYSTEM VALUE
    VALUES (0,jsonb_build_array(NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)::text)
    ON CONFLICT DO NOTHING;

-- Roll the location-level hourly aggregate up to borough for dashboard use.
CREATE OR REPLACE VIEW ems_dw.v_borough_hourly_ems_performance AS
SELECT a.date_key, a.hour_time_key, l.borough,
       sum(a.incident_count) AS incident_count,
       sum(a.valid_dispatch_count) AS valid_dispatch_count,
       sum(a.dispatch_response_seconds_sum) AS dispatch_response_seconds_sum,
       sum(a.dispatch_response_seconds_sum) /
         NULLIF(sum(a.valid_dispatch_count),0) AS average_dispatch_response_seconds,
       sum(a.valid_incident_response_count) AS valid_incident_response_count,
       sum(a.incident_response_seconds_sum) AS incident_response_seconds_sum,
       sum(a.incident_response_seconds_sum) /
         NULLIF(sum(a.valid_incident_response_count),0) AS average_incident_response_seconds,
       sum(a.travel_time_count) AS travel_time_count,
       sum(a.travel_time_seconds_sum) AS travel_time_seconds_sum,
       sum(a.travel_time_seconds_sum) / NULLIF(sum(a.travel_time_count),0)
         AS average_travel_time_seconds
FROM ems_dw.fact_borough_hourly_ems_performance a
JOIN ems_dw.dim_location l ON l.location_key = a.location_key
GROUP BY a.date_key, a.hour_time_key, l.borough;
