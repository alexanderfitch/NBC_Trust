# Phase 2 — Airtable CRM setup & Phase 1 integration test

Everything here runs from **your own terminal** (the build sandbox has no network access —
DECISIONS.md D-003). Your API token stays on your machine; nothing here requires sharing it.

## 1. One-time setup (~10 minutes)

1. **Create a free Airtable account/workspace** at airtable.com (or use an existing one).
   Note the workspace id (`wspXXXXXXXXXXXXXX`) from the workspace URL.
2. **Create a personal access token** at <https://airtable.com/create/tokens> with scopes
   `schema.bases:write`, `data.records:read`, `data.records:write`, and grant it access to that
   workspace.
3. **Create the base** (one command, run ONCE — it is not idempotent):

   ```bash
   cd /Users/Alexfitch/NBC_Trust
   export AIRTABLE_API_KEY=pat________________
   python3 scripts/setup_airtable.py --workspace-id wspXXXXXXXXXXXXXX
   ```

   This creates the "NBC Trust Succession CRM" base with three tables — **Firms** (pipeline
   fields + the 13-stage select + CRM-only fields), **Interactions**, **Compliance Log** — and
   prints the `AIRTABLE_BASE_ID` to export.

## 2. The Phase 1 integration test (~5 minutes)

```bash
export AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX     # printed by setup script
export AIRTABLE_TABLE=Firms
export AIRTABLE_IN_RADIUS_ONLY=1              # free tier: load 111 firms, not 867
python3 src/pipeline.py --as-of 2026-07-14
python3 src/pipeline.py --as-of 2026-07-14    # run twice on purpose
```

Pass criteria (check in the Airtable UI):
- [ ] Firms table holds **111 records** (not 222 — the second run must update, not duplicate).
- [ ] Spot-check **MJB FINANCIAL PLANNING** (CRD 141373): Lincoln, 4.2 mi, AUM $60,239,269,
      Fit 5, Readiness 5, First Registered 2006-11-01.
- [ ] Set a Stage/Notes value on any record by hand, re-run the pipeline, confirm your manual
      values survive (the writer only touches its own columns).
- [ ] A run reports `'written': 111` and no `http 422` errors.

If you see HTTP 422, the base schema and `crm_writer._fields_for()` have drifted — the error
message now prints Airtable's explanation of which field is wrong.

**Free-tier budget notes:** each full run ≈ 12 API calls in in-radius mode (cap: 1,000/month);
the base cap is 1,000 records total across all tables — 111 firms leaves ~890 for interactions
and compliance rows during the pilot. Upgrade to Team ($20/seat/mo) before loading all 867 firms
or going live with Mark's team.

## 3. Views to create by hand (~5 minutes — the API can't create views)

In the **Firms** table:
1. **Prospect Queue** — grid, filter `in Stage = empty OR 01/02`, sort Fit desc then Readiness desc.
2. **Active Relationships** — filter Stage 03–11 and Outcome = Active, group by Stage.
3. **Monthly Touch Due** — filter Cadence = Monthly and Next Touch Date ≤ today.
4. **Sweet Spot Map** — filter AUM $25M–$125M and Distance ≤ 90, sort Distance asc.
5. **Do Not Contact** — filter Do Not Contact = checked (review before any outreach batch).

In **Compliance Log**: one grid view sorted Timestamp desc, fields locked.

## 4. Automations (2, within the free plan's 100 runs/month)

1. *When Next Touch Date is today* → send email/Slack to owner ("touch due: {Firm Name}").
2. *When Stage changes to "08 Raised Hand"* → notify Mark immediately.

## 5. Stage names are provisional

The 13 stages in the Stage select are placeholders in NBC's honorable-exit language — Mark should
rename them in place (renaming options in Airtable preserves existing records; do not delete and
re-add). If he supplies a different 13, edit the choice names only.

## 6. What the pipeline owns vs what the client owns

| Pipeline-owned (overwritten monthly) | Client-owned (never touched) |
|---|---|
| CRD, Firm Name, City, State, Distance, AUM, Employees, IARs, Fit/Readiness Score, Band, Reg Type, First Registered, Item 11, Website, Phone | Stage, Relationship Score, Cadence, Next Touch Date, Owner, Notes, Outcome, Do Not Contact, Opt-Out Date, all Interactions, all Compliance Log rows |

Never re-key pipeline columns by hand — corrections belong upstream (in the feed or scoring
rules), otherwise next month's run silently reverts them.
