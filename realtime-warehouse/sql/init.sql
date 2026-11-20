CREATE DATABASE IF NOT EXISTS ems;

CREATE TABLE IF NOT EXISTS ems.stg_ems_incident
(
    INCIDENT_ID String,
    INCIDENT_DATETIME String,
    INITIAL_CALL_TYPE String,
    INITIAL_SEVERITY_LEVEL_CODE String,
    FINAL_CALL_TYPE String,
    FINAL_SEVERITY_LEVEL_CODE String,
    FIRST_ASSIGNMENT_DATETIME String,
    VALID_DISPATCH_RSPNS_TIME_INDC String,
    DISPATCH_RESPONSE_SECONDS_QY String,
    FIRST_ACTIVATION_DATETIME String,
    FIRST_ON_SCENE_DATETIME String,
    VALID_INCIDENT_RSPNS_TIME_INDC String,
    INCIDENT_RESPONSE_SECONDS_QY String,
    INCIDENT_TRAVEL_TM_SECONDS_QY String,
    FIRST_TO_HOSP_DATETIME String,
    FIRST_HOSP_ARRIVAL_DATETIME String,
    INCIDENT_CLOSE_DATETIME String,
    HELD_INDICATOR String,
    INCIDENT_DISPOSITION_CODE String,
    BOROUGH String,
    INCIDENT_DISPATCH_AREA String,
    ZIPCODE String,
    POLICEPRECINCT String,
    CITYCOUNCILDISTRICT String,
    COMMUNITYDISTRICT String,
    COMMUNITYSCHOOLDISTRICT String,
    CONGRESSIONALDISTRICT String,
    REOPEN_INDICATOR String,
    SPECIAL_EVENT_INDICATOR String,
    STANDBY_INDICATOR String,
    TRANSFER_INDICATOR String,
    raw_ingested_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(raw_ingested_at)
ORDER BY INCIDENT_ID;

CREATE TABLE IF NOT EXISTS ems.raw_incidents_kafka
(
    INCIDENT_ID String,
    INCIDENT_DATETIME String,
    INITIAL_CALL_TYPE String,
    INITIAL_SEVERITY_LEVEL_CODE String,
    FINAL_CALL_TYPE String,
    FINAL_SEVERITY_LEVEL_CODE String,
    FIRST_ASSIGNMENT_DATETIME String,
    VALID_DISPATCH_RSPNS_TIME_INDC String,
    DISPATCH_RESPONSE_SECONDS_QY String,
    FIRST_ACTIVATION_DATETIME String,
    FIRST_ON_SCENE_DATETIME String,
    VALID_INCIDENT_RSPNS_TIME_INDC String,
    INCIDENT_RESPONSE_SECONDS_QY String,
    INCIDENT_TRAVEL_TM_SECONDS_QY String,
    FIRST_TO_HOSP_DATETIME String,
    FIRST_HOSP_ARRIVAL_DATETIME String,
    INCIDENT_CLOSE_DATETIME String,
    HELD_INDICATOR String,
    INCIDENT_DISPOSITION_CODE String,
    BOROUGH String,
    INCIDENT_DISPATCH_AREA String,
    ZIPCODE String,
    POLICEPRECINCT String,
    CITYCOUNCILDISTRICT String,
    COMMUNITYDISTRICT String,
    COMMUNITYSCHOOLDISTRICT String,
    CONGRESSIONALDISTRICT String,
    REOPEN_INDICATOR String,
    SPECIAL_EVENT_INDICATOR String,
    STANDBY_INDICATOR String,
    TRANSFER_INDICATOR String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'ems.incidents.raw',
    kafka_group_name = 'ems-clickhouse-raw-v1',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1;

CREATE MATERIALIZED VIEW IF NOT EXISTS ems.mv_raw_incidents
TO ems.stg_ems_incident
AS SELECT
    INCIDENT_ID, INCIDENT_DATETIME, INITIAL_CALL_TYPE, INITIAL_SEVERITY_LEVEL_CODE,
    FINAL_CALL_TYPE, FINAL_SEVERITY_LEVEL_CODE, FIRST_ASSIGNMENT_DATETIME,
    VALID_DISPATCH_RSPNS_TIME_INDC, DISPATCH_RESPONSE_SECONDS_QY, FIRST_ACTIVATION_DATETIME,
    FIRST_ON_SCENE_DATETIME, VALID_INCIDENT_RSPNS_TIME_INDC, INCIDENT_RESPONSE_SECONDS_QY,
    INCIDENT_TRAVEL_TM_SECONDS_QY, FIRST_TO_HOSP_DATETIME, FIRST_HOSP_ARRIVAL_DATETIME,
    INCIDENT_CLOSE_DATETIME, HELD_INDICATOR, INCIDENT_DISPOSITION_CODE, BOROUGH,
    INCIDENT_DISPATCH_AREA, ZIPCODE, POLICEPRECINCT, CITYCOUNCILDISTRICT,
    COMMUNITYDISTRICT, COMMUNITYSCHOOLDISTRICT, CONGRESSIONALDISTRICT, REOPEN_INDICATOR,
    SPECIAL_EVENT_INDICATOR, STANDBY_INDICATOR, TRANSFER_INDICATOR, now64(3, 'UTC') AS raw_ingested_at
FROM ems.raw_incidents_kafka;

CREATE TABLE IF NOT EXISTS ems.fact_incident
(
    incident_id UInt64,
    incident_datetime String,
    event_date Date,
    borough LowCardinality(String),
    initial_call_type LowCardinality(String),
    final_call_type LowCardinality(String),
    initial_severity LowCardinality(String),
    final_severity LowCardinality(String),
    disposition_code LowCardinality(String),
    incident_count UInt8 DEFAULT 1,
    dispatch_seconds Nullable(Int32),
    dispatch_valid_flag String,
    dispatch_usable Bool,
    incident_response_seconds Nullable(Int32),
    incident_valid_flag String,
    incident_response_usable Bool,
    travel_seconds Nullable(Int32),
    travel_usable Bool,
    timestamp_order_ok Bool,
    ingested_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYear(event_date)
ORDER BY incident_id;

CREATE USER IF NOT EXISTS grafana_reader IDENTIFIED WITH no_password;
GRANT SELECT ON ems.* TO grafana_reader;

CREATE TABLE IF NOT EXISTS ems.processed_incidents_kafka
(
    incident_id UInt64,
    incident_datetime String,
    event_date Date,
    borough String,
    initial_call_type String,
    final_call_type String,
    initial_severity String,
    final_severity String,
    disposition_code String,
    incident_count UInt8,
    dispatch_seconds Nullable(Int32),
    dispatch_valid_flag String,
    dispatch_usable Bool,
    incident_response_seconds Nullable(Int32),
    incident_valid_flag String,
    incident_response_usable Bool,
    travel_seconds Nullable(Int32),
    travel_usable Bool,
    timestamp_order_ok Bool,
    ingested_at DateTime64(3, 'UTC')
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'ems.incidents.processed',
    kafka_group_name = 'ems-clickhouse-incidents-v1',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1,
    kafka_handle_error_mode = 'stream';

CREATE MATERIALIZED VIEW IF NOT EXISTS ems.mv_processed_incidents
TO ems.fact_incident
AS SELECT
    incident_id, incident_datetime, event_date, borough, initial_call_type, final_call_type,
    initial_severity, final_severity, disposition_code, incident_count, dispatch_seconds,
    dispatch_valid_flag, dispatch_usable, incident_response_seconds, incident_valid_flag,
    incident_response_usable, travel_seconds, travel_usable, timestamp_order_ok, ingested_at
FROM ems.processed_incidents_kafka;

CREATE OR REPLACE VIEW ems.v_incident_kpis AS
SELECT
    event_date,
    borough,
    initial_call_type,
    count() AS incident_count,
    countIf(dispatch_usable) AS valid_dispatch_count,
    avgIf(dispatch_seconds, dispatch_usable) AS avg_dispatch_seconds,
    countIf(incident_response_usable) AS valid_incident_response_count,
    avgIf(incident_response_seconds, incident_response_usable) AS avg_incident_response_seconds,
    countIf(travel_usable) AS valid_travel_count,
    avgIf(travel_seconds, travel_usable) AS avg_travel_seconds
FROM ems.fact_incident FINAL
GROUP BY event_date, borough, initial_call_type;
