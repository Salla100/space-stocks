#!/usr/bin/env python3
"""Build data/market.json from companies.json + Yahoo Finance.

  python scripts/build_market.py          # live data (needs: pip install yfinance pandas numpy)
  python scripts/build_market.py --demo   # synthetic prices, for previewing the page offline
"""
import json, sys, datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "market.json"
DEMO = "--demo" in sys.argv


def fx_code(c):  # Yahoo quotes London in pence
    return "GBP" if c == "GBp" else c


def download(symbols):
    if DEMO:
        rng = np.random.default_rng(7)
        idx = pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.offsets.BDay(1), periods=400)
        fx0 = {"NOKEUR=X": 0.085, "SEKEUR=X": 0.088, "GBPEUR=X": 1.17}
        close = {}
        for s in symbols:
            fx = s.endswith("=X")
            drift, vol = (0, .004) if fx else (rng.normal(.0007, .0008), rng.uniform(.012, .035))
            close[s] = fx0.get(s, rng.uniform(5, 400)) * np.exp(np.cumsum(rng.normal(drift, vol, len(idx))))
        caps = {s: float(rng.uniform(2e8, 1.2e11)) for s in symbols if not s.endswith("=X")}
        return pd.DataFrame(close, index=idx), caps

    import yfinance as yf
    df = yf.download(symbols, period="2y", interval="1d", auto_adjust=False,
                     progress=False, threads=True)["Close"]
    if isinstance(df, pd.Series):
        df = df.to_frame(symbols[0])
    caps = {}
    for s in symbols:
        if s.endswith("=X") or s.startswith("^") or s.endswith("BX.OL"):
            continue
        try:
            caps[s] = float(yf.Ticker(s).fast_info["market_cap"])
        except Exception as e:
            print(f"WARNING: no market cap for {s}: {e}", file=sys.stderr)
    return df.sort_index().ffill(limit=5), caps


def pct(a, b):
    return None if (a is None or b is None or not np.isfinite(a) or not np.isfinite(b) or b == 0) else round((a / b - 1) * 100, 2)


def at_or_before(s, date):
    s = s.loc[:date].dropna()
    return float(s.iloc[-1]) if len(s) else None


def main():
    cfg = json.loads((ROOT / "companies.json").read_text())
    cos = cfg["companies"]
    benches = cfg.get("benchmarks", {})
    fx_syms = sorted({f"{fx_code(c['currency'])}EUR=X" for c in cos if fx_code(c["currency"]) != "EUR"})
    syms = [c["ticker"] for c in cos] + fx_syms + [b["ticker"] for b in benches.values()]
    close, caps = download(syms)

    last = close[[c["ticker"] for c in cos if c["ticker"] in close]].dropna(how="all").index[-1]
    close = close.loc[:last]
    ytd0 = pd.Timestamp(year=last.year, month=1, day=1) - pd.Timedelta(days=1)

    def eur_rate(ccy):
        c = fx_code(ccy)
        r = 1.0 if c == "EUR" else at_or_before(close[f"{c}EUR=X"], last)
        return r / 100 if ccy == "GBp" else r

    rows, failed = [], []
    for c in cos:
        t = c["ticker"]
        s = close[t].dropna() if t in close else pd.Series(dtype=float)
        if len(s) < 2:
            failed.append(t)
            continue
        px = float(s.iloc[-1])
        y1 = s.loc[last - pd.DateOffset(years=1):]
        cap = caps.get(t)
        row = {
            **{k: c[k] for k in ("ticker", "name", "country", "currency", "segment", "exposure")},
            "norway": bool(c.get("norway")),
            "blurb": c.get("blurb", ""),
            "price": round(px, 4),
            "d1": pct(px, float(s.iloc[-2])),
            "w1": pct(px, at_or_before(s, last - pd.Timedelta(days=7))),
            "m1": pct(px, at_or_before(s, last - pd.DateOffset(months=1))),
            "ytd": pct(px, at_or_before(s, ytd0)),
            "y1": pct(px, float(y1.iloc[0])) if len(y1) > 200 else None,
            "hi52": round(float(y1.max()), 4), "lo52": round(float(y1.min()), 4),
            "mcapEUR": round(cap * eur_rate(c["currency"])) if cap else None,
            "spark": [round(float(v), 4) for v in s.iloc[-63:]],
        }
        rows.append(row)
    if failed:
        print(f"WARNING: no prices for {failed}", file=sys.stderr)

    def ew_index(tickers):
        """Equal-weighted index of daily returns (each stock counts the same), 1 year, base 100."""
        px = close[tickers].loc[last - pd.DateOffset(years=1):]
        rets = px.pct_change().iloc[1:]
        lvl = (1 + rets.mean(axis=1, skipna=True).fillna(0)).cumprod() * 100
        lvl = pd.concat([pd.Series([100.0], index=[px.index[0]]), lvl])
        return [round(float(v), 3) for v in lvl]

    def bench_index(key, dates):
        b = benches.get(key)
        if not b or b["ticker"] not in close or close[b["ticker"]].dropna().empty:
            return None
        s = close[b["ticker"]].reindex(dates).ffill().bfill()
        return {"name": b["name"], "values": [round(float(v / s.iloc[0] * 100), 3) for v in s]}

    dates = close.loc[last - pd.DateOffset(years=1):].index
    eu = [r["ticker"] for r in rows]
    no = [r["ticker"] for r in rows if r["norway"]]
    core = [r["ticker"] for r in rows if r["exposure"] == "core"]

    def summary(ts):
        rs = [r for r in rows if r["ticker"] in ts]
        def med(k):
            v = [r[k] for r in rs if r[k] is not None]
            return round(float(np.median(v)), 2) if v else None
        return {"count": len(rs), "advancers": sum(1 for r in rs if (r["d1"] or 0) > 0),
                "medianD1": med("d1"), "medianYtd": med("ytd"), "medianY1": med("y1"),
                "mcapEUR": sum(r["mcapEUR"] or 0 for r in rs) or None}

    out = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "asOf": last.strftime("%Y-%m-%d"),
        "sample": DEMO,
        "dates": [d.strftime("%Y-%m-%d") for d in dates],
        "views": {
            "europe": {"summary": summary(eu), "index": ew_index(eu), "coreIndex": ew_index(core),
                       "benchmark": bench_index("europe", dates)},
            "norway": {"summary": summary(no), "index": ew_index(no) if no else None,
                       "benchmark": bench_index("norway", dates)},
        },
        "companies": rows,
        "norwayUnlisted": cfg.get("norwayUnlisted", []),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    print(f"Wrote {OUT}: {len(rows)} companies, as of {out['asOf']}")


if __name__ == "__main__":
    main()
