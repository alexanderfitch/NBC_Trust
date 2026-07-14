"""Fit / readiness scoring and human-readable band labels.

Spec-silent choice: the spec's tenure formula literally anchors on the
year 2026 (``2026 - int(first_reg_date[:4])``) rather than deriving the
"current year" from config.AS_OF. That's kept literal here since the
spec gives an exact formula; if AS_OF ever moves off 2026 this constant
would need revisiting alongside it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import AUM_SWEET_MIN, AUM_SWEET_MAX

CURRENT_YEAR = 2026


def _tenure_years(rec):
    first_reg_date = rec.get("first_reg_date")
    if not first_reg_date:
        return None
    return CURRENT_YEAR - int(first_reg_date[:4])


def _is_clean_item11(rec):
    return rec.get("item11_flag") == "N" and rec.get("item11_yes_count") == 0


def _is_sweet_spot_aum(rec):
    aum_total = rec.get("aum_total")
    return aum_total is not None and AUM_SWEET_MIN <= aum_total <= AUM_SWEET_MAX


def fit_score(rec):
    score = 1
    reasons = []

    aum_total = rec.get("aum_total")
    if _is_sweet_spot_aum(rec):
        score += 2
        reasons.append("AUM in sweet spot ($25M-$125M)")
    elif aum_total is not None and (
        10_000_000 <= aum_total < AUM_SWEET_MIN or AUM_SWEET_MAX < aum_total <= 200_000_000
    ):
        score += 1
        reasons.append("AUM near sweet spot ($10M-$25M or $125M-$200M)")

    if _is_clean_item11(rec):
        score += 1
        reasons.append("clean disciplinary record (Item 11)")

    total_employees = rec.get("total_employees")
    if total_employees is not None and 1 <= total_employees <= 10:
        score += 1
        reasons.append("small employee count (1-10)")

    return min(score, 5), reasons


def readiness_score(rec):
    score = 1
    reasons = []

    tenure = _tenure_years(rec)
    if tenure is not None and tenure >= 20:
        score += 2
        reasons.append("long tenure (20+ years registered)")
    elif tenure is not None and 10 <= tenure < 20:
        score += 1
        reasons.append("established tenure (10-19 years registered)")

    iar_count = rec.get("iar_count")
    if iar_count is not None and iar_count <= 2:
        score += 1
        reasons.append("small adviser headcount (<=2 IARs)")

    total_employees = rec.get("total_employees")
    if total_employees is not None and total_employees <= 3:
        score += 1
        reasons.append("small total headcount (<=3 employees)")

    return min(score, 5), reasons


def band_label(rec):
    tenure = _tenure_years(rec)
    labels = []

    if tenure is not None and tenure >= 20:
        labels.append("long-tenured")
    elif tenure is not None and 10 <= tenure < 20:
        labels.append("established")

    total_employees = rec.get("total_employees")
    if total_employees is not None and total_employees <= 3:
        labels.append("small team")

    iar_count = rec.get("iar_count")
    if iar_count is not None and iar_count <= 1:
        labels.append("single-adviser")

    if _is_clean_item11(rec):
        labels.append("clean record")

    if _is_sweet_spot_aum(rec):
        labels.append("sweet-spot AUM")

    return ", ".join(labels)


def score_all(records):
    for rec in records:
        fit, fit_reasons = fit_score(rec)
        readiness, readiness_reasons = readiness_score(rec)
        rec["fit_score"] = fit
        rec["fit_reasons"] = fit_reasons
        rec["readiness_score"] = readiness
        rec["readiness_reasons"] = readiness_reasons
        rec["band_label"] = band_label(rec)
        rec["relationship_score"] = None
    return records
