from __future__ import annotations

import csv
import io
import unittest

from etl.load_ems import SOURCE_COLUMNS, validate_header


class HeaderValidationTests(unittest.TestCase):
    def test_accepts_expected_header(self) -> None:
        stream = io.StringIO(",".join(SOURCE_COLUMNS) + "\n")
        reader = validate_header(stream)
        self.assertEqual(tuple(reader.fieldnames or ()), SOURCE_COLUMNS)

    def test_rejects_missing_or_reordered_columns(self) -> None:
        reordered = list(SOURCE_COLUMNS)
        reordered[0], reordered[1] = reordered[1], reordered[0]
        with self.assertRaisesRegex(ValueError, "header"):
            validate_header(io.StringIO(",".join(reordered) + "\n"))

    def test_csv_module_handles_quoted_thousands_separator(self) -> None:
        reader = csv.reader(io.StringIO('"2,025",Y\n'))
        self.assertEqual(next(reader), ["2,025", "Y"])


if __name__ == "__main__":
    unittest.main()
