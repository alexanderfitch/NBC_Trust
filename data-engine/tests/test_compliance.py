"""Tests for permanent opt-out enforcement (src/compliance.py)."""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import compliance


def _rec(crd, name="FIRM"):
    return {"crd": crd, "business_name": name}


class TestLoadExclusions(unittest.TestCase):
    def test_missing_file_is_empty_not_an_error(self):
        self.assertEqual(compliance.load_exclusions("/nonexistent/nope.csv"), {})

    def test_reads_crds(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "e.csv"
            p.write_text("crd,firm_name,excluded_on,source,note\n"
                         "111,A,2026-01-01,manual,x\n"
                         "222,B,2026-02-02,airtable,y\n", encoding="utf-8")
            got = compliance.load_exclusions(p)
            self.assertEqual(set(got), {"111", "222"})
            self.assertEqual(got["222"]["source"], "airtable")

    def test_blank_crd_rows_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "e.csv"
            p.write_text("crd,firm_name,excluded_on,source,note\n"
                         ",,,,\n111,A,2026-01-01,manual,x\n", encoding="utf-8")
            self.assertEqual(set(compliance.load_exclusions(p)), {"111"})


class TestOptOutSignals(unittest.TestCase):
    def test_checkbox(self):
        self.assertTrue(compliance._is_opted_out({"Do Not Contact": True}))

    def test_opt_out_date(self):
        self.assertTrue(compliance._is_opted_out({"Opt-Out Date": "2026-05-01"}))

    def test_outcome_value(self):
        self.assertTrue(compliance._is_opted_out({"Outcome": "Do Not Contact"}))

    def test_clean_record_is_not_opted_out(self):
        self.assertFalse(compliance._is_opted_out(
            {"Do Not Contact": False, "Opt-Out Date": "", "Outcome": "Active"}))

    def test_empty_fields_is_not_opted_out(self):
        self.assertFalse(compliance._is_opted_out({}))


class TestAppendExclusions(unittest.TestCase):
    def test_creates_file_with_header(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sub" / "e.csv"
            added = compliance.append_exclusions({"111": "A"}, "2026-09-09", path=p)
            self.assertEqual(added, ["111"])
            with p.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["crd"], "111")
            self.assertEqual(rows[0]["excluded_on"], "2026-09-09")

    def test_append_only_never_rewrites_original_date(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "e.csv"
            compliance.append_exclusions({"111": "A"}, "2026-01-01", path=p)
            added = compliance.append_exclusions({"111": "A"}, "2026-09-09", path=p)
            self.assertEqual(added, [], "already-known CRD must not be re-added")
            with p.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["excluded_on"], "2026-01-01")

    def test_adds_only_the_new_ones(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "e.csv"
            compliance.append_exclusions({"111": "A"}, "2026-01-01", path=p)
            added = compliance.append_exclusions(
                {"111": "A", "222": "B"}, "2026-09-09", path=p)
            self.assertEqual(added, ["222"])
            self.assertEqual(set(compliance.load_exclusions(p)), {"111", "222"})


class TestApplyExclusions(unittest.TestCase):
    def test_splits_and_flags(self):
        recs = [_rec("111", "A"), _rec("222", "B"), _rec("333", "C")]
        kept, withheld = compliance.apply_exclusions(recs, {"222"})
        self.assertEqual([r["crd"] for r in kept], ["111", "333"])
        self.assertEqual([r["crd"] for r in withheld], ["222"])

    def test_every_record_gets_an_explicit_flag(self):
        recs = [_rec("111"), _rec("222")]
        compliance.apply_exclusions(recs, {"111"})
        self.assertTrue(recs[0]["excluded"])
        self.assertFalse(recs[1]["excluded"], "non-excluded must be False, not absent")

    def test_no_exclusions_keeps_everything(self):
        recs = [_rec("111"), _rec("222")]
        kept, withheld = compliance.apply_exclusions(recs, set())
        self.assertEqual(len(kept), 2)
        self.assertEqual(withheld, [])

    def test_missing_crd_is_never_excluded(self):
        recs = [{"business_name": "no crd"}]
        kept, withheld = compliance.apply_exclusions(recs, {""})
        self.assertEqual(len(kept), 1)
        self.assertEqual(withheld, [])


class TestFailClosed(unittest.TestCase):
    def test_no_credentials_reports_reason_not_empty_success(self):
        mapping, status = compliance.fetch_airtable_exclusions(
            api_key=None, base_id=None, table=None)
        self.assertEqual(mapping, {})
        self.assertEqual(status, "missing credentials")

    def test_unreachable_airtable_still_enforces_local_file(self):
        """The whole point of the local file: exclusions survive a failed fetch."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "e.csv"
            compliance.append_exclusions({"111": "A"}, "2026-01-01", path=p)

            orig = compliance.fetch_airtable_exclusions
            compliance.fetch_airtable_exclusions = lambda *a, **k: ({}, "network unavailable")
            try:
                effective, report = compliance.effective_exclusions("2026-09-09", path=p)
            finally:
                compliance.fetch_airtable_exclusions = orig

            self.assertEqual(effective, {"111"})
            self.assertIsNone(report["airtable"])
            self.assertEqual(report["local"], 1)

    def test_union_of_local_and_airtable(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "e.csv"
            compliance.append_exclusions({"111": "A"}, "2026-01-01", path=p)

            orig = compliance.fetch_airtable_exclusions
            compliance.fetch_airtable_exclusions = lambda *a, **k: ({"222": "B"}, "ok")
            try:
                effective, report = compliance.effective_exclusions("2026-09-09", path=p)
            finally:
                compliance.fetch_airtable_exclusions = orig

            self.assertEqual(effective, {"111", "222"})
            self.assertEqual(report["newly_recorded"], ["222"],
                             "an Airtable opt-out must be persisted to the audit file")
            self.assertEqual(set(compliance.load_exclusions(p)), {"111", "222"})


if __name__ == "__main__":
    unittest.main()
