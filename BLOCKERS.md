# What I need from other people

_Maintained by Alex · last updated 2026-09-09 · companion to PLAN.md_

Everything I can build without input from anyone else is either done or in progress. This is the
list of things that are genuinely blocked, ordered so the cheapest and most time-critical asks
come first. Each entry says **what** I need, **why** it blocks, and **what I'm doing meanwhile**
so nothing idles.

---

## Urgent — decide before the video shoot

These stop being cheap the moment Drew starts filming.

### 1. Video voicemails: yes or no? · *Mark, Sam, me*
**Need:** a decision on whether outbound uses "video voicemail" clips.
**Why it blocks:** Sam's own plan notes this has to be settled *before* the shoot, because it
changes what Drew films. Deciding after means a second shoot.
**Worth raising:** Sam suggests these could be shot internally on an iPhone — when authenticity
matters, lower production value can help rather than hurt. That would decouple it from Drew's
schedule entirely and make this reversible.
**Meanwhile:** nothing to build; the decision is the deliverable.

### 2. Approve the video production proposal · *NBC leadership*
**Why it blocks:** everything downstream of the shoot — messaging strategy, case study, microsite
copy, thought leadership. It's the first domino.

### 3. Who gets interviewed? · *Mark + Sam*
**Need:** one interview (likely Scott) or the full set (Mark, Scott, Dan, Morgan, possibly Kaci).
**Why it blocks:** Drew can't schedule or quote until he knows scope.
**My view, for what it's worth:** the case study rests on Dan and Morgan's actual handover, so
their own accounts are the load-bearing footage. A single Scott interview gets the strategy but
not the story.

---

## Blocking the microsite build

### 4. Brand assets · *NBC's web dev, or Mark*
**Need:** the real palette (hex values), typefaces, logo files, and any existing design system or
CSS from the main NBC Trust site.
**Why it blocks:** the microsite has to look like it belongs on their domain, not like a separate
product. Right now the palette is my placeholder guess.
**Meanwhile:** every colour is a CSS custom property in one `:root` block — swapping them is a
few minutes' work once I have real values.

### 5. Domain and mount point · *me + NBC's web dev*
**Need:** confirm the real domain, and whether this lives at `nbctrust.com/succession` or on a
subdomain. (PLAN.md decision #6.)
**Why it blocks:** canonical URLs, the sitemap, and internal links. It also matters for SEO — a
subdirectory inherits the main domain's authority, a subdomain largely doesn't. **I'd push for the
subdirectory** for that reason.
**Meanwhile:** already handled — `path_prefix` in `microsite/site.json` is the single source of
truth, so this is a one-line change either way.

### 6. Hosting and deploy target · *NBC's web dev*
**Need:** what the main site runs on (WordPress? a CMS? static?), and how I get pages onto it —
do I hand over built HTML, or does it need to be authored in their CMS?
**Why it blocks:** the forms in particular. A static host needs a serverless function for form
posts; a CMS may already have form handling I should use instead of building.
**Meanwhile:** building the site as plain static HTML/CSS with no framework, which is the easiest
thing to hand over in any of those scenarios.

### 7. Homepage feature · *NBC's web dev*
**Need:** agreement to feature the microsite on the main site homepage, and a slot spec.
**Why it blocks:** nothing I build, but it's the single biggest traffic driver in the plan and
it's not mine to schedule. Worth starting early — external web dev timelines rarely compress.

---

## Blocking real content

### 8. Microsite copy sign-off · *NBC leadership, compliance attorney*
**Update 2026-10-21:** Sam has stepped out; the microsite was redesigned and rewritten in full as
The Owner's Table (D-025), so this is no longer waiting on anyone to *write* copy.
**Need now:** NBC leadership to approve the positioning, the working name, and the draft copy, and
Dan to approve (or replace) the quote attributed to him, which is draft wording.
**Why it blocks:** launch, not the build. Every page is `status: draft` until approved, and
`python3 microsite/build.py --check` lists what is still owed.

### 9. Finished videos · *Drew*
**Need:** the 4–5 edited shorts, plus poster frames and captions.
**Meanwhile:** five video slots are wired and rendering labelled placeholders. Dropping in real
files is editing `videos` in `microsite/site.json`. My working titles are guesses — Drew's actual
edit list replaces them.

### 10. Checklist content · *Mark, Scott, with Dan and Morgan*
**Need:** the actual substance of the succession checklist.
**Why it blocks:** the primary download and the main lead-capture mechanism in Sam's plan.
**Note:** Sam is explicit that the backbone has to come from NBC Trust leadership, not from us —
he'll shape the copy, but Dan and Morgan are the best source of what actually mattered.

### 11. Messaging strategy elements · *NBC + Sam*
**Need:** which elements Sam should develop — tagline, elevator statement, category descriptor,
keyword do/don't list.
**Why it blocks:** scopes my category-descriptor research (PLAN.md B2).
**Flag:** there's a real tension in the "name a new category" idea. A coined term has zero search
volume by definition, so owning a category and ranking for existing demand pull against each
other. My recommendation is to do both deliberately — own the descriptor in brand copy, rank for
what advisers actually search — but that should be a conscious choice before Sam commits.

---

## Blocking launch (start early, these have external lead times)

### 12. Compliance attorney review · *NBC leadership to engage*
**Need:** review of all public copy, the consent language on the checklist form, required
disclosures, and a privacy policy.
**Why it blocks:** launch, absolutely. v1 of this project built nothing public; v2 is public by
design, from a company examined by the Fed and the Nebraska Department of Banking. This is a
serial dependency on an outside party — worth starting before the copy is final so the review
loop isn't the last thing standing.
**Meanwhile:** the footer carries a placeholder disclosure block, and I'm keeping every public
asset versioned in git so there's a reviewable record of what was published when.

### 13. Analytics and consent tooling · *Mark*
**Need:** which analytics they want (or approval to use something privacy-respecting), and whether
a cookie consent banner is required.
**Why it blocks:** C6, and it interacts with #12 — a Fed-examined firm's public site tracking
visitors is a compliance question, not just a technical one.

### 14. Email platform · *Mark, me*
**Need:** what they'll send outbound from.
**Why it blocks:** PLAN.md E3, and this one matters: **suppression has to read
`compliance/exclusions.csv`.** An opted-out firm must be unreachable by every channel, not just
the CSV export. If email goes out through a platform that doesn't honour that register, the
promise in README is false again — the exact bug D-016 just closed.

---

## Outstanding from Phase 1

### 15. The real ground-truth firm list · *Mark* ⚠️
**Need:** Mark's own 5–10 known Lincoln/Omaha-area firms.
**Why it matters:** this is a formal condition on the Phase 1 GO. DATA_QUALITY_REPORT.md §10
passes the gate on a *provisional* list I assembled from public knowledge (D-010), and the report
flags it as requiring replacement before outreach begins. Everything downstream now rests on that
list being right.
**This has been open since July.** Worth chasing.

### 16. Airtable base ID and a token with `data.records:read` · *me*
**Need:** to verify opt-out enforcement end to end against the live base (PLAN.md A5).
**Why it blocks:** I've tested it against synthetic data and it passes, but the live check needs a
token I shouldn't hold. Ticking "Do Not Contact" on one record and re-running the pipeline is a
two-minute test.

### 17. Rename the 13 CRM stages · *Mark*
**Need:** NBC's real language for the 13 pipeline stages.
**Why it blocks:** nothing technically — they're placeholders and renaming preserves records. But
the follow-up comms sequence (E4) gets designed around these names, so earlier is better.

---

## Not blocked — parked by decision

**Next-generation advisers ("Morgans").** Deferred until the primary funnel is live (PLAN.md §8).
The `next-generation` page exists as a minimal placeholder so a Morgan arriving via the case study
finds something addressed to them, and B6 keeps channel knowledge current. No individual-level
data, which is what keeps the system structurally free of anything that could proxy age.
