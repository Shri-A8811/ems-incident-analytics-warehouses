-- SQLite schema for the local batch warehouse.
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS dim_date (
 date_key INTEGER PRIMARY KEY, full_date TEXT UNIQUE, year_number INTEGER,
 quarter_number INTEGER, month_number INTEGER, month_name TEXT,
 day_of_month INTEGER, day_of_week_number INTEGER, day_name TEXT, is_weekend INTEGER
);
CREATE TABLE IF NOT EXISTS dim_location (
 location_key INTEGER PRIMARY KEY, borough TEXT, incident_dispatch_area TEXT,
 zipcode TEXT, police_precinct INTEGER, city_council_district INTEGER,
 community_district INTEGER, community_school_district INTEGER,
 congressional_district INTEGER
);
CREATE TABLE IF NOT EXISTS dim_call_type (
 call_type_key INTEGER PRIMARY KEY, source_call_type_code TEXT NOT NULL UNIQUE,
 call_type_description TEXT
);
CREATE TABLE IF NOT EXISTS dim_severity (
 severity_key INTEGER PRIMARY KEY, source_severity_code TEXT NOT NULL UNIQUE,
 source_description TEXT
);
CREATE TABLE IF NOT EXISTS dim_disposition (
 disposition_key INTEGER PRIMARY KEY, source_disposition_code TEXT NOT NULL UNIQUE,
 source_description TEXT
);
CREATE TABLE IF NOT EXISTS fact_ems_incident (
 incident_key INTEGER PRIMARY KEY, incident_id TEXT NOT NULL UNIQUE,
 incident_date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
 location_key INTEGER NOT NULL REFERENCES dim_location(location_key),
 initial_call_type_key INTEGER REFERENCES dim_call_type(call_type_key),
 final_call_type_key INTEGER REFERENCES dim_call_type(call_type_key),
 initial_severity_key INTEGER REFERENCES dim_severity(severity_key),
 final_severity_key INTEGER REFERENCES dim_severity(severity_key),
 disposition_key INTEGER REFERENCES dim_disposition(disposition_key),
 incident_datetime TEXT, first_assignment_datetime TEXT, first_activation_datetime TEXT,
 first_on_scene_datetime TEXT, first_to_hosp_datetime TEXT,
 first_hosp_arrival_datetime TEXT, incident_close_datetime TEXT,
 dispatch_response_seconds REAL, incident_response_seconds REAL,
 incident_travel_seconds REAL, valid_dispatch_response TEXT,
 valid_incident_response TEXT, held_indicator TEXT, reopen_indicator TEXT,
 special_event_indicator TEXT, standby_indicator TEXT, transfer_indicator TEXT,
 timestamp_order_issue INTEGER NOT NULL, dispatch_response_iqr_outlier INTEGER NOT NULL,
 incident_response_iqr_outlier INTEGER NOT NULL, incident_travel_iqr_outlier INTEGER NOT NULL,
 source_extract_name TEXT NOT NULL, loaded_at TEXT NOT NULL
);
