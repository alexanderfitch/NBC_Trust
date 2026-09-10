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

## D-015 · 2026-07-14 · Phase 2 on Airtable Free, schema as code
Client testing Phase 1 end-to-end on Airtable's free tier. Consequences: (1) base capped at
1,000 records → added `AIRTABLE_IN_RADIUS_ONLY` env flag so the upsert loads the 111 in-radius
firms, not all 867; (2) API calls run from the user's own terminal (build sandbox has no network,
D-003) — which also keeps the token off this machine entirely; (3) the base schema is created by
`scripts/setup_airtable.py` via the Meta API (config-as-code, reproducible) rather than hand-built;
views/automations are manual (no public API) per docs/PHASE2_AIRTABLE.md. The 13 stage names are
provisional placeholders for Mark to rename in place. Writer hardened for user-run testing:
surfaces Airtable 422 error bodies and spaces batches 0.25s under the 5 req/s limit.

## D-016 · 2026-09-09 · Permanent opt-out enforcement (dual-source, fails closed)
README promised that an opted-out prospect is *never* re-imported, but no code implemented it:
the Airtable schema had `Do Not Contact` / `Opt-Out Date` / `Outcome`, and `crm_writer` was
write-only (`performUpsert` on CRD, no GET), so a checked box had no effect on the next run — and
the CSV export, which is what any outreach batch actually works from, still contained the firm.
**Decision:** new `src/compliance.py`, invoked from the pipeline *before* any outreach surface is
written. Effective exclusion set = **union** of (a) `Do Not Contact` OR `Opt-Out Date` OR
`Outcome = "Do Not Contact"` in Airtable, and (b) `compliance/exclusions.csv`, an append-only file
committed to git. Three Airtable signals rather than one because staff reach for whichever field is
in front of them; failing open because someone used the "wrong" field is not acceptable.
Rationale for the local file: the exclusion must survive Airtable itself (a lapsed subscription
nearly happened in Sept 2026), must be enforceable with no token and no network, and must leave a
git-visible audit trail for the Fed / NE Dept. of Banking. An Airtable-only design would silently
stop enforcing exactly when the fetch fails. **Fails closed:** an unreachable Airtable does not
mean "nobody opted out" — the local file still applies and the run prints a loud warning that a
newer Airtable opt-out was not visible to it. Excluded firms are **retained** in the JSON research
snapshot with `excluded=true` rather than dropped, so diffs don't report them as false
terminations (cf. D-014) and an auditor can prove the exclusion was applied rather than inferring
it from an absence; they are withheld from the CSV export and the Airtable upsert. Reinstating a
firm is a deliberate manual edit of the CSV, visible in git history — nothing in code ever removes
an exclusion.

## D-017 · 2026-09-09 · Strategic pivot: invitation-only → public inbound funnel
Client's actual Phase 1 plan (Sam's "NBC TRUST SUCCESSION PLANNING PHASE I" doc, received today)
has evolved away from v1's premise. **Changes of record:**
(1) **Funnel inverted.** v1 Phase 3 was an *invitation-only* "raise your hand" page. It is now a
**public microsite** on the NBC Trust domain, featured from the homepage, fed by video
storytelling, a story-form case study, a downloadable checklist, thought leadership, digital
placements and email. Consequence: compliance-attorney review of public copy moves onto the
critical path, and public-asset versioning (v1 Phase 4) is no longer deferrable.
(2) **Two personas named.** "Dan" = senior advisor approaching succession (Phase 1, active).
"Morgan" = next-generation advisor (deferred by client decision until the Dan funnel is live).
Both are also real NBC Trust staff and the case study's subjects.
(3) **Scope of this workstream expanded** from "the data engine" to data + microsite build +
digital messaging strategy and placements + SEO/keyword research + thought-leadership opportunity
finding. Microsite build is mine; the homepage traffic feature stays with NBC's existing web dev.
(4) **Repo stays a monorepo** at the user's direction, restructured into legible top-level parts
(`data-engine/`, `microsite/`, `compliance/`, `research/`, `docs/`) rather than split across repos.
Deferred by decision: Morgan targeting (needs individual-level data; the free rep-level `IA_INDVL`
feed carries exam dates that proxy age, which D-012 excluded on purpose — revisiting it means
choosing between parse-time field-dropping with attorney review, channel-only reach, or firm-level
proxies; see PLAN.md §8). Also parked: v1's Phase 5 "AI prospect briefs", absent from the client's
plan. v1 plan preserved in git history at 708d146; PLAN.md is now v2.

## D-018 · 2026-09-09 · Monorepo restructure into legible top-level parts
Per D-017(4) the project stays one repo. Restructured (`git mv`, so history follows the files):
`src/ tests/ scripts/ data/` → **`data-engine/`**; new **`microsite/`** (`src/ content/ assets/`),
**`research/`**; **`compliance/`** and **`docs/`** stay at the monorepo root. Each directory has
its own README.
**Why compliance/ stays at the root:** it is not the pipeline's private state. The microsite will
write consent records and download requests to the same append-only register the pipeline reads
for suppression. One register, one truth, at the root where both workstreams can see it.
**The one code change required:** `config.py` previously had a single `REPO_ROOT =
parent.parent`, which after the move would have silently resolved to `data-engine/` and pointed
`compliance/` at the wrong place. Now split: `ENGINE_ROOT` (data-engine/) for pipeline data,
`REPO_ROOT` (monorepo root) for shared artifacts. Every other relative path — `tests`'
`parent.parent / "src"`, `download_feeds.py`'s `parent.parent / "data"` — was already relative to
the moved unit and needed no change.
Also updated: Makefile, `.github/workflows/monthly.yml` (which now also commits
`compliance/exclusions.csv`, since a monthly run can newly record an opt-out), `.gitignore`,
README layout, docs/PHASE2_AIRTABLE.md command paths. Verified: 53/53 tests pass, `make run`
writes to `data-engine/data/processed/`, `EXCLUSIONS_PATH` resolves to the monorepo root.
**Not rewritten:** path references inside DATA_QUALITY_REPORT.md and earlier DECISIONS entries.
Those are dated audit records and were accurate when written; this entry is the forward pointer.

## D-019 · 2026-09-09 · Microsite: copy/markup separation, stdlib static build
Building Stage C infrastructure before Sam's copy exists requires that integrating the real copy
later is *not* a rebuild. **Decision:** copy lives in `microsite/content/*.md`, markup in
`microsite/src/template.html`, joined by a stdlib-only builder (`microsite/build.py`, no pip, no
toolchain — same constraint as D-005). Sam edits markdown and never touches HTML; when his copy
lands it is a file swap. Side benefit: every page's copy is a versioned file in git, which
satisfies PLAN.md Stage F1 (public-asset versioning) for free rather than as extra work.
Sub-decisions:
- **Markdown subset is deliberately tiny** (headings, lists, blockquote, `**bold**`, `*italic*`,
  links, plus `[video:slug]` and `[cta:kind]` slots). A hand-rolled parser is only defensible
  while it stays small; anything unrecognised is emitted as a paragraph rather than silently
  dropped, so no copy can vanish.
- **Copy is HTML-escaped before inline formatting is applied.** Copy is human-authored and must
  never be able to inject markup; tested both ways.
- **`path_prefix` in site.json is the single source of truth for the mount point**, so PLAN.md
  decision #6 (main domain `/succession` vs a subdomain root) is a one-line config change, not a
  find-and-replace. `--local` builds with an empty prefix for preview and prints a do-not-deploy
  warning, since its canonical URLs omit the prefix.
- **Placeholders are marked with a literal `PLACEHOLDER` token** and `build.py --check` lists every
  one with file and line. Nothing placeholder-y can reach production unnoticed; the build prints a
  running count.
- **Video slots render labelled placeholders** until Drew delivers, so the page is reviewable now
  and the embed is already wired.
- **System fonts only, no CDN.** No webfont round-trip, no third-party dependency on a regulated
  public site, and the performance budget stays intact.
Design intent recorded in styles.css: editorial serif and generous measure, because the reader is
contemplating the end of a career they built — a SaaS landing page would be the wrong register.
Palette and domain are PLACEHOLDER pending NBC's real brand values.

## D-020 · 2026-09-10 · Internal dashboard reachable from the microsite, in preview builds only
Wanted: the prospect dashboard one click from the microsite while working. **Problem:** the
microsite is public by design (D-017), and the dashboard contains the proprietary scored prospect
list — 111 named firms with phone numbers, distances, AUM and succession-readiness scores. A nav
link on a public site would publish the client's confidential prospecting strategy.
**Decision:** `local_tools` in `microsite/site.json`, emitted **only** by `build.py --local`.
`collect_local_tools()` returns `[]` when `local` is false, which is the entire guard — no page is
written, no nav link rendered, and `_sitemap()` only ever receives `pages`, so tools cannot reach
the sitemap by construction. Six tests in `microsite/tests/test_build.py` assert the production
build emits nothing: no directory, no nav entry, no sitemap line. Verified by building both ways
and grepping the output for prospect data (CRD 141373 / MJB FINANCIAL) — clean.
Defence in depth: the copied page gets a sticky red "INTERNAL — confidential prospect data. Local
preview build only; never published" banner injected after `<body>`, and the nav link is styled as
a red outlined pill, deliberately unlike every real nav item, so neither the link nor the page can
be mistaken for public. A missing tool source is skipped with a notice rather than failing the
build, so a moved dashboard never blocks a preview.

## D-021 · 2026-09-10 · Dashboard basemap: baked-in vector, not a tile service
The prospect map showed dots and distance rings on a blank field — no geographic context.
**Rejected:** a tile basemap (Leaflet/Mapbox/OSM). It would add a runtime network dependency and a
CDN to an internal tool that must open from the filesystem, and every pan/zoom would tell a
third-party tile server which patch of Nebraska this firm is studying. Not a data leak in the
strict sense (tile requests carry z/x/y, not prospect records), but it is a needless external
observer on confidential research, on a page that must keep working offline.
**Decision:** bake the basemap in as SVG path data. State outlines for NE/IA/KS/MO/SD, projected
into the same Lincoln-centred equirectangular space `map()` already uses (2.887 px/mile), drawn
beneath the rings and dots, clipped to the frame, `pointer-events:none` so dot tooltips are
unaffected. Source: **US Census Bureau TIGERweb State_County service at full resolution, US
federal government public domain** — same provenance discipline as the ADV feeds (D-001).
Generator committed as `docs/dashboard/make_basemap.py` (`--write` patches the dashboard,
`--input` uses a local cache) so this is reproducible rather than a one-off paste, and so it can
be re-run if the projection constants change.
**Sizing:** the raw source is ~14–24k points per state. Detail is kept only where it can be seen:
~0.9 mile (2.5px) inside the frame plus a 60px margin, thinned to 45px outside — the ring still
has to close for the land fill, but nobody can see its shape out there. 0.5-mile detail was
tried first and cost 30 KB against 20 KB with no visible difference. Dashboard: 40 KB → 61 KB.
First attempt used a 1:20m boundary file, which left only ~12 visible points for Nebraska and
rendered the Missouri River as three straight segments — worse than no basemap, since it
misrepresented the border. Hence full-resolution source plus local simplification.
Also: `--land` / `--land-line` / `--land-label` tokens added to all four theme blocks so the
basemap follows light/dark; the `KS` label was moved to (381,532) because at (200,472) it collided
with the "90 mi" ring label, which sits on the down-left diagonal with the other two.

## D-022 · 2026-09-10 · Microsite visual design: refresh of nbctrustco.com, not a departure
Brief: make the microsite look polished and high-end for client meetings, reading as a modern
refresh of their existing site. Audited nbctrustco.com and pulled the real brand values from its
live stylesheet rather than guessing: **navy `#003D68`** (primary) and **orange `#FF6716`**
(accent), with a heavy serif wordmark. Also confirmed from their team page that **Dan Badeer** is a
real adviser there and **Kaci** is his assistant — the case-study subjects in Sam's doc are real
people, so naming and consent are Sam's and legal's call, not a copy decision.
**Inherited** (so it reads as the same company): the navy, the orange, and serif display type —
their logo is a serif, so editorial serif here is continuity.
**Deliberately left behind** (what dates the current site): dark photo-overlay hero, seven-item
nav, stock photography, bulleted list as a hero, boxed drop-shadow cards, bolted-on accessibility
widget.
**Register:** quiet confidence — the reader is contemplating the end of a career they built, and
the firm asking for that trust is a fiduciary. Editorial serif display, generous measure, hairline
rules instead of boxes, orange used about twice a page. Closer to a private bank's annual review
than a SaaS landing page. Still system fonts only: no CDN, no webfont round-trip, no third-party
request from a regulated public site.
**Structural addition:** `split_hero()` peels the leading `# heading` and its following paragraphs
into a distinct typographic hero region. That separation is most of what makes a page read as
designed rather than as a document.
**Draft copy:** the pages now carry plausible draft copy rather than visible `PLACEHOLDER` notes,
because scaffolding text all over the page undercuts a meeting. Honesty is preserved instead by
per-page `status: draft` front matter, a discreet "Draft — design review copy" ribbon, and
`--check` listing every draft page. `show_draft_notice: false` hides the ribbon for a clean
screen-share; it changes the ribbon, not the facts. Sam still owns final copy. The draft copy
turns their own site's line ("begin with the end in mind") back on the adviser, avoids any
guarantee, and contains no age language (D-012).
**Two real bugs found while verifying, both mine:**
(1) the pending-video placeholder used a gradient `border-box` trick that the solid border painted
straight over, leaving a box 3% off the page colour — effectively invisible. Now a dashed rule plus
a faint diagonal hatch.
(2) `.prose p` (0-1-1) silently outranked `.video__note` (0-1-0), so those tokens were being
ignored. Now scoped under `.video`, and small text deliberately uses `--ink-2` rather than
`--ink-3`, which lands at 3.9:1 on the page ground and fails AA at 13–15px.
Contrast verified in-browser across the palette: body 7.34:1, headings 15.64:1, CTA body on navy
7.46:1, button label on orange 5.6:1, footer body 8.43:1 — all clear of AA. (First measurement
run reported false failures because Chromium serialises `color-mix()` as `color(srgb 0-1)` floats
and the checker assumed 0-255; worth remembering when spot-checking contrast.)
