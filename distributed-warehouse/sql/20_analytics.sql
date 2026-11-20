-- Incident volume and valid response-time averages by borough, initial call type, and month.
SELECT
    g.borough,
    TO_CHAR(f.date_key, 'YYYY-MM') AS incident_month,
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
GROUP BY g.borough, TO_CHAR(f.date_key, 'YYYY-MM'), ct.call_type_code
ORDER BY incident_month, g.borough, initial_call_type;

-- Initial versus final call type counts by month.
SELECT
    TO_CHAR(f.date_key, 'YYYY-MM') AS incident_month,
    initial_ct.call_type_code AS initial_call_type,
    final_ct.call_type_code AS final_call_type,
    COUNT(*) AS incident_count
FROM fact_incident AS f
JOIN dim_call_type AS initial_ct ON initial_ct.call_type_key = f.initial_call_type_key
JOIN dim_call_type AS final_ct ON final_ct.call_type_key = f.final_call_type_key
GROUP BY incident_month, initial_call_type, final_call_type
ORDER BY incident_month, incident_count DESC;
