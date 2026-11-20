"""Opt-in local-stack checks: RUN_STACK_TESTS=1 python -m unittest tests.test_stack -v"""

from __future__ import annotations

import os
import base64
import json
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "scripts"))
from replay_csv import read_rows  # noqa: E402


@unittest.skipUnless(os.environ.get("RUN_STACK_TESTS") == "1", "set RUN_STACK_TESTS=1 for live Docker checks")
class RealtimeStackTests(unittest.TestCase):
    def compose(self, *args: str) -> str:
        result = subprocess.run(
            ["docker", "compose", *args], cwd=PROJECT_DIR, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    def clickhouse(self, query: str) -> str:
        return self.compose(
            "exec", "-T", "clickhouse", "clickhouse-client", "--format", "TabSeparatedRaw", "--query", query
        )

    def wait_for_version(self, incident: str, sent_after_ms: int) -> str:
        deadline = time.monotonic() + 10
        result = ""
        while time.monotonic() < deadline:
            result = self.clickhouse(
                "SELECT toUInt64(count()), toUInt64(toUnixTimestamp64Milli(max(ingested_at))) "
                f"FROM ems.fact_incident FINAL WHERE incident_id = {incident}"
            )
            count_text, timestamp_text = result.split("\t")
            if int(count_text) == 1 and int(timestamp_text) >= sent_after_ms:
                return result
            time.sleep(0.25)
        self.fail(f"no current fact version appeared within 10 seconds; last result={result!r}")

    def test_cluster_services_and_topics_are_healthy(self) -> None:
        result = self.compose("ps", "--format", "json")
        self.assertIn("kafka", result)
        self.assertIn("clickhouse", result)
        self.assertIn("spark", result)
        self.assertIn("grafana", result)
        topics = self.compose(
            "exec", "-T", "kafka", "/opt/kafka/bin/kafka-topics.sh", "--bootstrap-server", "kafka:9092", "--list"
        )
        self.assertIn("ems.incidents.raw", topics)
        self.assertIn("ems.incidents.processed", topics)

    def test_complete_snapshot_and_quality_counts(self) -> None:
        deadline = time.monotonic() + 30
        actual = ""
        while time.monotonic() < deadline:
            actual = self.clickhouse(
                "SELECT count(), countIf(dispatch_usable), countIf(incident_response_usable), "
                "countIf(travel_usable), countIf(NOT timestamp_order_ok) FROM ems.fact_incident FINAL"
            )
            if actual.startswith("1310\t"):
                break
            time.sleep(0.5)
        self.assertEqual(actual, "1310\t1309\t1293\t1294\t4")
        stage_deadline = time.monotonic() + 30
        staging = ""
        while time.monotonic() < stage_deadline:
            staging = self.clickhouse("SELECT count(), uniqExact(INCIDENT_ID) FROM ems.stg_ems_incident FINAL")
            if staging == "1310\t1310":
                break
            time.sleep(0.5)
        self.assertEqual(staging, "1310\t1310")
        source_column_count = self.clickhouse(
            "SELECT count() FROM system.columns WHERE database = 'ems' "
            "AND table = 'stg_ems_incident' AND name != 'raw_ingested_at'"
        )
        self.assertEqual(source_column_count, "31")

    def test_kpi_group_results_match_independent_source_calculation(self) -> None:
        rows = read_rows()
        expected = {}

        def source_number(value: str):
            cleaned = value.strip().replace(",", "")
            if not cleaned:
                return None
            try:
                return int(cleaned)
            except ValueError:
                return None

        def normalized(value: str) -> str:
            return value.strip() or "UNKNOWN"

        for row in rows:
            event_date = datetime.strptime(row["INCIDENT_DATETIME"], "%m/%d/%Y %I:%M:%S %p").date().isoformat()
            key = (event_date, normalized(row["BOROUGH"]), normalized(row["INITIAL_CALL_TYPE"]))
            metrics = expected.setdefault(key, {"incident_count": 0, "dispatch_count": 0, "dispatch_sum": 0,
                                                "incident_response_count": 0, "incident_response_sum": 0,
                                                "travel_count": 0, "travel_sum": 0})
            metrics["incident_count"] += 1
            dispatch = source_number(row["DISPATCH_RESPONSE_SECONDS_QY"])
            if row["VALID_DISPATCH_RSPNS_TIME_INDC"] == "Y" and dispatch is not None and dispatch >= 0:
                metrics["dispatch_count"] += 1
                metrics["dispatch_sum"] += dispatch
            incident_response = source_number(row["INCIDENT_RESPONSE_SECONDS_QY"])
            if row["VALID_INCIDENT_RSPNS_TIME_INDC"] == "Y" and incident_response is not None and incident_response >= 0:
                metrics["incident_response_count"] += 1
                metrics["incident_response_sum"] += incident_response
            travel = source_number(row["INCIDENT_TRAVEL_TM_SECONDS_QY"])
            if travel is not None and travel >= 0:
                metrics["travel_count"] += 1
                metrics["travel_sum"] += travel

        sql = """
            SELECT toString(event_date) AS event_date, borough, initial_call_type,
                count() AS incident_count,
                countIf(dispatch_usable) AS dispatch_count,
                if(countIf(dispatch_usable) = 0, CAST(NULL, 'Nullable(Float64)'), avgIf(dispatch_seconds, dispatch_usable)) AS dispatch_avg,
                countIf(incident_response_usable) AS incident_response_count,
                if(countIf(incident_response_usable) = 0, CAST(NULL, 'Nullable(Float64)'), avgIf(incident_response_seconds, incident_response_usable)) AS incident_response_avg,
                countIf(travel_usable) AS travel_count,
                if(countIf(travel_usable) = 0, CAST(NULL, 'Nullable(Float64)'), avgIf(travel_seconds, travel_usable)) AS travel_avg
            FROM ems.fact_incident FINAL
            GROUP BY event_date, borough, initial_call_type
            ORDER BY event_date, borough, initial_call_type
            FORMAT JSONEachRow
        """
        actual_rows = self.compose("exec", "-T", "clickhouse", "clickhouse-client", "--query", sql)
        actual = [json.loads(line) for line in actual_rows.splitlines() if line.strip()]
        self.assertEqual(len(actual), len(expected))
        for row in actual:
            key = (row["event_date"], row["borough"], row["initial_call_type"])
            want = expected[key]
            for result_name, expected_name in (
                ("incident_count", "incident_count"),
                ("dispatch_count", "dispatch_count"),
                ("incident_response_count", "incident_response_count"),
                ("travel_count", "travel_count"),
            ):
                self.assertEqual(int(row[result_name]), want[expected_name], key)
            for result_name, count_name, sum_name in (
                ("dispatch_avg", "dispatch_count", "dispatch_sum"),
                ("incident_response_avg", "incident_response_count", "incident_response_sum"),
                ("travel_avg", "travel_count", "travel_sum"),
            ):
                denominator = want[count_name]
                if denominator == 0:
                    self.assertIsNone(row[result_name], key)
                else:
                    self.assertAlmostEqual(float(row[result_name]), want[sum_name] / denominator, places=6, msg=str(key))

    def test_grafana_dashboard_is_provisioned_with_five_second_refresh(self) -> None:
        import base64
        import urllib.request

        env = {}
        env_file = PROJECT_DIR / ".env"
        if env_file.exists():
            env = dict(line.split("=", 1) for line in env_file.read_text().splitlines() if "=" in line and not line.startswith("#"))
        port = env.get("GRAFANA_PORT", "3002")
        user = env.get("GRAFANA_ADMIN_USER", "admin")
        password = env.get("GRAFANA_ADMIN_PASSWORD", "ems_local_admin")
        request = urllib.request.Request(f"http://127.0.0.1:{port}/api/dashboards/uid/ems-realtime")
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        request.add_header("Authorization", "Basic " + token)
        with urllib.request.urlopen(request, timeout=3) as response:
            document = json.loads(response.read().decode())
        dashboard = document["dashboard"]
        self.assertEqual(dashboard["refresh"], "5s")
        self.assertEqual(dashboard["title"], "EMS Realtime Incident Dashboard")
        self.assertEqual(len(dashboard["panels"]), 6)
        panels = {panel["id"]: panel for panel in dashboard["panels"]}
        self.assertNotEqual(panels[2]["fieldConfig"]["defaults"].get("unit"), "s")
        self.assertEqual(panels[6]["title"], "Dispatch and incident response averages by month")

    def test_replay_is_visible_in_grafana_query_data_within_ten_seconds(self) -> None:
        incident = read_rows()[0]["INCIDENT_ID"]
        before_ms = int(time.time() * 1000)
        sent_at = time.monotonic()
        subprocess.run(
            [sys.executable, str(PROJECT_DIR / "scripts" / "replay_csv.py"), "--incident-id", incident, "--rate", "0"],
            cwd=PROJECT_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
        env = {}
        env_file = PROJECT_DIR / ".env"
        if env_file.exists():
            env = dict(line.split("=", 1) for line in env_file.read_text().splitlines() if "=" in line and not line.startswith("#"))
        port = env.get("GRAFANA_PORT", "3002")
        user = env.get("GRAFANA_ADMIN_USER", "admin")
        password = env.get("GRAFANA_ADMIN_PASSWORD", "ems_local_admin")
        auth = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
        query = {
            "from": str(before_ms),
            "to": str(int(time.time() * 1000)),
            "queries": [
                {
                    "refId": "A",
                    "datasource": {"type": "grafana-clickhouse-datasource", "uid": "ems-clickhouse"},
                    "editorType": "sql",
                    "format": 1,
                    "queryType": "table",
                    "rawSql": "SELECT incident_id, count() AS incident_count FROM ems.fact_incident FINAL "
                              f"WHERE incident_id = {incident} GROUP BY incident_id",
                },
                {
                    "refId": "B",
                    "datasource": {"type": "grafana-clickhouse-datasource", "uid": "ems-clickhouse"},
                    "editorType": "sql",
                    "format": 1,
                    "queryType": "table",
                    "rawSql": "SELECT dateDiff('second', max(ingested_at), now()) AS seconds_since_ingest "
                              "FROM ems.fact_incident FINAL",
                },
            ],
        }
        deadline = time.monotonic() + 10
        last = "Grafana datasource query has not returned yet"
        while time.monotonic() < deadline:
            query["to"] = str(int(time.time() * 1000))
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/ds/query",
                data=json.dumps(query).encode(),
                headers={"Authorization": auth, "Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(request, timeout=2) as response:
                    body = json.loads(response.read().decode())
                result = body.get("results", {}).get("A", {})
                freshness_result = body.get("results", {}).get("B", {})
                if result.get("error") or freshness_result.get("error"):
                    last = str(result.get("error") or freshness_result.get("error"))
                elif result.get("frames"):
                    frame = result["frames"][0]
                    fields = frame.get("schema", {}).get("fields", [])
                    values = frame.get("data", {}).get("values", [])
                    row = {field.get("name"): values[index][0] for index, field in enumerate(fields) if index < len(values) and values[index]}
                    last = json.dumps(row)
                    if str(row.get("incident_id")) == incident and int(row.get("incident_count", 0)) == 1:
                        freshness_frame = freshness_result.get("frames", [{}])[0]
                        freshness_fields = freshness_frame.get("schema", {}).get("fields", [])
                        freshness_values = freshness_frame.get("data", {}).get("values", [])
                        freshness = {
                            field.get("name"): freshness_values[index][0]
                            for index, field in enumerate(freshness_fields)
                            if index < len(freshness_values) and freshness_values[index]
                        }
                        last = f"incident={row}; dashboard_freshness={freshness}"
                        if int(freshness.get("seconds_since_ingest", 999)) <= 10:
                            elapsed = time.monotonic() - sent_at
                            break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last = str(exc)
            time.sleep(0.25)
        else:
            self.fail(f"replayed incident was not returned by the Grafana ClickHouse query within 10 seconds; last result={last!r}")
        self.assertLess(elapsed, 10)
        print(f"Grafana query freshness: {elapsed:.2f}s")

    def test_duplicate_replay_does_not_increase_distinct_incident_count(self) -> None:
        incident = read_rows()[0]["INCIDENT_ID"]
        first_sent_after = int(time.time() * 1000)
        subprocess.run(
            [sys.executable, str(PROJECT_DIR / "scripts" / "replay_csv.py"), "--incident-id", incident, "--rate", "0"],
            cwd=PROJECT_DIR, check=True, capture_output=True, text=True,
        )
        self.wait_for_version(incident, first_sent_after)
        second_sent_after = int(time.time() * 1000)
        subprocess.run(
            [sys.executable, str(PROJECT_DIR / "scripts" / "replay_csv.py"), "--incident-id", incident, "--rate", "0"],
            cwd=PROJECT_DIR, check=True, capture_output=True, text=True,
        )
        result = self.wait_for_version(incident, second_sent_after)
        self.assertEqual(result.split("\t")[0], "1")
        stage_count = ""
        stage_deadline = time.monotonic() + 10
        while time.monotonic() < stage_deadline:
            stage_count = self.clickhouse(
                f"SELECT toUInt64(count()) FROM ems.stg_ems_incident FINAL WHERE INCIDENT_ID = '{incident}'"
            )
            if stage_count == "1":
                break
            time.sleep(0.25)
        self.assertEqual(stage_count, "1")


if __name__ == "__main__":
    unittest.main()
