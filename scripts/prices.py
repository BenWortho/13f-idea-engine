#!/usr/bin/env python3
"""
13F IDEA ENGINE — daily price helper (standalone / personal).

Fetches daily closing prices from Yahoo's public chart API (no key) and caches
one file per symbol under data/prices/. Used to ESTIMATE a manager's cost basis
(average price over the quarter a position was opened) and the return since.

There is no exact trade price in a 13F — this is an approximation, labelled as
such in the UI. Standard library only.
"""

import json, os, time, urllib.request, urllib.error, urllib.parse, gzip, datetime, http.cookiejar
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRICE_DIR = ROOT / "data" / "prices"; PRICE_DIR.mkdir(parents=True, exist_ok=True)
TARGET_DIR = ROOT / "data" / "targets"; TARGET_DIR.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 13f-idea-engine personal-project arj@inaam.me"
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    b = gzip.decompress(b)
                return json.loads(b)
        except Exception:
            time.sleep(0.8 * (attempt + 1))
    return None


def yahoo_symbol(ticker):
    # Yahoo uses '-' for share classes (BRK.B / BRK/B -> BRK-B). Also keeps the
    # symbol filesystem-safe (no '/'). Strip anything that isn't A-Z/0-9/-.
    s = ticker.strip().upper()
    for ch in (".", "/", " "):
        s = s.replace(ch, "-")
    s = "".join(c for c in s if c.isalnum() or c == "-").strip("-")
    return s


def fetch(ticker, years=3):
    """Return {YYYY-MM-DD: close} for a symbol, cached to disk. {} if unavailable."""
    sym = yahoo_symbol(ticker)
    if not sym:
        return {}
    f = PRICE_DIR / f"{sym}.json"
    if f.exists():
        return json.loads(f.read_text())
    now = int(time.time())
    p1 = now - int(years * 366 * 86400)
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
           f"?period1={p1}&period2={now}&interval=1d")
    j = _get_json(url)
    out = {}
    try:
        res = j["chart"]["result"][0]
        ts = res["timestamp"]
        cl = res["indicators"]["quote"][0]["close"]
        for t, c in zip(ts, cl):
            if c is None:
                continue
            d = datetime.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")
            out[d] = round(float(c), 4)
    except Exception:
        out = {}
    f.write_text(json.dumps(out))
    time.sleep(0.25)   # be polite to Yahoo
    return out


def avg_close(px, start, end):
    """Mean daily close over [start, end] (inclusive, 'YYYY-MM-DD' strings)."""
    vals = [c for d, c in px.items() if start <= d <= end]
    return round(sum(vals) / len(vals), 4) if vals else None


def latest_close(px):
    """(close, date) of the most recent available day, or (None, None)."""
    if not px:
        return None, None
    d = max(px)
    return px[d], d


def quarter_start(period):
    """First calendar day of the quarter that ENDS on `period` (a quarter-end date)."""
    y, m, _ = period.split("-")
    start_month = {"03": "01", "06": "04", "09": "07", "12": "10"}.get(m, "01")
    return f"{y}-{start_month}-01"


def map_prices(tickers):
    """Fetch (cached) prices for many symbols. Returns {ticker: {date: close}}."""
    out, n = {}, len(tickers)
    for i, t in enumerate(sorted(set(t for t in tickers if t))):
        out[t] = fetch(t)
        if (i + 1) % 100 == 0:
            print(f"    prices {i+1}/{n} ...")
    return out


# ---------------------------------------------------------------- analyst price targets
# 13F has no forward view; these come from Yahoo's authenticated quoteSummary endpoint
# (needs a cookie+crumb, rate-limits hard) or, if FINNHUB_KEY is set, Finnhub (reliable).
_YS = {"opener": None, "crumb": None}

def _yahoo_session():
    if _YS["opener"] is None:
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        crumb = None
        try:
            op.open(urllib.request.Request("https://finance.yahoo.com/quote/AAPL",
                                           headers={"User-Agent": BROWSER_UA}), timeout=20).read()
            c = op.open(urllib.request.Request("https://query2.finance.yahoo.com/v1/test/getcrumb",
                                               headers={"User-Agent": BROWSER_UA}), timeout=20).read().decode().strip()
            crumb = c if c and "<" not in c and len(c) < 40 else None
        except Exception:
            crumb = None
        _YS["opener"], _YS["crumb"] = op, crumb
    return _YS["opener"], _YS["crumb"]


def _raw_field(fd, key):
    v = fd.get(key)
    return v.get("raw") if isinstance(v, dict) else v


def _yahoo_target(sym):
    op, crumb = _yahoo_session()
    if not crumb:
        return {}
    url = (f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}"
           f"?modules=financialData&crumb={urllib.parse.quote(crumb)}")
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA, "Accept-Encoding": "gzip"})
            with op.open(req, timeout=20) as r:
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    b = gzip.decompress(b)
            fd = json.loads(b)["quoteSummary"]["result"][0]["financialData"]
            mean = _raw_field(fd, "targetMeanPrice")
            time.sleep(0.5)
            if mean is None:
                return {}
            return {"mean": mean, "high": _raw_field(fd, "targetHighPrice"),
                    "low": _raw_field(fd, "targetLowPrice"),
                    "n": _raw_field(fd, "numberOfAnalystOpinions"), "source": "yahoo"}
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                _YS["crumb"] = None       # crumb expired; drop it
                return {}
            if e.code == 429:
                time.sleep(3.0 * (attempt + 1)); continue
            return {}
        except Exception:
            return {}
    return {}


def _finnhub_target(sym, key):
    try:
        j = _get_json(f"https://finnhub.io/api/v1/stock/price-target?symbol={sym}&token={key}")
        mean = (j or {}).get("targetMean") or (j or {}).get("targetMedian")
        time.sleep(1.1)   # free tier: 60/min
        if not mean:
            return {}
        return {"mean": mean, "high": j.get("targetHigh"), "low": j.get("targetLow"),
                "n": None, "source": "finnhub"}
    except Exception:
        return {}


def fetch_target(ticker):
    """Analyst consensus target for a symbol, cached. {} if unavailable (not cached, so re-runs retry)."""
    sym = yahoo_symbol(ticker)
    if not sym:
        return {}
    f = TARGET_DIR / f"{sym}.json"
    if f.exists():
        return json.loads(f.read_text())
    key = os.environ.get("FINNHUB_KEY")
    out = _finnhub_target(sym, key) if key else {}
    if not out:
        out = _yahoo_target(sym)
    if out:
        f.write_text(json.dumps(out))
    return out


def map_targets(tickers):
    """Best-effort analyst targets for many symbols. Stops early if the source is clearly
    blocking (long empty streak) — a re-run fills the gaps once the cache warms / limit cools."""
    out, n, streak = {}, len(tickers), 0
    for i, t in enumerate(sorted(set(t for t in tickers if t))):
        r = fetch_target(t)
        out[t] = r
        streak = 0 if r else streak + 1
        if (i + 1) % 100 == 0:
            print(f"    targets {i+1}/{n} (empty streak {streak}) ...")
        if streak >= 50:
            print(f"    targets: {streak} consecutive misses — source is rate-limiting; stopping. Re-run to fill.")
            break
    return out


if __name__ == "__main__":
    import sys
    for t in sys.argv[1:] or ["AAPL", "BRK.B", "NVDA"]:
        px = fetch(t)
        c, d = latest_close(px)
        qs = quarter_start("2026-03-31")
        print(f"{t:<8} days={len(px):<5} latest {d} ${c}  |  Q1'26 avg ${avg_close(px, qs, '2026-03-31')}")
