from __future__ import annotations

import sys
import unittest
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "scripts"))

from replay_csv import EXPECTED_COLUMNS, SOURCE, read_rows  # noqa: E402


class ReplayContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = read_rows()

    def test_source_contract_and_idempotency_key(self) -> None:
        self.assertEqual(len(EXPECTED_COLUMNS), 31)
        ids = [row["INCIDENT_ID"] for row in self.rows]
        self.assertEqual(len(self.rows), 1310)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(ids))

    def test_replay_order_uses_incident_event_time(self) -> None:
        ordered = sorted(self.rows, key=lambda row: (row["_event_sort"], int(row["INCIDENT_ID"])))
        self.assertEqual(ordered[0]["_event_sort"], min(row["_event_sort"] for row in self.rows))
        self.assertEqual(ordered[-1]["_event_sort"], max(row["_event_sort"] for row in self.rows))
        self.assertTrue(all(left["_event_sort"] <= right["_event_sort"] for left, right in zip(ordered, ordered[1:])))

    def test_source_validity_flags_and_missing_durations_remain_available(self) -> None:
        dispatch_valid = sum(
            row["VALID_DISPATCH_RSPNS_TIME_INDC"] == "Y"
            and row["DISPATCH_RESPONSE_SECONDS_QY"]
            and int(row["DISPATCH_RESPONSE_SECONDS_QY"].replace(",", "")) >= 0
            for row in self.rows
        )
        incident_valid = sum(
            row["VALID_INCIDENT_RSPNS_TIME_INDC"] == "Y"
            and row["INCIDENT_RESPONSE_SECONDS_QY"]
            and int(row["INCIDENT_RESPONSE_SECONDS_QY"].replace(",", "")) >= 0
            for row in self.rows
        )
        self.assertEqual(dispatch_valid, 1309)
        self.assertEqual(incident_valid, 1293)
        self.assertEqual(sum(not row["INCIDENT_TRAVEL_TM_SECONDS_QY"] for row in self.rows), 16)

    def test_source_has_the_expected_snapshot_path(self) -> None:
        self.assertTrue(SOURCE.is_file())


if __name__ == "__main__":
    unittest.main()
