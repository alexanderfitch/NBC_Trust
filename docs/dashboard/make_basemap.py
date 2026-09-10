"""Regenerate the prospect dashboard's basemap path data.

Why this exists: the dashboard is a single self-contained HTML file with no
tile server, no CDN and no network dependency (it is an internal tool that
must open from the filesystem and never leak prospect coordinates to a third
party). So the basemap is baked in as SVG path data rather than fetched at
view time.

Source: US Census Bureau TIGERweb State_County service, full resolution,
US federal government public domain -- the same provenance discipline as the
ADV feeds (DECISIONS.md D-001).

The projection constants MUST match map() in prospect_dashboard.html. If you
change the viewBox or radius there, change them here and re-run.

Usage:
    python3 docs/dashboard/make_basemap.py              # fetch and print JSON
    python3 docs/dashboard/make_basemap.py --write      # patch the dashboard
    python3 docs/dashboard/make_basemap.py --input f.json   # use a local cache
"""

import argparse
import json
import math
import re
import urllib.parse
import urllib.request
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parent / "prospect_dashboard.html"

# --- must match map() in prospect_dashboard.html --------------------------
W, H = 640, 560
LAT, LON = 40.8136, -96.7026          # downtown Lincoln
MIPD = 69.0                           # miles per degree latitude
R = 97                                # visible radius, miles
SCALE = min(W, H) / 2 / R             # px per mile
COS = math.cos(math.radians(LAT))

# Detail is only worth paying for where it can be seen. Inside the frame
# (plus a margin so clipped edges never seam) we keep ~0.9 mile of detail --
# fine enough for the Missouri River's meanders at 2.9 px/mile, and half the
# payload of the 0.5-mile version, which showed no visible difference;
# outside we thin aggressively, because the ring still has to close for the
# land fill to work but nobody can see its shape.
PAD = 60
NEAR_TOL_PX = 2.5
FAR_TOL_PX = 45.0

STATES = {"Nebraska": "NE", "Iowa": "IA", "Kansas": "KS",
          "Missouri": "MO", "South Dakota": "SD"}
FIPS = {"31": "NE", "19": "IA", "20": "KS", "29": "MO", "46": "SD"}

# Hand-placed so each label sits in open space -- clear of the dot clusters and
# of the ring labels, which run down the left diagonal at (255,353) (194,414)
# (132,476). KS in particular has to avoid that diagonal.
LABEL_ANCHORS = {"NE": (41.55, -97.9), "IA": (41.55, -95.3),
                 "KS": (39.55, -96.3), "MO": (40.05, -95.15)}


def project(lon, lat):
    return (W / 2 + (lon - LON) * COS * MIPD * SCALE,
            H / 2 - (lat - LAT) * MIPD * SCALE)


def fetch():
    base = ("https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/"
            "State_County/MapServer/0/query")
    params = {
        "where": "STATE IN ('%s')" % "','".join(FIPS),
        "outFields": "NAME,STATE",
        "returnGeometry": "true",
        "geometryPrecision": "4",
        "outSR": "4326",
        "f": "geojson",
    }
    req = urllib.request.Request(base + "?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": "NBCTrust-succession-research"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def _rings(geom):
    polys = (geom["coordinates"] if geom["type"] == "MultiPolygon"
             else [geom["coordinates"]])
    for poly in polys:
        for ring in poly:
            yield ring


def _visible(x, y):
    return -PAD <= x <= W + PAD and -PAD <= y <= H + PAD


def simplify(points):
    """Thin a projected ring, keeping detail only inside the visible frame."""
    kept = [points[0]]
    for x, y in points[1:-1]:
        px, py = kept[-1]
        tol = NEAR_TOL_PX if (_visible(x, y) or _visible(px, py)) else FAR_TOL_PX
        if (x - px) ** 2 + (y - py) ** 2 >= tol * tol:
            kept.append((x, y))
    kept.append(points[-1])
    return kept


def build(data):
    paths, stats = {}, {}
    for feat in data["features"]:
        props = feat["properties"]
        code = STATES.get(props.get("NAME")) or FIPS.get(str(props.get("STATE")))
        if not code:
            continue
        out, vis_pts = [], 0
        for ring in _rings(feat["geometry"]):
            pts = [project(lon, lat) for lon, lat in ring]
            if not any(_visible(x, y) for x, y in pts):
                continue
            kept = simplify(pts)
            if len(kept) < 3:
                continue
            out.append("M" + "L".join("%.1f %.1f" % p for p in kept) + "Z")
            vis_pts += sum(1 for p in kept if _visible(*p))
        if out:
            paths[code] = out
            stats[code] = (sum(len(d) for d in out), vis_pts)

    labels = {c: tuple(round(v, 1) for v in project(lo, la))
              for c, (la, lo) in LABEL_ANCHORS.items()}
    return paths, labels, stats


def write_into_dashboard(paths, labels):
    html = DASHBOARD.read_text(encoding="utf-8")
    new_paths = "const BASEMAP = %s;" % json.dumps(paths, separators=(",", ":"))
    new_labels = "const BASEMAP_LABELS = %s;" % json.dumps(labels, separators=(",", ":"))
    html, n1 = re.subn(r"const BASEMAP = .*?;\n", new_paths + "\n", html, count=1, flags=re.S)
    html, n2 = re.subn(r"const BASEMAP_LABELS = .*?;\n", new_labels + "\n", html, count=1, flags=re.S)
    if not (n1 and n2):
        raise SystemExit("Could not find BASEMAP declarations in %s" % DASHBOARD)
    DASHBOARD.write_text(html, encoding="utf-8")
    print("patched %s" % DASHBOARD.name)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", help="local GeoJSON cache instead of fetching")
    ap.add_argument("--write", action="store_true", help="patch the dashboard in place")
    args = ap.parse_args()

    data = json.load(open(args.input)) if args.input else fetch()
    paths, labels, stats = build(data)

    total = sum(chars for chars, _ in stats.values())
    for code in sorted(stats):
        chars, vis = stats[code]
        print("  %-3s %5d chars, %4d points inside the frame" % (code, chars, vis))
    print("total path payload: %.1f KB" % (total / 1024))

    if args.write:
        write_into_dashboard(paths, labels)
    else:
        print("\n(dry run -- pass --write to patch the dashboard)")


if __name__ == "__main__":
    main()
