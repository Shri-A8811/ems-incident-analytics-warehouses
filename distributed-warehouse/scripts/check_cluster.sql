SELECT node_name, node_port
FROM citus_get_active_worker_nodes()
ORDER BY node_name;

SELECT n.nodename, COUNT(*) AS shard_placements
FROM pg_dist_placement AS p
JOIN pg_dist_shard AS s USING (shardid)
JOIN pg_dist_node AS n USING (groupid)
WHERE s.logicalrelid = 'fact_incident'::regclass
GROUP BY n.nodename
ORDER BY n.nodename;

SELECT COUNT(*) AS incident_rows,
       COUNT(DISTINCT incident_id) AS distinct_incidents,
       COUNT(*) FILTER (WHERE dispatch_response_usable) AS valid_dispatch_count,
       COUNT(*) FILTER (WHERE incident_response_usable) AS valid_incident_response_count,
       COUNT(*) FILTER (WHERE incident_travel_usable) AS valid_travel_count,
       COUNT(*) FILTER (WHERE NOT timestamp_order_ok) AS timestamp_order_issues
FROM fact_incident;
