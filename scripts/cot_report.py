#!/usr/bin/env python3
"""
COT report (HTML) - the ONE command to run the report. No other script is needed.

    python3 scripts/cot_report.py            # from the repo root; writes reports/COT_Report_latest.html (overwritten each run)

FINAL RULES (do not change unless Michael says so):
- Legacy futures-only COT from data/raw/legacy_fut; weekly era from 1992-10-01; 156+ clean weeks.
- Only IBKR-tradable futures (IBKR map below), open interest >= 45,000 as a liquidity proxy,
  minus thin products (THIN). No "Mine" column.
- Index = (net - min)/(max - min)*100 over 52 or 104 weeks. Briese CoT Movement Index = Comm 52 now
  minus 6 weeks ago; "+" requires a green row with change >= 40 or a red row with change <= -40.
- COLOUR: Market and IBKR cells are dark green if either Comm 52 or Comm 104 is >= 95
  and either Large 52 or Large 104 is <= 5 and Small 52 is <= 5. They are dark red if
  either commercial index is <= 5, either large spec index is >= 95, and Small 52 is >= 95.
  Otherwise, Comm 52 rounding to 100 or 0 gives light green or light red, respectively.
- ORDER: dark rows first, with a matching 100 or 0 on either commercial index at the
  top of that group. Light rows follow. Within each group, sort by |Comm 52| then
  |6-wk change|. Uncoloured rows follow by Comm 52 descending.
- SYMBOL MARKS: "+" = 40-pt move agreeing with row colour (none on uncoloured rows); "*" = Comm 104 matches Comm 52 at 0 or 100 (after the "+");
  ">" = absolute position agrees: Comm 52 = 100 and commercials actually net long, or Comm 52 = 0 and
  actually net short; "&" = green and above the 20-day SMA, or red and below it.
- No Comm Net column.
- No Mine, "Comm 52 six wks ago" or "weeks since 40-pt move" columns.
"""
import io
import json
import sys
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

WEEKLY_ERA_START = "1992-10-01"
MIN_OI = 45_000   # open interest used as a liquidity proxy (CFTC data has no volume)
THIN = {"SPXDIVAN","AIGCI","MFS","MME","DJUSRE","HH","EMD"}  # thinly traded at IBKR despite OI
MIN_HIST_WEEKS = 156
MOVE_WEEKS = 6
MOVE_THRESHOLD = 40
PRICE_ROOTS = {
    "6A": "A6", "6B": "B6", "6C": "AD", "6E": "E6", "6J": "J1",
    "6L": "BR", "6M": "MP", "6N": "N6", "6S": "E1", "ZB": "US",
    "BRR": "BTC", "LBR": "LBS",
}

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
            for n in (52, 104):
                row[f"{grp}_{n}"] = cot_index(g[grp], n).iloc[-1]
        ci = cot_index(g["comm"], 52)
        mv = ci.diff(MOVE_WEEKS)
        row["comm_52_move6"] = mv.iloc[-1]
        row["comm_52_ago6"] = ci.iloc[-1 - MOVE_WEEKS]
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


def load_sma20(repo: Path, asof: str) -> tuple[str, dict]:
    try:
        snapshot = json.loads((repo / "data" / "futures_sma20.json").read_text(encoding="utf-8"))
        price_date = date.fromisoformat(snapshot["as_of"])
        symbols = snapshot["symbols"]
        if price_date >= date.fromisoformat(asof) and isinstance(symbols, dict) and symbols:
            return price_date.isoformat(), symbols
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return "", {}


def build_html(res: pd.DataFrame, asof: str, price_date: str = "", sma20: dict = None) -> str:
    ext = lambda v: v >= 99.5 or v < 0.5  # matches the rounded value shown in the table
    res = res.copy()
    res["name"] = res["name"].str.replace(r" - (CHICAGO|NEW YORK|ICE|COMMODITY|CBOE).*$", "", regex=True)
    dark_green = (res["comm_52"].ge(95) | res["comm_104"].ge(95)) & (
        (res["large_52"].le(5) | res["large_104"].le(5)) & res["small_52"].le(5)
    )
    dark_red = (res["comm_52"].le(5) | res["comm_104"].le(5)) & (
        (res["large_52"].ge(95) | res["large_104"].ge(95)) & res["small_52"].ge(95)
    )
    res = res.round({c: 2 for c in res.columns if c not in ("date", "name", "ibkr", "exch")})
    res["top"] = dark_green | dark_red
    res["green"] = dark_green | (~res["top"] & res["comm_52"].ge(99.5))
    res["abs_comm"] = res["comm_52"].abs()
    res["abs_move"] = res["comm_52_move6"].abs()
    res["coloured"] = res["top"] | res["comm_52"].apply(ext)
    res["plus"] = res["coloured"] & (
        (res["green"] & res["comm_52_move6"].ge(MOVE_THRESHOLD))
        | (~res["green"] & res["comm_52_move6"].le(-MOVE_THRESHOLD))
    )
    res["matching_comm_extreme"] = (
        dark_green & (res["comm_52"].ge(99.5) | res["comm_104"].ge(99.5))
    ) | (
        dark_red & (res["comm_52"].lt(0.5) | res["comm_104"].lt(0.5))
    )
    top = res[res["top"]].sort_values(
        ["matching_comm_extreme", "abs_comm", "abs_move"], ascending=False
    )
    mid = res[res["coloured"] & ~res["top"]].sort_values(["abs_comm", "abs_move"], ascending=False)
    rest = res[~res["coloured"]].sort_values(["comm_52", "comm_52_move6"], ascending=False)
    res = pd.concat([top, mid, rest])
    heads = ["Market", "IBKR", "Comm 52", "Large 52", "Small 52", "Comm 52 chg (6 wk)",
             "Chg (6 wk) as of 6 wks ago",
             "Comm 104", "Large 104", "Small 104", "Open Int", "Comm jump 1wk (% OI)", "Jump z"]
    fmt = lambda v, f: "" if pd.isna(v) else format(v, f)
    sma20 = sma20 or {}
    price_note = f"Daily futures close as of {price_date}." if price_date else "Current price snapshot unavailable."
    rows = []
    for _, r in res.iterrows():
        style = ""
        if r["coloured"]:
            lng = r["green"]
            if r["top"]:
                style = "background:#006100;color:#fff;font-weight:bold" if lng else "background:#c00000;color:#fff;font-weight:bold"
            else:
                style = "background:#c6efce;font-weight:bold" if lng else "background:#ffc7ce;font-weight:bold"
        marks = "+" if r["plus"] else ""
        if (r["comm_52"] >= 99.5 and r["comm_104"] >= 99.5) or (
            r["comm_52"] < 0.5 and r["comm_104"] < 0.5
        ):
            marks += "*"
        if (r["comm_52"] >= 99.5 and r["comm_net"] > 0) or (r["comm_52"] < 0.5 and r["comm_net"] < 0):
            marks += ">"
        if r["coloured"]:
            trend = sma20.get(PRICE_ROOTS.get(r["ibkr"], r["ibkr"]))
            if trend == ("above" if lng else "below"):
                marks += "&amp;"
        cells = [(style, r["name"]), (style, r["ibkr"] + marks),
                 ("", fmt(r["comm_52"], ".0f")), ("", fmt(r["large_52"], ".0f")), ("", fmt(r["small_52"], ".0f")),
                 ("", fmt(r["comm_52_move6"], "+.0f")),
                 ("", fmt(r["move6_ago6"], "+.0f")),
                 ("", fmt(r["comm_104"], ".0f")), ("", fmt(r["large_104"], ".0f")), ("", fmt(r["small_104"], ".0f")),
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
<p><b>Dark green:</b> Comm 52 or Comm 104 &ge; 95, Large 52 or Large 104 &le; 5, and Small 52 &le; 5.
<b>Dark red:</b> Comm 52 or Comm 104 &le; 5, Large 52 or Large 104 &ge; 95, and Small 52 &ge; 95.
Dark rows are listed first ({int(res['top'].sum())} today), with a matching 100 (green) or 0 (red)
on either commercial index at the top of that group. Otherwise, Comm 52 rounding to 100 or 0 gives light green or light red, respectively.</p>
<p><b>+</b> after the symbol = Comm 52 rose at least 40 points in 6 weeks for a green row, or fell at least 40 points for a red row; no + on uncoloured rows. <b>*</b> = Comm 104 and Comm 52 are both at 0 or both at 100. <b>&gt;</b> = commercials are actually net long with a 100 score, or actually net short with a 0 score (absolute, not just relative).</p>
<p><b>&amp;</b> = green and above the 20-day simple moving average, or red and below it. {price_note}</p>
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
    asof = f"{latest:%Y-%m-%d}"
    # One fixed filename, overwritten every run, so reports never pile up. The date is inside the file.
    price_date, sma20 = load_sma20(repo_path, asof)
    (out / "COT_Report_latest.html").write_text(build_html(res, asof, price_date, sma20), encoding="utf-8")
    print(f"{len(res)} markets as of {asof} -> {out / 'COT_Report_latest.html'}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)

