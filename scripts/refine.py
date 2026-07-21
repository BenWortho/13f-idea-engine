#!/usr/bin/env python3
"""
13F IDEA ENGINE — re-score an existing ideas.json in place (standalone).

Applies build.py's CURRENT scoring/ranking + price logic to the buyers already
stored in data/ideas.json, without re-fetching from SEC (prices come from the
data/prices cache). Handy for iterating on the idea methodology fast.

    python3 scripts/refine.py

For a full refresh (new filings/managers) run scripts/build.py instead.
Standard library only.
"""

import json
from pathlib import Path
import build, prices

ROOT = Path(__file__).resolve().parent.parent
IDEAS = ROOT / "data" / "ideas.json"


def main():
    d = json.loads(IDEAS.read_text())
    all_tk = {i["ticker"] for p in d["periods"] for i in d["by_period"][p]["ideas"] if i.get("ticker")}
    px_map = prices.map_prices(all_tk)

    for period in d["periods"]:
        blk = d["by_period"][period]
        records = [{"cusip": i["cusip"], "issuer": i["issuer"], "ticker": i.get("ticker", ""),
                    "theme": i.get("theme"), "buyers": i["buyers"]} for i in blk["ideas"]]
        ideas = build.score_and_rank(records)
        for i in ideas:
            i["theme"] = build.theme_for(i["issuer"], i["ticker"])
        build.attach_prices(ideas, blk["managers"], period, px_map, None)
        blk["managers"].sort(key=lambda m: (m["ret"] is None, -(m["ret"] or 0)))
        blk["ideas"] = ideas
        blk["n_ideas"] = len(ideas)
        cons = sum(1 for i in ideas if i["n_buyers"] >= 3)
        print(f"  {period}:  {len(ideas)} ideas  {cons} with 3+ funds")

    IDEAS.write_text(json.dumps(d, indent=2))
    print(f"\nRewrote {IDEAS} ({IDEAS.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
