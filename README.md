# cot-history

Archive of the CFTC Commitments of Traders (COT) bulk files, kept up to date by GitHub Actions.

- `scripts/download_cot.py` downloads every report family into `data/raw/<family>/` (stdlib only).
- `.github/workflows/download-cot.yml` runs it on demand and on Friday/Monday evenings, then commits changes.
- `data/manifest.json` records size, SHA-256 and fetch time per file.

Report families: legacy futures-only, legacy futures+options, supplemental (CIT),
disaggregated (fut / fut+opt), Traders in Financial Futures (fut / fut+opt).

First run: Actions tab -> "Download CFTC COT data" -> Run workflow.
