#!/usr/bin/env python3
"""Download daily IAPD feeds from the SEC's IAPD compilation-reports site.

This script requires network access to https://reports.adviserinfo.sec.gov.
The original MVP spike acquired the same feeds through the in-app browser
(see DECISIONS.md D-003), but production uses standard HTTPS GET with
urllib.request and gzip decompression.

Usage:
    python3 scripts/download_feeds.py                # Use today's date
    python3 scripts/download_feeds.py --date 07-14-2026  # Specify MM_DD_YYYY

Output:
    - data/raw/firms_sec_NE_IA_KS_MO_{iso-date}.xml
    - data/raw/firms_state_NE_IA_KS_MO_{iso-date}.xml
    (Files are skipped if they already exist, preserving immutability.)
"""

import argparse
import gzip
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# Configuration
DATA_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
BASE_URL = "https://reports.adviserinfo.sec.gov/reports/CompilationReports"
USER_AGENT = "NBCTrust-succession-research contact@nbctrust.example"
TARGET_STATES = {"NE", "IA", "KS", "MO"}


def parse_date_arg(date_str):
    """Parse MM_DD_YYYY format to ISO YYYY-MM-DD."""
    try:
        dt = datetime.strptime(date_str, "%m-%d-%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date format '{date_str}'; use MM_DD_YYYY")


def get_today_date_str():
    """Return today's date as MM_DD_YYYY."""
    return datetime.now().strftime("%m-%d-%Y")


def download_feed(feed_name, date_str_mdy, iso_date):
    """Download a single feed, gunzip, filter by state, and save.

    Args:
        feed_name: "IA_FIRM_SEC_Feed" or "IA_FIRM_STATE_Feed"
        date_str_mdy: MM_DD_YYYY format date
        iso_date: YYYY-MM-DD format date (for output filename)

    Returns:
        (output_filename, record_count) or (None, 0) if skipped
    """
    output_filename = f"firms_{feed_name.split('_')[2].lower()}_NE_IA_KS_MO_{iso_date}.xml"
    output_path = DATA_RAW / output_filename

    # Skip if file already exists (immutability).
    if output_path.exists():
        print(f"  {output_filename}: already exists, skipping.")
        return (output_filename, None)  # Count unknown, but skipped

    # Build download URL.
    url = f"{BASE_URL}/{feed_name}_{date_str_mdy}.xml.gz"

    print(f"  Downloading {feed_name}_{date_str_mdy}.xml.gz ...", end=" ", flush=True)

    # Download with custom User-Agent.
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT}
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            compressed_data = response.read()
    except urllib.error.HTTPError as e:
        print(f"\nError: HTTP {e.code} {e.reason}")
        print(f"URL: {url}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\nError: {e.reason}")
        print(f"URL: {url}")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

    # Decompress.
    print("decompressing ...", end=" ", flush=True)
    try:
        xml_data = gzip.decompress(compressed_data).decode("utf-8")
    except Exception as e:
        print(f"\nError decompressing: {e}")
        sys.exit(1)

    # Filter to firms in target states.
    # Simple approach: split on '</Firm>', parse the state from MainAddr@State.
    print("filtering ...", end=" ", flush=True)

    firms = xml_data.split("</Firm>")
    filtered_firms = []

    for firm_chunk in firms:
        if not firm_chunk.strip():
            continue

        # Look for State attribute in MainAddr element.
        # Regex is overkill; simple string search for 'State="XX"' will do.
        state = None
        for line in firm_chunk.split("\n"):
            if 'State="' in line and "<MainAddr" in line:
                # Extract State attribute value.
                start = line.find('State="') + len('State="')
                end = line.find('"', start)
                if start < end:
                    state = line[start:end]
                break

        if state in TARGET_STATES:
            filtered_firms.append(firm_chunk + "</Firm>")

    # Write output.
    output_xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<SEC_Data>\n"
    output_xml += "\n".join(filtered_firms)
    output_xml += "\n</SEC_Data>\n"

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_xml)
    except IOError as e:
        print(f"\nError writing {output_path}: {e}")
        sys.exit(1)

    record_count = len(filtered_firms)
    print(f"OK ({record_count} firms)")

    return (output_filename, record_count)


def main():
    parser = argparse.ArgumentParser(
        description="Download and filter IAPD feeds for NE/IA/KS/MO states."
    )
    parser.add_argument(
        "--date",
        default=get_today_date_str(),
        help="Date in MM_DD_YYYY format (default: today)"
    )
    args = parser.parse_args()

    # Validate and convert date format.
    try:
        iso_date = parse_date_arg(args.date)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Ensure data/raw directory exists.
    DATA_RAW.mkdir(parents=True, exist_ok=True)

    print(f"Downloading feeds as of {args.date} (ISO: {iso_date}) ...\n")

    results = []
    for feed_name in ["IA_FIRM_SEC_Feed", "IA_FIRM_STATE_Feed"]:
        filename, count = download_feed(feed_name, args.date, iso_date)
        results.append((filename, count))

    print("\nDownload complete:")
    for filename, count in results:
        if count is not None:
            print(f"  {filename}: {count} firms")
        else:
            print(f"  {filename}: (skipped, already exists)")


if __name__ == "__main__":
    main()
