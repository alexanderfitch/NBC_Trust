import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from score import fit_score, readiness_score, band_label, score_all  # noqa: E402


def _base_rec(**overrides):
    rec = {
        "aum_total": None,
        "item11_flag": None,
        "item11_yes_count": 0,
        "total_employees": None,
        "iar_count": None,
        "first_reg_date": None,
    }
    rec.update(overrides)
    return rec


class TestFitScore(unittest.TestCase):
    def test_fit_score_five(self):
        rec = _base_rec(
            aum_total=50_000_000,
            item11_flag="N",
            item11_yes_count=0,
            total_employees=3,
        )
        score, reasons = fit_score(rec)
        self.assertEqual(score, 5)
        self.assertTrue(reasons)

    def test_fit_score_floor(self):
        rec = _base_rec(
            aum_total=None,
            item11_flag="Y",
            item11_yes_count=2,
            total_employees=None,
        )
        score, reasons = fit_score(rec)
        self.assertEqual(score, 1)
        self.assertEqual(reasons, [])

    def test_fit_score_near_sweet_spot(self):
        rec = _base_rec(aum_total=15_000_000)
        score, _ = fit_score(rec)
        self.assertEqual(score, 2)  # 1 base + 1 near-sweet-spot


class TestReadinessScore(unittest.TestCase):
    def test_readiness_tenure_25_solo(self):
        rec = _base_rec(
            first_reg_date="2001-01-01",  # 2026 - 2001 = 25 years
            iar_count=1,
            total_employees=2,
        )
        score, reasons = readiness_score(rec)
        self.assertEqual(score, 5)
        self.assertTrue(reasons)

    def test_readiness_floor(self):
        rec = _base_rec()
        score, reasons = readiness_score(rec)
        self.assertEqual(score, 1)
        self.assertEqual(reasons, [])


class TestBandLabel(unittest.TestCase):
    def test_band_label_never_mentions_age(self):
        cases = [
            _base_rec(first_reg_date="1990-01-01", total_employees=2, iar_count=1,
                      item11_flag="N", item11_yes_count=0, aum_total=50_000_000),
            _base_rec(first_reg_date="2015-01-01", total_employees=20, iar_count=5,
                      item11_flag="Y", item11_yes_count=1, aum_total=1_000_000),
            _base_rec(),
        ]
        for rec in cases:
            label = band_label(rec)
            self.assertNotIn("age", label.lower())

    def test_band_label_contents(self):
        rec = _base_rec(
            first_reg_date="2001-01-01",  # tenure 25 -> long-tenured
            total_employees=2,             # small team
            iar_count=1,                   # single-adviser
            item11_flag="N", item11_yes_count=0,  # clean record
            aum_total=50_000_000,          # sweet-spot AUM
        )
        label = band_label(rec)
        for expected in ("long-tenured", "small team", "single-adviser", "clean record", "sweet-spot AUM"):
            self.assertIn(expected, label)


class TestScoreAll(unittest.TestCase):
    def test_score_all_mutates_records(self):
        records = [_base_rec(aum_total=50_000_000, item11_flag="N", total_employees=3)]
        score_all(records)
        rec = records[0]
        for key in ("fit_score", "fit_reasons", "readiness_score", "readiness_reasons", "band_label", "relationship_score"):
            self.assertIn(key, rec)
        self.assertIsNone(rec["relationship_score"])


if __name__ == "__main__":
    unittest.main()
