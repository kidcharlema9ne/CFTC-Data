#!/usr/bin/env python3
"""Download every CFTC Commitments of Traders (COT) bulk archive into data/raw/.

Stdlib only. Safe to re-run: historical years are skipped once downloaded; the
current and previous year are always refreshed (CFTC revises them).

Usage:
    python scripts/download_cot.py            # incremental
    python scripts/download_cot.py --refresh  # re-download everything
"""
import argparse
import datetime as dt
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://www.cftc.gov/files/dea/history/"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw"

# family -> (first year to try, per-year file pattern, multi-year bundle names)
# Per-year patterns follow CFTC's published naming. Bundle names (older
# multi-year archives) are best effort: a 404 is logged and skipped.
FAMILIES = {
    "legacy_fut": (1986, "deacot{y}.zip", ["deacot1986_2016.zip"]),
    "legacy_futopt": (1995, "deahistfo{y}.zip", ["deahistfo_1995_2016.zip"]),
    "supplemental_cit": (2006, "dea_cit_txt_{y}.zip", ["dea_cit_txt_2006_2016.zip"]),
    "disagg_fut": (2006, "fut_disagg_txt_{y}.zip", ["fut_disagg_txt_hist_2006_2016.zip"]),
    "disagg_futopt": (2006, "com_disagg_txt_{y}.zip", ["com_disagg_txt_hist_2006_2016.zip"]),
    "tff_fut": (2006, "fut_fin_txt_{y}.zip", ["fut_fin_txt_2006_2016.zip"]),
    "tff_futopt": (2006, "com_fin_txt_{y}.zip", ["com_fin_txt_2006_2016.zip"]),
}

HEADERS = {"User-Agent": "cot-history/1.0 (personal research archive)"}


def fetch(url, tries=4):
    """Return bytes, or None on 404. Retries transient errors."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            err = f"HTTP {e.code}"
        except Exception as e:  # network hiccup
            err = repr(e)
        time.sleep(2 ** attempt)
    raise RuntimeError(f"giving up on {url}: {err}")


def save_zip(data, dest):
    tmp = dest.with_suffix(".tmp")
    tmp.write_bytes(data)
    if not zipfile.is_zipfile(tmp):  # CFTC sometimes serves an HTML page with 200
        tmp.unlink()
        return False
    tmp.replace(dest)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download all files")
    args = ap.parse_args()

    now_year = dt.date.today().year
    always_refresh = {now_year, now_year - 1}
    manifest_path = OUT.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    downloaded, missing, failed = 0, [], []

    for family, (start, pattern, bundles) in FAMILIES.items():
        fdir = OUT / family
        fdir.mkdir(parents=True, exist_ok=True)
        jobs = [(None, b) for b in bundles] + [
            (y, pattern.format(y=y)) for y in range(start, now_year + 1)
        ]
        for year, name in jobs:
            dest = fdir / name
            if dest.exists() and not args.refresh and year not in always_refresh:
                continue
            try:
                data = fetch(BASE + name)
            except RuntimeError as e:
                print(f"FAIL  {family}/{name}: {e}")
                failed.append(f"{family}/{name}")
                continue
            if data is None or not save_zip(data, dest):
                print(f"none  {family}/{name}")
                missing.append(f"{family}/{name}")
                continue
            digest = hashlib.sha256(dest.read_bytes()).hexdigest()
            manifest[f"{family}/{name}"] = {
                "bytes": dest.stat().st_size,
                "sha256": digest,
                "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            }
            downloaded += 1
            print(f"ok    {family}/{name} ({dest.stat().st_size:,} bytes)")

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"\ndownloaded={downloaded} not_found={len(missing)} failed={len(failed)}")
    if failed or (downloaded == 0 and not any(OUT.rglob("*.zip"))):
        sys.exit(1)


if __name__ == "__main__":
    main()
