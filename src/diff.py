"""Compare two firm-record snapshots keyed by CRD.

Spec-silent choice: "relative change >10%" for aum_total is computed as
abs(new - old) / abs(old), guarding old == 0 by treating any change off
of a zero AUM as reportable (falls under the None<->value style jump).
"""

FIELDS_TO_COMPARE = [
    "business_name",
    "street1",
    "city",
    "state",
    "zip",
    "aum_total",
    "total_employees",
    "iar_count",
    "item11_flag",
    "reg_type",
]

AUM_RELATIVE_CHANGE_THRESHOLD = 0.10


def _aum_changed(old, new):
    if old is None and new is None:
        return False
    if old is None or new is None:
        return True
    if old == 0:
        return new != 0
    return abs(new - old) / abs(old) > AUM_RELATIVE_CHANGE_THRESHOLD


def diff_snapshots(prev_records, curr_records):
    prev_by_crd = {rec["crd"]: rec for rec in prev_records}
    curr_by_crd = {rec["crd"]: rec for rec in curr_records}

    prev_crds = set(prev_by_crd)
    curr_crds = set(curr_by_crd)

    new_crds = sorted(curr_crds - prev_crds)
    dropped_crds = sorted(prev_crds - curr_crds)

    changed = []
    for crd in sorted(prev_crds & curr_crds):
        prev_rec = prev_by_crd[crd]
        curr_rec = curr_by_crd[crd]
        for field in FIELDS_TO_COMPARE:
            old_val = prev_rec.get(field)
            new_val = curr_rec.get(field)
            if field == "aum_total":
                if _aum_changed(old_val, new_val):
                    changed.append({"crd": crd, "field": field, "old": old_val, "new": new_val})
            else:
                if old_val != new_val:
                    changed.append({"crd": crd, "field": field, "old": old_val, "new": new_val})

    return {
        "new": new_crds,
        "dropped": dropped_crds,
        "changed": changed,
    }
