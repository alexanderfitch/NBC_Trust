"""End-to-end pipeline: parse feeds -> geocode -> score -> export -> diff.

Spec-silent choices:
- "previous snapshot" is found by globbing data/processed/firms_*.json,
  parsing the date out of the filename, and taking the latest one that
  is strictly less than --as-of (lexicographic ISO-date comparison).
- The Airtable export is always attempted after the CSV export; per
  spec it degrades gracefully (prints + returns skipped) when
  credentials or network are unavailable, so it never affects the
  pipeline's exit code.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import AS_OF, DATA_PROCESSED, DATA_RAW, RADIUS_MI
from parse_feeds import parse_all
from geo import load_geocodes, attach_distance
from score import score_all
from crm_writer import CSVCRMWriter, AirtableCRMWriter
from compliance import effective_exclusions, apply_exclusions
from diff import diff_snapshots

SNAPSHOT_RE = re.compile(r"^firms_(\d{4}-\d{2}-\d{2})\.json$")


def _sec_feed_path(as_of):
    return DATA_RAW / ("firms_sec_NE_IA_KS_MO_%s.xml" % as_of)


def _state_feed_path(as_of):
    return DATA_RAW / ("firms_state_NE_IA_KS_MO_%s.xml" % as_of)


def _geocode_path(as_of):
    return DATA_RAW / ("geocoded_%s.csv" % as_of)


def _find_previous_snapshot(as_of):
    if not DATA_PROCESSED.exists():
        return None
    candidates = []
    for path in DATA_PROCESSED.glob("firms_*.json"):
        m = SNAPSHOT_RE.match(path.name)
        if m and m.group(1) < as_of:
            candidates.append((m.group(1), path))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0])
    return candidates[-1][1]


def _summarize(records):
    total = len(records)
    by_feed = {}
    by_reg_type = {}
    by_geo_quality = {}
    in_radius = 0

    for rec in records:
        by_feed[rec["feed"]] = by_feed.get(rec["feed"], 0) + 1
        by_reg_type[rec["reg_type"]] = by_reg_type.get(rec["reg_type"], 0) + 1
        quality = rec.get("geo_quality", "unknown")
        by_geo_quality[quality] = by_geo_quality.get(quality, 0) + 1
        if rec.get("in_radius"):
            in_radius += 1

    return {
        "total": total,
        "by_feed": by_feed,
        "by_reg_type": by_reg_type,
        "by_geo_quality": by_geo_quality,
        "in_radius": in_radius,
    }


def _print_summary(summary):
    print("=== Pipeline summary ===")
    print("Total records: %d" % summary["total"])
    print("By feed: %s" % dict(sorted(summary["by_feed"].items())))
    print("By reg_type: %s" % dict(sorted(summary["by_reg_type"].items())))
    print("In radius: %d" % summary["in_radius"])
    print("Geocode quality: %s" % dict(sorted(summary["by_geo_quality"].items())))


def _print_diff_summary(diff):
    print("=== Diff vs previous snapshot ===")
    print("New: %d, Dropped: %d, Changed fields: %d" % (
        len(diff["new"]), len(diff["dropped"]), len(diff["changed"])
    ))


def _print_exclusion_summary(report, withheld):
    """Report opt-out enforcement. Loud when Airtable could not be consulted."""
    status = report["airtable_status"]
    if status == "ok":
        print("Opt-out check: %d in Airtable, %d in local audit file, %d effective."
              % (report["airtable"], report["local"], report["effective"]))
    else:
        # Fail closed and say so: the local file still applies, but a newly
        # checked box in Airtable would not be visible to this run.
        print("Opt-out check: Airtable NOT consulted (%s). Enforcing the %d "
              "exclusion(s) in the local audit file only -- a newer opt-out "
              "recorded in Airtable would NOT be caught by this run."
              % (status, report["local"]))

    if report["newly_recorded"]:
        print("  Newly recorded in compliance/exclusions.csv: %s"
              % ", ".join(report["newly_recorded"]))

    if withheld:
        print("  Withheld from CSV + Airtable (%d): %s"
              % (len(withheld),
                 ", ".join("%s (%s)" % (r.get("crd"), r.get("business_name"))
                           for r in withheld)))


def main(argv=None):
    parser = argparse.ArgumentParser(description="NBC_Trust succession pipeline")
    parser.add_argument("--as-of", default=AS_OF, help="As-of date (YYYY-MM-DD)")
    parser.add_argument("--radius", type=float, default=RADIUS_MI, help="Radius in miles")
    args = parser.parse_args(argv)

    as_of = args.as_of
    radius_mi = args.radius

    sec_path = _sec_feed_path(as_of)
    state_path = _state_feed_path(as_of)
    geocode_path = _geocode_path(as_of)

    records = parse_all(sec_path, state_path)

    geocodes = load_geocodes(geocode_path)
    attach_distance(records, geocodes)
    if radius_mi != RADIUS_MI:
        for rec in records:
            if rec["geo_quality"] != "failed":
                rec["in_radius"] = rec["distance_mi"] <= radius_mi

    score_all(records)

    records.sort(key=lambda r: r.get("crd") or "")

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    snapshot_path = DATA_PROCESSED / ("firms_%s.json" % as_of)
    with open(snapshot_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, sort_keys=True, ensure_ascii=True)
        fh.write("\n")

    # Permanent opt-out enforcement (README "Opt-out requests"; D-016).
    # Runs BEFORE any outreach surface is written. Excluded firms stay in the
    # JSON snapshot flagged excluded=True so diffs stay honest, but they are
    # withheld from the CSV and from Airtable.
    excluded_crds, excl_report = effective_exclusions(as_of)
    releasable, withheld = apply_exclusions(records, excluded_crds)
    _print_exclusion_summary(excl_report, withheld)

    # Rewrite the snapshot now that every record carries its excluded flag.
    with open(snapshot_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, sort_keys=True, ensure_ascii=True)
        fh.write("\n")

    csv_path = DATA_PROCESSED / ("crm_export_%s.csv" % as_of)
    csv_writer = CSVCRMWriter(csv_path)
    csv_result = csv_writer.upsert_firms(releasable, as_of)
    print("CSV export: %s" % csv_result)

    airtable_writer = AirtableCRMWriter()
    airtable_result = airtable_writer.upsert_firms(releasable, as_of)
    print("Airtable export: %s" % airtable_result)

    prev_snapshot_path = _find_previous_snapshot(as_of)
    if prev_snapshot_path is not None:
        with open(prev_snapshot_path, "r", encoding="utf-8") as fh:
            prev_records = json.load(fh)
        diff = diff_snapshots(prev_records, records)
        changes_path = DATA_PROCESSED / ("changes_%s.json" % as_of)
        with open(changes_path, "w", encoding="utf-8") as fh:
            json.dump(diff, fh, indent=2, sort_keys=True, ensure_ascii=True)
            fh.write("\n")
        print("Diffed against previous snapshot: %s" % prev_snapshot_path.name)
        _print_diff_summary(diff)
    else:
        print("No previous snapshot found before as-of=%s; skipping diff." % as_of)

    summary = _summarize(records)
    _print_summary(summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())
