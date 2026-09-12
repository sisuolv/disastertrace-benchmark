"""Regression checks for actual source and partial-archive failure modes."""

import io
import unittest

import audit_recovered as audit


class SourceContracts(unittest.TestCase):
    def test_cems_null_geometry_retains_record_without_inventing_feature(self):
        report = audit.cems(None)
        self.assertGreater(sum(r["missing_geometries"] for r in report["details"]), 0)
        for row in report["details"]:
            self.assertEqual(
                row["features"],
                sum(row["geometry_types"].values()) + row["missing_geometries"],
            )

    def test_tcir_metadata_rejects_executable_pickle_global(self):
        with self.assertRaisesRegex(ValueError, "Unsupported metadata pickle global"):
            audit.RestrictedArrayUnpickler(io.BytesIO(b"cos\nsystem\n.")).load()


if __name__ == "__main__":
    unittest.main(verbosity=2)
