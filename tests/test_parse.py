import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from parse_feeds import parse_feed, parse_all  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


class TestParseSec(unittest.TestCase):
    def setUp(self):
        self.records = parse_feed(FIXTURES / "sample_sec.xml", "SEC")
        self.by_crd = {r["crd"]: r for r in self.records}

    def test_crd_values(self):
        self.assertEqual(set(self.by_crd), {"288301", "105053"})

    def test_aum_total_is_int(self):
        rec = self.by_crd["288301"]
        self.assertEqual(rec["aum_total"], 213203341)
        self.assertIsInstance(rec["aum_total"], int)

        rec2 = self.by_crd["105053"]
        self.assertEqual(rec2["aum_total"], 428568259)

    def test_reg_type_sec_ria(self):
        rec = self.by_crd["288301"]
        self.assertEqual(rec["reg_type"], "SEC_RIA")
        self.assertEqual(rec["feed"], "SEC")

    def test_first_reg_date(self):
        self.assertEqual(self.by_crd["288301"]["first_reg_date"], "2021-04-08")
        self.assertEqual(self.by_crd["105053"]["first_reg_date"], "1986-05-22")

    def test_notice_filed_count(self):
        self.assertEqual(self.by_crd["288301"]["notice_filed_count"], 2)
        self.assertEqual(self.by_crd["105053"]["notice_filed_count"], 4)

    def test_basic_fields(self):
        rec = self.by_crd["288301"]
        self.assertEqual(rec["business_name"], "AO WEALTH ADVISORY")
        self.assertEqual(rec["city"], "URBANDALE")
        self.assertEqual(rec["state"], "IA")
        self.assertEqual(rec["zip"], "50322")
        self.assertEqual(rec["total_employees"], 7)
        self.assertEqual(rec["iar_count"], 4)
        self.assertEqual(rec["item11_flag"], "N")
        self.assertEqual(rec["item11_yes_count"], 0)
        self.assertEqual(rec["custody_flag"], "Y")
        self.assertEqual(rec["website"], "https://www.instagram.com/aowealthadvisory/")


class TestParseState(unittest.TestCase):
    def setUp(self):
        self.records = parse_feed(FIXTURES / "sample_state.xml", "STATE")
        self.by_crd = {r["crd"]: r for r in self.records}

    def test_crd_values(self):
        self.assertEqual(set(self.by_crd), {"291820", "114512"})

    def test_reg_type_state_era(self):
        # Kratky: no StateRgstn approval, but has an active ERA registration.
        rec = self.by_crd["291820"]
        self.assertEqual(rec["reg_type"], "STATE_ERA")
        self.assertEqual(rec["reg_states"], [])
        self.assertEqual(rec["first_reg_date"], "2017-12-26")

    def test_reg_type_state_ria(self):
        # Mooberry: approved KS state registration.
        rec = self.by_crd["114512"]
        self.assertEqual(rec["reg_type"], "STATE_RIA")
        self.assertEqual(rec["reg_states"], ["KS"])
        self.assertEqual(rec["first_reg_date"], "1999-09-09")

    def test_aum_total_none_when_missing(self):
        self.assertIsNone(self.by_crd["291820"]["aum_total"])
        self.assertIsNone(self.by_crd["114512"]["aum_total"])

    def test_empty_items_yield_none(self):
        rec = self.by_crd["291820"]
        self.assertIsNone(rec["total_employees"])
        self.assertIsNone(rec["iar_count"])

    def test_notice_filed_count_zero_for_state(self):
        self.assertEqual(self.by_crd["291820"]["notice_filed_count"], 0)
        self.assertEqual(self.by_crd["114512"]["notice_filed_count"], 0)


class TestParseAll(unittest.TestCase):
    def test_dedup_prefers_sec(self):
        # Both fixture files are disjoint on CRD, so parse_all should
        # simply combine them with no dedup firing.
        records = parse_all(FIXTURES / "sample_sec.xml", FIXTURES / "sample_state.xml")
        crds = {r["crd"] for r in records}
        self.assertEqual(crds, {"288301", "105053", "291820", "114512"})
        for rec in records:
            self.assertIn("also_in_state_feed", rec)


if __name__ == "__main__":
    unittest.main()
