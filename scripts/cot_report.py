#!/usr/bin/env python3
"""
COT report (HTML) - the ONE command to run the report. No other script is needed.

    python3 scripts/cot_report.py            # from the repo root; writes reports/COT_Report_latest.html (overwritten each run)

FINAL RULES (do not change unless Michael says so):
- Legacy futures-only COT from data/raw/legacy_fut; weekly era from 1992-10-01; 156+ clean weeks.
- Only IBKR-tradable futures (IBKR map below), open interest >= 45,000 as a liquidity proxy,
  minus thin products (THIN). No "Mine" column.
- Index = (net - min)/(max - min)*100 over 26 or 52 weeks. Briese CoT Movement Index = Comm 26 now
  minus 6 weeks ago; |change| >= 40 -> "*" after the IBKR symbol (text only, no colour).
- ORDER: (1) dark group: Comm 26 is 0 or 100 AND Large 26 and Small 26 are each 0 or 100 (extreme = rounds to 0 or 100);
  (2) light group: Comm 26 is 0 or 100 but at least one spec is not; (3) everything else by
  Comm 26 descending. Groups 1-2 sorted by |Comm 26| then |6-wk change|.
- COLOUR: only the Market and IBKR cells, only when Comm 26 is 0 or 100: Comm 26 = 100 is
  green, Comm 26 = 0 is red (by the index, NOT the net position); dark for group 1, light
  for group 2. Nothing else in the table is coloured.
- SYMBOL MARKS: "*" = 40-pt move (text only); "+" = Comm 52 also at 0 or 100 (after the "*");
  ">" = absolute position agrees: Comm 26 = 100 and commercials actually net long, or Comm 26 = 0 and
  actually net short (last mark).
- No Comm Net column.
- No Mine, "Comm 26 six wks ago" or "weeks since 40-pt move" columns.
"""
import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

WEEKLY_ERA_START = "1992-10-01"
MIN_OI = 45_000   # open interest used as a liquidity proxy (CFTC data has no volume)
THIN = {"SPXDIVAN","AIGCI","MFS","MME","DJUSRE","HH","EMD"}  # thinly traded at IBKR despite OI
MIN_HIST_WEEKS = 156
MOVE_WEEKS = 6
MOVE_THRESHOLD = 40

# CFTC market name -> (IBKR symbol, exchange). Matched against IBKR's published
# exchange fee schedules (CME/CBOT/NYMEX/COMEX/ICE US). Verify in IBKR's Product Search.
IBKR = {
    # CME FX
    "AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE": ("6A", "CME"),
    "BRITISH POUND - CHICAGO MERCANTILE EXCHANGE": ("6B", "CME"),
    "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE": ("6C", "CME"),
    "EURO FX - CHICAGO MERCANTILE EXCHANGE": ("6E", "CME"),
    "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE": ("6J", "CME"),
    "SWISS FRANC - CHICAGO MERCANTILE EXCHANGE": ("6S", "CME"),
    "MEXICAN PESO - CHICAGO MERCANTILE EXCHANGE": ("6M", "CME"),
    "NZ DOLLAR - CHICAGO MERCANTILE EXCHANGE": ("6N", "CME"),
    "BRAZILIAN REAL - CHICAGO MERCANTILE EXCHANGE": ("6L", "CME"),
    "SO AFRICAN RAND - CHICAGO MERCANTILE EXCHANGE": ("6Z", "CME"),
    "EURO FX/BRITISH POUND XRATE - CHICAGO MERCANTILE EXCHANGE": ("RP", "CME"),
    "EURO FX/JAPANESE YEN XRATE - CHICAGO MERCANTILE EXCHANGE": ("RY", "CME"),
    # Equity index
    "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE": ("ES", "CME"),
    "NASDAQ MINI - CHICAGO MERCANTILE EXCHANGE": ("NQ", "CME"),
    "RUSSELL E-MINI - CHICAGO MERCANTILE EXCHANGE": ("RTY", "CME"),
    "E-MINI S&P 400 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE": ("EMD", "CME"),
    "EMINI RUSSELL 1000 VALUE INDEX - CHICAGO MERCANTILE EXCHANGE": ("RSV", "CME"),
    "MICRO E-MINI S&P 500 INDEX - CHICAGO MERCANTILE EXCHANGE": ("MES", "CME"),
    "MICRO E-MINI NASDAQ-100 INDEX - CHICAGO MERCANTILE EXCHANGE": ("MNQ", "CME"),
    "MICRO E-MINI RUSSELL 2000 INDX - CHICAGO MERCANTILE EXCHANGE": ("M2K", "CME"),
    "NIKKEI STOCK AVERAGE YEN DENOM - CHICAGO MERCANTILE EXCHANGE": ("NIY", "CME"),
    "DJIA x $5 - CHICAGO BOARD OF TRADE": ("YM", "CBOT"),
    "MICRO E-MINI DJIA (x$0.5) - CHICAGO BOARD OF TRADE": ("MYM", "CBOT"),
    "DOW JONES U.S. REAL ESTATE IDX - CHICAGO BOARD OF TRADE": ("DJUSRE", "CBOT"),
    "MSCI EAFE - ICE FUTURES U.S.": ("MFS", "ICE US"),
    "MSCI EM INDEX - ICE FUTURES U.S.": ("MME", "ICE US"),
    "VIX FUTURES - CBOE FUTURES EXCHANGE": ("VX", "CFE"),
    "S&P 500 ANNUAL DIVIDEND INDEX - CHICAGO MERCANTILE EXCHANGE": ("SPXDIVAN", "CME"),
    # Rates
    "UST 2Y NOTE - CHICAGO BOARD OF TRADE": ("ZT", "CBOT"),
    "UST 5Y NOTE - CHICAGO BOARD OF TRADE": ("ZF", "CBOT"),
    "UST 10Y NOTE - CHICAGO BOARD OF TRADE": ("ZN", "CBOT"),
    "ULTRA UST 10Y - CHICAGO BOARD OF TRADE": ("TN", "CBOT"),
    "UST BOND - CHICAGO BOARD OF TRADE": ("ZB", "CBOT"),
    "ULTRA UST BOND - CHICAGO BOARD OF TRADE": ("UB", "CBOT"),
    "FED FUNDS - CHICAGO BOARD OF TRADE": ("ZQ", "CBOT"),
    "SOFR-3M - CHICAGO MERCANTILE EXCHANGE": ("SR3", "CME"),
    "SOFR-1M - CHICAGO MERCANTILE EXCHANGE": ("SR1", "CME"),
    "EURO SHORT TERM RATE - CHICAGO MERCANTILE EXCHANGE": ("ESTR", "CME"),
    "BLOOMBERG IG CREDIT FUTURES - CHICAGO BOARD OF TRADE": ("IQB", "CBOT"),
    # CBOT ags
    "CORN - CHICAGO BOARD OF TRADE": ("ZC", "CBOT"),
    "SOYBEANS - CHICAGO BOARD OF TRADE": ("ZS", "CBOT"),
    "SOYBEAN MEAL - CHICAGO BOARD OF TRADE": ("ZM", "CBOT"),
    "SOYBEAN OIL - CHICAGO BOARD OF TRADE": ("ZL", "CBOT"),
    "ROUGH RICE - CHICAGO BOARD OF TRADE": ("ZR", "CBOT"),
    "WHEAT-SRW - CHICAGO BOARD OF TRADE": ("ZW", "CBOT"),
    "WHEAT-HRW - CHICAGO BOARD OF TRADE": ("KE", "CBOT"),
    "BBG COMMODITY - CHICAGO BOARD OF TRADE": ("AIGCI", "CBOT"),
    # CME livestock / lumber / butter
    "LIVE CATTLE - CHICAGO MERCANTILE EXCHANGE": ("LE", "CME"),
    "FEEDER CATTLE - CHICAGO MERCANTILE EXCHANGE": ("GF", "CME"),
    "LEAN HOGS - CHICAGO MERCANTILE EXCHANGE": ("HE", "CME"),
    "LUMBER - CHICAGO MERCANTILE EXCHANGE": ("LBR", "CME"),
    "BUTTER (CASH SETTLED) - CHICAGO MERCANTILE EXCHANGE": ("CB", "CME"),
    # Crypto (CME)
    "BITCOIN - CHICAGO MERCANTILE EXCHANGE": ("BRR", "CME"),
    "MICRO BITCOIN - CHICAGO MERCANTILE EXCHANGE": ("MBT", "CME"),
    "ETHER CASH SETTLED - CHICAGO MERCANTILE EXCHANGE": ("ETH", "CME"),
    "MICRO ETHER - CHICAGO MERCANTILE EXCHANGE": ("MET", "CME"),
    "SOL - CHICAGO MERCANTILE EXCHANGE": ("SOL", "CME"),
    "XRP - CHICAGO MERCANTILE EXCHANGE": ("XRP", "CME"),
    # NYMEX
    "WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE": ("CL", "NYMEX"),
    "GASOLINE RBOB - NEW YORK MERCANTILE EXCHANGE": ("RB", "NYMEX"),
    "NY HARBOR ULSD - NEW YORK MERCANTILE EXCHANGE": ("HO", "NYMEX"),
    "NAT GAS NYME - NEW YORK MERCANTILE EXCHANGE": ("NG", "NYMEX"),
    "HENRY HUB LAST DAY FIN - NEW YORK MERCANTILE EXCHANGE": ("HH", "NYMEX"),
    "BRENT LAST DAY - NEW YORK MERCANTILE EXCHANGE": ("BZ", "NYMEX"),
    "PALLADIUM - NEW YORK MERCANTILE EXCHANGE": ("PA", "NYMEX"),
    "PLATINUM - NEW YORK MERCANTILE EXCHANGE": ("PL", "NYMEX"),
    # COMEX
    "GOLD - COMMODITY EXCHANGE INC.": ("GC", "COMEX"),
    "MICRO GOLD - COMMODITY EXCHANGE INC.": ("MGC", "COMEX"),
    "SILVER - COMMODITY EXCHANGE INC.": ("SI", "COMEX"),
    "COPPER- #1 - COMMODITY EXCHANGE INC.": ("HG", "COMEX"),
    "ALUMINUM MWP - COMMODITY EXCHANGE INC.": ("ALI", "COMEX"),
    "STEEL-HRC - COMMODITY EXCHANGE INC.": ("HRC", "COMEX"),
    # ICE US softs / dollar index
    "COCOA - ICE FUTURES U.S.": ("CC", "ICE US"),
    "COFFEE C - ICE FUTURES U.S.": ("KC", "ICE US"),
    "COTTON NO. 2 - ICE FUTURES U.S.": ("CT", "ICE US"),
    "SUGAR NO. 11 - ICE FUTURES U.S.": ("SB", "ICE US"),
    "FRZN CONCENTRATED ORANGE JUICE - ICE FUTURES U.S.": ("OJ", "ICE US"),
    "USD INDEX - ICE FUTURES U.S.": ("DX", "ICE US"),
}

COLS = {
    "Market and Exchange Names": "name",
    "As of Date in Form YYYY-MM-DD": "date",
    "CFTC Contract Market Code": "code",
    "Open Interest (All)": "oi",
    "Noncommercial Positions-Long (All)": "nc_l",
    "Noncommercial Positions-Short (All)": "nc_s",
    "Commercial Positions-Long (All)": "c_l",
    "Commercial Positions-Short (All)": "c_s",
    "Nonreportable Positions-Long (All)": "nr_l",
    "Nonreportable Positions-Short (All)": "nr_s",
}


def load(repo: Path) -> pd.DataFrame:
    d = repo / "data" / "raw" / "legacy_fut"
    files = [d / "deacot1986_2016.zip"] + [d / f"deacot{y}.zip" for y in range(2017, 2027)]
    frames = []
    for f in files:
        with zipfile.ZipFile(f) as z:
            raw = z.read(z.namelist()[0])
        df = pd.read_csv(io.BytesIO(raw), encoding="latin1",
                         dtype={"CFTC Contract Market Code": str}, low_memory=False)
        df.columns = [c.strip() for c in df.columns]
        df = df[[c for c in COLS if c in df.columns]].rename(columns=COLS)
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["code"] = df["code"].str.strip()
    df["name"] = df["name"].str.strip()
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] >= WEEKLY_ERA_START]
    df = df.drop_duplicates(["code", "date"], keep="last").sort_values(["code", "date"])
    for c in ["oi", "nc_l", "nc_s", "c_l", "c_s", "nr_l", "nr_s"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["comm"] = df["c_l"] - df["c_s"]
    df["large"] = df["nc_l"] - df["nc_s"]
    df["small"] = df["nr_l"] - df["nr_s"]
    return df


def cot_index(s: pd.Series, n: int) -> pd.Series:
    lo = s.rolling(n, min_periods=n).min()
    hi = s.rolling(n, min_periods=n).max()
    rng = (hi - lo).replace(0, np.nan)
    return (s - lo) / rng * 100


def build(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for code, g in df.groupby("code"):
        g = g.sort_values("date").reset_index(drop=True)
        if g["name"].iloc[-1] not in IBKR or len(g) < MIN_HIST_WEEKS:
            continue
        tail = g.tail(MIN_HIST_WEEKS)
        if (tail["date"].iloc[-1] - tail["date"].iloc[0]).days > MIN_HIST_WEEKS * 7 + 28:
            continue
        nm = g["name"].iloc[-1]
        row = {"name": nm, "ibkr": IBKR[nm][0], "exch": IBKR[nm][1],
               "date": g["date"].iloc[-1],
               "oi": g["oi"].iloc[-1]}
        for grp in ("comm", "large", "small"):
            for n in (26, 52):
                row[f"{grp}_{n}"] = cot_index(g[grp], n).iloc[-1]
        ci = cot_index(g["comm"], 26)
        mv = ci.diff(MOVE_WEEKS)
        row["comm_26_move6"] = mv.iloc[-1]
        row["comm_26_ago6"] = ci.iloc[-1 - MOVE_WEEKS]
        row["move6_ago6"] = mv.iloc[-1 - MOVE_WEEKS]
        hit = np.where(mv.abs().values >= MOVE_THRESHOLD)[0]
        row["wks_since_signal"] = (len(mv) - 1 - hit[-1]) if len(hit) else np.nan
        jump = g["comm"].diff() / g["oi"] * 100
        row["comm_jump_pct_oi"] = jump.iloc[-1]
        sd = jump.iloc[:-1].std()
        row["jump_z"] = jump.iloc[-1] / sd if sd and sd > 0 else np.nan
        row["comm_net"] = g["comm"].iloc[-1]
        out.append(row)
    return pd.DataFrame(out)


def build_html(res: pd.DataFrame, asof: str) -> str:
    ext = lambda v: v >= 99.5 or v < 0.5  # matches the rounded value shown in the table
    res = res.copy()
    res["name"] = res["name"].str.replace(r" - (CHICAGO|NEW YORK|ICE|COMMODITY|CBOE).*$", "", regex=True)
    res["top"] = res.apply(lambda r: ext(r["comm_26"]) and ext(r["large_26"]) and ext(r["small_26"]), axis=1)
    res["star"] = res["comm_26_move6"].abs() >= MOVE_THRESHOLD
    res["abs_comm"] = res["comm_26"].abs()
    res["abs_move"] = res["comm_26_move6"].abs()
    res["c_ext"] = res["comm_26"].apply(ext)
    top = res[res["top"]].sort_values(["abs_comm", "abs_move"], ascending=False)
    mid = res[res["c_ext"] & ~res["top"]].sort_values(["abs_comm", "abs_move"], ascending=False)
    rest = res[~res["c_ext"]].sort_values(["comm_26", "comm_26_move6"], ascending=False)
    res = pd.concat([top, mid, rest])
    heads = ["Market", "IBKR", "Comm 26", "Large 26", "Small 26", "Comm 26 chg (6 wk)",
             "Chg (6 wk) as of 6 wks ago",
             "Comm 52", "Large 52", "Small 52", "Open Int", "Comm jump 1wk (% OI)", "Jump z"]
    fmt = lambda v, f: "" if pd.isna(v) else format(v, f)
    rows = []
    for _, r in res.iterrows():
        style = ""
        if r["c_ext"]:
            lng = r["comm_26"] >= 99.5  # index 100 = green, index 0 = red
            if r["top"]:
                style = "background:#006100;color:#fff;font-weight:bold" if lng else "background:#c00000;color:#fff;font-weight:bold"
            else:
                style = "background:#c6efce;font-weight:bold" if lng else "background:#ffc7ce;font-weight:bold"
        plus = "+" if ext(r["comm_52"]) else ""
        if (r["comm_26"] >= 99.5 and r["comm_net"] > 0) or (r["comm_26"] < 0.5 and r["comm_net"] < 0):
            plus += ">"
        cells = [(style, r["name"]), (style, r["ibkr"] + ("*" if r["star"] else "") + plus),
                 ("", fmt(r["comm_26"], ".0f")), ("", fmt(r["large_26"], ".0f")), ("", fmt(r["small_26"], ".0f")),
                 ("", fmt(r["comm_26_move6"], "+.0f")),
                 ("", fmt(r["move6_ago6"], "+.0f")),
                 ("", fmt(r["comm_52"], ".0f")), ("", fmt(r["large_52"], ".0f")), ("", fmt(r["small_52"], ".0f")),
                 ("", fmt(r["oi"], ",.0f")), ("", fmt(r["comm_jump_pct_oi"], "+.2f")),
                 ("", fmt(r["jump_z"], "+.2f"))]
        rows.append("<tr>" + "".join(
            f'<td style="{s}">{v}</td>' for s, v in cells) + "</tr>")
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>COT Index Report {asof}</title>
<style>
body{{font-family:Arial,sans-serif;margin:12px;font-size:13px}}
h1{{font-size:18px;margin:0 0 4px}} p{{margin:4px 0;color:#333}}
.wrap{{overflow-x:auto}} table{{border-collapse:collapse}}
th{{background:#1f3864;color:#fff;padding:5px 7px;position:sticky;top:0;font-size:12px}}
td{{padding:3px 7px;border:1px solid #ddd;text-align:right;white-space:nowrap}}
td:nth-child(1){{text-align:left}} td:nth-child(2){{text-align:center}}
</style></head><body>
<h1>Legacy COT Index Report &mdash; liquid IBKR futures &mdash; as of {asof}</h1>
<p>{len(res)} markets. Index 0 = most net short of the window, 100 = most net long. Source: CFTC legacy futures-only COT.</p>
<p><b>Top of the list:</b> Comm 26 at 0 or 100 and Large 26 and Small 26 both at 0 or 100 ({int(res['top'].sum())} today).
<b>Market/IBKR colour (Comm 26 at 0 or 100):</b> Comm 26 = 100 is green, Comm 26 = 0 is red; dark = Large 26 and Small 26 also both at 0 or 100 (listed first), light = at least one spec is not (listed next).
<b>*</b> after the symbol = Comm 26 moved 40+ points in 6 weeks. <b>+</b> = Comm 52 is also at 0 or 100. <b>&gt;</b> = commercials are actually net long with a 100 score, or actually net short with a 0 score (absolute, not just relative).</p>
<div class="wrap"><table><tr>{"".join(f"<th>{h}</th>" for h in heads)}</tr>
{chr(10).join(rows)}
</table></div></body></html>"""


def main(repo: str = None):
    repo_path = Path(repo) if repo else Path(__file__).resolve().parent.parent
    out = repo_path / "reports"
    out.mkdir(exist_ok=True)
    df = load(repo_path)
    latest = df["date"].max()
    res = build(df)
    res = res[(res["date"] == latest) & (res["oi"] >= MIN_OI) & (~res["ibkr"].isin(THIN))].copy()
    res = res.round({c: 2 for c in res.columns if c not in ("date", "name", "ibkr", "exch")})
    asof = f"{latest:%Y-%m-%d}"
    # One fixed filename, overwritten every run, so reports never pile up. The date is inside the file.
    (out / "COT_Report_latest.html").write_text(build_html(res, asof), encoding="utf-8")
    print(f"{len(res)} markets as of {asof} -> {out / 'COT_Report_latest.html'}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
