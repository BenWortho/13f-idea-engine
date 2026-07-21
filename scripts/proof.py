#!/usr/bin/env python3
"""
13F Idea Engine — PROOF OF PIPELINE (standalone / personal).

Pulls the two most recent 13F-HR holdings filings for each manager in
managers.json straight from public SEC EDGAR, diffs quarter-over-quarter,
and prints real activity: NEW buys, ADDS, TRIMS, EXITS — plus a
cross-manager "consensus" view of names bought by multiple managers.

Standard library only. No inaam systems touched. Read-only public data.
"""

import json, time, urllib.request, urllib.error, xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "managers.json").read_text())
UA = CFG["user_agent"]
ADD_TRIM_THRESHOLD = 0.05  # >5% share change counts as a real add/trim


def get(url, is_json=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    import gzip; raw = gzip.decompress(raw)
                time.sleep(0.15)  # SEC fair-access: stay well under 10 req/s
                return json.loads(raw) if is_json else raw
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            time.sleep(0.6 * (attempt + 1))
    return None


def local(tag):
    return tag.split("}")[-1]


def latest_two_13f(cik):
    """Return the two most recent 13F-HR/A filings as (reportDate, accession)."""
    data = get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", is_json=True)
    if not data:
        return []
    rec = data["filings"]["recent"]
    by_period = {}  # reportDate -> (filingDate, accession)  keep latest filing per period
    for form, fdate, rdate, acc in zip(rec["form"], rec["filingDate"], rec["reportDate"], rec["accessionNumber"]):
        if form in ("13F-HR", "13F-HR/A"):
            if rdate not in by_period or fdate > by_period[rdate][0]:
                by_period[rdate] = (fdate, acc)
    periods = sorted(by_period.keys(), reverse=True)[:2]
    return [(p, by_period[p][1]) for p in periods]


def info_table_url(cik, accession):
    accno = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accno}/"
    idx = get(base + "index.json", is_json=True)
    if not idx:
        return None
    xmls = [f["name"] for f in idx["directory"]["item"] if f["name"].lower().endswith(".xml")]
    # prefer obvious info-table names, else sniff content
    for name in sorted(xmls, key=lambda n: ("infotable" not in n.lower() and "13f" not in n.lower(), n)):
        if name.lower() == "primary_doc.xml":
            continue
        return base + name
    return None


def parse_holdings(url):
    """Return {cusip: {'issuer','shares','value'}} aggregating common-stock (SH) rows, excluding options."""
    raw = get(url)
    if not raw:
        return {}
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return {}
    holdings = defaultdict(lambda: {"issuer": "", "shares": 0, "value": 0})
    for el in root.iter():
        if local(el.tag) != "infoTable":
            continue
        f = {}
        for c in el.iter():
            f[local(c.tag)] = (c.text or "").strip()
        put_call = f.get("putCall", "")
        if put_call:  # skip options; count only the underlying long stock rows
            continue
        cusip = f.get("cusip", "").strip().upper()
        if not cusip:
            continue
        try:
            shares = int(float(f.get("sshPrnamt", "0") or 0))
            value = int(float(f.get("value", "0") or 0))
        except ValueError:
            shares, value = 0, 0
        h = holdings[cusip]
        h["issuer"] = f.get("nameOfIssuer", h["issuer"])[:40]
        h["shares"] += shares
        h["value"] += value
    return holdings


def diff(curr, prev):
    out = {"new": [], "exit": [], "add": [], "trim": []}
    for cusip, h in curr.items():
        if cusip not in prev:
            out["new"].append((cusip, h["issuer"], h["value"]))
        else:
            p = prev[cusip]["shares"]
            if p > 0:
                chg = (h["shares"] - p) / p
                if chg > ADD_TRIM_THRESHOLD:
                    out["add"].append((cusip, h["issuer"], round(chg * 100)))
                elif chg < -ADD_TRIM_THRESHOLD:
                    out["trim"].append((cusip, h["issuer"], round(chg * 100)))
    for cusip, h in prev.items():
        if cusip not in curr:
            out["exit"].append((cusip, h["issuer"], h["value"]))
    return out


def main():
    consensus = defaultdict(lambda: {"issuer": "", "buyers": [], "value": 0})
    print(f"\n{'='*72}\n  13F IDEA ENGINE — LIVE PROOF  ({len(CFG['managers'])} managers)\n{'='*72}")
    for m in CFG["managers"]:
        try:
            filings = latest_two_13f(m["cik"])
            if len(filings) < 2:
                print(f"\n● {m['name']:<34} — need 2 filings, found {len(filings)} (skip)")
                continue
            (cur_p, cur_acc), (prev_p, prev_acc) = filings
            curr = parse_holdings(info_table_url(m["cik"], cur_acc))
            prev = parse_holdings(info_table_url(m["cik"], prev_acc))
            if not curr or not prev:
                print(f"\n● {m['name']:<34} — could not parse holdings (skip)")
                continue
            d = diff(curr, prev)
            print(f"\n● {m['name']}   [{prev_p} → {cur_p}]   {len(curr)} positions")
            print(f"    NEW {len(d['new']):>3} | ADD {len(d['add']):>3} | TRIM {len(d['trim']):>3} | EXIT {len(d['exit']):>3}")
            for cusip, issuer, val in sorted(d["new"], key=lambda x: -x[2])[:4]:
                print(f"      + NEW  {issuer:<40} ${val:,}")
                c = consensus[cusip]; c["issuer"] = issuer; c["buyers"].append(m["name"]); c["value"] += val
        except Exception as e:
            print(f"\n● {m['name']:<34} — error: {e}")

    print(f"\n{'='*72}\n  CONSENSUS NEW BUYS  (names newly bought by >1 manager this quarter)\n{'='*72}")
    ranked = sorted(consensus.items(), key=lambda kv: (-len(kv[1]["buyers"]), -kv[1]["value"]))
    shown = 0
    for cusip, c in ranked:
        if len(c["buyers"]) > 1:
            print(f"  {len(c['buyers'])}× {c['issuer']:<40} {', '.join(b.split()[0] for b in c['buyers'])}")
            shown += 1
    if not shown:
        print("  (no overlap this quarter — each manager's new buys were unique)")
    print()


if __name__ == "__main__":
    main()
