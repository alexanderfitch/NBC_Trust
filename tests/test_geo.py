import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from geo import haversine_miles, load_geocodes, impute_from_zip, attach_distance  # noqa: E402

OMAHA_MAIN_OFFICE_LAT = 41.2565
OMAHA_MAIN_OFFICE_LON = -95.9345
LINCOLN_LAT = 40.8136
LINCOLN_LON = -96.7026


class TestHaversine(unittest.TestCase):
    def test_lincoln_to_omaha(self):
        dist = haversine_miles(LINCOLN_LAT, LINCOLN_LON, OMAHA_MAIN_OFFICE_LAT, OMAHA_MAIN_OFFICE_LON)
        self.assertAlmostEqual(dist, 49, delta=4)


class TestLoadGeocodes(unittest.TestCase):
    def test_missing_file_returns_empty_dict(self):
        result = load_geocodes(Path("/nonexistent/path/does_not_exist.csv"))
        self.assertEqual(result, {})


class TestZipImputation(unittest.TestCase):
    def test_impute_from_zip_mates(self):
        records = [
            {"crd": "1", "zip": "68116"},
            {"crd": "2", "zip": "68116"},  # missing from geocodes, should borrow from "1"
        ]
        geocodes = {
            "1": {"lat": 41.0, "lon": -96.0, "match": "Match", "match_type": "Exact"},
        }
        imputed = impute_from_zip(records, geocodes)
        self.assertIn("2", imputed)
        self.assertEqual(imputed["2"]["quality"], "zip_imputed")
        self.assertAlmostEqual(imputed["2"]["lat"], 41.0)
        self.assertAlmostEqual(imputed["2"]["lon"], -96.0)

    def test_impute_fails_without_zip_mates(self):
        records = [{"crd": "3", "zip": "99999"}]
        geocodes = {}
        imputed = impute_from_zip(records, geocodes)
        self.assertEqual(imputed["3"]["quality"], "failed")

    def test_attach_distance_end_to_end(self):
        records = [
            {"crd": "1", "zip": "68116"},
            {"crd": "2", "zip": "68116"},
            {"crd": "3", "zip": "00000"},
        ]
        geocodes = {
            "1": {"lat": OMAHA_MAIN_OFFICE_LAT, "lon": OMAHA_MAIN_OFFICE_LON, "match": "Match", "match_type": "Exact"},
        }
        attach_distance(records, geocodes)
        by_crd = {r["crd"]: r for r in records}

        self.assertEqual(by_crd["1"]["geo_quality"], "exact")
        self.assertIsNotNone(by_crd["1"]["distance_mi"])

        self.assertEqual(by_crd["2"]["geo_quality"], "zip_imputed")
        self.assertIsNotNone(by_crd["2"]["distance_mi"])

        self.assertEqual(by_crd["3"]["geo_quality"], "failed")
        self.assertIsNone(by_crd["3"]["distance_mi"])
        self.assertFalse(by_crd["3"]["in_radius"])


if __name__ == "__main__":
    unittest.main()
