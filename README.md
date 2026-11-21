# European Space Stocks

A public market overview of listed European space companies, with a Norway view (`#norway`).
Static GitHub Pages site at https://stocks.svenamberg.com

## How it works
`.github/workflows/update-space-stocks.yml` runs on weekdays at 17:45 UTC. It runs `scripts/build_market.py`, which pulls
prices from Yahoo Finance and commits `data/market.json`. The page only reads that file.

## Editing the company list
`companies.json` holds the companies, tickers (Yahoo symbols), segment, exposure tag (core / major / supplier),
a one-line description, `norway: true` for the Norway view, the benchmarks and the "not listed" Norwegian players.
After editing, run the workflow again.

## Local
    pip install yfinance pandas numpy
    python scripts/build_market.py          # live
    python scripts/build_market.py --demo   # offline sample
    python -m http.server                   # http://localhost:8000/

## Check after the first live run
- London tickers (QQ.L, MRO.L) are quoted in pence. Make sure their market caps look sensible; if they come out 100x
  too small, remove the `/ 100` GBp handling in `eur_rate` for market cap.
- If a benchmark symbol (`^STOXX`, `OSEBX.OL`) returns no data, its line is just left off the chart.
