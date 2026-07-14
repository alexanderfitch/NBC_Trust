"""CRM export writers: a deterministic CSV writer and an optional Airtable writer.

Spec-silent choices:
- CSVCRMWriter always (over)writes ``out_path`` fully on each call, since
  the pipeline treats each run as producing one authoritative snapshot.
- AirtableCRMWriter batches of 10 records per PATCH request, matching the
  Airtable API's own upsert batch limit; any URLError (including DNS
  failure in a no-network sandbox) is treated as "network unavailable"
  rather than a hard failure, so the pipeline can still complete.
"""

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

CSV_FIELDS = [
    "crd",
    "business_name",
    "city",
    "state",
    "zip",
    "phone",
    "website",
    "feed",
    "reg_type",
    "first_reg_date",
    "filing_date",
    "total_employees",
    "iar_count",
    "aum_total",
    "total_accounts",
    "item11_flag",
    "distance_mi",
    "in_radius",
    "fit_score",
    "readiness_score",
    "band_label",
    "relationship_score",
    "fit_reasons",
    "readiness_reasons",
]

AIRTABLE_BATCH_SIZE = 10


class CRMWriter(ABC):
    @abstractmethod
    def upsert_firms(self, records, as_of):
        """Write records to the CRM. Returns a dict summary of what happened."""
        raise NotImplementedError


class CSVCRMWriter(CRMWriter):
    def __init__(self, out_path):
        self.out_path = Path(out_path)

    def _row_for(self, rec):
        row = {}
        for field in CSV_FIELDS:
            if field == "fit_reasons":
                row[field] = "; ".join(rec.get("fit_reasons") or [])
            elif field == "readiness_reasons":
                row[field] = "; ".join(rec.get("readiness_reasons") or [])
            else:
                row[field] = rec.get(field)
        return row

    def upsert_firms(self, records, as_of):
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(records, key=lambda r: r.get("crd") or "")

        with open(self.out_path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for rec in ordered:
                writer.writerow(self._row_for(rec))

        return {
            "skipped": False,
            "written": len(ordered),
            "path": str(self.out_path),
            "as_of": as_of,
        }


class AirtableCRMWriter(CRMWriter):
    def __init__(self):
        self.api_key = os.environ.get("AIRTABLE_API_KEY")
        self.base_id = os.environ.get("AIRTABLE_BASE_ID")
        self.table = os.environ.get("AIRTABLE_TABLE")

    def _fields_for(self, rec):
        return {
            "CRD": rec.get("crd"),
            "Firm Name": rec.get("business_name"),
            "City": rec.get("city"),
            "State": rec.get("state"),
            "Distance (mi)": rec.get("distance_mi"),
            "AUM": rec.get("aum_total"),
            "Employees": rec.get("total_employees"),
            "IARs": rec.get("iar_count"),
            "Fit Score": rec.get("fit_score"),
            "Readiness Score": rec.get("readiness_score"),
            "Band": rec.get("band_label"),
            "Reg Type": rec.get("reg_type"),
            "First Registered": rec.get("first_reg_date"),
            "Item 11": rec.get("item11_flag"),
            "Website": rec.get("website"),
            "Phone": rec.get("phone"),
        }

    def upsert_firms(self, records, as_of):
        if not (self.api_key and self.base_id and self.table):
            print("AirtableCRMWriter: skipping upsert -- missing one or more of "
                  "AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE in the environment.")
            return {"skipped": True, "reason": "missing credentials"}

        # Free-tier guard: Airtable Free caps a base at 1,000 records total.
        # Set AIRTABLE_IN_RADIUS_ONLY=1 to upsert only in-radius firms (~111)
        # and leave room for Interactions / Compliance Log records.
        if os.environ.get("AIRTABLE_IN_RADIUS_ONLY"):
            before = len(records)
            records = [r for r in records if r.get("in_radius")]
            print("AirtableCRMWriter: AIRTABLE_IN_RADIUS_ONLY set -- upserting "
                  "%d in-radius firms (of %d total)." % (len(records), before))

        url = "https://api.airtable.com/v0/%s/%s" % (self.base_id, self.table)
        ordered = sorted(records, key=lambda r: r.get("crd") or "")
        batches_sent = 0

        try:
            for i in range(0, len(ordered), AIRTABLE_BATCH_SIZE):
                batch = ordered[i:i + AIRTABLE_BATCH_SIZE]
                payload = {
                    "performUpsert": {"fieldsToMergeOn": ["CRD"]},
                    "records": [{"fields": self._fields_for(rec)} for rec in batch],
                }
                body = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=body,
                    method="PATCH",
                    headers={
                        "Authorization": "Bearer %s" % self.api_key,
                        "Content-Type": "application/json",
                    },
                )
                urllib.request.urlopen(req, timeout=30)
                batches_sent += 1
                time.sleep(0.25)  # stay well under Airtable's 5 req/s per-base limit
        except urllib.error.HTTPError as exc:
            # Surface Airtable's error body -- a 422 here usually means a field
            # name/type mismatch between _fields_for() and the base schema.
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:500]
            except Exception:
                pass
            print("AirtableCRMWriter: Airtable rejected batch %d (HTTP %s): %s"
                  % (batches_sent + 1, exc.code, detail))
            return {"skipped": True, "reason": "http %s" % exc.code,
                    "batches_sent": batches_sent, "detail": detail}
        except urllib.error.URLError as exc:
            print("AirtableCRMWriter: network unavailable, skipping upsert (%s)" % exc)
            return {"skipped": True, "reason": "network"}

        return {"skipped": False, "written": len(ordered), "batches": batches_sent, "as_of": as_of}
