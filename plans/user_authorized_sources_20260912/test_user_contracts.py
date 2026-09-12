"""Regression checks for the actual user-provided export formats."""

import unittest

from audit_user_sources import EMDAT, ROOT, parse_cma, read_emdat


class UserSourceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dimension, cls.columns, cls.rows = read_emdat(EMDAT)

    def test_incorrect_a1_dimension_does_not_truncate_workbook(self):
        self.assertEqual(self.dimension, "A1:A1")
        self.assertEqual(len(self.columns), 47)
        self.assertEqual(len(self.rows), 17022)

    def test_empty_spatial_and_date_cells_remain_missing(self):
        kenya = next(r for r in self.rows if r["DisNo."] == "2026-0153-KEN")
        drought = next(r for r in self.rows if r["DisNo."] == "2025-9122-SOM")
        self.assertIsNone(kenya["Latitude"])
        self.assertIsNone(kenya["Longitude"])
        self.assertIsNone(drought["Start Day"])

    def test_optional_cma_wind_column_is_retained(self):
        storms = parse_cma(ROOT / "extracted/cma/CH1950BST.txt")
        # Simultaneous storms share timestamps; the archive line disambiguates.
        row = next(p for s in storms for p in s["points"] if p["source_line"] == 266)
        self.assertEqual(row["time_raw"], "1950072718")
        self.assertEqual(row["wind_raw"], 9)
        self.assertEqual(row["optional_wind_raw"], 12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
