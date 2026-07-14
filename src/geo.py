"""Distance-from-Lincoln calculations and Census geocoder handling.

Spec-silent choices:
- The Census batch geocoder CSV has no header row; columns are read
  positionally: id, input address, match indicator, match type, matched
  address, "lon,lat", tigerline id, side.
- A match indicator of ``Tie`` still carries usable coordinates (the
  geocoder picked one of several equally-good candidates), so it is
  treated like ``Match`` for distance purposes but is never labeled
  ``exact`` — only an exact match indicator + exact match type earns
  that label.
- ``impute_from_zip`` only pulls coordinates from *exactly* matched
  records (never from other zip-imputed or non-exact ones), to avoid
  compounding error across imputation rounds.
"""

import csv
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import LINCOLN_LAT, LINCOLN_LON, RADIUS_MI

EARTH_RADIUS_MI = 3958.8


def haversine_miles(lat1, lon1, lat2, lon2):
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.asin(min(1.0, math.sqrt(a)))
    return EARTH_RADIUS_MI * c


def load_geocodes(path):
    """Load Census batch geocoder output into crd -> geocode info.

    Returns {} (and prints a warning) if the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        print("WARNING: geocode file not found at %s -- proceeding with no "
              "geocode data (all distances will be unknown)." % path)
        return {}

    geocodes = {}
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row:
                continue
            crd = row[0].strip()
            match = row[2].strip() if len(row) > 2 else ""
            match_type = row[3].strip() if len(row) > 3 else ""

            lat = lon = None
            if len(row) > 5 and row[5].strip():
                coord = row[5].strip()
                parts = coord.split(",")
                if len(parts) == 2:
                    try:
                        lon = float(parts[0].strip())
                        lat = float(parts[1].strip())
                    except ValueError:
                        lat = lon = None

            geocodes[crd] = {
                "lat": lat,
                "lon": lon,
                "match": match,
                "match_type": match_type,
            }
    return geocodes


def _has_usable_coords(g):
    return (
        g is not None
        and g.get("lat") is not None
        and g.get("lon") is not None
        and g.get("match") in ("Match", "Tie")
    )


def impute_from_zip(records, geocodes):
    """Compute zip-fallback coordinates for records lacking a usable geocode.

    Returns dict: crd -> {'lat', 'lon', 'quality'} where quality is
    'zip_imputed' (mean of same-zip exact matches) or 'failed' (no
    usable geocode and no zip-mates to borrow from).
    """
    zip_to_coords = {}
    for rec in records:
        g = geocodes.get(rec.get("crd"))
        if g and g.get("match") == "Match" and g.get("lat") is not None:
            zip5 = (rec.get("zip") or "")[:5]
            if zip5:
                zip_to_coords.setdefault(zip5, []).append((g["lat"], g["lon"]))

    imputed = {}
    for rec in records:
        crd = rec.get("crd")
        g = geocodes.get(crd)
        if _has_usable_coords(g):
            continue  # already geocoded directly; no imputation needed

        zip5 = (rec.get("zip") or "")[:5]
        coords = zip_to_coords.get(zip5)
        if coords:
            mean_lat = sum(c[0] for c in coords) / len(coords)
            mean_lon = sum(c[1] for c in coords) / len(coords)
            imputed[crd] = {"lat": mean_lat, "lon": mean_lon, "quality": "zip_imputed"}
        else:
            imputed[crd] = {"lat": None, "lon": None, "quality": "failed"}
    return imputed


def attach_distance(records, geocodes):
    """Attach geo_lat, geo_lon, geo_quality, distance_mi, in_radius to each record."""
    imputed = impute_from_zip(records, geocodes)

    for rec in records:
        crd = rec.get("crd")
        g = geocodes.get(crd)

        if _has_usable_coords(g):
            rec["geo_lat"] = g["lat"]
            rec["geo_lon"] = g["lon"]
            if g.get("match") == "Match" and g.get("match_type") == "Exact":
                rec["geo_quality"] = "exact"
            else:
                rec["geo_quality"] = "non_exact"
        else:
            fallback = imputed.get(crd, {"lat": None, "lon": None, "quality": "failed"})
            rec["geo_lat"] = fallback["lat"]
            rec["geo_lon"] = fallback["lon"]
            rec["geo_quality"] = fallback["quality"]

        if rec["geo_quality"] == "failed":
            rec["distance_mi"] = None
            rec["in_radius"] = False
        else:
            dist = haversine_miles(LINCOLN_LAT, LINCOLN_LON, rec["geo_lat"], rec["geo_lon"])
            rec["distance_mi"] = round(dist, 1)
            rec["in_radius"] = dist <= RADIUS_MI

    return records
