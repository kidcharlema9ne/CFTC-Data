# cot-history

Archive of the CFTC Commitments of Traders (COT) bulk files, kept up to date by GitHub Actions.

- `scripts/download_cot.py` downloads every report family into `data/raw/<family>/` (stdlib only).
- `.github/workflows/download-cot.yml` runs it on demand and on Friday/Monday evenings, then commits changes.
- `data/manifest.json` records size, SHA-256 and fetch time per file.

Report families: legacy futures-only, legacy futures+options, supplemental (CIT),
disaggregated (fut / fut+opt), Traders in Financial Futures (fut / fut+opt).

First run: Actions tab -> "Download CFTC COT data" -> Run workflow.

## Running the COT report
See RUN_REPORT.md: `python3 scripts/cot_report.py` writes `reports/COT_Report_<date>.html`.

## Futures PRICES live elsewhere
Daily futures prices are NOT in this repo. They are in Michael's Cloudflare R2 bucket and are read through GitHub Actions in `kidcharlema9ne/insider-buying-research`. Start at [FUTURES_DATA.md](https://github.com/kidcharlema9ne/insider-buying-research/blob/main/FUTURES_DATA.md).

## IG client sentiment
`scripts/ig_sentiment.py` reads IG's "% of client accounts long/short" for the report's markets (list and IG page addresses in `config/ig_markets.csv`) and writes `data/ig_sentiment/` plus `reports/IG_Sentiment_latest.html`. Workflow: **IG client sentiment** (weekday evenings, or run it by hand). It uses a headless browser because IG draws the figure with JavaScript. If IG blocks GitHub's servers the run fails and commits nothing.
