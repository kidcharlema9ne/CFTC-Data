# IG sentiment data (start here)

**If the user says "IG sentiment", "IG client sentiment", "IG positioning" or "the IG report", this is it.**
Repo: `kidcharlema9ne/cot-history` (private). Do not build a new scraper - the data already exists here.

## What it is
IG (ig.com) publishes what share of its retail client **accounts** are long or short each market.
A GitHub job collects it for 39 markets from the COT report, every weekday at 4:00pm US Eastern,
and keeps a running history. It counts accounts, not position size, and it is retail only.
It is not COT data. IG shows only the majority side; the other side is 100 minus it.

## Where the data is
| File | What it holds |
|---|---|
| `data/ig_sentiment/history.csv` | **The history.** One row per market per run, appended every weekday. Use this for charts and trends. |
| `data/ig_sentiment/latest.csv` | The newest snapshot (all 39 markets, overwritten each run). |
| `data/ig_sentiment/ig_sentiment_YYYY-MM-DD.csv` | One snapshot file per day. |
| `reports/IG_Sentiment_latest.html` | Readable report, grouped: stock indexes, interest rates, currencies, energy, commodities. Shows percent long for the last 20 readings (newest gets a * if it moved 10+ points since the previous reading) (newest first, then working backwards; latest in bold). `python3 scripts/ig_sentiment.py --report-only` rebuilds it from saved data without scraping. |
| `config/ig_markets.csv` | The market list: COT symbol, COT name, plain display name used in the report, IG page address, and whether the pair is flipped. |
| `scripts/ig_sentiment.py` | The scraper (headless browser; IG draws the numbers with JavaScript). |
| `.github/workflows/ig-sentiment.yml` | The weekday 4pm job. It can also be run by hand from the Actions tab. |

## Running it on request ("run IG sentiment")
- **To just read it:** open `reports/IG_Sentiment_latest.html` (or `.pdf`) and `data/ig_sentiment/history.csv`. No run needed.
- **To get a fresh reading now:** start the workflow `IG client sentiment` (`ig-sentiment.yml`) on `main` with
  `workflow_dispatch`, e.g. `gh api -X POST repos/kidcharlema9ne/cot-history/actions/workflows/ig-sentiment.yml/dispatches -f ref=main`.
  It takes about 2 minutes, then emails the report. A hand run is a **one-off**: it writes `reports/IG_Sentiment_manual.html/.pdf`
  and `data/ig_sentiment/manual_latest.csv`, and does **not** touch `history.csv` or the daily report.
  Only add `-f 'inputs[save_to_history]=true'` if the user explicitly wants that reading saved to the history.
- The official history is built only by the weekday 4pm Eastern scheduled run.
- An assistant needs GitHub access to this repo with permission to run workflows. A read-only connection can read the files but cannot start a run.

## Reading the columns
- `pct_long_futures_view` / `pct_short_futures_view` - **use these.** Long and short as seen from the futures contract.
- `ig_pct_long_raw` / `ig_pct_short_raw` - IG's own figures for the page it quotes.
- `flipped` = yes for the yen, Canadian dollar, Swiss franc, peso and real. IG quotes USD/JPY, USD/CAD,
  USD/CHF, USD/MXN and USD/BRL, so long yen = short USD/JPY. The futures-view columns already account for this.
- `cot_symbol` is the same symbol as in the COT report (for example 6J, ZN, GC). `group` is the report section.
- `snapshot_utc` is when the run happened (UTC). `status` is `ok` for good rows.

## Not covered
These COT markets have no IG page, so they are not tracked: Ultra 10Y, Ultra bond, Fed Funds, SOFR 1M and 3M,
HRW wheat, feeder cattle. The micro S&P and micro Nasdaq were dropped because they share IG pages with the
regular contracts (ES and NQ).

## Charting
Read `history.csv`, filter by `cot_symbol`, plot `pct_long_futures_view` against `snapshot_utc`.
History began 2026-11-15, so there are few points at first.

## If a run fails
IG may block GitHub's servers. The job then fails and commits nothing, so history shows a gap, not bad data.
Check the Actions tab. Fallback: run `python3 scripts/ig_sentiment.py` from a home computer (needs `pip install playwright`
and `playwright install chromium`).
