# DECISIONS.md — assumptions, trade-offs, dead ends

_Append-only log for auditability. Client is examined by the Federal Reserve and the Nebraska
Department of Banking and Finance; this file is part of the audit trail._

## D-001 · 2026-07-14 · Data source selection
The SEC.gov FOIA "Form ADV Data" page states explicitly: *"The SEC does not have access to data
for state-registered investment advisers."* Its monthly CSV zips cover SEC-registered advisers +
ERAs only, and post-2025 data moved to adviserinfo.sec.gov. **Decision:** use the IAPD
*compilation reports* instead — daily XML feeds published by the SEC's IAPD site that include a
dedicated **State Investment Adviser Report** (state RIAs file Form ADV through the same IARD
system): `https://reports.adviserinfo.sec.gov/reports/CompilationReports/IA_FIRM_STATE_Feed_MM_DD_YYYY.xml.gz`
and `IA_FIRM_SEC_Feed_MM_DD_YYYY.xml.gz`. Both are U.S.-government public data, not BrokerCheck;
constraint #1 satisfied. State feed includes Part 1A Items 1,3,5,6,7,8,9,10,11 + Part 1B.

## D-002 · 2026-07-14 · Snapshot as-of
Feeds dated 2026-07-14 (published daily). SEC feed: 23,532 firms nationwide; State feed: 21,723.

## D-003 · 2026-07-14 · Environment constraint: no shell network access
This build sandbox denies all network egress from the shell (curl denied twice, incl. with sandbox
override). **Workaround:** acquired the feeds through the in-app browser — fetched the .gz
same-origin from reports.adviserinfo.sec.gov, decompressed with DecompressionStream, stream-split
on `</Firm>`, kept firms with main office in NE/IA/KS/MO, and exported raw XML + parsed rows to
`data/raw/`. **Production design remains the straightforward one**: a `download_feeds.py` step
using plain HTTPS GET, keeping the full national .gz immutably in `data/raw/`. The in-browser path
is a spike-only workaround, not part of the deliverable pipeline.

## D-004 · 2026-07-14 · Scope cut at acquisition: 4-state subset
Only firms with main office in NE, IA, KS, MO were persisted (889 firms: 522 SEC feed, 367 state
feed). Justification: 90 mi around Lincoln cannot reach any other state — nearest SD point ≈130 mi,
CO/WY ≫300 mi. MO's northwest corner (~Rock Port) is ~70 mi straight-line, so MO is included.
Risk accepted: a firm whose MAIN office is elsewhere but with a branch near Lincoln is excluded in
the MVP (branch data exists in the rep-level feed; noted as a Phase-2+ enhancement and a known
limitation in the report).

## D-005 · 2026-07-14 · Stdlib-only Python for the spike
Sandbox has Python 3.9, no pandas/requests, and no pip (no network). **Decision:** implement the
pipeline with the standard library only (xml.etree, csv, json, math, urllib). Production
recommendation stays Python 3.11 + pinned pandas, but nothing in the data volume (≲1k rows)
requires it. Determinism is easier without heavy deps anyway.

## D-006 · 2026-07-14 · Radius default
Brief conflicts ("1.5 hours" vs "four-hour drive"). Default **90 mi** per the brief's own TODO
default; configurable single constant `RADIUS_MI`. All firms in the 4-state set are kept in the
processed output with `in_radius` flags, so widening the radius is a re-run, not a re-download.

## D-007 · 2026-07-14 · Straight-line distance, not drive time
Haversine miles from Lincoln (40.8136, −96.7026). A routing API would add a key, a dependency and
a failure mode to estimate something the client evaluates by eye anyway ("can I drive there and
back for lunch?"). At this radius the error is modest and symmetric. Revisit if the client wants
true drive-time bands.

## D-008 · 2026-07-14 · Cross-feed dedup rule
A CRD can appear in both feeds (e.g., mid-transition firms; 4 duplicate CRDs observed in the
4-state set). Rule: keep the SEC-feed record, flag `also_in_state_feed=true`. CRD is the primary
key everywhere.

## D-009 · 2026-07-14 · Geocode fallback
Census batch geocoder is authoritative; failures ("C/O …" addresses, new suites) fall back to the
mean lat/lon of successfully geocoded firms in the same 5-digit ZIP (`zip_imputed`), else
`failed` (excluded from radius, listed in the report). At 90 mi, ZIP-centroid error (±3 mi) cannot
flip an in/out decision except within ~3 mi of the boundary — acceptable; production can re-geocode
failures via the interactive Census endpoint.

## D-010 · 2026-07-14 · Ground-truth list is provisional
Client has not yet supplied the 5–10 known-firm list (Appendix A #4). Substituting a provisional
list of well-known Lincoln/Omaha-area RIAs assembled from public knowledge and verified against
IAPD. The report flags this as REQUIRING client replacement before the GO is final.

## D-011 · 2026-07-14 · Delegation ledger
- Feed download/parse: done by lead in-browser (forced by D-003; would otherwise be Haiku work).
- Census batch geocode transfer: Haiku agent (mechanical, exact steps supplied).
- Pipeline modules + unit tests: Sonnet agent (well-specified implementation).
- Coverage analysis, ground-truth audit, report, GO/NO-GO: lead (Fable) — judgment calls.
- README / GitHub Actions workflow / production download script: Haiku agent.
Escalations: none required — Haiku geocode agent (889 addresses, 93% match, zero deviations) and
Sonnet pipeline agent (31/31 tests, deterministic) both passed acceptance on the first attempt.

## D-013 · 2026-07-14 · Tenure anchor year
`score.py` anchors tenure at year 2026 per the spec formula rather than deriving from `--as-of`.
Fine for monthly runs this year; make it dynamic when convenient (one-line change, noted in the
module docstring).

## D-014 · 2026-07-14 · Change-detection evidence
Verified against a synthetic prior snapshot (2 removals, 1 ghost, ±AUM mutations). Evidence kept in
`docs/validation_evidence/`; the synthetic snapshot is stored OUTSIDE `data/processed/` so real
monthly diffs never compare against it.

## D-012 · 2026-07-14 · Age handling
No individual ages exist anywhere in the firm-level feeds (none are collected on Part 1A), so the
no-age constraint is structurally satisfied; the readiness proxy is firm tenure + size only, and
`band_label` is a text label with no numbers. The rep-level feed (IA_INDVL) contains exam dates
that could proxy individual age — deliberately NOT ingested in Phase 1.
