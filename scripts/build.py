#!/usr/bin/env python3
"""
13F IDEA ENGINE — data builder (standalone / personal).

For each manager in managers.json (~100 concentrated active funds), pulls the
last few 13F-HR filings, diffs each quarter, and surfaces IDEAS = names a fund
NEWLY bought or added >=25% shares. Ranks by how many funds did so (consensus).

Also ESTIMATES, per idea, a cost basis = average share price over the quarter
the position was opened (Yahoo daily prices, cached) and the return since, plus
a per-manager scorecard = value-weighted return of that quarter's buys. 13F has
no trade price, so cost basis is an approximation, labelled as such in the UI.

    python3 scripts/discover_managers.py --write   # (optional) refresh manager list
    python3 scripts/build.py                        # pull + diff + price + write
    python3 scripts/render.py                       # bake index.html

Raw holdings cached per accession in data/holdings/, prices in data/prices/ —
so re-runs are fast. Standard library only. Public data (SEC EDGAR + OpenFIGI + Yahoo).
"""

import json, time, urllib.request, urllib.error, gzip, datetime
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
import prices   # local module: cached daily closes + quarter helpers

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"; DATA.mkdir(exist_ok=True)
HOLD_DIR = DATA / "holdings"; HOLD_DIR.mkdir(exist_ok=True)
CFG = json.loads((ROOT / "managers.json").read_text())
UA = CFG["user_agent"]
CACHE_PATH = DATA / "cusip_map.json"
CUSIP_CACHE = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}

N_PERIODS_FETCH = 8     # holdings quarters to pull (deep history => first-buy quarter per fund)
N_TRANSITIONS   = 5     # selectable quarters exposed in the UI dropdown
SIG_ADD     = 0.25      # an "add" counts as an idea only if shares grew >=25%
CAP_PER_LIST = 50
CAP_IDEAS    = 600      # per quarter, cap the ranked idea list
AEST = datetime.timezone(datetime.timedelta(hours=10))   # Australian Eastern Standard Time


# ------------------------------------------------------------------ fetch
def get(url, is_json=False, method="GET", body=None, headers=None):
    h = {"User-Agent": UA, "Accept-Encoding": "gzip"}
    if headers: h.update(headers)
    data = body.encode() if isinstance(body, str) else body
    req = urllib.request.Request(url, headers=h, data=data, method=method)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                time.sleep(0.12)
                return json.loads(raw) if is_json else raw
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(2.0 * (attempt + 1)); continue
            if attempt == 3: return None
            time.sleep(0.6 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.6 * (attempt + 1))
    return None


def local(tag): return tag.split("}")[-1]


def latest_n_13f(cik, n):
    d = get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", is_json=True)
    if not d: return []
    rec = d["filings"]["recent"]
    by_period = {}
    for form, fd, rd, acc in zip(rec["form"], rec["filingDate"], rec["reportDate"], rec["accessionNumber"]):
        if form in ("13F-HR", "13F-HR/A") and (rd not in by_period or fd > by_period[rd][0]):
            by_period[rd] = (fd, acc)
    return [(p, by_period[p][1]) for p in sorted(by_period, reverse=True)[:n]]


def info_table_url(cik, accession):
    accno = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accno}/"
    idx = get(base + "index.json", is_json=True)
    if not idx: return None
    xmls = [f["name"] for f in idx["directory"]["item"] if f["name"].lower().endswith(".xml")]
    cand = [n for n in xmls if n.lower() != "primary_doc.xml"]
    cand.sort(key=lambda n: (("infotable" not in n.lower() and "13f" not in n.lower()), n))
    return base + cand[0] if cand else None


def parse_holdings(url):
    raw = get(url)
    if not raw: return {}
    try: root = ET.fromstring(raw)
    except ET.ParseError: return {}
    H = defaultdict(lambda: {"issuer": "", "shares": 0, "value": 0})
    for el in root.iter():
        if local(el.tag) != "infoTable": continue
        f = {local(c.tag): (c.text or "").strip() for c in el.iter()}
        if f.get("putCall"): continue
        cusip = f.get("cusip", "").strip().upper()
        if not cusip: continue
        try:
            shares = int(float(f.get("sshPrnamt", "0") or 0))
            value = int(float(f.get("value", "0") or 0))
        except ValueError:
            shares, value = 0, 0
        h = H[cusip]
        h["issuer"] = f.get("nameOfIssuer", h["issuer"]).strip()[:48]
        h["shares"] += shares
        h["value"] += value
    return H


def holdings_for(cik, accession):
    f = HOLD_DIR / f"{accession.replace('-', '')}.json"
    if f.exists():
        return json.loads(f.read_text())
    h = parse_holdings(info_table_url(cik, accession))
    if h:
        f.write_text(json.dumps({k: dict(v) for k, v in h.items()}))
    return h


# ------------------------------------------------------------------ ticker + theme
def map_tickers(cusips):
    todo = [c for c in cusips if c not in CUSIP_CACHE]
    for i in range(0, len(todo), 10):
        batch = todo[i:i + 10]
        body = json.dumps([{"idType": "ID_CUSIP", "idValue": c, "exchCode": "US"} for c in batch])
        res = get("https://api.openfigi.com/v3/mapping", is_json=True, method="POST",
                  body=body, headers={"Content-Type": "application/json"})
        if res:
            for c, r in zip(batch, res):
                d = (r.get("data") or [{}])[0]
                CUSIP_CACHE[c] = d.get("ticker", "")
        else:
            for c in batch: CUSIP_CACHE.setdefault(c, "")
        time.sleep(1.7)
    CACHE_PATH.write_text(json.dumps(CUSIP_CACHE, indent=0))
    return CUSIP_CACHE


THEMES = [
    # checked FIRST so clean-energy names beat the generic Energy & Power bucket
    ("Green Energy & Decarbonisation", ["solar","wind ","renewab","clean energy","nextera","first solar","enphase","sunrun","solaredge","ormat tech","ge vernova","vernova","constellation energy","hydrogen","fuel cell","plug power","bloom energy","battery","lithium","electric vehicle","tesla","rivian","lucid","chargepoint","evgo","charging","carbon capture","decarbon","geothermal","energy storage","heat pump","canadian solar","jinko","vestas","orsted","nextracker","array tech","shoals","stem inc","clean harbors"]),
    ("Energy & Power",       ["power","grid","electr","utility","exxon","chevron","occidental","conoco","oil","natural gas"," gas","pipeline","midstream","refining","duke energy","southern co","dominion","williams cos","kinder morgan","schlumberger","halliburton","baker hughes","nuclear","nrg energy","vistra"]),
    ("Financials",           ["bank","financ","capital one","insur","keycorp","bbva","pinnacle","visa","mastercard","payment","american express","berkshire","jpmorgan","goldman","morgan stanley","charles schwab","blackstone","kkr","apollo"]),
    ("Healthcare",           ["pharma","health","medic","bio","therap","dexcom","idexx","humana","gsk","astrazeneca","vertex","thermo","stryker","danaher","abbott","merck","lilly","unitedhealth","pfizer","amgen"]),
    ("Tech & Communications",["semiconduct","nvidia","amd","asml","broadcom","arista","technolog","software","digital","intuit","microsoft","salesforce","adobe","applied mat","spotify","reddit","alphabet","meta platforms","servicenow","shopify","palo alto","apple","amazon","netflix","uber","google","micron"]),
    ("Industrials & Materials",["rail","infrastruct","schneider","eaton","industrial","machin","dover","trane","emerson","deere","parker","vertiv","weyerhaeuser","caterpillar","honeywell","ge ","boeing","union pac"]),
    ("Consumer",             ["food","agri","consumer","retail","ebay","home depot","costco","nike","chipotle","sprouts","mcdonald","starbucks","walmart","procter","coca","pepsi","tjx","dollar"]),
]

def theme_for(issuer, ticker):
    s = (issuer + " " + (ticker or "")).lower()
    for name, kws in THEMES:
        if any(k in s for k in kws): return name
    return "Other / review"


# ---- inaam impact framework: 5 pillars -> 7 thematic classes (A-G), per how-inaam-invests.pdf
# A holding can map to more than one class ("which ones best fit"). Keyword-based, best-effort.
INAAM_CLASSES = [
    ("A", "Charging",   "Energy",      ["solar","first solar","enphase","sunrun","solaredge","canadian solar","jinko","array tech","nextracker","shoals","renewab","clean energy","electrification","schneider","quanta serv"]),
    ("B", "Generating", "Energy",      ["power","utilit","wind ","vestas","orsted","nextera","constellation energy","duke energy","southern co","dominion","aes corp","west holdings","ormat tech","nrg energy","vistra","ge vernova","vernova","exelon","edison intl","public service enterprise"]),
    ("C", "Feeding",    "Agriculture", ["water","xylem","veralto","ecolab","pentair","american water","evoqua","deere","corteva","nutrien","mosaic","archer","bunge","specialty chem","food","agri","sysco","sprouts"]),
    ("D", "Building",   "Consumption", ["fintech","payment","visa","mastercard","block inc","paypal","sofi","oportun","adyen","fiserv","fidelity national","beauty","cosmetic","estee lauder","elf beaut","life scienc","thermo fisher","danaher","mettler","chargepoint","ev charging","evgo","blink charg"]),
    ("E", "Driving",    "Consumption", ["mobility","tesla","rivian","lucid","uber","lyft","general motors","ford motor","automob","consumer goods","enterprise","software","ibm","salesforce","servicenow","oracle"]),
    ("F", "Sustaining", "Waste",       ["waste","recycl","republic services","gfl environmental","casella","biotech","amgen","vertex pharm","regeneron","gilead","biogen","moderna","lifestyle","nike","lululemon","deckers"]),
    ("G", "Protecting", "Health",      ["environmental","clean harbors","cyber","crowdstrike","palo alto","zscaler","fortinet","sentinelone","oncolog","onco","novocure","exact sciences","natera","guardant","exelixis","iovance"]),
]
INAAM_META = [{"key": k, "name": n, "pillar": p} for k, n, p, _ in INAAM_CLASSES]

def inaam_for(issuer, ticker):
    s = (issuer + " " + (ticker or "")).lower()
    return [k for k, n, p, kws in INAAM_CLASSES if any(kw in s for kw in kws)]


# ------------------------------------------------------------------ scoring (shared with refine.py)
def qualifies(b):
    return b["action"] == "new" or (b.get("chg") is not None and b["chg"] >= SIG_ADD)

def conviction(n_buyers, sum_weight, has_new):
    s = n_buyers * 14 + min(30, sum_weight * 100 * 2) + (10 if has_new else 0)
    return round(min(100, s))

def label(score):
    return "High" if score >= 55 else "Medium" if score >= 30 else "Low"


def score_and_rank(records):
    """records: [{cusip, issuer, ticker, theme, buyers:[...]}]. Filter to qualifying
    buys, rank by number of funds buying, cap."""
    ideas = []
    for r in records:
        qb = [b for b in r["buyers"] if qualifies(b)]
        if not qb: continue
        n = len({b["manager"] for b in qb})
        sum_w = sum(b["weight"] or 0 for b in qb)
        has_new = any(b["action"] == "new" for b in qb)
        s = conviction(n, sum_w, has_new)
        ideas.append({
            "cusip": r["cusip"], "ticker": r.get("ticker", ""), "issuer": r["issuer"],
            "n_buyers": n,
            "buyers": sorted(qb, key=lambda b: -(b["value"] or 0)),
            "sum_weight": round(sum_w, 4), "has_new": has_new,
            "theme": r.get("theme"), "conviction": s, "conviction_label": label(s),
        })
    ideas.sort(key=lambda x: (-x["n_buyers"], -x["conviction"], -x["sum_weight"]))
    consensus = [i for i in ideas if i["n_buyers"] > 1]
    singles = [i for i in ideas if i["n_buyers"] == 1]
    return (consensus + singles)[:CAP_IDEAS]


# ------------------------------------------------------------------ diff
def diff(curr, prev, total_curr):
    out = {"new": [], "add": [], "trim": [], "exit": []}
    for cusip, h in curr.items():
        w = h["value"] / total_curr if total_curr else 0
        base = {"cusip": cusip, "issuer": h["issuer"], "value": h["value"],
                "shares": h["shares"], "weight": round(w, 5)}
        if cusip not in prev:
            out["new"].append({**base, "chg": None})
        else:
            p = prev[cusip]["shares"]
            if p > 0:
                chg = (h["shares"] - p) / p
                if chg > 0.02: out["add"].append({**base, "chg": round(chg, 3)})
                elif chg < -0.02: out["trim"].append({**base, "chg": round(chg, 3)})
    for cusip, h in prev.items():
        if cusip not in curr:
            out["exit"].append({"cusip": cusip, "issuer": h["issuer"], "value": h["value"],
                                "shares": h["shares"], "weight": None, "chg": None})
    for k in out: out[k].sort(key=lambda r: -(r["value"] or 0))
    return out


def build_period(period, mgr_holdings, mgr_meta):
    managers_out = []
    agg = defaultdict(lambda: {"issuer": "", "buyers": []})
    for name, periods in mgr_holdings.items():
        if period not in periods: continue
        older = [p for p in periods if p < period]
        if not older: continue
        prev_label = max(older)
        curr, prev = periods[period], periods[prev_label]
        total = sum(h["value"] for h in curr.values())
        d = diff(curr, prev, total)
        m = mgr_meta[name]
        scope = "large" if len(curr) > 400 else "concentrated"
        managers_out.append({"name": name, "cik": m["cik"], "tag": m["tag"], "scope": scope,
                             "as_of": period, "prev": prev_label, "positions": len(curr),
                             "aum_m": round(total / 1e6),   # 13F US-long book value, $M
                             "counts": {k: len(v) for k, v in d.items()}})
        for rec in d["new"]:
            e = agg[rec["cusip"]]; e["issuer"] = rec["issuer"]
            e["buyers"].append({"manager": name, "action": "new", "value": rec["value"],
                                "shares": rec["shares"], "weight": rec["weight"], "chg": None})
        for rec in d["add"]:
            e = agg[rec["cusip"]]; e["issuer"] = rec["issuer"]
            e["buyers"].append({"manager": name, "action": "add", "value": rec["value"],
                                "shares": rec["shares"], "weight": rec["weight"], "chg": rec["chg"]})
    records = [{"cusip": c, "issuer": e["issuer"], "ticker": "", "theme": None, "buyers": e["buyers"]}
               for c, e in agg.items()]
    return managers_out, records


def first_buy_quarter(mgr_holdings, fund, cusip):
    """Earliest fetched quarter in which `fund` held `cusip`; also flag if that is our
    oldest fetched quarter (position may predate the data window => entry is a floor)."""
    periods = sorted(mgr_holdings.get(fund, {}))
    for p in periods:
        if cusip in mgr_holdings[fund][p]:
            return p, (p == periods[0])
    return None, False


def attach_prices(ideas, managers_out, period, px_map, mgr_holdings):
    """Idea-level cost basis (this quarter's avg) + per-FUND cost basis (each fund's first
    buy quarter) + a per-manager scorecard weighted by each fund's own position return."""
    qs = prices.quarter_start(period)
    perf = defaultdict(lambda: {"wsum": 0.0, "vsum": 0.0, "buys": 0})
    for i in ideas:
        px = px_map.get(i["ticker"]) if i["ticker"] else None
        cur, cur_d = prices.latest_close(px) if px else (None, None)
        entry = prices.avg_close(px, qs, period) if px else None
        i["est_entry"] = entry
        i["cur_price"] = cur
        i["cur_date"] = cur_d
        i["ret"] = round((cur - entry) / entry, 4) if (entry and cur) else None
        for b in i["buyers"]:
            fq, before = first_buy_quarter(mgr_holdings, b["manager"], i["cusip"]) if mgr_holdings else (None, False)
            fentry = prices.avg_close(px, prices.quarter_start(fq), fq) if (px and fq) else None
            if fentry is None:                 # no history (e.g. refine): fall back to this quarter's avg
                fentry, fq = entry, (fq or period)
            b["opened"] = fq
            b["opened_before"] = before
            b["est_entry"] = fentry
            b["ret"] = round((cur - fentry) / fentry, 4) if (fentry and cur) else None
            b["est_gain"] = round(b["shares"] * (cur - fentry)) if (fentry and cur and b.get("shares")) else None
            p = perf[b["manager"]]; p["buys"] += 1
            if b["ret"] is not None and b["value"]:
                p["wsum"] += b["ret"] * b["value"]; p["vsum"] += b["value"]
    for m in managers_out:
        p = perf[m["name"]]
        m["buys"] = p["buys"]
        m["ret"] = round(p["wsum"] / p["vsum"], 4) if p["vsum"] else None


def main():
    mgr_meta = {m["name"]: m for m in CFG["managers"]}
    mgr_holdings = {}
    print(f"Pulling up to {N_PERIODS_FETCH} quarters for {len(CFG['managers'])} managers ...")
    for m in CFG["managers"]:
        periods = {}
        for p, acc in latest_n_13f(m["cik"], N_PERIODS_FETCH):
            h = holdings_for(m["cik"], acc)
            if h: periods[p] = h
        if len(periods) >= 2:
            mgr_holdings[m["name"]] = periods

    # selectable quarters = the N most recent that any fund reports; default = NEWEST
    cur_counts = defaultdict(int)
    for periods in mgr_holdings.values():
        for p in sorted(periods, reverse=True)[:-1]:
            cur_counts[p] += 1
    sel = sorted(cur_counts, reverse=True)[:N_TRANSITIONS]
    default = sel[0] if sel else None
    print(f"Selectable quarters: {[(p, cur_counts[p]) for p in sel]}  (default {default})")

    per_period, surviving = {}, set()
    for period in sel:
        managers_out, records = build_period(period, mgr_holdings, mgr_meta)
        ideas = score_and_rank(records)
        per_period[period] = (managers_out, ideas)
        surviving.update(i["cusip"] for i in ideas)

    print(f"Mapping {len(surviving)} CUSIP->ticker via OpenFIGI (cached) ...")
    tickers = map_tickers(sorted(surviving))
    for period in sel:
        for i in per_period[period][1]:
            i["ticker"] = tickers.get(i["cusip"], "")
            i["theme"] = theme_for(i["issuer"], i["ticker"])
            i["inaam"] = inaam_for(i["issuer"], i["ticker"])

    all_tk = {i["ticker"] for _, ideas in per_period.values() for i in ideas if i["ticker"]}
    print(f"Fetching daily prices for {len(all_tk)} tickers via Yahoo (cached) ...")
    px_map = prices.map_prices(all_tk)

    by_period = {}
    for period in sel:
        managers_out, ideas = per_period[period]
        prev_label = managers_out[0]["prev"] if managers_out else None
        attach_prices(ideas, managers_out, period, px_map, mgr_holdings)
        managers_out.sort(key=lambda m: (m["ret"] is None, -(m["ret"] or 0)))
        by_period[period] = {"prev": prev_label,
                             "n_managers": len(managers_out), "n_ideas": len(ideas),
                             "managers": managers_out, "ideas": ideas}
        cons = sum(1 for i in ideas if i["n_buyers"] >= 3)
        print(f"  {period}:  {len(managers_out)} mgrs  {len(ideas)} ideas  {cons} with 3+ funds")

    out = {
        "generated_at": datetime.datetime.now(AEST).strftime("%Y-%m-%d %H:%M AEST"),
        "periods": sel,
        "period_counts": {p: cur_counts[p] for p in sel},
        "default_period": default,
        "n_managers_total": len(mgr_holdings),
        "inaam_classes": INAAM_META,
        "by_period": by_period,
        "note": f"Ideas = names a fund NEWLY bought or added >=25% this quarter, ranked by how many of the {len(mgr_holdings)} tracked funds did so. Each fund's est. buy price = average price over the quarter that fund first opened the position (13F has no trade price — this is an approximation; '≥' means opened before our data window). Return is to the latest close. AUM = the fund's US-listed 13F book value. Long-only, US-listed; 13F lags up to 45 days. Idea generator, not a trade signal.",
    }
    (DATA / "ideas.json").write_text(json.dumps(out, indent=2))
    kb = (DATA / "ideas.json").stat().st_size / 1024
    print(f"\nWrote {DATA/'ideas.json'}  ({kb:.0f} KB)  —  {len(sel)} quarters, {len(mgr_holdings)} managers")


if __name__ == "__main__":
    main()
