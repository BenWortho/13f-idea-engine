# 13F Idea Engine

A self-updating stock-idea generator built from SEC 13F-HR filings of ~270
concentrated, active managers ("superinvestors" + focused value/growth/activist
shops). Each quarter it diffs every fund's book, surfaces **ideas** — names a
fund *newly bought* or *added ≥25%* — and ranks them by how many tracked funds
did the same (consensus). It then estimates a cost basis and the return since,
and tags each name with the inaam impact framework.

**Live site:** https://benwortho1.github.io/13f-idea-engine/

The whole thing bakes down to a single self-contained `index.html` (data inlined,
no server, no network) that rebuilds itself every weekday via GitHub Actions.

> Idea generator, not investment advice. 13F is long-only, US-listed, and lags up
> to 45 days. There is no trade price in a 13F — cost basis is an approximation.

## How it works

```
discover_managers.py   resolve ~270 funds -> current 13F-HR CIKs (SEC full-index)
        │
build.py               pull 8 quarters/fund, diff each quarter, score ideas,
        │              map CUSIP->ticker (OpenFIGI), price them, estimate returns
        ▼
data/ideas.json        multi-quarter dataset (ideas, buyers, prices, returns)
        │
targets.py             + analyst consensus price target / upside (Finnhub)
        │
render.py              bake ideas.json into a self-contained index.html
        ▼
index.html             double-click to open, or served via GitHub Pages
```

### Data sources
- **SEC EDGAR** 13F-HR filings (holdings) and submissions index — the raw signal.
- **OpenFIGI** — CUSIP → ticker mapping (cached in `data/cusip_map.json`).
- **Finnhub** — current price (`/quote`) + analyst price targets. Set as the
  `FINNHUB_KEY` repo secret. Free tier (60 req/min) is enough.
- **Yahoo** — historical daily closes (immutable; fetched once per ticker, cached).

Raw holdings are cached per accession in `data/holdings/` (immutable), prices in
`data/prices/`, so re-runs are incremental and fast.

## Self-update

`.github/workflows/update.yml` runs **every weekday at 22:00 UTC** (and on demand
via *workflow_dispatch*):

1. restore the price/target cache (Actions cache; seeded from the repo on a cold start)
2. `build.py` → `targets.py` → `render.py`
3. commit the refreshed outputs (`index.html`, `data/ideas.json`, new holdings)
4. deploy `index.html` to GitHub Pages

The price cache (`data/prices`, `data/targets`) is *not* committed on each run —
it's 24MB of small files that change daily — so it's carried between runs via the
Actions cache instead. Historical closes never change, so past-quarter cost bases
stay stable; only the recent tail (current price) is refreshed.

### Required secret
- `FINNHUB_KEY` — a free key from https://finnhub.io. Without it, prices fall back
  to Yahoo (rate-limited) and analyst targets are skipped.

## Run it locally

```bash
python3 scripts/build.py         # pull + diff + price + score  -> data/ideas.json
python3 scripts/targets.py       # (optional) add analyst targets
python3 scripts/render.py        # bake data/ideas.json -> index.html
open index.html                  # (macOS) view it

# optional maintenance
python3 scripts/discover_managers.py --write   # refresh the manager roster
python3 scripts/refine.py                       # re-score without re-fetching SEC
```

Standard library only — no `pip install`. Set `FINNHUB_KEY` in your environment
for reliable prices/targets:

```bash
FINNHUB_KEY=xxxx python3 scripts/build.py
```

## Methodology notes
- **Idea** = a fund newly opened a position, or grew an existing one by ≥25% shares.
- **Consensus** = number of distinct tracked funds that did so this quarter.
- **Conviction** blends consensus, position weight, and whether it's a fresh buy.
- **Est. buy** = average daily close over the quarter a fund *first opened* the
  position (13F has no trade date/price — "≥" flags positions opened before our
  data window). **Return** is to the latest close.
- **AUM** = the fund's US-listed 13F book value (excludes cash, bonds, shorts, non-US).
- Pure quant/market-maker shops (Citadel, Renaissance, …) are excluded — their
  thousand-name books drown the signal.
