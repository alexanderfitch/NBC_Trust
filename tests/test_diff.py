import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from diff import diff_snapshots  # noqa: E402


def _rec(crd, **overrides):
    base = {
        "crd": crd,
        "business_name": "FIRM %s" % crd,
        "street1": "123 MAIN ST",
        "city": "LINCOLN",
        "state": "NE",
        "zip": "68508",
        "aum_total": 50_000_000,
        "total_employees": 5,
        "iar_count": 2,
        "item11_flag": "N",
        "reg_type": "SEC_RIA",
    }
    base.update(overrides)
    return base


class TestDiffSnapshots(unittest.TestCase):
    def test_identical_snapshots_produce_no_changes(self):
        records = [_rec("1"), _rec("2")]
        result = diff_snapshots(records, records)
        self.assertEqual(result["new"], [])
        self.assertEqual(result["dropped"], [])
        self.assertEqual(result["changed"], [])

    def test_new_and_dropped(self):
        prev = [_rec("1"), _rec("2")]
        curr = [_rec("1"), _rec("3")]
        result = diff_snapshots(prev, curr)
        self.assertEqual(result["new"], ["3"])
        self.assertEqual(result["dropped"], ["2"])
        self.assertEqual(result["changed"], [])

    def test_aum_small_change_not_flagged(self):
        prev = [_rec("1", aum_total=100_000_000)]
        curr = [_rec("1", aum_total=105_000_000)]  # +5%
        result = diff_snapshots(prev, curr)
        self.assertEqual(result["changed"], [])

    def test_aum_large_change_flagged(self):
        prev = [_rec("1", aum_total=100_000_000)]
        curr = [_rec("1", aum_total=120_000_000)]  # +20%
        result = diff_snapshots(prev, curr)
        self.assertEqual(len(result["changed"]), 1)
        change = result["changed"][0]
        self.assertEqual(change["crd"], "1")
        self.assertEqual(change["field"], "aum_total")
        self.assertEqual(change["old"], 100_000_000)
        self.assertEqual(change["new"], 120_000_000)

    def test_other_field_change_flagged(self):
        prev = [_rec("1", total_employees=5)]
        curr = [_rec("1", total_employees=8)]
        result = diff_snapshots(prev, curr)
        self.assertEqual(len(result["changed"]), 1)
        self.assertEqual(result["changed"][0]["field"], "total_employees")


if __name__ == "__main__":
    unittest.main()
