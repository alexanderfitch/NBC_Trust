#!/usr/bin/env python3
"""Create the NBC Trust succession CRM base in Airtable (Phase 2 schema).

Run this ONCE from a machine with network access (not the sandboxed build
environment -- see DECISIONS.md D-003):

    export AIRTABLE_API_KEY=pat...        # personal access token, see below
    python3 scripts/setup_airtable.py --workspace-id wspXXXXXXXXXXXXXX

The token needs scopes: schema.bases:write, data.records:read,
data.records:write -- and access to the target workspace. Create it at
https://airtable.com/create/tokens (the user does this in their own browser;
the token never needs to be shared with anyone).

Creates one base ("NBC Trust Succession CRM") containing:
  - Firms          -- pipeline-owned fields (must match crm_writer._fields_for)
                      plus CRM-only fields (Stage, Cadence, Relationship Score...)
  - Interactions   -- one row per touch, linked to Firms
  - Compliance Log -- append-only consent/asset/audit events, linked to Firms

NOT idempotent: running twice creates a second base (Airtable's Meta API has
no upsert for bases). Run once, then record the printed AIRTABLE_BASE_ID.

Views and automations cannot be created via the public API -- create those by
hand per docs/PHASE2_AIRTABLE.md (5 minutes).

The 13 pipeline stages below are PROVISIONAL defaults for the client to
rename in place (renaming a select option in Airtable preserves records).
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.airtable.com/v0/meta"

STAGES = [
    ("01 Identified", "grayLight2"),
    ("02 Researched", "grayLight2"),
    ("03 Warm Path Found", "blueLight2"),
    ("04 Introduced", "blueLight2"),
    ("05 First Conversation", "cyanLight2"),
    ("06 Relationship Building", "cyanLight2"),
    ("07 Invited (Landing Page)", "tealLight2"),
    ("08 Raised Hand", "greenLight2"),
    ("09 Discovery Meeting", "greenLight2"),
    ("10 Mutual Fit Assessment", "yellowLight2"),
    ("11 Proposal Discussed", "orangeLight2"),
    ("12 Agreement Signed", "redLight2"),
    ("13 Transition In Progress", "purpleLight2"),
]

DATE = {"type": "date", "options": {"dateFormat": {"name": "iso"}}}
DATETIME = {"type": "dateTime", "options": {
    "timeZone": "America/Chicago",
    "dateFormat": {"name": "iso"},
    "timeFormat": {"name": "24hour"},
}}


def _num(precision):
    return {"type": "number", "options": {"precision": precision}}


def _select(names_or_pairs):
    choices = []
    for c in names_or_pairs:
        if isinstance(c, tuple):
            choices.append({"name": c[0], "color": c[1]})
        else:
            choices.append({"name": c})
    return {"type": "singleSelect", "options": {"choices": choices}}


FIRMS_FIELDS = [
    # --- pipeline-owned: names/types must match crm_writer._fields_for() ---
    {"name": "CRD", "type": "singleLineText"},              # primary field
    {"name": "Firm Name", "type": "singleLineText"},
    {"name": "City", "type": "singleLineText"},
    {"name": "State", "type": "singleLineText"},
    dict({"name": "Distance (mi)"}, **_num(1)),
    {"name": "AUM", "type": "currency",
     "options": {"precision": 0, "symbol": "$"}},
    dict({"name": "Employees"}, **_num(0)),
    dict({"name": "IARs"}, **_num(0)),
    dict({"name": "Fit Score"}, **_num(0)),
    dict({"name": "Readiness Score"}, **_num(0)),
    {"name": "Band", "type": "singleLineText"},
    {"name": "Reg Type", "type": "singleLineText"},
    dict({"name": "First Registered"}, **DATE),
    {"name": "Item 11", "type": "singleLineText"},
    {"name": "Website", "type": "url"},
    {"name": "Phone", "type": "phoneNumber"},
    # --- CRM-only: owned by the client, never touched by the pipeline ---
    dict({"name": "Stage"}, **_select(STAGES)),
    dict({"name": "Relationship Score"}, **_num(0)),        # manual 1-5
    dict({"name": "Cadence"}, **_select(["Monthly", "Quarterly", "Annual"])),
    dict({"name": "Next Touch Date"}, **DATE),
    {"name": "Owner", "type": "singleLineText"},
    {"name": "Notes", "type": "multilineText"},
    dict({"name": "Outcome"}, **_select(
        ["Active", "Paused", "Declined", "Not a Fit", "Do Not Contact"])),
    {"name": "Do Not Contact", "type": "checkbox",
     "options": {"icon": "check", "color": "redBright"}},
    dict({"name": "Opt-Out Date"}, **DATE),
]


def _request(path, payload, token):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Authorization": "Bearer %s" % token,
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        sys.exit("Airtable API error (HTTP %s) on %s:\n%s" % (exc.code, path, body))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace-id", required=True,
                    help="Airtable workspace id (starts with 'wsp'; visible in "
                         "the workspace URL at airtable.com)")
    ap.add_argument("--base-name", default="NBC Trust Succession CRM")
    args = ap.parse_args()

    token = os.environ.get("AIRTABLE_API_KEY")
    if not token:
        sys.exit("Set AIRTABLE_API_KEY in the environment first.")

    # 1. Create the base with the Firms table.
    base = _request("/bases", {
        "name": args.base_name,
        "workspaceId": args.workspace_id,
        "tables": [{"name": "Firms",
                    "description": "Prospect universe. Pipeline-owned columns are "
                                   "overwritten monthly; CRM columns (Stage, Notes, "
                                   "Cadence...) are never touched by the pipeline.",
                    "fields": FIRMS_FIELDS}],
    }, token)
    base_id = base["id"]
    firms_table_id = base["tables"][0]["id"]
    print("Created base %s with Firms table %s" % (base_id, firms_table_id))

    # 2. Interactions table (linked to Firms).
    link = {"type": "multipleRecordLinks",
            "options": {"linkedTableId": firms_table_id}}
    _request("/bases/%s/tables" % base_id, {
        "name": "Interactions",
        "description": "One row per touch (call, meeting, note).",
        "fields": [
            {"name": "Interaction", "type": "singleLineText"},
            dict({"name": "Date"}, **DATE),
            dict({"name": "Firm"}, **link),
            dict({"name": "Type"}, **_select(
                ["Call", "Email", "Meeting", "Event", "Letter", "Other"])),
            {"name": "Summary", "type": "multilineText"},
            {"name": "By", "type": "singleLineText"},
            {"name": "Next Step", "type": "singleLineText"},
            dict({"name": "Next Touch Date"}, **DATE),
        ],
    }, token)
    print("Created Interactions table")

    # 3. Compliance Log table (append-only by convention).
    _request("/bases/%s/tables" % base_id, {
        "name": "Compliance Log",
        "description": "Append-only: consent, opt-outs, published-asset versions. "
                       "Never edit or delete rows -- add corrections as new rows.",
        "fields": [
            {"name": "Entry", "type": "singleLineText"},
            dict({"name": "Timestamp"}, **DATETIME),
            dict({"name": "Firm"}, **link),
            dict({"name": "Event Type"}, **_select(
                ["Consent Opt-In", "Opt-Out", "Asset Published",
                 "Copy Approved", "Audit Export", "Note"])),
            {"name": "Detail", "type": "multilineText"},
            {"name": "Actor", "type": "singleLineText"},
            {"name": "Source", "type": "singleLineText"},
        ],
    }, token)
    print("Created Compliance Log table")

    print()
    print("Done. Now export these for the pipeline:")
    print("  export AIRTABLE_BASE_ID=%s" % base_id)
    print("  export AIRTABLE_TABLE=Firms")
    print("  export AIRTABLE_IN_RADIUS_ONLY=1   # recommended on the free tier")
    print()
    print("Then create the 5 views and 2 automations per docs/PHASE2_AIRTABLE.md.")


if __name__ == "__main__":
    main()
