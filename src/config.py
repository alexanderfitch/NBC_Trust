"""Shared configuration constants for the NBC_Trust pipeline.

Spec-silent choices made here:
- Paths are resolved relative to the repository root (the parent of this
  ``src`` directory), so the pipeline works the same whether invoked as
  ``python3 src/pipeline.py`` from the repo root or imported from tests.
- AS_OF is a plain string (not a date object) since every consumer only
  ever needs it for filename templating and simple string comparisons.
"""

from pathlib import Path

# Approximate downtown Lincoln, NE coordinates.
LINCOLN_LAT = 40.8136
LINCOLN_LON = -96.7026

# Search radius, in miles, used to flag firms as "in range" of Lincoln.
RADIUS_MI = 90.0

# AUM "sweet spot" for succession-ready targets (regulatory AUM, USD).
AUM_SWEET_MIN = 25_000_000
AUM_SWEET_MAX = 125_000_000

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_PROCESSED = REPO_ROOT / "data" / "processed"

AS_OF = "2026-07-14"
