#!/usr/bin/env python3
"""
13F IDEA ENGINE — analyst price-target enrichment (standalone / personal).

Adds an analyst consensus price target + implied upside to each idea in
data/ideas.json. Decoupled from build.py because the free target sources are
flaky at scale — this is best-effort and RE-RUNNABLE: cached hits persist, so
running it again fills gaps once rate limits cool.

    python3 scripts/targets.py               # best-effort via Yahoo (rate-limited)
    FINNHUB_KEY=xxxx python3 scripts/targets.py   # reliable, full coverage (free key)

Only consensus names (bought by 2+ funds) are fetched, to limit load.
Standard library only.
"""

import json, os
from pathlib import Path
import prices

ROOT = Path(__file__).resolve().parent.parent
IDEAS = ROOT / "data" / "ideas.json"


def main():
    d = json.loads(IDEAS.read_text())
    tks = set()
    for p in d["periods"]:
        for i in d["by_period"][p]["ideas"]:
            if i.get("ticker") and i["n_buyers"] >= 2:
                tks.add(i["ticker"])
    src = "Finnhub" if os.environ.get("FINNHUB_KEY") else "Yahoo (best-effort)"
    print(f"Fetching analyst targets for {len(tks)} consensus tickers via {src} ...")
    tmap = prices.map_targets(tks)
    got = sum(1 for v in tmap.values() if v)

    for p in d["periods"]:
        for i in d["by_period"][p]["ideas"]:
            t = tmap.get(i.get("ticker")) or {}
            mean = t.get("mean")
            i["target"] = mean
            i["target_n"] = t.get("n")
            cur = i.get("cur_price")
            i["upside"] = round((mean - cur) / cur, 4) if (mean and cur) else None

    d["targets_source"] = "finnhub" if os.environ.get("FINNHUB_KEY") else "yahoo"
    IDEAS.write_text(json.dumps(d, indent=2))
    print(f"\n{got}/{len(tks)} consensus tickers got a target. Rewrote {IDEAS}.")
    if got < len(tks) * 0.5 and not os.environ.get("FINNHUB_KEY"):
        print("Low coverage — Yahoo is rate-limiting. Re-run to fill, or set a free FINNHUB_KEY for full coverage.")


if __name__ == "__main__":
    main()
