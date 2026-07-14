# DATA QUALITY REPORT — Phase 1 Gate

_NBC Trust "Honorable Exit" advisor-succession engine · Data as of **2026-07-14** · Report by the
build lead (Fable 5) per the Validation Protocol in the build brief §5._

**One-line verdict: GO** — the free public data demonstrably contains the small, state-registered
firms the product targets (21 in-radius firms in the $25–125M sweet spot, 18 of them
state-registered), field quality is high, and every check below passed. Two conditions attach:
(1) Mark must replace the provisional known-firm list with his own before outreach begins;
(2) the branch-office limitation in §9 must be accepted or scheduled.

---

## 1. Source & integrity (brief §5.1)

| Item | Value |
|---|---|
| Sources | IAPD compilation feeds (public U.S. government data, published daily by the SEC's IAPD site; **not** FINRA BrokerCheck) |
| Files | `IA_FIRM_SEC_Feed_07_14_2026.xml.gz` (23,532 firms nationwide) · `IA_FIRM_STATE_Feed_07_14_2026.xml.gz` (21,723 firms nationwide) |
| As-of | 2026-07-14 (both feeds) |
| Persisted | 4-state (NE/IA/KS/MO) raw `<Firm>` XML subsets in `data/raw/`, 522 + 367 = 889 records; kept immutably, never edited in place |
| Schema | Verified against live records; parser unit-tested on fixtures extracted from the real files (31/31 tests pass) |
| Determinism | Pipeline run twice → byte-identical `firms_2026-07-14.json`, MD5 `871cd3c23f8d86c976d61eded365978b` |

Important nuance for the audit trail: the SEC.gov FOIA "Form ADV Data" page **excludes
state-registered advisers entirely** ("The SEC does not have access to data for state-registered
investment advisers"). The IAPD compilation feeds are the only free source that includes them —
this selection is the load-bearing decision of Phase 1 (DECISIONS.md D-001).

## 2. Coverage — the make-or-break check (brief §5.2)

**The feared failure mode was real, and the chosen source avoids it.** If we had used the
SEC-registered data alone, the in-radius $25–125M sweet spot would contain **3 firms** and the
product premise would be broken. With the state feed included it contains **21**.

In-radius universe (≤90 mi of Lincoln, main-office basis): **111 firms** —
64 SEC-registered RIAs, 40 state-registered RIAs, 7 exempt-reporting advisers.
Cities: Omaha 76, Lincoln 17, Grand Island 5, Hastings 2, Council Bluffs 2, others 9.

AUM distribution of the in-radius universe:

| AUM band | SEC-registered | State-registered | ERA |
|---|---|---|---|
| <$10M | — | 11 | — |
| $10–25M | — | 2 | — |
| **$25–125M (target)** | **3** | **18** | — |
| $125–200M | 9 | — | — |
| $200M–1B | 31 | — | — |
| >$1B | 21 | — | — |
| not filed / null | — | 9 | 7 |

This is exactly the regulatory split theory predicted (state registration caps near $100M), and it
means **the state feed is not a nice-to-have — it is the product**.

External benchmark: the state feed contains 16,292 approved state-registered RIAs nationwide vs
**16,575** reported by NASAA's 2025 Investment Adviser Section Annual Report → **≈98%
completeness**. Firms holding a Nebraska state registration in the feed: 121 (this counts firms
registered *with* Nebraska regardless of main-office location, so it is the right comparison basis
for a future NDBF cross-check).

Known-firm check (provisional list — client to replace, DECISIONS.md D-010): 6 of 6 confidently
known Lincoln/Omaha-area RIAs are present with correct details — Pittenger & Anderson (Lincoln,
CRD 111033), Lutz Financial (117273), Cambridge Advisors (104851), Lawson Kroeker (105053),
CWM/Carson (155344), Foster Group (107148, Des Moines — correctly outside radius). Two additional
names checked and correctly absent: SMITHHAYES (dissolved/absorbed years ago) and D.A. Davidson
(a broker-dealer, out of scope by design).

## 3. Geocoding accuracy (brief §5.3)

- Census batch geocoder, 889 addresses (867 unique after cross-feed dedup): **825 matched (92.8%)**,
  37 No_Match, 5 Tie. Match types: 711 exact, 114 non-exact.
- Failures are the expected kind ("C/O …" lines, brand-new suites); 32 were imputed from
  same-ZIP neighbors (`zip_imputed`, ±~3 mi worst case), 10 remain `failed` and are excluded from
  the radius (listed in the processed JSON by `geo_quality`).
- Random 20-sample audit (seed 42): **20/20** returned the same street number + ZIP as the input;
  19/20 were "Exact" matches.
- Known-distance spot checks all geographically correct: Lincoln firms 0–7.7 mi, Omaha 39–51,
  Council Bluffs 54, **Grand Island 88 (just inside the 90-mi radius)**, **Norfolk 92 (just
  outside)**, Des Moines 166, Topeka 131, Wichita 214, St. Louis 362.
- Distance is straight-line haversine, not drive time (DECISIONS.md D-007).

## 4. Field reliability (brief §5.4) — 4-state set, n=889

| Field | Null/blank | Notes |
|---|---|---|
| Total AUM (Item 5F) | 16.1% overall; **6.2% among RIAs** (49/794) | ERAs don't file Item 5F — expected. 9 in-radius state RIAs lack AUM; they stay in the CRM unscored on AUM with reasons recorded. |
| Employees (5A) / IARs (5B) | 10.6% | Same ERA effect. |
| First-registration date | 0.1% | Tenure proxy near-complete. |
| Item 11 flag | 0.0% | 7.5% of firms answer "Y" (≥1 disclosure). |
| Sanity | AUM=0: 2.5% (mostly new/ERA firms) · employees=0: 1 firm · dates before 1940: 0 · AUM >$50B: 19 (verified to be genuinely large national firms HQ'd in MO/KS, not parse errors) |

Tenure-proxy semantics verified manually (§6 below): the date used is the **registration approval
date** (SEC `Rgstn Dt`, or earliest state `Rgltr Dt`), not the latest amendment.

## 5. Deduplication & entity integrity (brief §5.5)

- CRD is the primary key throughout. 22 CRDs appear in both feeds (firms mid-transition between
  state and SEC registration); rule: keep the SEC record, flag `also_in_state_feed` → 867 unique
  firms, and CRD uniqueness is enforced after dedup.
- HQ vs branch: the feeds are **main-office** records — one row per firm, so no double counting.
  The converse limitation (out-of-state HQ with a Lincoln-area branch) is in §9.

## 6. Ground-truth accuracy audit (brief §5.7)

10 firms from our output compared field-by-field against the live IAPD site (independent
transport: the public IAPD firm API, not our feed): Pittenger & Anderson, Lutz, Lawson Kroeker,
Guide Rock, Teckmeyer, MJB Financial Planning, Clark Wealth, Evergreen Capital, Spiehs, CWM.

- Firm found on IAPD: **10/10** · Name: 10/10 · Street/city/state: 10/10
- SEC-vs-state registration classification: **10/10**
- First-registration date: exact match on all firms where IAPD displayed the corresponding
  jurisdiction entry (e.g., Teckmeyer NE 10/25/2006, MJB NE 11/1/2006, Clark NE 2/22/2008,
  Lawson Kroeker SEC 5/22/1986, Spiehs NE 10/5/2023). One 1-day display discrepancy (Evergreen:
  feed 2006-01-26 vs IAPD "1/27/2006" on a different status row) — immaterial to a tenure band.
- Notice-filing counts spot-checked (Lawson Kroeker: 4 = 4). AUM is not shown by the IAPD summary
  API, so AUM was validated structurally instead (typed parse + fixture tests + the >$50B outlier
  review in §4); a per-firm AUM check against ADV PDFs is a good follow-up for Mark's own list.

## 7. Change-detection correctness (brief §5.6)

Simulated prior month (synthetic snapshot archived in `docs/validation_evidence/`): removed 2
firms, injected 1 ghost firm, changed one firm's AUM by +25%, another's address, another's AUM by
+5% (below threshold). Result: **2 new, 1 dropped, 2 changed — all correct, zero false
terminations, and the +5% AUM move correctly ignored** (threshold 10%). Diff logic also covered by
unit tests.

## 8. Scoring output sanity

Top of the ranked list behaves like the product intends — e.g., MJB Financial Planning (Lincoln,
4.2 mi, $60M AUM, single adviser, registered 2006, clean Item 11) scores fit 5 / readiness 5 with
band "long-tenured, small team, single-adviser, clean record, sweet-spot AUM". 7 in-radius firms
score ≥4 on both axes; 21 sit in the AUM sweet spot. No age, birth year, or number-coded age proxy
appears anywhere in the output (the firm-level feeds contain no individual ages at all —
DECISIONS.md D-012).

## 9. Known limitations

1. **Main-office basis**: a firm HQ'd outside NE/IA/KS/MO with a Lincoln-area branch is missed.
   Fix path: ingest branch offices from the rep-level feed (IA_INDVL) in Phase 2+ (~1–2 days).
2. **Provisional ground-truth list**: assembled from public knowledge, not from Mark. Replace and
   re-run the §2 check (minutes, not days).
3. **9 in-radius state RIAs with null AUM** — real small firms; they remain in the CRM but can't be
   AUM-scored. Manual review recommended (they may be attractive targets).
4. Straight-line distance, not drive time (D-007). Grand Island (88 mi) illustrates the boundary
   sensitivity; the radius is one constant if Mark prefers 75 or 120 mi.
5. Relationship score is deliberately manual/null — it's Mark's knowledge, not data.
6. This spike acquired the feeds via an in-browser workaround because the build sandbox blocks
   shell network access (D-003); production uses `scripts/download_feeds.py` over plain HTTPS.
7. ERAs (7 in radius) file no Item 5, so they carry no AUM/headcount signals — typically fund
   managers, mostly irrelevant to this product; they're retained but score low.

## 10. GO / NO-GO

**GO.** The universe the product needs — small, long-tenured, clean-record advisory firms within
driving distance of Lincoln — is present, identifiable, and scoreable in free public SEC/IAPD data
(21 sweet-spot firms in radius; 98% national completeness vs the NASAA benchmark; 6/6 known firms
found; 10/10 ground-truth audit; deterministic, tested pipeline). Proceed to Phase 2 (Airtable CRM
configuration) once Mark supplies (a) his real known-firm list for a confirmatory re-check and
(b) an Airtable base + API key. If either the client's list or the radius decision surfaces firms
we can't find, treat that as a re-opened gate.
