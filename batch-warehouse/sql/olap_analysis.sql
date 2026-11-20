-- Milestone 6: OLAP operations for the EMS dispatch warehouse.
-- Run from PowerShell in D:\EDA Project after starting PostgreSQL:
-- docker compose --env-file .env up -d postgres
-- Get-Content sql/olap_analysis.sql | docker exec -i ems-postgres-batch psql -U ems_admin -d ems_dw -v ON_ERROR_STOP=1
-- Response-time averages include only source-valid, non-null measurements.

\pset pager off
\timing on

-- 1. ROLL-UP: incidents from month and borough to year and city totals.
SELECT d.year_number,
       d.month_number,
       l.borough,
       count(*) AS incidents,
       count(*) FILTER (WHERE f.valid_incident_response = 'Y'
                         AND f.incident_response_seconds IS NOT NULL) AS valid_response_count,
       round(avg(f.incident_response_seconds) FILTER (
           WHERE f.valid_incident_response = 'Y'
             AND f.incident_response_seconds IS NOT NULL), 1) AS avg_incident_response_seconds,
       GROUPING(d.year_number, d.month_number, l.borough) AS rollup_level
FROM ems_dw.fact_ems_incident f
JOIN ems_dw.dim_date d ON d.date_key = f.incident_date_key
JOIN ems_dw.dim_location l ON l.location_key = f.location_key
WHERE f.incident_date_key BETWEEN 20240101 AND 20260630
GROUP BY ROLLUP (d.year_number, d.month_number, l.borough)
ORDER BY d.year_number NULLS LAST, d.month_number NULLS LAST, l.borough NULLS LAST;

-- 2. DRILL-DOWN: start with borough totals, then view one borough month by month.
-- Change 'BROOKLYN' to a borough in the result if desired.
SELECT d.year_number, d.month_number, l.borough,
       count(*) AS incidents
FROM ems_dw.fact_ems_incident f
JOIN ems_dw.dim_date d ON d.date_key = f.incident_date_key
JOIN ems_dw.dim_location l ON l.location_key = f.location_key
WHERE f.incident_date_key BETWEEN 20240101 AND 20260630
  AND upper(coalesce(l.borough, '')) = 'BROOKLYN'
GROUP BY d.year_number, d.month_number, l.borough
ORDER BY d.year_number, d.month_number;

-- 3. SLICE: one year (2025), compared by borough and month.
SELECT d.month_number, d.month_name, l.borough,
       count(*) AS incidents
FROM ems_dw.fact_ems_incident f
JOIN ems_dw.dim_date d ON d.date_key = f.incident_date_key
JOIN ems_dw.dim_location l ON l.location_key = f.location_key
WHERE d.year_number = 2025
GROUP BY d.month_number, d.month_name, l.borough
ORDER BY d.month_number, incidents DESC;

-- 4. DICE: select a date range, two boroughs, and two initial call types.
-- INJURY and SICK are frequent source call-type codes in this dataset.
SELECT d.year_number, d.month_number, l.borough,
       c.source_call_type_code, c.call_type_description,
       count(*) AS incidents
FROM ems_dw.fact_ems_incident f
JOIN ems_dw.dim_date d ON d.date_key = f.incident_date_key
JOIN ems_dw.dim_location l ON l.location_key = f.location_key
JOIN ems_dw.dim_call_type c ON c.call_type_key = f.initial_call_type_key
WHERE f.incident_date_key BETWEEN 20250101 AND 20251231
  AND upper(coalesce(l.borough, '')) IN ('BROOKLYN', 'QUEENS')
  AND c.source_call_type_code IN ('INJURY', 'SICK')
GROUP BY d.year_number, d.month_number, l.borough,
         c.source_call_type_code, c.call_type_description
ORDER BY d.month_number, l.borough, incidents DESC;

-- 5. PIVOT: turn borough categories into columns for a compact year comparison.
SELECT d.year_number,
       count(*) FILTER (WHERE upper(l.borough) = 'BRONX') AS bronx,
       count(*) FILTER (WHERE upper(l.borough) = 'BROOKLYN') AS brooklyn,
       count(*) FILTER (WHERE upper(l.borough) = 'MANHATTAN') AS manhattan,
       count(*) FILTER (WHERE upper(l.borough) = 'QUEENS') AS queens,
       count(*) FILTER (WHERE upper(l.borough) = 'RICHMOND / STATEN ISLAND') AS richmond_staten_island,
       count(*) FILTER (WHERE upper(coalesce(l.borough, '')) NOT IN
           ('BRONX', 'BROOKLYN', 'MANHATTAN', 'QUEENS', 'RICHMOND / STATEN ISLAND')) AS other_or_missing_borough
FROM ems_dw.fact_ems_incident f
JOIN ems_dw.dim_date d ON d.date_key = f.incident_date_key
JOIN ems_dw.dim_location l ON l.location_key = f.location_key
WHERE f.incident_date_key BETWEEN 20240101 AND 20260630
GROUP BY d.year_number
ORDER BY d.year_number;

-- 6. CUBE: generate detail and every subtotal combination for year, borough,
-- and initial call type. GROUPING() distinguishes subtotal NULLs from real NULLs.
SELECT d.year_number, l.borough, c.source_call_type_code,
       GROUPING(d.year_number) AS year_is_total,
       GROUPING(l.borough) AS borough_is_total,
       GROUPING(c.source_call_type_code) AS call_type_is_total,
       count(*) AS incidents
FROM ems_dw.fact_ems_incident f
JOIN ems_dw.dim_date d ON d.date_key = f.incident_date_key
JOIN ems_dw.dim_location l ON l.location_key = f.location_key
LEFT JOIN ems_dw.dim_call_type c ON c.call_type_key = f.initial_call_type_key
WHERE f.incident_date_key BETWEEN 20240101 AND 20260630
GROUP BY CUBE (d.year_number, l.borough, c.source_call_type_code)
ORDER BY year_is_total, d.year_number NULLS LAST,
         borough_is_total, l.borough NULLS LAST,
         call_type_is_total, c.source_call_type_code NULLS LAST;

-- 7. GROUPING SETS: explicitly request monthly totals, monthly-by-borough
-- totals, yearly totals, and one grand total.
SELECT d.year_number, d.month_number, l.borough,
       GROUPING(d.year_number, d.month_number, l.borough) AS grouping_level,
       count(*) AS incidents,
       count(*) FILTER (WHERE f.valid_dispatch_response = 'Y'
                         AND f.dispatch_response_seconds IS NOT NULL) AS valid_dispatch_count,
       round(avg(f.dispatch_response_seconds) FILTER (
           WHERE f.valid_dispatch_response = 'Y'
             AND f.dispatch_response_seconds IS NOT NULL), 1) AS avg_dispatch_response_seconds
FROM ems_dw.fact_ems_incident f
JOIN ems_dw.dim_date d ON d.date_key = f.incident_date_key
JOIN ems_dw.dim_location l ON l.location_key = f.location_key
WHERE f.incident_date_key BETWEEN 20240101 AND 20260630
GROUP BY GROUPING SETS (
    (d.year_number, d.month_number, l.borough),
    (d.year_number, d.month_number),
    (d.year_number),
    ()
)
ORDER BY d.year_number NULLS LAST, d.month_number NULLS LAST,
         l.borough NULLS LAST;
