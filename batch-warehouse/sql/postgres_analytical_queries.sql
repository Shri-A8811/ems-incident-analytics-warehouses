-- Example batch-warehouse analyses. Run with psql so timings are recorded.
\timing on
\pset pager off

-- 1. Monthly incident demand.
SELECT d.year_number, d.month_number, d.month_name, count(*) AS incidents
FROM ems_dw.fact_ems_incident f
JOIN ems_dw.dim_date d ON d.date_key = f.incident_date_key
WHERE f.incident_date_key BETWEEN 20240101 AND 20260630
GROUP BY d.year_number, d.month_number, d.month_name
ORDER BY d.year_number, d.month_number;

-- 2. Most common initial call types.
SELECT c.source_call_type_code, c.call_type_description, count(*) AS incidents
FROM ems_dw.fact_ems_incident f
JOIN ems_dw.dim_call_type c ON c.call_type_key = f.initial_call_type_key
GROUP BY c.source_call_type_code, c.call_type_description
ORDER BY incidents DESC
LIMIT 15;

-- 3. Borough response performance. Only source-valid incident response times
-- are averaged; show their valid sample size next to the average.
SELECT l.borough,
       count(*) AS incidents,
       count(*) FILTER (
         WHERE f.valid_incident_response='Y' AND f.incident_response_seconds IS NOT NULL
       ) AS valid_response_count,
       round(avg(f.incident_response_seconds) FILTER (
         WHERE f.valid_incident_response='Y' AND f.incident_response_seconds IS NOT NULL
       ),1) AS avg_incident_response_seconds
FROM ems_dw.fact_ems_incident f
JOIN ems_dw.dim_location l ON l.location_key = f.location_key
GROUP BY l.borough
ORDER BY incidents DESC;

-- 4. Peak weekday and hour combinations.
SELECT d.day_name, t.hour_number, count(*) AS incidents
FROM ems_dw.fact_ems_incident f
JOIN ems_dw.dim_date d ON d.date_key = f.incident_date_key
JOIN ems_dw.dim_time t ON t.time_key = f.incident_time_key
WHERE f.incident_date_key BETWEEN 20240101 AND 20260630
GROUP BY d.day_of_week_number, d.day_name, t.hour_number
ORDER BY incidents DESC
LIMIT 20;

-- 5. Index-use and elapsed-time example for the June incremental period.
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT count(*)
FROM ems_dw.fact_ems_incident
WHERE incident_date_key BETWEEN 20260601 AND 20260630;
