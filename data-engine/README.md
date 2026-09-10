# data-engine

The prospect data pipeline: public SEC Form ADV feeds in, scored and deduplicated firms out.

```bash
make test                                        # 53 tests
make run                                         # pipeline at the config default as-of
python3 data-engine/src/pipeline.py --as-of 2026-07-14 --radius 90
```

- `src/` — pipeline modules. `pipeline.py` orchestrates; `config.py` holds every tunable constant.
- `tests/` — unit tests, run from the monorepo root via `make test`.
- `scripts/` — `download_feeds.py` (monthly refresh), `setup_airtable.py` (base schema, run once).
- `data/raw/` — immutable feed snapshots. **Never edit or delete**; IAPD does not archive, so a
  lost snapshot is lost permanently.
- `data/processed/` — pipeline output: JSON snapshots, CSV export, month-over-month diffs.

Two roots matter here (`src/config.py`): `ENGINE_ROOT` is this directory, `REPO_ROOT` is the
monorepo root. Anything shared across workstreams — `compliance/` above all — is addressed from
`REPO_ROOT`, because the microsite writes there too.
