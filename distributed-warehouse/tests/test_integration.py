"""Opt-in database checks; set RUN_DB_TESTS=1 after starting the Citus cluster."""

from __future__ import annotations

import os
import unittest
import csv
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from etl.load_ems import DEFAULT_SOURCE, load_csv, run_psql


def reference_analytics():
    """Calculate grouped KPIs independently from the raw CSV, without SQL transforms."""
    source = Path(__file__).resolve().parents[2] / "data" / "source" / "EMS_Incident_Dispatch_Data_20261015.csv"
    groups = defaultdict(lambda: {"incidents": 0, "dispatch": [], "incident": [], "travel": []})
    with source.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            incident_date = datetime.strptime(row["INCIDENT_DATETIME"], "%m/%d/%Y %I:%M:%S %p")
            key = (
                row["BOROUGH"].strip() or "UNKNOWN",
                incident_date.strftime("%Y-%m"),
                row["INITIAL_CALL_TYPE"].strip() or "UNKNOWN",
            )
            group = groups[key]
            group["incidents"] += 1
            metrics = (
                ("dispatch", "VALID_DISPATCH_RSPNS_TIME_INDC", "DISPATCH_RESPONSE_SECONDS_QY"),
                ("incident", "VALID_INCIDENT_RSPNS_TIME_INDC", "INCIDENT_RESPONSE_SECONDS_QY"),
                ("travel", None, "INCIDENT_TRAVEL_TM_SECONDS_QY"),
            )
            for metric, validity_column, value_column in metrics:
                raw = row[value_column]
                if not raw:
                    continue
                seconds = int(raw.replace(",", ""))
                flag_is_valid = validity_column is None or row[validity_column] == "Y"
                if flag_is_valid and seconds >= 0:
                    group[metric].append(seconds)

    def rounded_average(values):
        if not values:
            return None
        mean = Decimal(sum(values)) / Decimal(len(values))
        return mean.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        key: (
            values["incidents"],
            len(values["dispatch"]), rounded_average(values["dispatch"]),
            len(values["incident"]), rounded_average(values["incident"]),
            len(values["travel"]), rounded_average(values["travel"]),
        )
        for key, values in groups.items()
    }


@unittest.skipUnless(os.getenv("RUN_DB_TESTS") == "1", "requires a running local Citus cluster")
class CitusIntegrationTests(unittest.TestCase):
    @staticmethod
    def query(sql: str) -> list[str]:
        output = run_psql("-A", "-t", "-F", "\t", "-c", sql, capture_output=True)
        return [line for line in output.splitlines() if line.strip()]

    def test_worker_and_shard_placement(self) -> None:
        active_workers = self.query("SELECT COUNT(*) FROM citus_get_active_worker_nodes()")
        self.assertEqual(active_workers, ["2"])
        placements = self.query(
            """SELECT COUNT(DISTINCT n.nodename)
               FROM pg_dist_placement p
               JOIN pg_dist_shard s USING (shardid)
               JOIN pg_dist_node n USING (groupid)
               WHERE s.logicalrelid = 'fact_incident'::regclass"""
        )
        self.assertEqual(placements, ["2"])
        shards = self.query(
            "SELECT COUNT(*) FROM pg_dist_shard WHERE logicalrelid = 'fact_incident'::regclass"
        )
        self.assertEqual(shards, ["4"])
        per_worker = self.query(
            """SELECT n.nodename, COUNT(*)
               FROM pg_dist_placement p
               JOIN pg_dist_shard s USING (shardid)
               JOIN pg_dist_node n USING (groupid)
               WHERE s.logicalrelid = 'fact_incident'::regclass
               GROUP BY n.nodename ORDER BY n.nodename"""
        )
        self.assertEqual(per_worker, ["worker-1\t2", "worker-2\t2"])

    def test_all_source_columns_and_unknown_geography_are_kept(self) -> None:
        staged_columns = self.query(
            """SELECT COUNT(*) FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'stg_ems_incident'"""
        )
        self.assertEqual(staged_columns, ["31"])
        missing_zip = self.query(
            """SELECT COUNT(*) FROM fact_incident f
               JOIN dim_geography g USING (geography_key)
               WHERE g.zipcode = 'UNKNOWN'"""
        )
        self.assertEqual(missing_zip, ["35"])

    def test_full_load_and_idempotent_rerun(self) -> None:
        first = load_csv(DEFAULT_SOURCE)
        second = load_csv(DEFAULT_SOURCE)
        self.assertEqual(first, (1310, 1310))
        self.assertEqual(second, (1310, 1310))
        actual = self.query("SELECT COUNT(*), COUNT(DISTINCT incident_id) FROM fact_incident")
        self.assertEqual(actual, ["1310\t1310"])

    def test_query_has_visible_valid_response_denominators(self) -> None:
        actual = self.query(
            """SELECT COUNT(*),
                      COUNT(*) FILTER (WHERE dispatch_response_usable),
                      COUNT(*) FILTER (WHERE incident_response_usable),
                      COUNT(*) FILTER (WHERE incident_travel_usable),
                      COUNT(*) FILTER (WHERE NOT timestamp_order_ok)
               FROM fact_incident"""
        )
        self.assertEqual(actual, ["1310\t1309\t1293\t1294\t4"])

    def test_warehouse_analytics_match_independent_csv_calculation(self) -> None:
        expected = reference_analytics()
        rows = self.query(
            """SELECT g.borough,
                      TO_CHAR(f.date_key, 'YYYY-MM') AS incident_month,
                      ct.call_type_code AS initial_call_type,
                      COUNT(*) AS incident_count,
                      COUNT(*) FILTER (WHERE f.dispatch_response_usable) AS valid_dispatch_count,
                      COALESCE(ROUND(AVG(f.dispatch_response_seconds) FILTER (WHERE f.dispatch_response_usable), 2)::text, ''),
                      COUNT(*) FILTER (WHERE f.incident_response_usable) AS valid_incident_response_count,
                      COALESCE(ROUND(AVG(f.incident_response_seconds) FILTER (WHERE f.incident_response_usable), 2)::text, ''),
                      COUNT(*) FILTER (WHERE f.incident_travel_usable) AS valid_travel_count,
                      COALESCE(ROUND(AVG(f.incident_travel_seconds) FILTER (WHERE f.incident_travel_usable), 2)::text, '')
               FROM fact_incident AS f
               JOIN dim_geography AS g USING (geography_key)
               JOIN dim_call_type AS ct ON ct.call_type_key = f.initial_call_type_key
               GROUP BY g.borough, TO_CHAR(f.date_key, 'YYYY-MM'), ct.call_type_code"""
        )
        actual = {}
        for row in rows:
            (
                borough, incident_month, call_type, incidents,
                dispatch_count, dispatch_avg,
                incident_count, incident_avg,
                travel_count, travel_avg,
            ) = row.split("\t")

            def decimal_or_none(value: str):
                return Decimal(value) if value else None

            actual[(borough, incident_month, call_type)] = (
                int(incidents), int(dispatch_count), decimal_or_none(dispatch_avg),
                int(incident_count), decimal_or_none(incident_avg),
                int(travel_count), decimal_or_none(travel_avg),
            )
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
