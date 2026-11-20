from __future__ import annotations

import csv
import unittest
from collections import Counter
from datetime import datetime
from pathlib import Path

from etl.load_ems import DEFAULT_SOURCE, SOURCE_COLUMNS, validate_header


def parsed(value: str) -> datetime | None:
    return datetime.strptime(value, "%m/%d/%Y %I:%M:%S %p") if value else None


def source_valid(flag: str, value: str) -> bool:
    number = int(value.replace(",", "")) if value else None
    return flag == "Y" and number is not None and number >= 0


class EMSDataContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with DEFAULT_SOURCE.open(encoding="utf-8-sig", newline="") as stream:
            reader = validate_header(stream)
            cls.rows = list(reader)

    def test_source_has_expected_rows_and_unique_ids(self) -> None:
        ids = [row["INCIDENT_ID"] for row in self.rows]
        self.assertEqual(len(ids), 1310)
        self.assertEqual(len(set(ids)), 1310)

    def test_expected_source_columns_are_preserved(self) -> None:
        self.assertEqual(len(SOURCE_COLUMNS), 31)

    def test_dispatch_validity_rule_and_missingness(self) -> None:
        usable = sum(source_valid(row["VALID_DISPATCH_RSPNS_TIME_INDC"], row["DISPATCH_RESPONSE_SECONDS_QY"]) for row in self.rows)
        self.assertEqual(usable, 1309)
        self.assertEqual(sum(not row["INCIDENT_RESPONSE_SECONDS_QY"] for row in self.rows), 17)
        self.assertEqual(sum(not row["INCIDENT_TRAVEL_TM_SECONDS_QY"] for row in self.rows), 16)

    def test_timestamp_order_quality_flag_finds_four_rows(self) -> None:
        timeline = (
            "INCIDENT_DATETIME",
            "FIRST_ASSIGNMENT_DATETIME",
            "FIRST_ACTIVATION_DATETIME",
            "FIRST_ON_SCENE_DATETIME",
            "FIRST_TO_HOSP_DATETIME",
            "FIRST_HOSP_ARRIVAL_DATETIME",
            "INCIDENT_CLOSE_DATETIME",
        )
        violations = Counter()
        for row in self.rows:
            values = [parsed(row[column]) for column in timeline]
            if any(left and right and right < left for left, right in zip(values, values[1:])):
                violations["out_of_order"] += 1
        self.assertEqual(violations["out_of_order"], 4)

    def test_source_path_exists(self) -> None:
        self.assertTrue(Path(DEFAULT_SOURCE).is_file())


if __name__ == "__main__":
    unittest.main()
