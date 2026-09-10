# NBC Trust "Honorable Exit" Succession Pipeline — Phase 1

This repository contains the first phase of NBC Trust's advisor-succession research engine: a repeatable data pipeline that identifies small ($25–125M AUM) investment-adviser firms within ~90 miles of Lincoln, Nebraska, from public SEC Form ADV data, and loads qualified prospects into Airtable for relationship-driven outreach. NBC Trust is a $175M AUM trust company committed to dignified advisor successions as a core business practice.

This phase validates the core data sources and provides a working pipeline; all subsequent CRM workflow, scoring refinement, and landing-page infrastructure depend on a passing Data Quality validation gate. See `DATA_QUALITY_REPORT.md` for coverage analysis, geocoding validation, deduplication rules, and the formal GO/NO-GO decision.

## Data sources

The pipeline uses **two public, daily SEC-published XML feeds** that include both SEC-registered investment advisers (RIAs with $100M+ AUM) and state-registered RIAs (smaller advisers filing with their state), with Item 5 (AUM, employees) and Item 11 fields:

- `https://reports.adviserinfo.sec.gov/reports/CompilationReports/IA_FIRM_SEC_Feed_MM_DD_YYYY.xml.gz` — SEC-registered RIAs
- `https://reports.adviserinfo.sec.gov/reports/CompilationReports/IA_FIRM_STATE_Feed_MM_DD_YYYY.xml.gz` — State-registered RIAs

Both are U.S. government public domain data published through the SEC's Investment Adviser Public Disclosure (IAPD) system. The pipeline deliberately excludes FINRA BrokerCheck data due to its marketing-use restrictions.

## Repository layout

- **`data/raw/`** — Immutable snapshots of downloaded feeds (XML) and geocoding results (CSV), keyed by ISO date. Never delete or modify files here.
- **`data/processed/`** — Pipeline output: JSON snapshots of scored/deduplicated firms, CSV exports, and diffs showing month-over-month changes.
- **`src/`** — Pipeline modules: `pipeline.py` (orchestrator), `parse_feeds.py`, `geo.py`, `score.py`, `crm_writer.py`, `compliance.py` (opt-out enforcement), `diff.py`, `config.py`.
- **`tests/`** — Unit tests for pipeline modules.
- **`compliance/`** — `exclusions.csv`, the append-only permanent opt-out register. Append only; never delete a row (see "Opt-out requests" below and DECISIONS.md D-016).
- **`scripts/`** — Utility scripts, including `download_feeds.py` (monthly data refresh).
- **`docs/`** — This README, `DATA_QUALITY_REPORT.md`, `PLAN.md`, and `DECISIONS.md`.

## How to run

### Quick test
```bash
make test
python3 src/pipeline.py
```

The pipeline defaults to the `AS_OF` date in `src/config.py`. To process a different date:
```bash
python3 src/pipeline.py --as-of 2026-07-21 --radius 90
```

The `--radius` flag is optional (default 90 miles); all firms in the processed output include an `in_radius` flag so you can re-filter without re-running.

### Monthly refresh
```bash
python3 scripts/download_feeds.py --date 07-14-2026
python3 src/pipeline.py --as-of 2026-07-14
```

By default, `download_feeds.py` uses today's date; pass `--date MM_DD_YYYY` to fetch a specific date. The script skips download if the files already exist (immutability); delete `data/raw/firms_*.xml` if you need to re-fetch.

## Airtable setup

To load prospects directly into Airtable, set these environment variables before running the pipeline:

- `AIRTABLE_API_KEY` — Your Airtable personal access token (keep this secret; never commit it).
- `AIRTABLE_BASE_ID` — The ID of the Airtable base where prospects are stored.
- `AIRTABLE_TABLE` — The name of the table to load (e.g., "Firms").

```bash
export AIRTABLE_API_KEY="pat_..."
export AIRTABLE_BASE_ID="app_..."
export AIRTABLE_TABLE="Firms"
python3 src/pipeline.py
```

If any of these are missing, the pipeline will skip Airtable upload and print a notice. **A CSV export is always written to `data/processed/` regardless of Airtable credentials.**

## Monthly refresh via GitHub Actions

A scheduled GitHub Actions workflow runs on the 3rd of each month at 12:00 UTC. To enable it:

1. Create a GitHub repository secret for `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID`, and `AIRTABLE_TABLE`.
2. Push this repository to GitHub.
3. The workflow at `.github/workflows/monthly.yml` will automatically download the latest feeds and run the pipeline, committing the results back to the repo.

For a manual run, use the "Run workflow" button in the GitHub Actions tab.

## Data handling and PII

Prospect data is sensitive and must be handled carefully:

- **Airtable base access:** Keep the base restricted to authorized NBC Trust staff only. Use Airtable's sharing and API-token scoping to enforce least-privilege access.
- **No secrets in the repository:** Never commit Airtable API keys, FINRA credentials, or personal information to version control.
- **Opt-out requests:** If a prospect requests removal from the research list, tick **Do Not Contact** on their Firms record in Airtable (or set `Opt-Out Date`, or `Outcome = Do Not Contact` — any one of the three is honoured) and log the request in the Compliance Log table. **That prospect is never re-imported by a future run.** Enforcement is in `src/compliance.py` and runs before any outreach surface is written: the firm is withheld from the CSV export and from the Airtable upsert, and its CRD is appended to `compliance/exclusions.csv` — an append-only file committed to git, so the exclusion survives Airtable itself and is still enforced when the pipeline runs with no token or no network. Excluded firms remain in the JSON research snapshot flagged `excluded: true` so month-over-month diffs stay honest and the exclusion is provable to an examiner. Nothing in the code ever removes an exclusion; reinstating a firm is a deliberate edit of that CSV, visible in git history. See DECISIONS.md D-016.
- **Consent:** All outreach materials generated from this data are subject to federal compliance review before publication.

## Known limitations

See `DATA_QUALITY_REPORT.md` Section 9 for a complete list of data-quality trade-offs, geocoding fallbacks, and out-of-scope enhancements (e.g., multi-state branch offices, rep-level tenure data).
