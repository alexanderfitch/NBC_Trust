"""Permanent opt-out enforcement for the NBC_Trust pipeline.

README.md promises that a prospect who asks to be removed is *never*
re-imported by a future run. This module is that promise's implementation.

Design (DECISIONS.md D-016):
- Airtable is the working surface: staff check ``Do Not Contact``, set an
  ``Opt-Out Date``, or set ``Outcome = Do Not Contact`` on a Firms record.
- ``compliance/exclusions.csv`` is the durable, append-only audit record.
  It is committed to git, so the exclusion survives Airtable (subscription
  lapse, base deletion, export/re-import) and is enforceable with no token
  and no network -- which is exactly when you least want it to fail open.
- The effective exclusion set is the UNION of the two. Rows are only ever
  appended; nothing here removes an exclusion, by design. Reinstating a
  firm is a deliberate manual edit of the CSV, visible in git history.

Spec-silent choices:
- CRD is the key everywhere else in this codebase (D-008), so it is the key
  here too. It is stored as a string to match the parsed records.
- Excluded firms are RETAINED in the JSON research snapshot with
  ``excluded=True`` rather than dropped, so month-over-month diffs do not
  report them as false terminations (cf. D-014) and so an auditor can prove
  the exclusion was applied rather than inferring it from an absence.
  They are withheld from the CSV export and the Airtable upsert -- the two
  surfaces that actually feed outreach.
"""

import csv
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from config import REPO_ROOT

EXCLUSIONS_PATH = REPO_ROOT / "compliance" / "exclusions.csv"

EXCLUSION_FIELDS = ["crd", "firm_name", "excluded_on", "source", "note"]

# An Airtable Firms record counts as opted out if ANY of these hold. Three
# signals rather than one because staff reach for whichever field is in front
# of them; failing open because someone used the "wrong" one is not acceptable.
_DNC_FIELD = "Do Not Contact"
_OPT_OUT_DATE_FIELD = "Opt-Out Date"
_OUTCOME_FIELD = "Outcome"
_OUTCOME_DNC_VALUE = "Do Not Contact"


def load_exclusions(path=EXCLUSIONS_PATH):
    """Read the append-only exclusions file. Returns {crd: row-dict}.

    A missing file is normal (nobody has opted out yet) and yields {}.
    """
    path = Path(path)
    if not path.exists():
        return {}

    out = {}
    with open(path, "r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            crd = (row.get("crd") or "").strip()
            if crd:
                out[crd] = row
    return out


def _is_opted_out(fields):
    """True if an Airtable Firms record's fields signal an opt-out."""
    if fields.get(_DNC_FIELD):
        return True
    if (fields.get(_OPT_OUT_DATE_FIELD) or "").strip():
        return True
    if (fields.get(_OUTCOME_FIELD) or "").strip() == _OUTCOME_DNC_VALUE:
        return True
    return False


def fetch_airtable_exclusions(api_key=None, base_id=None, table=None):
    """Page the Firms table and return {crd: firm_name} for opted-out firms.

    Returns (mapping, status). Status is "ok", or a reason string when the
    fetch could not run. A failed fetch is NOT treated as "nobody is opted
    out" -- callers must fail closed and fall back to the local file only.
    """
    api_key = api_key or os.environ.get("AIRTABLE_API_KEY")
    base_id = base_id or os.environ.get("AIRTABLE_BASE_ID")
    table = table or os.environ.get("AIRTABLE_TABLE")

    if not (api_key and base_id and table):
        return {}, "missing credentials"

    found = {}
    offset = None
    base_url = "https://api.airtable.com/v0/%s/%s" % (base_id, urllib.parse.quote(table))

    try:
        while True:
            params = {"pageSize": "100"}
            # Only pull the fields the decision depends on -- cheaper and it
            # keeps prospect PII out of this code path entirely.
            for i, field in enumerate(
                    ["CRD", "Firm Name", _DNC_FIELD, _OPT_OUT_DATE_FIELD, _OUTCOME_FIELD]):
                params["fields[%d]" % i] = field
            if offset:
                params["offset"] = offset

            req = urllib.request.Request(
                base_url + "?" + urllib.parse.urlencode(params),
                headers={"Authorization": "Bearer %s" % api_key},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.load(resp)

            for rec in payload.get("records", []):
                fields = rec.get("fields", {})
                crd = str(fields.get("CRD") or "").strip()
                if crd and _is_opted_out(fields):
                    found[crd] = fields.get("Firm Name") or ""

            offset = payload.get("offset")
            if not offset:
                break

    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        return {}, "http %s %s" % (exc.code, detail)
    except urllib.error.URLError as exc:
        return {}, "network unavailable (%s)" % exc

    return found, "ok"


def append_exclusions(new_crds, as_of, path=EXCLUSIONS_PATH, source="airtable"):
    """Append newly-seen exclusions to the audit file. Returns the CRDs added.

    Append-only: a CRD already present is left exactly as first recorded, so
    the original ``excluded_on`` date is never rewritten by a later run.
    """
    path = Path(path)
    existing = load_exclusions(path)
    to_add = {crd: name for crd, name in new_crds.items() if crd not in existing}
    if not to_add:
        return []

    path.parent.mkdir(parents=True, exist_ok=True)
    is_new_file = not path.exists()
    with open(path, "a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=EXCLUSION_FIELDS)
        if is_new_file:
            writer.writeheader()
        for crd in sorted(to_add):
            writer.writerow({
                "crd": crd,
                "firm_name": to_add[crd],
                "excluded_on": as_of,
                "source": source,
                "note": "opt-out recorded in Airtable; permanent per README",
            })
    return sorted(to_add)


def apply_exclusions(records, excluded_crds):
    """Mark excluded records and split them out.

    Sets ``excluded`` on every record (True/False) so the JSON snapshot
    carries the evidence, and returns (kept, withheld) where ``withheld``
    is the list of excluded records for reporting.
    """
    kept, withheld = [], []
    for rec in records:
        crd = str(rec.get("crd") or "").strip()
        if crd and crd in excluded_crds:
            rec["excluded"] = True
            withheld.append(rec)
        else:
            rec["excluded"] = False
            kept.append(rec)
    return kept, withheld


def effective_exclusions(as_of, path=EXCLUSIONS_PATH):
    """Resolve the full exclusion set for a run and persist any new entries.

    Returns (crd_set, report). The set is the union of the local audit file
    and whatever Airtable currently flags; when Airtable is unreachable the
    local file still applies, so exclusions fail CLOSED.
    """
    local = load_exclusions(path)
    fetched, status = fetch_airtable_exclusions()

    added = []
    if status == "ok":
        added = append_exclusions(fetched, as_of, path=path)

    effective = set(local) | set(fetched)
    return effective, {
        "local": len(local),
        "airtable": len(fetched) if status == "ok" else None,
        "airtable_status": status,
        "newly_recorded": added,
        "effective": len(effective),
    }
