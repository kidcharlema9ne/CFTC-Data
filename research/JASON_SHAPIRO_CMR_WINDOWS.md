# Jason Shapiro CMR Windows — reconstructed lookbacks

Research note, 21 November 2026. **These are inferred settings, not confirmed proprietary Crowded Market Report (CMR) settings.** The original reconstruction was performed 8 November 2026 using screenshots of CMR heat maps from 2024–2026 and CFTC Legacy Futures Only reports. This file documents research; it does **not** modify the weekly COT report or its signal rules.

## Inferred market-specific windows

Windows count **weekly COT reports**, not trading days. Ranges indicate tied or near-tied fits.

| Sector | Market | Weekly reports |
|---|---|---:|
| Rates | 30-year Treasury bonds | 98 |
| Rates | 10-year Treasury notes | 98–99 |
| Rates | 5-year Treasury notes | 98 |
| Rates | 2-year Treasury notes | 98–99 |
| Equity indexes | Nasdaq-100 consolidated | 28 |
| Equity indexes | S&P 500 E-mini | 28 |
| Equity indexes | Dow $5 | 28 |
| Equity indexes | Russell 2000 E-mini | 28 |
| Livestock | Live cattle | 14 |
| Livestock | Lean hogs | 14 |
| Softs | Cocoa | 11 |
| Softs | Sugar | 135 |
| Softs | Orange juice | 9 |
| Softs | Coffee | 9 |
| Softs | Cotton | 41 |
| Softs | Lumber | 140 |
| Metals | Gold | 25 |
| Metals | Silver | 25 |
| Metals | Palladium | 214 or 218 |
| Metals | Platinum | 17 |
| Metals | Copper | 84 |
| Crypto | Bitcoin | 78–97 |
| Crypto | Ether | 74–96 |
| Currencies | U.S. Dollar Index | 91–92 |
| Currencies | New Zealand dollar | 81–82 |
| Currencies | Australian dollar | 81 |
| Currencies | British pound | 31 |
| Currencies | Canadian dollar | 31 |
| Currencies | Japanese yen | 31 |
| Currencies | Euro | 91 |
| Currencies | Swiss franc | 31 |
| Energy | WTI crude oil | 41 |
| Energy | RBOB gasoline | 41 |
| Energy | Heating oil / ULSD | 41 |
| Energy | Natural gas | 69 |
| Grains | Corn | 77 |
| Grains | Oats | 6 available reports (tentative) |
| Grains | Chicago wheat | 11 |
| Grains | Soybeans | 138 |
| Grains | Soybean meal | 32–33 |
| Grains | Soybean oil | 35 |

## Reconstruction method

For each CFTC trader group separately, compute net position = longs − shorts. The COT index is:

`100 × (current net − rolling minimum net) / (rolling maximum net − rolling minimum net)`

Include the current weekly report in the rolling window, and round the output to the nearest integer for comparison with CMR screenshot readings. Candidate windows ranged from 3 to 364 reports, subject to available history. The primary comparison used 18 sampled weeks in 2026 (54 readings per market across commercials, large specs, and small specs); additional 2024–2025 screenshots helped validate. For tied fits use the shorter window as a reproducible convention, **not** as proof that Shapiro uses it.

The U.S. Dollar Index matched all 54 sampled 2026 readings with 91–92 reports, but July 2024 readings needed a different fit. NZD matched all 66 available readings across 2025–2026 with 81–82 reports. Platinum averaged 0.89 index points of error (34/54 exact); WTI averaged 1.69 (10/54 exact). The 30-year bond commercial reading on one November screenshot was 82 versus 34 in our 98-report reconstruction, demonstrating that even a generally good fit can have serious individual misses.

A time-split diagnostic trained window choices on the first 14 sampled dates and evaluated the last 10: market-specific windows averaged 1.68 index points of error over 1,200 readings across 40 markets, versus 9.27 for the best single common window selected on the training dates. This tests screenshot replication, **not predictive trading performance**.

## Interpretation and limitations

- CMR's actual lookback lengths are not verified; some windows may change or depend on market definitions, reporting conventions, or data preprocessing.
- Oats has sparse historical rows and its six-report fit is especially tentative.
- Equity-index CMR trading guidance may use a commercials-only exception; do not silently substitute that for this repository's existing three-group alignment rules.
- The reconstruction of COT index values is distinct from any backtest. A separate 2008–2026 Shapiro reversal backtest found only a small event-weighted gain, with equal-market weighting near zero; its 95% interval on improvement over matched weeks crossed zero.
- Backtests must respect actual CFTC publication timestamps, eligible entry sessions, pre-entry ATR, and roll handling. Do not infer a tradable edge from screenshot agreement.

## Original research artifacts

Saved in the user's ChatGPT Library (not necessarily in this GitHub repository):

1. `Shapiro_COT_Lookback_Settings.docx` — full window table, fit errors, and replication methodology, created 2026-11-08.
2. `COT_Report_Shapiro_2026-11-03.html` — reconstructed report, created 2026-11-10; source commit recorded there: `acb3f94d7596caf07041556bbf065100c60aad6a`.
3. `Shapiro_COT_All_Markets_Backtest.html` — historical reversal study, created 2026-11-08.

Source materials: CMR New Member Guide (pp. 8–9 and 14), supplied CMR heat-map screenshots (2024–2026), and CFTC Legacy Futures Only archives.

**Maintenance rule:** Treat this as a standalone research reference. Do not change `scripts/cot_report.py`, default lookbacks, highlighting, or weekly report rules without explicit user approval.
