# NBC Trust "Honorable Exit" — Build Plan v2

_Owner: Alex (data + web + digital) · v2 written 2026-09-09 · Supersedes the Phase-1-only plan_

> **What changed.** v1 planned a data pipeline feeding an *invitation-only* "raise your hand"
> page. The client's actual strategy (Sam's "NBC TRUST SUCCESSION PLANNING PHASE I" doc) has
> evolved into a **public, inbound attraction funnel**: a microsite on the NBC Trust domain,
> fed by video storytelling, a case study, a downloadable checklist, thought leadership, digital
> placements and email. Two prospect personas are now named. My scope grew from "the data engine"
> to **data + microsite build + digital strategy + SEO/keyword research**.
> The original v1 plan is preserved in git history at commit `708d146`. Strategic pivot logged as
> D-017.

## 1. Objective

Give NBC Trust ($175M AUM trust company, Lincoln NE) a repeatable engine for attracting advisors
who want a dignified succession. Two halves, run concurrently:

- **Data (me)** — find and qualify the prospect universe, build the microsite that converts it,
  own digital placement and SEO, and keep the whole thing auditable.
- **Comms (Sam, with Drew on video)** — messaging strategy, video storytelling, case study,
  checklist content, thought leadership, email copy.

Hard constraints carried forward from v1, all still binding: public SEC Form ADV data only, **no
FINRA BrokerCheck** (ToU forbids marketing use), **no age in any public-facing output**, auditable
for Fed / Nebraska Dept. of Banking examination, simple enough for a solo maintainer. The
deliverable is the engine — never guaranteed leads.

## 2. The two personas

| | **"Dan"** | **"Morgan"** |
|---|---|---|
| Who | Senior advisor approaching succession | Next-generation advisor / successor |
| Status | **Phase 1 — active now** | **Deferred — see §8** |
| Data | Firm-level Form ADV (built, GO) | None built. Would need individual-level data. |

Dan and Morgan are also real NBC Trust people and the subjects of the case study — their actual
experience is the proof story the whole funnel rests on.

**Morgans are explicitly out of scope until everything else ships.** Reasoning and the constraint
that makes it non-trivial are in §8; the short version is that identifying individual advisors
means rep-level data, which reopens the age question D-012 closed on purpose. Sam's doc asks that
microsite copy stay *Morgan-aware* so we don't paint into a corner — that costs nothing now and is
noted in Stage D.

## 3. Division of labor

| Who | Owns |
|---|---|
| **Alex (me)** | Prospect data engine · microsite build · digital messaging strategy & placements · SEO/keyword research & category-descriptor analysis · thought-leadership opportunity finding · outbound target lists · CRM/pipeline mechanics · compliance tooling |
| **Sam** | Messaging strategy · microsite copy · case study · checklist content · thought-leadership writing · email/outbound copy · follow-up comms sequence |
| **Drew** | Video shoot and edit (4–5 short videos + B-roll) |
| **NBC leadership** (Mark, Scott) | Approve video proposal · choose interview subjects · supply checklist backbone · rename the 13 CRM stages · compliance-attorney review |
| **NBC's existing web dev** | Homepage feature that drives traffic to the microsite; possibly digital creative production |

## 4. Stages

Stages B and C start **now** and are deliberately copy-independent — the mistake to avoid is
idling until Sam's copy lands.

### Stage A — Data foundation · *largely done*

| # | Task | Status |
|---|------|--------|
| A1 | Pipeline: parse → geocode → distance → score → CSV/Airtable → diff | ✅ GO (DATA_QUALITY_REPORT.md) |
| A2 | Airtable CRM base, schema-as-code, free-tier load path | ✅ built; base live, 111 in-radius firms loaded |
| A3 | Permanent opt-out enforcement (dual-source, fails closed) | ✅ D-016, 53 tests |
| A4 | Airtable views (5+1), 2 automations, rename 13 stages | ⬜ manual UI + Mark's language |
| A5 | Verify opt-out end-to-end against the live base (needs `data.records:read`) | ⬜ |
| A6 | Tenure anchor: derive from `--as-of`, not hardcoded 2026 (D-013) | ⬜ one-liner; skews scores in January |
| A7 | Dashboard reads the JSON snapshot instead of baked-in numbers | ⬜ |
| A8 | Replace provisional ground-truth firm list with Mark's own | ⬜ **condition on the Phase 1 GO** |

### Stage B — Research that unblocks Sam · *starts now*

These are my deliverables **to** Sam. Every one of them makes his messaging strategy better, and
the doc explicitly asks for my input on keywords and Morgan channels.

| # | Task | Feeds |
|---|------|-------|
| B1 | Keyword & search-demand research: what advisors actually search when thinking about exiting | Messaging strategy, microsite SEO, thought-leadership topics |
| B2 | **Category-descriptor analysis** — the doc wants to name a new category (the "RPO" example). Test the tension: an owned term nobody searches vs. ranking for existing demand. Recommend a primary descriptor + the search terms to rank for alongside it | Messaging strategy, positioning |
| B3 | Competitive/SERP landscape: who else talks about advisor succession, what they rank for, where the gaps are | Thought leadership, differentiation |
| B4 | Thought-leadership opportunity map: ranked topics with search demand + difficulty | Sam's writing queue |
| B5 | Digital placement plan: channels, targeting, budget bands, expected CPMs | Outbound + digital creative specs |
| B6 | Morgan channel scan — where next-gen advisors congregate online, **channel-only, no individual data** | Keeps Morgan optionality open at zero cost |

### Stage C — Microsite infrastructure · *starts now, copy-independent*

| # | Task | Notes |
|---|------|-------|
| C1 | **Repo restructure** per §5 — do this first, everything else lands into it | |
| C2 | Site scaffold + design system on the NBC Trust domain, matching main-site brand | Public, SEO-first |
| C3 | Video embed harness for 4–5 shorts + poster frames | Built before videos exist; accepts placeholders |
| C4 | Checklist download: gated form → consent capture → Airtable Compliance Log + follow-up trigger | Lead magnet; consent is a compliance artifact, not a nice-to-have |
| C5 | Contact form → Airtable Firms/Interactions, tied to CRD where we can match | The "contact us directly" CTA |
| C6 | Analytics + conversion tracking, privacy-respecting | Feeds B5 and proves the funnel |
| C7 | SEO technical foundation: metadata, structured data, sitemap, performance budget | |
| C8 | Staging environment + attorney-review workflow for public copy | Review is on the critical path now |

### Stage D — Microsite assembly · *blocked on Sam's copy + Drew's videos*

| # | Task | Blocked on |
|---|------|-----------|
| D1 | Integrate real copy: microsite hub, story-form case study | Sam |
| D2 | Integrate finished videos | Drew |
| D3 | Checklist PDF production from NBC leadership's content | Mark/Scott, Dan/Morgan |
| D4 | Morgan-aware pass: parallel view or cross-link, per Sam's note | Decision in §7 |
| D5 | Homepage feature coordination | NBC's web dev |
| D6 | Compliance-attorney review of all public copy → revisions | Attorney |
| D7 | Launch | All of the above |

### Stage E — Outbound & follow-up · *needs data + copy*

| # | Task | Notes |
|---|------|-------|
| E1 | Build the high-quality outbound target list from the pipeline | The doc names this as outbound's prerequisite — it's the data engine's payoff |
| E2 | **Video-voicemail decision** | ⚠️ Must be settled **before Drew shoots** (§6). Investigate iPhone-shot internally — low production value reads as authentic here |
| E3 | Email infrastructure, list hygiene, suppression wired to `compliance/exclusions.csv` | An opted-out firm must be unreachable by *every* channel, not just the CSV |
| E4 | Follow-up comms sequence implemented as CRM stages + cadence views | Sam/Mark/me jointly design; I build |
| E5 | Inbound inquiry triage: what happens in the first hour, day, week | |

### Stage F — Compliance tooling · *continuous; hardened before launch*

Was v1's Phase 4, and it's no longer optional-feeling: the moment public copy and inbound consent
exist, this is what makes the whole thing examinable.

| # | Task |
|---|------|
| F1 | Versioned archive of every public asset (copy, video scripts, checklist) with publish dates |
| F2 | Append-only consent log export: opt-ins, opt-outs, download requests, timestamped |
| F3 | One-command audit bundle (CSV + PDF) |
| F4 | Airtable plan upgrade trigger — free tier's 1,000-record cap will not survive real inbound (§9) |

### Stage G — Morgans · *deferred, do not start*

Parked by decision. See §8.

## 5. Proposed repo structure

Everything stays in this repo, split so each part is legible on its own:

```
NBC_Trust/
├── README.md              front door: what this is, how to run, where things live
├── PLAN.md                this file
├── DECISIONS.md           append-only audit log (unchanged)
├── data-engine/           the pipeline
│   ├── src/  tests/  scripts/  data/
├── microsite/             the public site
│   ├── src/  content/  assets/
├── compliance/            exclusions register, consent exports, audit bundles
├── research/              my deliverables to Sam: keyword, SERP, category, placement, TL map
└── docs/                  reports, runbooks, internal dashboard
```

Moving `src/` changes what `config.py:REPO_ROOT` resolves to, so C1 includes fixing those paths
and re-running the suite to prove nothing broke. It is a mechanical change but not a free one —
worth doing before there's more code to move, not after.

## 6. Critical path and the two timing traps

Sam's doc sets the sequence: **videos first** (they generate the insight that shapes messaging),
then messaging strategy, then microsite copy, then thought leadership.

```
Drew: shoot ──────────► edit ──────────► videos done ──────┐
Sam:  questions ──► shoot ──► messaging strategy ──► microsite copy ──► TL copy
Alex: Stage B research ──► Stage C infrastructure ──────────┴──► Stage D assembly ──► launch
```

**Trap 1 — the video-voicemail decision (E2).** If outbound wants video voicemails, that format
has to be decided *before* Drew shoots, or it means a second shoot. This is the cheapest
decision on the list and the most expensive to get wrong.

**Trap 2 — my microsite timeline depends on Sam's copy length and page elements.** Sam names this
explicitly. Mitigation is Stage C: build the scaffold, forms, consent capture and video harness
against placeholder content, so when copy lands it's an integration, not a build.

## 7. Decisions needed

| # | Decision | Who | Blocks |
|---|----------|-----|--------|
| 1 | Approve video production proposal | NBC leadership | Everything downstream |
| 2 | One interview (Scott) or all of Mark/Scott/Dan/Morgan/Kaci | Mark + Sam | Shoot scheduling |
| 3 | Video voicemails yes/no — **before the shoot** | Mark, Sam, me | Shoot scope |
| 4 | Which messaging-strategy elements: tagline, elevator statement, category descriptor, keyword do/don't list | NBC + Sam | B2 scope |
| 5 | Parallel Morgan page, a cross-link, or neither | Sam + me | D4 |
| 6 | Microsite on main domain (`/succession`) vs subdomain | Me + NBC web dev | C2, SEO strategy |
| 7 | Replace provisional ground-truth firm list | Mark | A8, the GO's condition |
| 8 | Airtable paid plan timing | Mark | F4 |

## 8. Morgans — why deferred, and what it will cost later

Decision: **do not build for Morgans until the Dan funnel is live and producing inbound.**

The obstacle is not effort, it's a constraint collision. Finding individual next-gen advisors
means individual-level data, and the only free public source is the SEC's rep-level `IA_INDVL`
feed. D-012 deliberately excluded that feed because it carries exam dates that can proxy
individual age — and "no age anywhere public" is a hard client constraint. Today the constraint is
satisfied *structurally*: no age data exists anywhere in the system, which is a much stronger thing
to tell an examiner than "we have it but we're careful with it."

When we revisit, the options are: (a) ingest rep-level data with exam-date fields dropped at parse
time, documented and attorney-reviewed; (b) reach Morgans purely through channels — digital
targeting, thought leadership, a parallel microsite view — keeping the system structurally
age-free; (c) firm-level proxies (small firms with a second younger IAR) which gets partway there
using data we already have.

Until then, B6 keeps the channel knowledge current at no cost, and D4 keeps the copy from
excluding them.

## 9. Risks

1. **Compliance review is now on the critical path.** v1 built nothing public; v2's entire premise
   is public. Every asset needs attorney review before launch, and that's a serial dependency with
   an external party. Build the review workflow early (C8), don't discover it at launch.
2. **Category descriptor vs. search demand (B2).** Owning a new category term and ranking for what
   people actually search are in tension — a coined term has zero search volume by definition. The
   answer is probably both: own the descriptor in brand copy, rank for existing demand. Worth
   resolving before Sam commits the messaging strategy.
3. **Airtable free tier will break under real inbound.** 1,000 records total across all tables;
   111 firms are already in. Every inquiry, interaction and consent row counts. Set the upgrade
   trigger before launch, not after records start silently failing to write.
4. **External dependency on NBC's web dev** for the homepage feature — the single biggest traffic
   driver in the plan, and not mine to schedule.
5. **Data staleness.** The snapshot is 2026-07-14; IAPD publishes daily and does not archive, so a
   missed month is permanently missed. The GitHub Actions monthly cron exists but is unenabled.
6. **Opt-out must bind every channel (E3).** The register currently gates the CSV and Airtable. The
   moment email exists, suppression has to read the same file or the promise in README is false
   again — which is exactly the bug D-016 just fixed.
7. **Solo maintainer.** Everything here has to stay simple enough to hand over or pick back up
   cold. That constraint killed heavier tooling in v1 and still applies.

## 10. Carried forward / added / dropped vs v1

**Carried forward:** data pipeline and its GO gate · Airtable CRM with 13 stages · opt-out
enforcement · compliance tooling (was Phase 4) · every hard constraint.

**Added:** public SEO-driven microsite (replacing the invitation-only page) · keyword and
category-descriptor research · digital placement strategy · thought-leadership opportunity finding ·
checklist lead magnet with consent capture · video embed infrastructure · homepage traffic feature ·
email/outbound infrastructure · the Dan/Morgan persona split · repo restructure.

**Dropped or parked:** invitation-only gating (superseded by inbound attraction) · v1's Phase 5
"AI prospect briefs" (not in the client's plan; park until asked) · Morgan targeting (§8).
