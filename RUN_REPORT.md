# Running the COT report

Say "run the COT report". Then do exactly this and nothing else (do not rebuild or rewrite the script):

1. `python3 scripts/cot_report.py` from the repo root (pandas required; the data is already in `data/raw/legacy_fut`).
2. Send `reports/COT_Report_latest.html` to the user. Do not paste code into the chat.

Do NOT commit or push the report, and do NOT write it (or anything else) to the Claude project. The file is overwritten on every run, so nothing accumulates.

The rules (IBKR markets, liquidity screen, order, colours and symbol marks) are in `scripts/cot_report.py`. Change the script only if Michael asks.

The `&` suffix uses `data/futures_sma20.json`, a dated snapshot of MarketParquet futures trends. Green symbols get `&` above the 20-day simple moving average and red symbols get `&` below it. The report shows the price date. Missing symbols, exact ties and snapshots older than the COT as-of date are skipped.

The **Export COT 20-day trend snapshot** workflow in `kidcharlema9ne/insider-buying-research` reads the verified R2 archive. For automatic updates, add a `COT_HISTORY_SYNC_TOKEN` Actions secret in that repository using a fine-grained token scoped to `cot-history` with Contents read/write access. The exporter then refreshes the snapshot after the nightly futures import. Until that secret is set, run the exporter manually and commit its `futures_sma20.json` artifact here under `data/`.

