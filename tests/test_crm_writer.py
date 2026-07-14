"""Tests for AirtableCRMWriter batching/filtering with a mocked network."""

import io
import json
import os
import sys
import unittest
import unittest.mock as mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import crm_writer  # noqa: E402

FAKE_ENV = {
    "AIRTABLE_API_KEY": "pat_test",
    "AIRTABLE_BASE_ID": "app_test",
    "AIRTABLE_TABLE": "Firms",
}


def _rec(crd, in_radius):
    return {"crd": crd, "business_name": "FIRM " + crd, "in_radius": in_radius,
            "city": "LINCOLN", "state": "NE", "distance_mi": 1.0}


class TestAirtableWriter(unittest.TestCase):
    def _run(self, records, extra_env=None):
        env = dict(FAKE_ENV, **(extra_env or {}))
        captured = []

        def fake_urlopen(req, timeout=None):
            captured.append(json.loads(req.data.decode("utf-8")))
            return io.BytesIO(b"{}")

        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(crm_writer.urllib.request, "urlopen", fake_urlopen), \
             mock.patch.object(crm_writer.time, "sleep", lambda s: None):
            result = crm_writer.AirtableCRMWriter().upsert_firms(records, "2026-07-14")
        return result, captured

    def test_in_radius_filter_env(self):
        records = [_rec("1", True), _rec("2", False), _rec("3", True)]
        result, captured = self._run(records, {"AIRTABLE_IN_RADIUS_ONLY": "1"})
        self.assertEqual(result["written"], 2)
        sent_crds = [r["fields"]["CRD"] for b in captured for r in b["records"]]
        self.assertEqual(sent_crds, ["1", "3"])

    def test_no_filter_by_default(self):
        env = {k: v for k, v in os.environ.items()}
        env.pop("AIRTABLE_IN_RADIUS_ONLY", None)
        records = [_rec("1", True), _rec("2", False)]
        with mock.patch.dict(os.environ, env, clear=True):
            result, captured = self._run(records)
        self.assertEqual(result["written"], 2)

    def test_upsert_merges_on_crd(self):
        _, captured = self._run([_rec("42", True)])
        self.assertEqual(captured[0]["performUpsert"]["fieldsToMergeOn"], ["CRD"])

    def test_http_error_surfaces_detail(self):
        import urllib.error

        def failing_urlopen(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url, 422, "Unprocessable",  hdrs=None,
                fp=io.BytesIO(b'{"error":{"type":"UNKNOWN_FIELD_NAME"}}'))

        with mock.patch.dict(os.environ, FAKE_ENV, clear=False), \
             mock.patch.object(crm_writer.urllib.request, "urlopen", failing_urlopen):
            result = crm_writer.AirtableCRMWriter().upsert_firms(
                [_rec("1", True)], "2026-07-14")
        self.assertTrue(result["skipped"])
        self.assertIn("422", result["reason"])
        self.assertIn("UNKNOWN_FIELD_NAME", result["detail"])


if __name__ == "__main__":
    unittest.main()
