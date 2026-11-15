#!/usr/bin/env python3
"""
IG client-sentiment report for the 48 COT-report markets.

    python3 scripts/ig_sentiment.py            # from the repo root
    python3 scripts/ig_sentiment.py --report-only   # rebuild the html from saved data, no scraping

Opens each IG market page in a real (headless) Chromium browser, because IG draws the
"NN% of client accounts are long/short" figure with JavaScript - a plain download never
sees it. Needs:  pip install playwright  &&  playwright install --with-deps chromium

Reads   config/ig_markets.csv          (one row per COT market, with the IG page address)
Writes  data/ig_sentiment/ig_sentiment_<date>.csv   dated snapshot
        data/ig_sentiment/latest.csv               newest snapshot (overwritten)
        data/ig_sentiment/history.csv              one row per market per run (appended)
        reports/IG_Sentiment_latest.html           readable report: last 20 readings of percent long, newest first (overwritten)

Notes
- IG only shows the majority side ("76% are long"); the other side is 100 minus that.
- Pairs IG quotes as USD/X (yen, Canadian dollar, Swiss franc, peso, real) are flipped so the
  numbers match the futures (long yen = short USD/JPY). The raw IG figure is kept too.
- IG counts accounts, not position size, and is retail only. It is not COT data.
- If most pages fail (IG's bot protection can block cloud servers) the script exits with an
  error and writes nothing, so the workflow never commits an empty report.
"""
import csv
import html
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETS = ROOT / "config" / "ig_markets.csv"
OUT_DIR = ROOT / "data" / "ig_sentiment"
REPORT = ROOT / "reports" / "IG_Sentiment_latest.html"
REPORT_MANUAL = ROOT / "reports" / "IG_Sentiment_manual.html"   # hand-run reports; never saved to history

SENTIMENT_RE = re.compile(r"(\d{1,3})\s*%\s+of client accounts are\s+(long|short)", re.I)
PAGE_TIMEOUT_MS = 45_000
SENTIMENT_TIMEOUT_MS = 25_000
MAX_FAILURE_SHARE = 0.5   # if more than this share of reachable markets fail, treat as blocked


def parse_sentiment(text):
    """Return (percent_long, percent_short) from page text, or None if absent."""
    m = SENTIMENT_RE.search(text or "")
    if not m:
        return None
    pct, side = int(m.group(1)), m.group(2).lower()
    if not 0 <= pct <= 100:
        return None
    return (pct, 100 - pct) if side == "long" else (100 - pct, pct)


def to_futures_view(ig_long, ig_short, flip):
    """Swap sides when IG quotes the pair as USD/X, so it matches the futures contract."""
    return (ig_short, ig_long) if flip else (ig_long, ig_short)


def display_names():
    """Plain names for the report (config column display_name), keyed by COT symbol."""
    return {m["cot_symbol"]: m.get("display_name") or m["cot_market"].title() for m in load_markets()}


def load_markets():
    with open(MARKETS, newline="") as f:
        return list(csv.DictReader(f))


def scrape(markets):
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    results = {}
    cache = {}   # several COT markets share one IG page (ES/MES, NQ/MNQ)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
            locale="en-US", viewport={"width": 1280, "height": 900})
        page = context.new_page()
        for row in markets:
            url = row["ig_url"].strip()
            sym = row["cot_symbol"]
            if not url:
                results[sym] = ("no_ig_page", None)
                continue
            if url in cache:
                results[sym] = cache[url]
                continue
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                # wait until the sentiment sentence has been drawn
                page.wait_for_function(
                    "() => /\\d+\\s*%\\s+of client accounts are\\s+(long|short)/i.test(document.body.innerText)",
                    timeout=SENTIMENT_TIMEOUT_MS)
                parsed = parse_sentiment(page.inner_text("body"))
                outcome = ("ok", parsed) if parsed else ("parse_failed", None)
            except PWTimeout:
                title = ""
                try:
                    title = page.title()
                except Exception:
                    pass
                outcome = ("timeout_or_blocked", title[:80])
            except Exception as exc:   # network error, navigation error
                outcome = ("error", str(exc)[:80])
            cache[url] = outcome
            results[sym] = outcome
            print(f"{sym:4} {outcome[0]:18} {outcome[1] if outcome[1] else ''}", flush=True)
        browser.close()
    return results


def build_rows(markets, results, stamp):
    rows = []
    for m in markets:
        status, payload = results.get(m["cot_symbol"], ("not_run", None))
        flip = m["flip_to_match_futures"].strip() == "1"
        ig_long = ig_short = fut_long = fut_short = ""
        if status == "ok":
            ig_long, ig_short = payload
            fut_long, fut_short = to_futures_view(ig_long, ig_short, flip)
        rows.append({
            "snapshot_utc": stamp, "group": m["group"], "cot_symbol": m["cot_symbol"], "cot_market": m["cot_market"],
            "pct_long_futures_view": fut_long, "pct_short_futures_view": fut_short,
            "ig_pct_long_raw": ig_long, "ig_pct_short_raw": ig_short,
            "flipped": "yes" if flip else "no", "status": status,
            "ig_url": m["ig_url"], "note": m["note"],
        })
    return rows


FIELDS = ["snapshot_utc", "group", "cot_symbol", "cot_market", "pct_long_futures_view",
          "pct_short_futures_view", "ig_pct_long_raw", "ig_pct_short_raw", "flipped",
          "status", "ig_url", "note"]


def write_csv(path, rows, append=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or not append
    with open(path, "a" if append else "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)


REPORT_URL = "https://github.com/kidcharlema9ne/cot-history/blob/main/reports/IG_Sentiment_latest.html"
JUMP_POINTS = 10       # star the newest reading if it moved this many points or more
HISTORY_COLUMNS = 20   # how many past readings the report shows per market


def load_history(path):
    """Return (dates, series): the newest HISTORY_COLUMNS distinct dates (oldest first),
    and series[symbol][date] = percent long. One reading per market per day (the latest)."""
    series, dates = {}, set()
    if path.exists():
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                if r.get("status") != "ok" or r.get("pct_long_futures_view", "") == "":
                    continue
                day = r["snapshot_utc"][:10]
                dates.add(day)
                series.setdefault(r["cot_symbol"], {})[day] = int(r["pct_long_futures_view"])
    return sorted(dates)[-HISTORY_COLUMNS:], series


def shade(pct):
    """Green only at 70% long or more, red only at 30% long or less, otherwise no colour."""
    if pct >= 70:
        return "#bfe3c8"
    if pct <= 30:
        return "#f3c9c6"
    return "#ffffff"


def overlay(seen, series, rows, stamp):
    """Manual runs: show today's live reading in the report without saving it to history.csv."""
    day = stamp[:10]
    for r in rows:
        if r["status"] == "ok" and r["pct_long_futures_view"] != "":
            series.setdefault(r["cot_symbol"], {})[day] = int(r["pct_long_futures_view"])
    return sorted(set(seen) | {day})[-HISTORY_COLUMNS:], series


def date_grid(seen, stamp, count=HISTORY_COLUMNS):
    """The latest reading date, then the weekdays before it, newest first."""
    latest = datetime.strptime(seen[-1] if seen else stamp[:10], "%Y-%m-%d").date()
    dates, day = [latest.isoformat()], latest
    while len(dates) < count:
        day -= timedelta(days=1)
        if day.weekday() < 5:
            dates.append(day.isoformat())
    return dates


def jumped(sym_series, dates, v):
    """True if the newest reading moved JUMP_POINTS or more since the last earlier reading."""
    earlier = [sym_series[x] for x in dates[1:] if x in sym_series]
    return bool(earlier) and abs(v - earlier[0]) >= JUMP_POINTS


def write_markdown(rows, stamp, path, columns=10, report_url="", history_path=None, manual=False):
    """Compact markdown table for the daily GitHub email (issue comment)."""
    seen, series = load_history(history_path or OUT_DIR / "history.csv")
    if manual:
        seen, series = overlay(seen, series, rows, stamp)
    dates = date_grid(seen, stamp, columns)
    names = display_names()
    out = ["## IG Bank Customer Positioning", "",
           "**%% Long**  (🟩 70+ · 🟥 30 or less · ⬜ in between · * = moved %d+ points since last reading)" % JUMP_POINTS, "",
           "| Market | " + " | ".join(d[5:7] + "/" + d[8:10] for d in dates) + " |",
           "|:--|" + "|".join([":-:"] * len(dates)) + "|"]
    current = None
    for r in rows:
        if r["group"] != current:
            current = r["group"]
            out.append("| **%s** |%s" % (current, " |" * len(dates)))
        s = series.get(r["cot_symbol"], {})
        cells = []
        for i, d in enumerate(dates):
            v = s.get(d)
            if v is None:
                cells.append("na")
                continue
            mark = "🟩" if v >= 70 else "🟥" if v <= 30 else "⬜"
            cells.append("%s%d%s" % (mark, v, "*" if i == 0 and jumped(s, dates, v) else ""))
        out.append("| %s | %s |" % (names.get(r["cot_symbol"], r["cot_market"].title()), " | ".join(cells)))
    if report_url:
        out += ["", "[Full report (20 days)](%s)" % report_url]
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")


def write_html(rows, stamp, history_path=None, manual=False):
    seen, series = load_history(history_path or OUT_DIR / "history.csv")
    if manual:
        seen, series = overlay(seen, series, rows, stamp)
    dates = date_grid(seen, stamp)
    names = display_names()
    head = "".join("<th class='n%s'>%s</th>" % (" now" if i == 0 else "",
                                                  d[5:7] + "/" + d[8:10])
                   for i, d in enumerate(dates))
    width = 2 + max(len(dates), 1)
    parts, current = [], None
    for r in rows:   # rows are already in the order set by config/ig_markets.csv
        if r["group"] != current:
            current = r["group"]
            parts.append("<tr class='grp'><td colspan='%d'>%s</td></tr>" % (width, html.escape(current)))
        cells = []
        for i, d in enumerate(dates):
            v = series.get(r["cot_symbol"], {}).get(d)
            cls = "n now" if i == 0 else "n"
            if v is None:
                cells.append("<td class='%s dash'>na</td>" % cls)
            else:
                star = ""
                if i == 0 and jumped(series.get(r["cot_symbol"], {}), dates, v):
                    star = "*"
                cells.append("<td class='%s' style='background:%s'>%d%s</td>" % (cls, shade(v), v, star))
        parts.append("<tr><td class='sym'>%s</td><td>%s</td>%s</tr>" % (
            html.escape(r["cot_symbol"]),
            html.escape(names.get(r["cot_symbol"], r["cot_market"].title())), "".join(cells)))
    ok = sum(1 for r in rows if r["status"] == "ok")
    doc = f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>IG Bank Customer Positioning</title>
<style>body{{font:13px system-ui;margin:10px}}.wrap{{overflow-x:auto}}h2{{margin:0 0 2px}}.sub{{font-weight:600;margin-bottom:6px}}.legend{{font-weight:400;color:#555;font-size:12px}}
table{{border-collapse:collapse;width:auto}}
td,th{{padding:2px 4px;border-bottom:1px solid #e2e2e2;text-align:left;white-space:nowrap}}
th{{font-size:11px;color:#444}}.n{{text-align:center;min-width:28px}}
.now{{font-weight:700;border-right:2px solid #555}}.dash{{color:#bbb}}
.sym{{font-weight:600;padding-right:6px}}.grp td{{background:#eef1f5;font-weight:600;padding-top:8px}}</style>
<h2>IG Bank Customer Positioning</h2>
<div class="sub">% Long <span class="legend">&nbsp;* = moved {JUMP_POINTS}+ points since last reading</span></div>
<div class="wrap"><table><tr><th>Sym</th><th>Market</th>{head}</tr>
{"".join(parts)}</table></div>"""
    out = REPORT_MANUAL if manual else REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")


def write_pdf(pdf_path, html_path=REPORT):
    """Render the html report to a one-page PDF with headless Chromium (needs playwright)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(Path(html_path).resolve().as_uri())
        pg.pdf(path=str(pdf_path), format="Letter", landscape=False, print_background=True,
               margin={"top": "0.3in", "bottom": "0.3in", "left": "0.3in", "right": "0.3in"}, scale=0.8)
        b.close()


def rows_from_latest():
    """Rebuild rows from data/ig_sentiment/latest.csv (used by --report-only)."""
    with open(OUT_DIR / "latest.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("pct_long_futures_view", "pct_short_futures_view"):
            r[k] = r[k] if r[k] == "" else int(r[k])
    return rows


def main():
    if "--report-only" in sys.argv:   # rebuild the html from saved data, no scraping
        rows = rows_from_latest()
        write_html(rows, rows[0]["snapshot_utc"])
        if "--email-body" in sys.argv:   # also write the markdown used for the daily email
            write_markdown(rows, rows[0]["snapshot_utc"], sys.argv[sys.argv.index("--email-body") + 1],
                           report_url=REPORT_URL)
        if "--pdf" in sys.argv:
            write_pdf(REPORT.with_suffix(".pdf"))
        print("Report rebuilt from saved data.")
        return
    markets = load_markets()
    results = scrape(markets)
    reachable = [s for s, (st, _) in results.items() if st != "no_ig_page"]
    failed = [s for s in reachable if results[s][0] != "ok"]
    if not reachable or len(failed) / len(reachable) > MAX_FAILURE_SHARE:
        print(f"\nERROR: {len(failed)} of {len(reachable)} IG pages failed. IG is probably blocking "
              "this server. Nothing was written.", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d %H:%M")
    rows = build_rows(markets, results, stamp)
    for r in rows:   # numbers for the html builder
        for k in ("pct_long_futures_view", "pct_short_futures_view"):
            r[k] = r[k] if r[k] == "" else int(r[k])
    manual = "--manual" in sys.argv
    if manual:   # hand-run: its own files; history.csv, latest.csv and the daily report are not touched
        write_csv(OUT_DIR / "manual_latest.csv", rows)
    else:
        write_csv(OUT_DIR / f"ig_sentiment_{now:%Y-%m-%d}.csv", rows)
        write_csv(OUT_DIR / "latest.csv", rows)
        write_csv(OUT_DIR / "history.csv", [r for r in rows if r["status"] == "ok"], append=True)
    write_html(rows, stamp, manual=manual)
    page = REPORT_MANUAL if manual else REPORT
    if "--pdf" in sys.argv:
        write_pdf(page.with_suffix(".pdf"), page)
    if "--email-body" in sys.argv:
        write_markdown(rows, stamp, sys.argv[sys.argv.index("--email-body") + 1],
                       report_url=REPORT_URL.replace("_latest", "_manual") if manual else REPORT_URL, manual=manual)
    ok = sum(1 for r in rows if r["status"] == "ok")
    print(f"\nDone: {ok} markets with data, {len(failed)} failed, "
          f"{len(markets) - len(reachable)} not offered by IG.")


if __name__ == "__main__":
    main()
