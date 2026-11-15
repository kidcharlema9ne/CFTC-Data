#!/usr/bin/env python3
"""
IG client-sentiment report for the 48 COT-report markets.

    python3 scripts/ig_sentiment.py            # from the repo root

Opens each IG market page in a real (headless) Chromium browser, because IG draws the
"NN% of client accounts are long/short" figure with JavaScript - a plain download never
sees it. Needs:  pip install playwright  &&  playwright install --with-deps chromium

Reads   config/ig_markets.csv          (one row per COT market, with the IG page address)
Writes  data/ig_sentiment/ig_sentiment_<date>.csv   dated snapshot
        data/ig_sentiment/latest.csv               newest snapshot (overwritten)
        data/ig_sentiment/history.csv              one row per market per run (appended)
        reports/IG_Sentiment_latest.html           readable report (overwritten)

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
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETS = ROOT / "config" / "ig_markets.csv"
OUT_DIR = ROOT / "data" / "ig_sentiment"
REPORT = ROOT / "reports" / "IG_Sentiment_latest.html"

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
            "snapshot_utc": stamp, "cot_symbol": m["cot_symbol"], "cot_market": m["cot_market"],
            "pct_long_futures_view": fut_long, "pct_short_futures_view": fut_short,
            "ig_pct_long_raw": ig_long, "ig_pct_short_raw": ig_short,
            "flipped": "yes" if flip else "no", "status": status,
            "ig_url": m["ig_url"], "note": m["note"],
        })
    return rows


FIELDS = ["snapshot_utc", "cot_symbol", "cot_market", "pct_long_futures_view",
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


def write_html(rows, stamp):
    def cell(r):
        if r["status"] != "ok":
            return "<td colspan='3' class='na'>%s</td>" % html.escape(
                r["note"] or r["status"].replace("_", " "))
        lg = r["pct_long_futures_view"]
        shade = "#1b7f3b" if lg >= 70 else "#b3261e" if lg <= 30 else "#555"
        bar = ("<div class='bar'><span style='width:%d%%'></span></div>" % lg)
        return ("<td class='n' style='color:%s'>%d%%</td><td class='n'>%d%%</td><td>%s</td>"
                % (shade, lg, r["pct_short_futures_view"], bar))
    body = "\n".join(
        "<tr><td>%s</td><td>%s</td>%s</tr>" % (
            html.escape(r["cot_symbol"]), html.escape(r["cot_market"].title()),
            cell({**r, "pct_long_futures_view": r["pct_long_futures_view"],
                  "pct_short_futures_view": r["pct_short_futures_view"]}))
        for r in rows)
    ok = sum(1 for r in rows if r["status"] == "ok")
    doc = f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>IG client sentiment</title>
<style>body{{font:15px system-ui;margin:16px}}table{{border-collapse:collapse;width:100%}}
td,th{{padding:5px 8px;border-bottom:1px solid #ddd;text-align:left}}.n{{text-align:right}}
.na{{color:#888;font-style:italic}}.bar{{background:#f3c9c6;width:120px;height:10px}}
.bar span{{display:block;background:#bfe3c8;height:10px}}</style>
<h2>IG client sentiment - COT markets</h2>
<p>{ok} of {len(rows)} markets as of {stamp} UTC. Share of IG retail client <b>accounts</b>
long or short, shown from the futures point of view (yen, Canadian dollar, Swiss franc, peso and real
are flipped from IG's USD/X quotes). Green = 70%+ long, red = 30% or less. Not COT data.</p>
<table><tr><th>Symbol</th><th>Market</th><th class="n">Long</th><th class="n">Short</th><th></th></tr>
{body}</table>"""
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(doc, encoding="utf-8")


def main():
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
    write_csv(OUT_DIR / f"ig_sentiment_{now:%Y-%m-%d}.csv", rows)
    write_csv(OUT_DIR / "latest.csv", rows)
    write_csv(OUT_DIR / "history.csv", [r for r in rows if r["status"] == "ok"], append=True)
    write_html(rows, stamp)
    ok = sum(1 for r in rows if r["status"] == "ok")
    print(f"\nDone: {ok} markets with data, {len(failed)} failed, "
          f"{len(markets) - len(reachable)} not offered by IG.")


if __name__ == "__main__":
    main()
