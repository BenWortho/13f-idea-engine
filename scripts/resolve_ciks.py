#!/usr/bin/env python3
"""Resolve each manager name to its CURRENTLY-ACTIVE 13F-HR filer CIK.

Strategy: EDGAR full-text search restricted to recent 13F-HR filings, then
keep only hits whose filer display-name actually contains the manager's key
token, and pick the CIK with the most recent filing.
"""
import os, json, time, urllib.request, urllib.parse, gzip
from collections import defaultdict

UA = os.environ.get("SEC_CONTACT") or "13f-idea-engine research-tool"  # no "github" — SEC 403s it; see build.py

# name -> key token that MUST appear in the filer's display name (guards against word-match noise)
QUERIES = {
    "Generation Investment Management": "generation investment",
    "Impax Asset Management":           "impax",
    "Parnassus":                        "parnassus",
    "Domini Impact Investments":        "domini",
    "Trillium Asset Management":        "trillium",
    "Boston Common Asset Management":   "boston common",
    "Zevin Asset Management":           "zevin",
    "Nia Impact Advisors":             "nia impact",
    "Community Capital Management":     "community capital",
    "Terra Alpha Investments":          "terra alpha",
    "Praxis / Everence Capital":        "praxis",
    "Brown Advisory":                   "brown advisory",
}

def fts(query):
    params = urllib.parse.urlencode({"q": f'"{query}"', "forms": "13F-HR",
                                     "startdt": "2025-06-01", "enddt": "2026-12-31"})
    url = f"https://efts.sec.gov/LATEST/search-index?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    time.sleep(0.2)
    return json.loads(raw)

print(f"{'MANAGER':<34} {'CURRENT CIK':<12} LATEST      FILER NAME")
print("-" * 92)
resolved = {}
for name, token in QUERIES.items():
    try:
        d = fts(token)
        best = defaultdict(lambda: ("", ""))  # cik -> (display, latest_date)
        for h in d.get("hits", {}).get("hits", []):
            s = h["_source"]
            for dn in s.get("display_names", []):
                if token.lower() in dn.lower():
                    cik = dn.split("CIK ")[-1].rstrip(")")
                    fd = s.get("file_date", "")
                    if fd > best[cik][1]:
                        best[cik] = (dn.split("  (")[0], fd)
        if best:
            cik, (dn, fd) = max(best.items(), key=lambda kv: kv[1][1])
            resolved[name] = cik
            print(f"{name:<34} {cik:<12} {fd}  {dn}")
        else:
            print(f"{name:<34} {'??':<12} {'':<11} (no recent match — resolve manually)")
    except Exception as e:
        print(f"{name:<34} ERROR: {e}")

print("\nJSON:")
print(json.dumps(resolved, indent=2))
