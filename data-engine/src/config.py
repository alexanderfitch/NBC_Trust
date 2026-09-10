"""Shared configuration constants for the NBC_Trust pipeline.

Spec-silent choices made here:
- Paths are resolved relative to ``data-engine/`` (the parent of this
  ``src`` directory), so the pipeline works the same whether invoked as
  ``python3 data-engine/src/pipeline.py`` from the monorepo root or
  imported from tests. Shared artifacts outside the engine are addressed
  from ``REPO_ROOT`` instead -- see the note on the two roots below.
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

# Two roots, deliberately distinct (D-018):
#   ENGINE_ROOT is data-engine/ -- everything this pipeline owns lives under it.
#   REPO_ROOT is the monorepo root -- shared, cross-workstream artifacts live there
#   (compliance/ in particular, which the microsite will also write to).
ENGINE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ENGINE_ROOT.parent
DATA_RAW = ENGINE_ROOT / "data" / "raw"
DATA_PROCESSED = ENGINE_ROOT / "data" / "processed"

AS_OF = "2026-07-14"
