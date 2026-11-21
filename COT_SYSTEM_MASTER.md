# COT SYSTEM MASTER: start here

Michael's COT (Commitments of Traders) work in one place. Any assistant (Claude, ChatGPT or other) that is asked about "my COT system", "the COT System", "the COT price index system", "the COT gap system", "the COT report" or "COT research" should read this file first.

Owner: Michael (futures trader, GitHub user kidcharlema9ne). Last updated: 21 Nov 2026.

## 1. Names (they all point to the same things)

- **COT report**: the weekly colour-coded table of the 48 markets. Same thing as "run the report". It is a tool alongside the COT System, not the system itself.
- **COT System**: the trading system that combines the commercial COT index with a price index. This is its one official name. Older names that mean the same thing: "COT gap system" and "COT price index system". Do not use those in new work.
- **COT index**: where the current commercial (or large spec, or small spec) net position sits inside its own range over the last 26, 52 or 156 weeks, from 0 to 100. Legacy futures-only report, weekly data from 1 Oct 1992.
- **Price index**: where the current price sits inside its own range over the last 252 sessions, from 0 to 100.

## 2. Where everything lives

| What | Where |
|---|---|
| Raw CFTC COT data (all report families) and the COT report script | GitHub `kidcharlema9ne/cot-history` (this repo) |
| How to run the report | `RUN_REPORT.md` in this repo. Say "run the COT report". Do not rebuild or change the script without Michael's approval. |
| COT System: spec, tests, results, sealed-data rules (currently still inside the insider-buying-research repo under its old name, "cot_gap"; Michael wants it moved to its own COT System repo) | GitHub `kidcharlema9ne/insider-buying-research`, folder `research/cot_gap`, branch `claude/cot-gap-20261121` (frozen system) and the out-of-sample branch `claude/cot-gap-oos-20261121` |
| The running research log (numbered entries, results with run links) | `docs/SHARED_LOG.md` in insider-buying-research. Entries 103 to 123 cover the COT System (logged under its old name, "COT gap"). |
| Michael's standing decisions | `docs/MICHAEL_DETERMINATIONS.md` in insider-buying-research |
| Futures PRICES (not in this repo) | Michael's Cloudflare R2 bucket `insider-research` (prefix `marketparquet/futures_daily/`), reachable only through GitHub Actions in insider-buying-research. Start at `FUTURES_DATA.md` there. |
| Don't-fade list, evidence notes, sources | Claude Project "COT Research", doc `COT_RESEARCH_NOTES.md` (copy of the key points is in section 6 below) |
| Report rules in plain words | Claude Project "COT Research", doc `COT_REPORT_SPEC.md` (the script in this repo is the authority) |

## 3. The COT System (frozen version, "system v1")

- Signal: the commercial COT index plus the price index, minus 100, reaches 40 or more (long or short mirror).
- Windows: 52-week COT index, 252-session price index.
- Stop: 4 times the average true range (ATR). Exit: the close of session 21.
- Michael also asked about a 2 ATR stop with a 6 ATR profit target variant, and a 26-week COT window variant. Only about 6 percent of trades reach a 6 ATR target, so the real choice is stop width.
- Sealed data: the last five years were sealed while the system was developed. Michael unsealed them on 21 Nov 2026 for one out-of-sample run. Treat that as a one-time look. Nothing may be re-tuned on those years.
- Sizing asked for in the out-of-sample run: 0.25 percent volatility positions, tested on a 1,000,000 dollar account (all futures) and a 330,000 dollar account (only markets where micros or ETF stand-ins allow that size). Micros assumed to exist in all years.
- Michael does not want 4 ATR of risk per trade on the real account. 2 ATR is acceptable.
- Plan: bring the system to a fund manager he knows. Next development idea: size by signal quality (26-week signals smaller, trades that pass the smoothness test larger).

## 4. Standing rules from Michael

- Only the 48 markets in the COT report. Only markets tradable at Interactive Brokers. Open interest at least 45,000.
- Count independent episodes, pooled across markets. A reading that sits at an extreme for eight weeks is one episode, not eight.
- No Python code or script output pasted in chat. Deliver the finished result.
- Do not let reports or files pile up (the report file is overwritten every run).
- Describe factors and rules in plain words. Do not use letter codes or short variable names.
- Michael wants the finished report readable inline in any assistant.
- Results need a committed script plus a run link before they count (the insider-buying-research convention).

## 5. Findings so far

The full, checkable record is `docs/SHARED_LOG.md` in insider-buying-research. Headline points as stated by Claude in the 21 Nov 2026 chats (verify against the log entries before relying on them):

- 4 ATR stop, session-21 exit: Sharpe about 1.04 on the 26-week signal and 1.10 on the 52-week signal, drawdowns 3 to 5 percent.
- 2 ATR stop: Sharpe 0.86 to 1.04, drawdowns 7 to 8 percent, and its edge depended more on the window chosen.
- The smoothness filter was proposed but was not declared in advance, so treat it as exploratory.
- Out-of-sample result (21 Nov 2026 run): not recorded in this file yet. Read the newest entries in the shared log.

## 6. Don't-fade summary (details and sources in COT_RESEARCH_NOTES.md in the Claude Project)

A contrarian signal needs a crowd of discretionary or trend-following directional bets. Do not fade structural positions: leveraged fund shorts in the Treasury futures (a large share is the cash-futures basis trade), dealer and intermediary categories, swap dealers, and legacy commercials in financial futures. Candidates to test as fades: managed money extremes in commodities, leveraged funds in currencies and equity indices, combination of managed money extreme with producer/merchant on the opposite extreme.

## 7. Open items

1. Extend the index work to the disaggregated report (managed money, producer/merchant, swap dealers) and the financial futures report (leveraged funds, asset managers, dealers).
2. Record the out-of-sample result here and in the shared log.
3. Smoothness filter and signal-quality sizing, declared in advance before testing.

## 8. If you are an assistant without access to these repos

Ask Michael to paste this: "My COT work is documented in GitHub kidcharlema9ne/cot-history, file COT_SYSTEM_MASTER.md. The COT System (old name: COT gap) is in kidcharlema9ne/insider-buying-research, folder research/cot_gap, branch claude/cot-gap-20261121. Read those before answering."

## 9. Keeping this file current

Whenever a COT finding, decision or status changes, update this file in the same session and add the numbered entry to the shared log in insider-buying-research.
