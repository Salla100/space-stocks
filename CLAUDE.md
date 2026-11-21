# European Space Stocks

**Subdomain:** stocks.svenamberg.com
**Repo:** github.com/Salla100/space-stocks
**Status:** Live
**Design:** Space theme. See the root site's CLAUDE.md for the design system.

## What it does
Public market overview of listed European space companies, with a Norway view (`#norway`).
Static page: `index.html` reads `data/market.json`.

## Data
`.github/workflows/update-space-stocks.yml` runs on weekdays at 17:45 UTC. It runs `scripts/build_market.py`
(Yahoo Finance via yfinance) and commits `data/market.json`. There's no API key.
`python scripts/build_market.py --demo` writes offline sample data, and the page shows a "Sample data" banner for it.

## Editing companies
All in `companies.json`: Yahoo ticker, segment, exposure (core / major / supplier), blurb, `norway: true`,
benchmarks, and the unlisted Norwegian players for the Norway view.
