#!/usr/bin/env python3
"""
13F IDEA ENGINE — manager discovery (standalone / personal).

Resolves a curated list of NOTABLE CONCENTRATED active managers ("superinvestor"
hedge funds + focused value/growth shops) to their CURRENT active 13F-HR CIK by
matching against SEC's authoritative quarterly full-index (every 13F-HR filer,
exact name + CIK). No CIK guessing: a manager is only added if a real filer name
in the index contains its distinctive token AND data.sec.gov confirms a recent
13F-HR (holdings) filing. Pure quant/market-maker shops (Citadel, Renaissance,
Millennium, ...) are intentionally excluded — their books are thousands of
positions and drown the idea signal.

    python3 scripts/discover_managers.py            # dry run: print report
    python3 scripts/discover_managers.py --write     # rewrite managers.json

Standard library only. Read-only public SEC data.
"""

import os, json, sys, time, urllib.request, gzip, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "managers.json").read_text())
UA = os.environ.get("SEC_CONTACT") or CFG.get("user_agent") or "13f-idea-engine research-tool"  # no "github" — SEC 403s it; see build.py

INDEX_QUARTERS = ["2026/QTR2", "2026/QTR1"]
STALE_BEFORE = "2025-06-30"   # drop managers whose latest 13F-HR is older than this

# Curated candidates: distinctive UPPER token that must appear in the filer's
# name  ->  (display name, style tag). Tokens are chosen to be specific enough
# to avoid substring collisions; the report prints the matched filer name so
# false matches can be spotted and fixed.
CANDIDATES = [
    ("BERKSHIRE HATHAWAY",   ("Berkshire Hathaway",          "value-Buffett")),
    ("PERSHING SQUARE CAPITAL",("Pershing Square",           "activist-Ackman")),
    ("THIRD POINT",          ("Third Point",                 "activist-Loeb")),
    ("APPALOOSA",            ("Appaloosa",                   "distressed-Tepper")),
    ("GREENLIGHT CAPITAL",   ("Greenlight Capital",          "value-Einhorn")),
    ("ICAHN",                ("Icahn Capital",               "activist-Icahn")),
    ("BAUPOST",              ("Baupost Group",               "value-Klarman")),
    ("TIGER GLOBAL",         ("Tiger Global",                "growth-Coleman")),
    ("LONE PINE",            ("Lone Pine Capital",           "growth-Mandel")),
    ("VIKING GLOBAL",        ("Viking Global",               "l/s-Halvorsen")),
    ("COATUE",               ("Coatue Management",           "tech-Laffont")),
    ("MAVERICK CAPITAL",     ("Maverick Capital",            "l/s-Ainslie")),
    ("AKRE CAPITAL",         ("Akre Capital",                "quality-Akre")),
    ("FUNDSMITH",            ("Fundsmith",                   "quality-Smith")),
    ("HIMALAYA CAPITAL",     ("Himalaya Capital",            "value-Li Lu")),
    ("TWEEDY",               ("Tweedy Browne",               "deep-value")),
    ("FAIRHOLME",            ("Fairholme Capital",           "value-Berkowitz")),
    ("DUQUESNE",             ("Duquesne Family Office",      "macro-Druckenmiller")),
    ("SOROS FUND",           ("Soros Fund Management",       "macro-Soros")),
    ("GLENVIEW CAPITAL",     ("Glenview Capital",            "l/s-Robbins")),
    ("HARRIS ASSOCIATES",    ("Harris Associates (Oakmark)", "value-Nygren")),
    ("RUANE",                ("Ruane Cunniff (Sequoia)",     "quality")),
    ("MARKEL",               ("Markel Group",                "insurance-float")),
    ("GATES FOUNDATION",     ("Gates Foundation Trust",      "endowment")),
    ("ALTIMETER",            ("Altimeter Capital",           "tech-Gerstner")),
    ("WHALE ROCK",           ("Whale Rock Capital",          "tech-growth")),
    ("HHLR",                 ("Hillhouse (HHLR)",            "growth-Zhang")),
    ("SANDS CAPITAL",        ("Sands Capital",               "growth")),
    ("POLEN CAPITAL",        ("Polen Capital",               "quality-growth")),
    ("EAGLE CAPITAL MANAGEMENT", ("Eagle Capital Management", "value")),
    ("EGERTON",              ("Egerton Capital",             "l/s")),
    ("LANSDOWNE",            ("Lansdowne Partners",          "l/s")),
    ("TCI FUND",             ("TCI Fund Management",         "activist-Hohn")),
    ("EMINENCE CAPITAL",     ("Eminence Capital",            "l/s-Sandler")),
    ("CORVEX",               ("Corvex Management",           "activist-Meister")),
    ("VALUEACT",             ("ValueAct Capital",            "activist")),
    ("TRIAN FUND MANAGEMENT",("Trian Fund Management",       "activist-Peltz")),
    ("STARBOARD VALUE",      ("Starboard Value",             "activist-Smith")),
    ("ELLIOTT INVESTMENT",   ("Elliott Investment Mgmt",     "activist-Singer")),
    ("JANA PARTNERS",        ("JANA Partners",               "activist")),
    ("SACHEM HEAD",          ("Sachem Head Capital",         "activist-Ferguson")),
    ("HOUND PARTNERS",       ("Hound Partners",              "l/s")),
    ("TYBOURNE",             ("Tybourne Capital",            "growth")),
    ("DARSANA",              ("Darsana Capital",             "l/s")),
    ("LIGHT STREET",         ("Light Street Capital",        "tech-growth")),
    ("DRAGONEER",            ("Dragoneer Investment",        "growth")),
    ("D1 CAPITAL",           ("D1 Capital",                  "growth-Sundheim")),
    ("SLATE PATH",           ("Slate Path Capital",          "l/s")),
    ("MATRIX CAPITAL MANAGEMENT", ("Matrix Capital Mgmt",    "tech-Benson")),
    ("GIVERNY",              ("Giverny Capital",             "quality")),
    ("BROAD RUN",            ("Broad Run Investment",        "quality")),
    ("WEDGEWOOD",            ("Wedgewood Partners",          "growth")),
    ("SMEAD",                ("Smead Capital",               "value")),
    ("GABELLI",              ("GAMCO / Gabelli",             "value")),
    ("SOUTHEASTERN ASSET",   ("Southeastern (Longleaf)",     "value")),
    ("DAVIS SELECTED",       ("Davis Selected Advisers",     "value-Davis")),
    ("MILLER VALUE",         ("Miller Value Partners",       "value-Bill Miller")),
    ("PZENA",                ("Pzena Investment Mgmt",        "deep-value")),
    ("HOTCHKIS",             ("Hotchkis & Wiley",            "value")),
    ("ARIEL INVESTMENTS",    ("Ariel Investments",           "value")),
    ("YACKTMAN",             ("Yacktman Asset Mgmt",          "value")),
    ("OAKTREE",              ("Oaktree Capital",             "credit-Marks")),
    ("FARALLON",             ("Farallon Capital",            "event-driven")),
    ("GOTHAM ASSET",         ("Gotham Asset Mgmt",            "value-Greenblatt")),
    ("ABRAMS CAPITAL",       ("Abrams Capital",              "value-Abrams")),
    ("LINDSELL TRAIN",       ("Lindsell Train",              "quality")),
    ("PAULSON",              ("Paulson & Co",                "event-driven")),
    ("TONTINE",              ("Tontine Associates",          "value-Kass")),
    ("SEMPER AUGUSTUS",      ("Semper Augustus",             "value")),
    ("GREENHAVEN",           ("Greenhaven Associates",       "value")),
    ("MAR VISTA",            ("Mar Vista Investment",        "quality")),
    ("WOODLINE",             ("Woodline Partners",           "l/s")),
    ("PENTWATER",            ("Pentwater Capital",           "event-driven")),
    ("SENATOR INVESTMENT",   ("Senator Investment",          "event-driven")),
    ("CANYON CAPITAL",       ("Canyon Capital",              "credit")),
    ("KING STREET",          ("King Street Capital",         "credit")),
    ("SILVER POINT",         ("Silver Point Capital",        "credit")),
    ("PELHAM",               ("Pelham Capital",              "l/s")),
    ("GARDNER RUSSO",        ("Gardner Russo & Quinn",       "value")),
    ("FIRST EAGLE",          ("First Eagle Investment",      "value")),
    ("DODGE & COX",          ("Dodge & Cox",                 "value")),
    ("SELECT EQUITY",        ("Select Equity Group",         "quality")),
    ("CANTILLON",            ("Cantillon Capital",           "quality")),
    ("KENSICO",              ("Kensico Capital",             "l/s")),
    ("STEADFAST",            ("Steadfast Capital",           "l/s")),
    ("SOROBAN",              ("Soroban Capital",             "l/s")),
    ("SLATE PATH",           ("Slate Path Capital",          "l/s")),
    ("MELVIN",               ("Melvin Capital",              "l/s")),
    ("PABRAI",               ("Pabrai (Dalal Street)",       "value-Pabrai")),
    ("DALAL STREET",         ("Pabrai (Dalal Street)",       "value-Pabrai")),
    ("SCION ASSET",          ("Scion Asset Mgmt",            "deep-value-Burry")),
    ("SEQUOIA FUND",         ("Sequoia Fund",                "quality")),
    ("CHILTON",              ("Chilton Investment",          "l/s")),
    ("STOCKBRIDGE",          ("Stockbridge Partners",        "l/s")),
    ("MOORE CAPITAL",        ("Moore Capital",               "macro-Bacon")),
    ("HAYMAN",               ("Hayman Capital",              "macro-Bass")),
    ("KENNEDY CAPITAL",      ("Kennedy Capital",             "smid-value")),
    ("DIAMOND HILL",         ("Diamond Hill Capital",        "value")),
    ("ARISTOTLE CAPITAL",    ("Aristotle Capital",           "quality")),
    ("WCM INVESTMENT",       ("WCM Investment Mgmt",          "quality-growth")),
    ("BAILLIE GIFFORD",      ("Baillie Gifford",             "growth")),
    ("HELIKON",              ("Helikon Investments",         "l/s")),
    ("EMINENCE",             ("Eminence Capital",            "l/s-Sandler")),
    ("STONEPINE",            ("Stonepine Capital",           "l/s")),
    ("TOURBILLON",           ("Tourbillon Capital",          "l/s")),
    ("PAR CAPITAL",          ("PAR Capital",                 "l/s")),

    # ===================== BATCH 2 (+~100 more concentrated funds) =====================
    # --- biotech / healthcare specialists ---
    ("BAKER BROS",           ("Baker Bros. Advisors",        "biotech")),
    ("PERCEPTIVE ADVISORS",  ("Perceptive Advisors",         "biotech")),
    ("RA CAPITAL",           ("RA Capital",                  "biotech")),
    ("REDMILE",              ("Redmile Group",               "healthcare")),
    ("DEEP TRACK",           ("Deep Track Capital",          "biotech")),
    ("ECOR1",                ("EcoR1 Capital",               "biotech")),
    ("ROCK SPRINGS",         ("Rock Springs Capital",        "healthcare")),
    ("CASDIN",               ("Casdin Capital",              "biotech")),
    ("FORESITE",             ("Foresite Capital",            "biotech")),
    ("AVORO",                ("Avoro Capital",               "biotech")),
    ("VENBIO",               ("venBio",                      "biotech")),
    ("BVF",                  ("BVF Partners",                "biotech")),
    ("CORMORANT",            ("Cormorant Asset Mgmt",        "biotech")),
    ("BOXER CAPITAL",        ("Boxer Capital",               "biotech")),
    ("SUVRETTA",             ("Suvretta Capital",            "healthcare-l/s")),
    ("CADIAN CAPITAL",       ("Cadian Capital",              "tech-health-l/s")),
    ("PARADIGM BIOCAPITAL",  ("Paradigm BioCapital",         "biotech")),
    ("LOGOS GLOBAL",         ("Logos Global Management",     "biotech")),
    # --- growth / tiger cubs / tech L-S ---
    ("DURABLE CAPITAL",      ("Durable Capital",             "growth-Ellenbogen")),
    ("HOLOCENE",             ("Holocene Advisers",           "l/s")),
    ("ALPHA WAVE",           ("Alpha Wave Global",           "growth")),
    ("SYLEBRA",              ("Sylebra Capital",             "tech")),
    ("TEKNE",                ("Tekne Capital",               "tech")),
    ("WOODSON",              ("Woodson Capital",             "tech-consumer")),
    ("CONTOUR ASSET",        ("Contour Asset Mgmt",          "tech")),
    ("ALKEON",               ("Alkeon Capital",              "growth")),
    ("SCOPIA",               ("Scopia Capital",              "l/s")),
    ("SENVEST",              ("Senvest Management",          "l/s")),
    ("GILDER GAGNON",        ("Gilder Gagnon Howe",          "growth")),
    ("SCULPTOR",             ("Sculptor Capital",            "multi-strat")),
    ("ATHANOR",              ("Athanor Capital",             "l/s")),
    ("LUXOR CAPITAL",        ("Luxor Capital",               "l/s")),
    # --- value / quality ---
    ("FIRST PACIFIC ADVISORS",("First Pacific Advisors (FPA)","value")),
    ("THIRD AVENUE",         ("Third Avenue Mgmt",           "deep-value")),
    ("WEITZ INVESTMENT",     ("Weitz Investment",            "value")),
    ("HARDING LOEVNER",      ("Harding Loevner",             "quality")),
    ("BRAVE WARRIOR",        ("Brave Warrior (Greenberg)",   "value")),
    ("MARSHFIELD",           ("Marshfield Associates",       "quality")),
    ("ENSEMBLE CAPITAL",     ("Ensemble Capital",            "quality")),
    ("MAIRS",                ("Mairs & Power",               "value")),
    ("NUANCE INVESTMENTS",   ("Nuance Investments",          "value")),
    ("VULCAN VALUE",         ("Vulcan Value Partners",       "value")),
    ("LONGVIEW PARTNERS",    ("Longview Partners",           "quality")),
    ("TORRAY",               ("Torray LLC",                  "value")),
    ("ALTA FOX",             ("Alta Fox Capital",            "smid-value")),
    ("VOSS CAPITAL",         ("Voss Capital",                "smid-value")),
    ("PRAETORIAN",           ("Praetorian Capital",          "macro-value")),
    ("GATOR CAPITAL",        ("Gator Capital",               "financials")),
    ("BOYAR",                ("Boyar Asset Mgmt",            "value")),
    ("PALM VALLEY",          ("Palm Valley Capital",         "value")),
    ("MARSHALL WACE",        ("SKIP",                        "skip")),
    ("VULCAN INC",           ("SKIP",                        "skip")),
    # --- activist / event-driven ---
    ("POLITAN CAPITAL",      ("Politan Capital",             "activist-Koffey")),
    ("ANCORA",               ("Ancora Advisors",            "activist")),
    ("ENGINE CAPITAL",       ("Engine Capital",              "activist")),
    ("ENGAGED CAPITAL",      ("Engaged Capital",             "activist")),
    ("BARINGTON",            ("Barington Capital",           "activist")),
    ("LEGION PARTNERS",      ("Legion Partners",             "activist")),
    ("IMPACTIVE",            ("Impactive Capital",           "activist")),
    ("INCLUSIVE CAPITAL",    ("Inclusive Capital (Ubben)",   "activist")),
    ("IRENIC",               ("Irenic Capital",              "activist")),
    ("MANTLE RIDGE",         ("Mantle Ridge",                "activist")),
    ("BROWNING WEST",        ("Browning West",               "activist")),
    ("CANNELL",              ("Cannell Capital",             "activist")),
    ("LAND & BUILDINGS",     ("Land & Buildings",            "reit-activist")),
    # --- macro / global-macro ---
    ("TUDOR INVESTMENT",     ("Tudor Investment",            "macro-Jones")),
    ("CAXTON",               ("Caxton Associates",           "macro")),
    ("DISCOVERY CAPITAL",    ("Discovery Capital",           "macro-Citrone")),
    ("ELEMENT CAPITAL",      ("Element Capital",             "macro")),
    ("ROKOS",                ("Rokos Capital",               "macro")),
    ("BREVAN HOWARD",        ("Brevan Howard",               "macro")),
    # --- family offices / insurance float / permanent capital ---
    ("MSD CAPITAL",          ("MSD Capital (Dell)",          "family-office")),
    ("MSD PARTNERS",         ("MSD Partners (Dell)",         "family-office")),
    ("WILLETT ADVISORS",     ("Willett Advisors (Bloomberg)","family-office")),
    ("EMERSON COLLECTIVE",   ("Emerson Collective (Jobs)",   "family-office")),
    ("ICONIQ",               ("Iconiq Capital",              "family-office")),
    ("CASCADE INVESTMENT",   ("Cascade (Gates)",             "family-office")),
    ("WILLOUGHBY",           ("Willoughby Capital",          "family-office")),
    ("FAIRFAX FINANCIAL",    ("Fairfax Financial (Watsa)",   "insurance-value")),
    ("WHITE MOUNTAINS",      ("White Mountains",             "insurance")),
    ("LOEWS",                ("Loews Corp",                  "insurance")),
    ("MARKEL GROUP",         ("Markel Group",                "insurance")),
    # --- sector specialists ---
    ("KIMMERIDGE",           ("Kimmeridge Energy",           "energy-activist")),
    ("ENCOMPASS CAPITAL",    ("Encompass Capital",           "energy-l/s")),
    ("ZIMMER PARTNERS",      ("Zimmer Partners",             "utilities")),
    ("ELECTRON CAPITAL",     ("Electron Capital",            "utilities-infra")),
    ("SRB CORP",             ("SRB Corp",                    "value")),
    ("SELECT EQUITY GROUP",  ("Select Equity Group",         "quality")),
    ("FINDLAY PARK",         ("Findlay Park",                "quality")),
    ("COOPER INVESTORS",     ("Cooper Investors",            "value")),
    ("SENATOR",              ("Senator Investment",          "event-driven")),
    ("MERIAN",               ("SKIP",                        "skip")),
]


def raw(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    b = gzip.decompress(b)
                time.sleep(0.12)
                return b
        except Exception:
            time.sleep(0.6 * (attempt + 1))
    return None


def load_roster():
    seen = {}
    for q in INDEX_QUARTERS:
        b = raw(f"https://www.sec.gov/Archives/edgar/full-index/{q}/company.idx")
        if not b:
            print(f"  (could not load {q} index)"); continue
        for line in b.decode("latin-1").splitlines():
            if "13F-HR" not in line:
                continue
            name = line[:62].strip()
            rest = line[62:].split()
            if len(rest) < 3 or not rest[0].startswith("13F-HR"):
                continue
            try:
                cik = int(rest[1])
            except ValueError:
                continue
            seen.setdefault(cik, name)
    return seen


def latest_13fhr(cik):
    d = raw(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json")
    if not d:
        return None, 0
    try:
        rec = json.loads(d)["filings"]["recent"]
    except Exception:
        return None, 0
    periods = [rd for fm, rd in zip(rec["form"], rec["reportDate"]) if fm in ("13F-HR", "13F-HR/A")]
    if not periods:
        return None, 0
    return max(periods), len(periods)


def main():
    write = "--write" in sys.argv
    print("Loading SEC 13F-HR roster from full-index ...")
    roster = load_roster()
    print(f"  roster: {len(roster)} unique 13F-HR filers\n")
    name_items = [(n.upper(), c) for c, n in roster.items()]

    resolved, misses, seen_cik, seen_name = [], [], set(), set()
    print(f"{'MANAGER':<30} {'CIK':<12} {'LATEST':<11} FILER NAME")
    print("-" * 100)
    for token, (display, tag) in CANDIDATES:
        if display == "SKIP" or display in seen_name:
            continue
        cands = {c: roster[c] for up, c in name_items if token in up}
        if not cands:
            misses.append((display, "no 13F-HR filer name matched token"))
            continue
        best = None
        for c in cands:
            lp, n = latest_13fhr(c)
            if lp and (best is None or lp > best[1]):
                best = (c, lp, n, cands[c])
        if not best:
            misses.append((display, "matched filer(s) but none file 13F-HR"))
            continue
        cik, lp, n, filer = best
        if lp < STALE_BEFORE:
            misses.append((display, f"latest 13F-HR {lp} is stale"))
            continue
        if cik in seen_cik:
            continue
        seen_cik.add(cik); seen_name.add(display)
        resolved.append({"cik": f"{cik:010d}", "name": display, "tag": tag, "latest": lp})
        print(f"{display:<30} {cik:<12} {lp:<11} {filer[:46]}")

    print(f"\nResolved {len(resolved)} managers.  Misses ({len(misses)}):")
    for name, why in misses:
        print(f"   - {name:<30} {why}")

    if write:
        out = {
            "_comment": "Personal 13F idea engine — ~100 concentrated active managers. CIKs verified as current 13F-HR filers.",
            "_generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
            "user_agent": UA,
            "managers": sorted(resolved, key=lambda m: m["name"]),
            "_dropped": [{"name": n, "reason": w} for n, w in misses],
        }
        (ROOT / "managers.json").write_text(json.dumps(out, indent=2))
        print(f"\nWrote managers.json — {len(resolved)} managers")
    else:
        print("\n(dry run — pass --write to update managers.json)")


if __name__ == "__main__":
    main()
