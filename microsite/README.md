# microsite

**The Owner's Table** — NBC Trust's free community and resource hub for independent advisors who
own their firm, served on the NBC Trust domain (PLAN.md Stage C/D; redesign in DECISIONS.md D-025).

The idea it is built on: *the work that wins back your week is the same work that makes a
practice transferable.* Members get value now (library, tools, briefing, roundtables) and raise
their hand about succession only when they are ready.

- `content/` — all copy, as markdown. Pages are listed in `site.json`; library articles are
  discovered from `content/library/`. Versioning copy is a compliance requirement (PLAN.md F1).
- `src/` — `template.html`, `styles.css`, and `partials/` (forms, tools, the hero illustration).
- `assets/` — the mark, icons and share image (`make_icons.py` regenerates them; needs PIL), and
  self-hosted fonts under `assets/fonts/` with their OFL licences.

```bash
python3 microsite/build.py --local   # preview build at a server root (includes internal tools)
python3 microsite/build.py --check   # list placeholders, draft pages and missing videos
make test-microsite
```

The markdown subset is documented at the top of `build.py`. Write links root-relative
(`/library/`); the mount prefix is added at build time.

Public-facing copy requires compliance-attorney review before launch. Every page is
`status: draft` until it has had it, and nothing here ships without it. The two forms are not
connected to anything yet (PLAN.md C4/C5).
