"""Parse IAPD/SEC Form ADV Part 1A XML feeds into plain dicts.

Spec-silent choices:
- Both raw feed files are a sequence of concatenated ``<Firm>`` elements
  with no enclosing root, so we wrap the raw text in a synthetic
  ``<Firms>...</Firms>`` root before handing it to ElementTree.
- Numeric fields that are absent or unparsable are returned as ``None``
  rather than 0, so downstream scoring can distinguish "not reported"
  from "reported as zero".
- ``website`` is the first ``<WebAddr>`` text found in document order,
  stripped; blank strings are treated as missing (None).
"""

import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).parent))


def _int(val):
    if val is None:
        return None
    val = val.strip()
    if val == "":
        return None
    try:
        return int(val)
    except ValueError:
        return None


def _text_or_none(elem):
    if elem is None or elem.text is None:
        return None
    text = elem.text.strip()
    return text or None


def _item11_yes_count(firm):
    count = 0
    for suffix in ("A", "B", "C", "D", "E", "F", "G", "H"):
        elem = firm.find("FormInfo/Part1A/Item11" + suffix)
        if elem is None:
            continue
        for value in elem.attrib.values():
            if value == "Y":
                count += 1
    return count


def _custody_flag(firm):
    item9a = firm.find("FormInfo/Part1A/Item9A")
    if item9a is None:
        return "N"
    if item9a.get("Q9A1A") == "Y" or item9a.get("Q9A1B") == "Y":
        return "Y"
    return "N"


def _sec_reg_type(firm):
    rgstn = firm.find("Rgstn")
    firm_type = rgstn.get("FirmType") if rgstn is not None else None
    if firm_type == "Registered":
        return "SEC_RIA"
    return "SEC_ERA_OR_OTHER:" + (firm_type or "")


def _state_reg_type(firm):
    state_dates = []
    approved = False
    for rgltr in firm.findall("StateRgstn/Rgltrs/Rgltr"):
        if rgltr.get("St") in ("APPROVED", "APPROVED_RES"):
            approved = True
    era_present = firm.find("ERA/Rgltrs/Rgltr") is not None
    if approved:
        return "STATE_RIA"
    if era_present:
        return "STATE_ERA"
    return "STATE_OTHER"


def _state_reg_states(firm):
    codes = set()
    for rgltr in firm.findall("StateRgstn/Rgltrs/Rgltr"):
        cd = rgltr.get("Cd")
        if cd:
            codes.add(cd)
    return sorted(codes)


def _sec_first_reg_date(firm):
    rgstn = firm.find("Rgstn")
    return rgstn.get("Dt") if rgstn is not None else None


def _state_first_reg_date(firm):
    dates = []
    for rgltr in firm.findall("StateRgstn/Rgltrs/Rgltr"):
        dt = rgltr.get("Dt")
        if dt:
            dates.append(dt)
    for rgltr in firm.findall("ERA/Rgltrs/Rgltr"):
        dt = rgltr.get("Dt")
        if dt:
            dates.append(dt)
    return min(dates) if dates else None


def _notice_filed_count(firm):
    notice_filed = firm.find("NoticeFiled")
    if notice_filed is None:
        return 0
    return len(notice_filed.findall("States"))


def _parse_firm(firm, feed_type):
    info = firm.find("Info")
    main_addr = firm.find("MainAddr")
    item3a = firm.find("FormInfo/Part1A/Item3A")
    item3c = firm.find("FormInfo/Part1A/Item3C")
    item5a = firm.find("FormInfo/Part1A/Item5A")
    item5b = firm.find("FormInfo/Part1A/Item5B")
    item5f = firm.find("FormInfo/Part1A/Item5F")
    item5h = firm.find("FormInfo/Part1A/Item5H")
    item11 = firm.find("FormInfo/Part1A/Item11")
    filing = firm.find("Filing")
    website_elem = firm.find("FormInfo/Part1A/Item1/WebAddrs/WebAddr")

    record = {
        "crd": info.get("FirmCrdNb") if info is not None else None,
        "business_name": info.get("BusNm") if info is not None else None,
        "legal_name": info.get("LegalNm") if info is not None else None,
        "street1": main_addr.get("Strt1") if main_addr is not None else None,
        "street2": main_addr.get("Strt2") if main_addr is not None else None,
        "city": main_addr.get("City") if main_addr is not None else None,
        "state": main_addr.get("State") if main_addr is not None else None,
        "zip": main_addr.get("PostlCd") if main_addr is not None else None,
        "phone": main_addr.get("PhNb") if main_addr is not None else None,
        "website": _text_or_none(website_elem),
        "org_form": item3a.get("OrgFormNm") if item3a is not None else None,
        "org_state": item3c.get("StateCD") if item3c is not None else None,
        "filing_date": filing.get("Dt") if filing is not None else None,
        "total_employees": _int(item5a.get("TtlEmp")) if item5a is not None else None,
        "iar_count": _int(item5b.get("Q5B1")) if item5b is not None else None,
        "aum_total": _int(item5f.get("Q5F2C")) if item5f is not None else None,
        "aum_discretionary": _int(item5f.get("Q5F2A")) if item5f is not None else None,
        "aum_nondiscretionary": _int(item5f.get("Q5F2B")) if item5f is not None else None,
        "total_accounts": _int(item5f.get("Q5F2F")) if item5f is not None else None,
        "fp_clients_range": item5h.get("Q5H") if item5h is not None else None,
        "item11_flag": item11.get("Q11") if item11 is not None else None,
        "item11_yes_count": _item11_yes_count(firm),
        "custody_flag": _custody_flag(firm),
        "umbrella": info.get("UmbrRgstn") if info is not None else None,
        "feed": feed_type,
    }

    if feed_type == "SEC":
        record["reg_type"] = _sec_reg_type(firm)
        record["reg_states"] = []
        record["first_reg_date"] = _sec_first_reg_date(firm)
        record["notice_filed_count"] = _notice_filed_count(firm)
    else:
        record["reg_type"] = _state_reg_type(firm)
        record["reg_states"] = _state_reg_states(firm)
        record["first_reg_date"] = _state_first_reg_date(firm)
        record["notice_filed_count"] = 0

    return record


def parse_feed(path, feed_type):
    """Parse one raw feed file into a list of firm dicts.

    ``feed_type`` must be 'SEC' or 'STATE'.
    """
    if feed_type not in ("SEC", "STATE"):
        raise ValueError("feed_type must be 'SEC' or 'STATE', got %r" % (feed_type,))

    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()

    root = ET.fromstring("<Firms>" + raw + "</Firms>")

    records = []
    for firm in root.findall("Firm"):
        records.append(_parse_firm(firm, feed_type))
    return records


def parse_all(sec_path, state_path):
    """Parse both feeds and dedup on CRD, preferring the SEC record."""
    sec_records = parse_feed(sec_path, "SEC")
    state_records = parse_feed(state_path, "STATE")

    sec_crds = {rec["crd"] for rec in sec_records}

    combined = list(sec_records)
    for rec in state_records:
        if rec["crd"] in sec_crds:
            continue
        combined.append(rec)

    state_crds = {rec["crd"] for rec in state_records}
    for rec in combined:
        if rec["feed"] == "SEC" and rec["crd"] in state_crds:
            rec["also_in_state_feed"] = True
        else:
            rec["also_in_state_feed"] = False

    return combined
