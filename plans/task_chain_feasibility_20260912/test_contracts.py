"""Regression checks for actual source-semantic traps in the downloaded sample."""

import unittest
from datetime import datetime, timezone

import build_chains as build


class SourceContracts(unittest.TestCase):
    def test_upper_visibility_is_not_a_point_value(self):
        parsed = build.visibility("25010KT P6SM FEW020")
        self.assertIsNone(parsed["upper_m"])
        self.assertEqual(parsed["lower_m"], 9656.064)
        self.assertFalse(build.below(parsed))

    def test_fraction_and_mixed_visibility(self):
        self.assertAlmostEqual(build.visibility("1 1/4SM +RA BR")["lower_m"], 2011.68)
        self.assertTrue(build.below(build.visibility("1/2SM SN FZFG")))
        self.assertIsNone(build.below(build.visibility("M1SM FG")))

    def test_metar_trend_does_not_become_the_observation(self):
        parsed = build.visibility("EGKK 271150Z VRB02KT 4000 BR TEMPO 0800 FG")
        self.assertEqual(parsed["lower_m"], 4000)
        self.assertFalse(build.below(parsed))

    def test_international_censoring(self):
        parsed = build.visibility("EGLL 271150Z 25005KT 9999 BKN005")
        self.assertEqual(parsed["lower_m"], 10000)
        self.assertIsNone(parsed["upper_m"])
        self.assertTrue(build.below(build.visibility("VRB02KT 0000 FG")))

    def test_native_threshold_survives_rounded_archive_column(self):
        # This real 1000 m report becomes 0.62 miles in IEM's numeric column.
        parsed = build.visibility(
            "EGKK 270820Z VRB03KT 1000 R08R/1400U BR OVC002 05/05 Q1033"
        )
        self.assertEqual(parsed["lower_m"], 1000)
        self.assertFalse(build.below(parsed))
        self.assertLess(0.62 * 1609.344, 1000)

    def test_suspect_temperature_remains_rejected(self):
        with self.assertRaisesRegex(ValueError, "temperature_quality_2"):
            build.ncei_temperature({"TMP": "+0478,2"})
        self.assertEqual(build.ncei_temperature({"TMP": "-0228,1"}), -22.8)

    def test_taf_24_hour_boundary(self):
        reference = datetime(2024, 12, 31, 20, tzinfo=timezone.utc)
        self.assertEqual(
            build.day_time("3124", reference), datetime(2025, 1, 1, tzinfo=timezone.utc)
        )

    def test_observation_replay_availability(self):
        rows = [
            {"time": "2024-01-13T05:53:00Z", "value": 1},
            {"time": "2024-01-13T05:59:00Z", "value": 2},
            {"time": "2024-01-13T06:53:00Z", "value": 3},
        ]
        result = build.latest_observation(rows, build.instant("2024-01-13T06:00:00Z"))
        self.assertEqual(result["value"], 1)

    def test_real_taf_conditional_interval_and_projection(self):
        model = build.taf(
            build.captured(4, "taf-native-den-2"),
            "KDEN",
            build.instant("2024-01-13T05:37:00Z"),
        )
        self.assertEqual(len(model["conditional"]), 1)
        condition = model["conditional"][0]
        self.assertEqual(condition["start"], "2024-01-13T08:00:00Z")
        self.assertEqual(condition["end"], "2024-01-13T11:00:00Z")
        self.assertTrue(build.below(condition["visibility"]))
        prevailing = next(
            x for x in model["segments"] if x["start"] == "2024-01-13T07:00:00Z"
        )
        self.assertFalse(build.below(prevailing["visibility"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
