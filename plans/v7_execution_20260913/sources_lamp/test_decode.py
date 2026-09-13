import datetime as dt
import unittest

from decode import MILE_METERS, advance_hour, parse_fltcat, parse_lav


def fixture():
    rows = ["KSFO TEST GFS LAMP 2330 UTC 12/31/2024"]
    end = dt.datetime(2024, 12, 31, 23, 30, tzinfo=dt.timezone.utc)
    ends = [end + dt.timedelta(minutes=15 * (i + 1)) for i in range(24)]
    for field, values in (
        ("UTC", [t.hour for t in ends]), ("MIN", [t.minute for t in ends]),
        ("VIS", [7] * 24), ("CIG", [8] * 24),
        ("VPVL", [0] * 24), ("VPL", [1] * 24),
        ("VPI", [2] * 24), ("VPM", [4] * 24), ("VPVFR", [96] * 24),
    ):
        rows.append(f"{field:<5}" + "".join(f"{v:3d}" for v in values))
    return "\n".join(rows)


class NativeSemanticsTests(unittest.TestCase):
    def test_midnight_rollover_retains_window(self):
        rows = parse_fltcat(fixture())
        self.assertEqual(rows[1]["physical_end"], "2025-01-01T00:00:00+00:00")
        self.assertEqual(rows[0]["physical_start"], "2024-12-31T23:30:00+00:00")

    def test_probability_not_category_and_native_threshold(self):
        row = parse_fltcat(fixture())[0]
        self.assertEqual(row["vis_category"], 7)
        self.assertEqual(row["probability_percent"]["VPL"], 1)
        self.assertEqual(MILE_METERS, 1609.344)
        self.assertNotEqual(MILE_METERS, 1000)

    def test_reject_missing_probability(self):
        text = fixture().replace("VPL    1", "VPL  999", 1)
        with self.assertRaises(ValueError):
            parse_fltcat(text)

    def test_reject_incoherent_cumulative_probability(self):
        text = fixture().replace("VPL    1", "VPL    9", 1)
        with self.assertRaises(ValueError):
            parse_fltcat(text)

    def test_reject_duplicate_station_cycle(self):
        with self.assertRaises(ValueError):
            parse_fltcat(fixture() + "\n\n" + fixture())

    def test_same_hour_next_day_only_for_hourly_traversal(self):
        start = dt.datetime(2024, 1, 1, 1, tzinfo=dt.timezone.utc)
        self.assertEqual(advance_hour(start, 1), start + dt.timedelta(days=1))

    def test_native_lav_retains_half_hour_and_missing_category(self):
        text = (
            " KSFO GFS LAMP GUIDANCE 1/01/2024 0030 UTC\n"
            " UTC  01 02\n"
            " VIS   7999\n"
            " CIG   8  8\n"
        )
        rows = parse_lav(text)
        self.assertEqual(rows[0]["native_cycle_at"], "2024-01-01T00:30:00+00:00")
        self.assertEqual(rows[0]["valid_at"], "2024-01-01T01:00:00+00:00")
        self.assertEqual(rows[1]["missing_or_invalid_categorical_fields"], ["VIS"])


if __name__ == "__main__":
    unittest.main()
