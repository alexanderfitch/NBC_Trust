# NBC Trust "Honorable Exit" — Build Plan

_Author: Fable 5 (technical lead / orchestrator) · Started 2026-07-14 · Status: Phase 1 in progress_

## 1. Objective restatement (≤200 words)

NBC Trust ($175M AUM trust company, Lincoln NE) wants a repeatable, dignified advisor-succession
pipeline: identify small ($25–125M AUM) advisory firms within ~90 miles of Lincoln from **public
SEC Form ADV data only**, score them on fit and succession-readiness, load them into **Airtable**
for relationship-driven outreach across 13 stages, and host an invitation-only "raise your hand"
page. Hard constraints: no FINRA BrokerCheck data (ToU prohibits marketing use), no age in any
public-facing output (internal "retirement-readiness band" only), auditable and simple enough for
a solo maintainer, deliverable is the tool — never guaranteed leads.

**The #1 risk is coverage**: ideal targets are small firms, which are usually *state*-registered,
while the SEC's headline bulk files cover only SEC-registered advisers ($100M+) and ERAs. If
in-radius sub-$100M firms aren't in the free data, the product premise fails. Phase 1 therefore
front-loads a Data Validation Protocol with a GO/NO-GO gate before anything else is built.

**Resolution found on day 1:** the SEC's IAPD site publishes daily *compilation feeds* that include
a **State-Registered Investment Adviser Report** (state RIAs file ADV through the same IARD
system), with Item 5 (AUM, employees, clients) and Item 11 — so state-registered small firms ARE
in free, public SEC-published data. Coverage is quantified in DATA_QUALITY_REPORT.md.

## 2. Open questions & operating assumptions (Appendix A)

| # | Question | Assumption in force |
|---|----------|--------------------|
| 1 | RIAs or brokers? | RIAs / investment advisers (Form ADV universe). BD-only reps are out of scope — confirm with Mark. |
| 2 | Radius | **90 mi (~1.5 h)** MVP; configurable (`src/config.py: RADIUS_MI`), widen to 4h later. |
| 3 | AUM band | $25–125M as **scoring input**, not a hard filter. |
| 4 | Ground-truth firms | Client list not yet supplied. Using a **provisional** list of publicly known Lincoln/Omaha RIAs (see DATA_QUALITY_REPORT §7); Mark must replace with his own 5–10 names. |
| 5 | State vs SEC registered targets | Answered empirically — both are covered; see coverage section of the report. |
| 6–8 | Deck ownership / hosting / deliverable framing | No build impact in Phase 1; deliverable framed as "the tool" throughout. |
| 9 | Regulator framing | Fed + NE Dept. of Banking; compliance attorney reviews public copy. Nothing public-facing is built in Phase 1. |

## 3. Phase map

- **Phase 1 (NOW)** — Data pipeline + validation gate. See §4.
- **Phase 2** — Airtable CRM config: Firms table (pipeline-owned fields locked), Interactions table,
  Compliance log table, 13-stage single-select, views per cadence (monthly/quarterly/annual),
  last-touch automations. ~2–3 days once the base/API key exist.
- **Phase 3** — Invitation landing page: static page (client's voice + video embed), "raise your
  hand" form → Airtable via a tiny serverless function; consent text + timestamped opt-in/opt-out
  log. No age language; compliance-attorney review loop.
- **Phase 4** — Compliance tooling: versioned copies of every public asset, append-only consent
  log export, one-command audit bundle (CSV + PDF).
- **Phase 5 (optional)** — AI prospect briefs: one-paragraph firm summary + editable outreach note
  draft from the firm's public ADV record. Nothing that "warms up" or persuades.

## 4. Phase 1 task list

| # | Task | Depends on | Owner (model tier) | Status |
|---|------|-----------|--------------------|--------|
| 1 | Verify live data sources; confirm state-RIA coverage exists | — | **Lead (Fable)** — judgment | ✅ done |
| 2 | Acquire feeds (SEC + State, as-of 2026-07-14), persist raw | 1 | Lead (env constraints forced hands-on; see D-003/D-004) | ✅ done |
| 3 | Geocode 889 addresses via Census batch | 2 | **Cheap (Haiku)** — mechanical, fully specified | 🔄 running |
| 4 | Pipeline code: parse → distance → score → CSV/Airtable writer → diff + unit tests | 2 | **Mid (Sonnet)** — from lead's spec | 🔄 running |
| 5 | Coverage analysis (SEC vs state, AUM distribution, NE benchmark) | 2 | **Lead (Fable)** — the make-or-break judgment | next |
| 6 | Ground-truth checks (known firms, IAPD field audit, geocode spot checks) | 3,4 | Lead + cheap agents for lookups | pending |
| 7 | Change-detection verification (simulated second snapshot) | 4 | Mid (Sonnet) | pending |
| 8 | DATA_QUALITY_REPORT.md + GO/NO-GO | 5,6,7 | **Lead (Fable)** | pending |
| 9 | README, Makefile, monthly schedule config | 4 | Cheap (Haiku) | pending |

Parallelization: 3 ∥ 4 (running now); 5 alongside; 6 fans out.

## 5. Tech choices (one-line justifications)

- **Python, stdlib-only for the spike** (xml.etree, csv, json, urllib): this sandbox has no pip/network; production pins Python 3.11 + pandas, but stdlib keeps the spike runnable anywhere. (D-005)
- **Data source: IAPD compilation feeds** (`IA_FIRM_SEC_Feed_*.xml.gz`, `IA_FIRM_STATE_Feed_*.xml.gz`, daily, public domain): the only free source that includes state-registered RIAs with Item 5/11 data. The FOIA monthly zips exclude state RIAs entirely.
- **Geocoding: U.S. Census batch geocoder**: free, no key, 10k addresses/request, public-domain results; cache results in repo.
- **CRM: Airtable behind a `CRMWriter` interface** with a CSV implementation as fallback/systems-of-record export: swappable per constraint #4.
- **Scheduling: GitHub Actions monthly cron** (spec'd, not yet enabled — needs a repo remote + secrets).
- **Distance: haversine straight-line** at 90 mi (≈1.5–2.0 h drive in NE road network); driving-time API adds a dependency for marginal MVP value. (D-007)

## 6. Data-quality proof (read of Section 5)

Every check in the brief's §5 maps to a numbered section of `DATA_QUALITY_REPORT.md`:
source integrity & determinism (5.1) via re-run hash comparison; coverage (5.2) via
SEC/state/ERA counts in-radius, AUM distribution, provisional known-firm check, NE-total
benchmark vs external count; geocoding (5.3) via match-rate + 20-sample manual audit + known-city
spot distances; field reliability (5.4) via null/sanity tables + manual tenure-date verification
on IAPD; dedup (5.5) via CRD uniqueness + cross-feed dedup rule; change detection (5.6) via a
mutated-snapshot test with zero-false-termination assertion; ground truth (5.7) via 10-firm
field-level IAPD comparison. The report ends with a one-line GO/NO-GO and, if NO-GO, the exact
gap and cost to close it.
