# Running the COT report

Say "run the COT report". Then do exactly this and nothing else (do not rebuild or rewrite the script):

1. `python3 scripts/cot_report.py` from the repo root (pandas required; the data is already in `data/raw/legacy_fut`).
2. Send `reports/COT_Report_latest.html` to the user. Do not paste code into the chat.

Do NOT commit or push the report, and do NOT write it (or anything else) to the Claude project. The file is overwritten on every run, so nothing accumulates.

The rules (IBKR markets, liquidity screen, order, colours, `*` `+` `>` marks) are fixed inside `scripts/cot_report.py`; its docstring lists them. Change the script only if Michael asks.
