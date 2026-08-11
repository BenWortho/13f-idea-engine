# 13F Idea Engine — Project Status & Handoff

**A complete record of what this project is, everything done to it, every decision
made, and everything still planned.** Read this first if you're picking the project
back up.

- **Last updated:** 2026-08-11
- **Local path:** `~/13f-idea-engine`
- **Current GitHub repo:** `github.com/BenWortho/13f-idea-engine` (public) — ✅ *transferred from `benwortho1` on 2026-07-30*
- **Live site:** https://benwortho.github.io/13f-idea-engine/
- **Full backup:** `~/13f-idea-engine-backup.bundle` (single-file clone incl. history)

---

## Table of contents
1. [What it is](#1-what-it-is)
2. [Status at a glance](#2-status-at-a-glance)
3. [How it works (architecture)](#3-how-it-works-architecture)
4. [What we changed this session](#4-what-we-changed-this-session)
5. [Decisions made (with rationale)](#5-decisions-made-with-rationale)
6. [File-by-file reference](#6-file-by-file-reference)
7. [Git history](#7-git-history)
8. [Technical details & gotchas](#8-technical-details--gotchas)
9. [What's planned / pending](#9-whats-planned--pending)
10. [How to operate it going forward](#10-how-to-operate-it-going-forward)
11. [Methodology & limitations](#11-methodology--limitations)
12. [Recovery](#12-recovery)

---

## 1. What it is

A **self-updating stock-idea generator** built from SEC **13F-HR** filings of ~270
concentrated, active managers ("superinvestors" + focused value/growth/activist
shops, quant/market-maker shops deliberately excluded).

Each quarter it:
- pulls every tracked fund's holdings,
- **diffs** consecutive quarters,
- surfaces **ideas** = a name a fund *newly bought* or *added ≥25% shares*,
- ranks them by **consensus** (how many tracked funds did the same),
- estimates a **cost basis** and **return since**, and an analyst **price target**,
- tags each name with the **inaam impact framework** (7 classes A–G across 5 pillars).

The whole thing bakes down to a **single self-contained `index.html`** (data inlined,
no server, no network needed to view) that **rebuilds itself every weekday** via
GitHub Actions and deploys to GitHub Pages.

> **It's an idea generator, not investment advice.** 13F is long-only, US-listed,
> and lags up to 45 days. There is no trade price in a 13F — cost basis is an
> approximation.

---

## 2. Status at a glance

| Area | State |
|---|---|
| Data pipeline (SEC → diff → price → score → render) | ✅ Working |
| Self-update automation (GitHub Actions, weekday cron) | ✅ Working, verified live |
| Live site on GitHub Pages | ✅ Live (HTTP 200) on `BenWortho` |
| Price refresh (was frozen) | ✅ **Fixed** — prices advanced Jul 20 → Jul 23 → Jul 27 unattended |
| Default landing quarter (was near-empty) | ✅ **Fixed** — lands on newest *mature* quarter |
| Personal email removed from code | ✅ Done (SEC contact now configurable) — **pushed to the public repo 2026-07-30** |
| Backup + migration runbook | ✅ Done (`bundle` + `MIGRATION.md`) |
| **Move to your own GitHub account** | ✅ **Done** — transferred to `BenWortho`, Pages carried over |
| Delete old `benwortho1` copy | ✅ N/A — a transfer *moves* the repo; no duplicate left behind |
| **Analyst targets (Target/upside column)** | ⚠️ **0/600 until `FINNHUB_KEY` secret is set** — deliberately deferred 2026-08-11 |
| `SEC_CONTACT` secret | ✅ Set 2026-08-11 — **currently the URL form** `inaam 13f-idea-engine https://inaam.me`, pending Ben's chosen email |
| Failure alerting | ✅ **Added 2026-08-11** — a failed run now opens/updates a GitHub issue, and a stale site says so on the page |

**First automated run result (proof it all works, on `benwortho1`):**
- Both CI jobs (`refresh`, `deploy`) succeeded.
- Auto-committed `chore: auto-refresh 2026-07-25` and deployed to Pages.
- Default period correctly = `2026-03-31` (273 funds), not the sparse in-season quarter.
- **Prices refreshed** to `2026-07-23` (fix confirmed). Q2'26 filers ticked 13 → 17.
- Targets still `0/600` (needs the Finnhub key).

### 2.1 The 12-day outage (2026-07-30 → 2026-08-11) — resolved

Worth reading before touching the pipeline, because the *cause* was trivial and the
*duration* was the real defect.

**What happened.** The two final commits of 30 Jul added a guard that refuses to start
if the SEC User-Agent carries no email or URL (`build.py:51-60`). It was correct and it
worked. But the `SEC_CONTACT` secret it demanded was never set — the repo had **no
secrets at all** — so the guard fired on every run. Eight consecutive scheduled runs
failed, each in 9–20 seconds, from 2026-07-30 through 2026-08-10.

**Why nobody noticed for 12 days.** A failed run commits nothing and deploys nothing, so
GitHub Pages carried on serving the last good build. The site returned HTTP 200, looked
completely normal, and served data frozen at `2026-07-30 09:08 AEST`. Nothing anywhere
said otherwise. This is the same silent-failure class the 30 Jul work was fixing one
layer down — the guard made *SEC 403s* loud, but left *the guard itself firing* silent.

**The fix (2026-08-11).**
1. Set the `SEC_CONTACT` secret. Both SEC hosts verified 200 with the URL form.
2. Manual run `31448081830` — `refresh` + `deploy` both green in ~10 min. Q2'26 filers
   27 → **60**, prices advanced to `2026-08-10`, commit `chore: auto-refresh 2026-08-11`.
3. **Closed the silence, two ways** — because the secret was a one-off but the blind spot
   was structural:
   - `.github/workflows/update.yml` gained an `alert` job (`if: failure()`) that opens a
     GitHub issue, or comments on the existing open one so a long outage is one thread.
   - `render.py` gained `showStaleness()` — the page itself warns, in red, when the build
     date is more than `STALE_AFTER_DAYS = 4` days old. Verified against the real outage:
     the 30 Jul build trips it at 11 days; today's build stays silent; an unparseable
     timestamp fails closed to hidden.

**The lesson to keep:** for a scheduled job whose output is a *published artifact*, the
failure is invisible by construction. Success must be asserted, not assumed.

---

## 3. How it works (architecture)

```
scripts/discover_managers.py   resolve ~270 funds -> current 13F-HR CIKs (SEC full-index)
        │                       (writes managers.json)
        ▼
scripts/build.py               for each fund: pull last 8 quarters of 13F-HR, diff each
        │                       quarter, score ideas (consensus + conviction), map
        │                       CUSIP->ticker (OpenFIGI), price them (Yahoo history +
        │                       Finnhub current), estimate per-fund cost basis & return
        ▼
data/ideas.json                multi-quarter dataset (ideas, buyers, prices, returns, themes)
        │
scripts/targets.py             + analyst consensus price target / upside (Finnhub, best-effort)
        │
scripts/render.py              inline + minify ideas.json into a self-contained index.html
        ▼
index.html                     double-click to open, or served via GitHub Pages
```

Helper/optional:
- `scripts/prices.py` — daily-close cache (Yahoo history + Finnhub current) + analyst-target fetch. Imported by `build.py`, `targets.py`, `refine.py`.
- `scripts/refine.py` — re-score `ideas.json` in place from the cached buyers/prices, **without** re-hitting SEC. Fast methodology iteration.
- `scripts/resolve_ciks.py` — one-off helper to resolve specific impact-fund names to CIKs via EDGAR full-text search.
- `scripts/proof.py` — (pre-existing helper; not in the main path).

**Data sources**
| Source | Used for | Key? | Notes |
|---|---|---|---|
| SEC EDGAR | 13F-HR holdings + submissions index | No (needs a descriptive User-Agent) | The raw signal. Works everywhere. |
| OpenFIGI | CUSIP → ticker | No | Cached in `data/cusip_map.json`. |
| Yahoo Finance (chart v8) | **historical** daily closes (immutable) | No | 429s from home IP, but **works from GitHub Actions**. |
| Finnhub | **current** price (`/quote`) + analyst targets | **Yes** (`FINNHUB_KEY`) | Free tier, 60 req/min. |

**Caching** (why re-runs are cheap): raw holdings are cached **per accession** in
`data/holdings/` (immutable — a filing never changes), prices per symbol in
`data/prices/`, CUSIP map in `data/cusip_map.json`. Only new filings / the recent
price tail are fetched each run.

**Key parameters** (top of `build.py`):
- `N_PERIODS_FETCH = 8` — quarters of history pulled per fund (deep enough to find each fund's first-buy quarter).
- `N_TRANSITIONS = 5` — quarters exposed in the UI dropdown.
- `SIG_ADD = 0.25` — an "add" counts as an idea only if shares grew ≥25%.
- `CAP_IDEAS = 600` — per-quarter cap on the ranked idea list.
- `MATURE_FRAC = 0.5` — default view = newest quarter with ≥50% of peak coverage *(added this session)*.

---

## 4. What we changed this session

### 4.1 Diagnosis (problems found in the starting state)
- **No automation** — every refresh was a manual `python3 …`. This was the core of "make it update itself."
- **Prices were frozen (bug).** `prices.fetch()` returned the cached file forever and never re-fetched, so "current price" and every "return since" number was stuck at the date the cache was first built (Jul 20). Fatal for a self-updating engine.
- **Misleading default view.** It defaulted to the newest quarter (`2026-06-30`), but only 13 of 273 funds had filed (13F's 45-day lag), so the landing page looked nearly empty.
- **Analyst targets dead.** `data/targets/` was empty (0 files), `targets_source` was null; Yahoo's target endpoint blocks. The Target column showed `—` everywhere.
- **Fallback source gone.** Yahoo `chart` 429s from a home IP; **Stooq** (the obvious keyless fallback) is now behind a **JavaScript proof-of-work wall** — returns a challenge page, not CSV. OpenFIGI + SEC were fine.
- **Hosting.** Repo was **private** — free GitHub Pages needs a public repo (or a paid plan).
- **Data footprint.** `data/prices/` = 24 MB across **1,507 files that change every day**; `data/holdings/` = 21 MB / 2,159 files (immutable); `ideas.json` 8.4 MB + `index.html` 4.3 MB change every run.

### 4.2 Fix — price refresh (`scripts/prices.py`)
Prices now **stay current** instead of caching forever:
- History (immutable past closes) is fetched **once** per symbol via Yahoo and cached.
- The **recent tail** is refreshed every run: **Finnhub `/quote`** supplies the current close (reliable, keyed); a fresh **Yahoo** pull is the fallback.
- A **freshness gate** (`_expected_latest()` = previous UTC weekday) decides when a cached series is stale, so the tail actually advances each day.
- New helpers: `finnhub_symbol()`, `_expected_latest()`, `_yahoo_history()`, `_finnhub_quote()`; `_get_json()` gained an `attempts` arg; `fetch()` signature is now `fetch(ticker, years=3, key=None)`; `map_prices(tickers, key=None)` threads the Finnhub key (defaults to `$FINNHUB_KEY`).

### 4.3 Fix — sensible default quarter (`scripts/build.py`)
- Added `MATURE_FRAC = 0.5`. Default period is now the **newest quarter with ≥50% of peak coverage**, so the UI never lands on the near-empty in-season quarter. The sparse newest quarter is still selectable in the dropdown (labelled with its filer count).
- Passed the Finnhub key into `prices.map_prices(...)`; added `import os`.

### 4.4 De-personalization (portable to any account)
- Removed the hard-coded email `arj@inaam.me` from `scripts/prices.py`, `scripts/resolve_ciks.py`, `scripts/discover_managers.py`, and `managers.json`.
- The SEC **User-Agent** now reads `$SEC_CONTACT` → falls back to `managers.json` → then a neutral default `13f-idea-engine (+https://github.com)`. Set `SEC_CONTACT` (env or GitHub secret) to your own name/email or URL if you want a real contact string.
- Verified: no `arj@inaam.me` / `inaam.me` remains in any tracked source, all scripts still compile, and the `SEC_CONTACT` override works.

### 4.5 Automation (`.github/workflows/update.yml`) — **NEW**
- Triggers: `schedule` cron **`0 22 * * 1-5`** (weekdays 22:00 UTC ≈ 08:00 AEST, after the US close) **+** manual `workflow_dispatch`.
- Permissions: `contents: write` (commit refreshed outputs), `pages: write` + `id-token: write` (deploy).
- **Actions cache** for `data/prices` + `data/targets` (rolling key `pxcache-…` / `restore-keys: pxcache-`) so the price cache is carried between runs **without** committing 24 MB of churn daily. Cold start falls back to the seed committed in the repo.
- Steps: restore cache → `build.py` (env `FINNHUB_KEY`, `SEC_CONTACT`) → `targets.py` (`continue-on-error`) → `render.py` → **commit only** `index.html`, `data/ideas.json`, `data/holdings`, `data/cusip_map.json`, `managers.json` (never the price cache) → assemble `_site/` → `upload-pages-artifact` → separate `deploy` job (`actions/deploy-pages`).

### 4.6 Docs & hygiene
- `README.md` — overview, architecture, sources, self-update, local run, methodology. Live-URL de-hardcoded to `<your-github-username>`.
- `MIGRATION.md` — runbook to move the project to your own account (both methods).
- `.gitignore` — `.DS_Store`, `__pycache__/`, `*.pyc`, `_site/`. Stopped tracking `.DS_Store`.

### 4.7 Immediate site correctness + go-live
- Patched the committed `data/ideas.json` `default_period` → `2026-03-31` (same maturity rule) and **re-rendered** so the deployed site was correct *before* the first CI run.
- Made the repo **public**; enabled **GitHub Pages** with `build_type=workflow`.
- Committed, pushed, **triggered the first run**, and **verified** (see [§2](#2-status-at-a-glance)).
- Created the full backup bundle `~/13f-idea-engine-backup.bundle` (verified complete history).

---

## 5. Decisions made (with rationale)

| Decision | Choice | Why |
|---|---|---|
| **Hosting** | Public repo + GitHub Pages | Free, permanent live URL, zero-maintenance. Public SEC data, no secrets in the repo. |
| **Refresh cadence** | Daily on **weekdays** (22:00 UTC) | Keeps prices/returns current and picks up new 13F filers within a day during the 45-day season. Holdings are cached so runs are cheap. |
| **Analyst targets** | Wire a free **Finnhub** key | Yahoo blocks targets; Finnhub free tier (60/min) gives reliable coverage and doubles as the current-price source. |
| **Price source strategy** | Yahoo history (once) + Finnhub current (each run) | Past closes are immutable → fetch once; only the current close needs refreshing. Stooq (the keyless fallback) is now PoW-walled. |
| **Price cache in git** | **Not** committed daily; carried via Actions cache; committed seed for cold start | 1,507 files change daily — committing them would bloat the repo fast. |
| **Move to your account** | **Transfer** the existing repo (chosen) | One command from the current owner; keeps history. *(Needs your username — pending.)* |

---

## 6. File-by-file reference

**Scripts** (`scripts/`, standard library only — no `pip install`):
- `build.py` — main builder: SEC pull → diff → score → price → write `data/ideas.json`. Holds the scoring, theme/impact tagging, and the `MATURE_FRAC` default logic.
- `prices.py` — price cache (Yahoo history + Finnhub current) + analyst-target fetch; freshness gate; symbol mapping.
- `targets.py` — enriches `ideas.json` with analyst target + upside (consensus names, `n_buyers ≥ 2`). Re-runnable/best-effort.
- `render.py` — inlines `ideas.json` into the self-contained `index.html`. Contains the full HTML/CSS/JS template.
- `refine.py` — re-score in place from cached data (no SEC refetch).
- `discover_managers.py` — resolve the manager roster to current 13F-HR CIKs; `--write` rewrites `managers.json`.
- `resolve_ciks.py` — one-off EDGAR full-text resolver for specific impact-fund names.
- `proof.py` — pre-existing helper.

**Config / data:**
- `managers.json` — the roster (**274 managers**), `user_agent`, `_dropped` list. Source of truth for `build.py`.
- `data/ideas.json` — generated dataset (committed; the render input).
- `data/holdings/` — per-accession raw holdings cache (immutable; committed).
- `data/prices/` — per-symbol daily-close cache (**not** committed daily; Actions cache; seeded in repo).
- `data/targets/` — analyst-target cache (same handling as prices).
- `data/cusip_map.json` — CUSIP→ticker cache (committed).
- `index.html` — the deployable, self-contained app (committed; served by Pages).

**Meta:**
- `.github/workflows/update.yml` — the self-update pipeline.
- `README.md`, `MIGRATION.md`, `PROJECT_STATUS.md` (this file), `.gitignore`.

> ⚠️ **`managers.json` vs `discover_managers.py`:** the live `managers.json` has **274**
> managers (many tagged `data-selected`), which is a *broader* set than the ~120 curated
> `CANDIDATES` hard-coded in `discover_managers.py`. Running `discover_managers.py --write`
> would **overwrite** `managers.json` with only the curated set — don't run it casually or
> you'll shrink the roster. Update the roster deliberately.

---

## 7. Git history

`main` on `BenWortho/13f-idea-engine`, local and remote in sync as of 2026-07-30:
```
0955430  Add PROJECT_STATUS.md — full handoff: everything done + everything planned
d39e68d  Add MIGRATION.md — runbook to move the project to your own account
17b7388  Make it account-portable: configurable SEC contact, no personal data
71fe430  chore: auto-refresh 2026-07-29     <- CI bot
1dde3d7  chore: auto-refresh 2026-07-28     <- CI bot
78fa471  chore: auto-refresh 2026-07-27     <- CI bot
5cc0d45  chore: auto-refresh 2026-07-25     <- CI bot
b2983ae  Make the engine self-updating: CI, live prices/targets, sane default
9e8b414  initial commit
```
*(The three doc/portability commits were rebased on top of the bot's data commits — the
SHAs changed from the pre-rebase `10e1558` / `de41ba0` / `c9da2d1`. Clean rebase: the bot
only ever touches `data/ideas.json`, `data/holdings/`, `index.html`, which those three
commits don't. Expect that to keep being true, so `git pull --rebase` is always the right
reconcile — never force-push, you'd drop the bot's cached holdings.)*

---

## 8. Technical details & gotchas

- **Yahoo 429 locally, fine on Actions.** The `chart` API rate-limits home IPs but
  worked cleanly from GitHub's runners (1,135 tickers in a ~10-min run). So prices
  refresh even *without* Finnhub — the key is only strictly required for **targets**.
- **Stooq is dead as a fallback** — it now serves a JavaScript proof-of-work challenge
  instead of CSV. Don't rely on it.
- **Finnhub free tier** = 60 req/min. `/quote` (current price) and `/stock/price-target`
  are usable; the code throttles (`~1.1s`/call) and stops early on long empty streaks.
- **Freshness gate:** `_expected_latest()` = the previous UTC weekday. A cached series
  whose newest date is older than that is refreshed. Errs toward refreshing (harmless).
- **Symbol mapping differs by source:** Yahoo uses `-` for share classes (`BRK.B`→`BRK-B`,
  also filesystem-safe); Finnhub uses `.` (`BRK.B`). Handled by `yahoo_symbol()` /
  `finnhub_symbol()`.
- **SEC User-Agent** is required (they rate-limit anonymous/abusive traffic). Now driven
  by `$SEC_CONTACT`.
- **`utcnow`/`utcfromtimestamp` deprecation** warnings under Python 3.12 are harmless
  (kept for style consistency; they don't fail the build).
- **Scoring:** `conviction = n_buyers*14 + min(30, sum_weight*200) + (10 if any NEW) `,
  capped at 100; label High ≥55 / Medium ≥30 / Low. Consensus names (`n_buyers>1`) rank
  above singles. `putCall` positions are skipped; long US-listed only.
- **inaam impact classes** (keyword-based, best-effort, a name can map to several):
  A Charging · B Generating (Energy) · C Feeding (Agriculture) · D Building · E Driving
  (Consumption) · F Sustaining (Waste) · G Protecting (Health).

---

## 9. What's planned / pending

### 9.1 Move the repo to your own account — ✅ **DONE (2026-07-30, transfer to `BenWortho`)**
Repo now lives at `github.com/BenWortho/13f-idea-engine`; live site
**https://benwortho.github.io/13f-idea-engine/** (verified 200).

What actually happened, and the gotchas worth remembering:
- Transfer initiated with `gh api --method POST repos/benwortho1/13f-idea-engine/transfer -f new_owner=BenWortho`.
  The API responded with the repo *still* under `benwortho1`, and `repos/BenWortho/…` 404'd
  for a few minutes — **that response is not a failure**, the transfer is just eventually
  consistent. It completed on its own; no email/notification acceptance step was needed
  (both accounts are the same person's).
- **Pages carried over** (`has_pages=true`, `build_type=workflow` intact), contrary to the
  original assumption that it wouldn't. No need to re-create it.
- **Secrets did NOT carry over** — the secret list is empty. See [§9.2](#92-set-the-finnhub_key-secret--enables-analyst-targets).
- **`gh auth switch` does not change what `git push` uses.** This Mac's git credential
  helper is `osxkeychain`, which kept serving `BenWortho`'s token and gave
  `403 Permission to benwortho1/… denied to BenWortho`. Fix: bypass the keychain for the
  one command — `git -c credential.helper='!gh auth git-credential' push origin main`
  while the intended account is `gh auth switch`ed active.
- Old URL `benwortho1.github.io/13f-idea-engine/` now 404s, as expected. A transfer *moves*
  the repo, so there is no old copy to delete.

*(The alternative "fresh repo" method is still documented in `MIGRATION.md`; it's the one
to use if you ever want `arj@inaam.me` scrubbed from the older commits' **history** — the
transfer keeps it there, only the current tip is clean.)*

### 9.2 Set the `FINNHUB_KEY` secret — **enables analyst targets**
Targets are `0/600` in **every** quarter until this is set (verified again 2026-07-30 —
`targets_source` reads `yahoo`, but actual coverage is zero because Yahoo's target endpoint
blocks). Get a free key at **finnhub.io** (30s, no card), then:
```bash
gh secret set FINNHUB_KEY --repo BenWortho/13f-idea-engine
```
Prices already work without it; this fills the **Target / upside** column and makes the
current-price leg more robust. **This is the last outstanding item on the project.**

### 9.3 Housekeeping after the move
- ✅ `README.md` live-URL line updated to `benwortho.github.io`.
- ✅ No old copy to delete (transfer moves the repo; `benwortho1/…` no longer exists).
- ⏳ (Optional) set `SEC_CONTACT` secret to a real contact string — right now the SEC
  User-Agent falls back to the neutral `13f-idea-engine (+https://github.com)` default.

### 9.4 `[FINDING]` The inaam class tagger covers 8% of the list

Measured 2026-08-11 on the Q2'26 quarter: **49 of 600 ideas carry any inaam class.** The
entire consensus top of the quarter — KLAC, BKNG, NVDA, AMD, MU, TSM — is untagged; `GEV`
(Class B) is the only classed name in the top 8.

The cause is structural, not a missing keyword. `inaam_for()` (`build.py:215`) matches
substrings against **issuer name + ticker**, and a 13F gives you nothing else — no SIC
code, no industry, no description. "KLA CORP" contains no word that any sector keyword
could match. The current keyword lists are therefore mostly *enumerated company names*,
so coverage only ever extends to names somebody thought to add by hand.

**Do not simply expand the keyword lists to raise the number.** Two reasons:
- Per `SECTOR-DESKS-PLAN-v2.md:309`, Pillar 2 is **"not mechanically screenable"** — the
  B/C label is a judgement on core business activity across five dimensions. A keyword
  hit is not that, and a fuller-looking column would imply a methodology judgement the
  code has not made, against a **PDS-disclosed** framework.
- The honest framing is that A–G here is a *sort aid over 13F names*, not a Class
  assignment. Raising coverage without raising rigour widens the gap between what it
  looks like and what it is.

**The defensible upgrade, if wanted:** map ticker → CIK via SEC's free `company_tickers.json`,
then read the **SIC code** from `data.sec.gov/submissions/CIK…json`. That is a sourced fact
rather than a guess, keyless, and already within the pipeline's existing SEC budget. It
gives real industry routing ("this is in electrical equipment — look at it for Class A")
while leaving the Class judgement to a human. **Not built** — it is a genuine scope
decision, not an obvious win.

### 9.5 Do not build a Pillar 1 screen here — `inaam-impact-scorecard` already is one

The obvious next step is to filter the 600 ideas down to names that could clear the
3-pillar gate, so the output is *ownable candidates* rather than *what other funds bought*.
**Do not build that screen in this repo.**

`~/inaam-impact-scorecard` (`github.com/BenWortho/inaam-impact-scorecard`, private) already
implements all five Pillar 1 tests in `src/impact_scorecard/scoring.py`, read off the
workbook's own benchmark column C16:C20:

```python
MARKET_CAP_MIN_M = 500.0          # C16 ">500"
EBITDA_MIN_M     = 100.0          # C17 ">100"
TRAILING_PE_RANGE = (10.0, 20.0)  # C18 "10 - 20"
NPM_RANGE         = (0.05, 0.10)  # C20 "5-10"
                                  # C19 "Positive" dividend yield
```

`SECTOR-DESKS-PLAN-v2.md:316` flags Pillar 1 as "defined two incompatible ways" — the PDS
version (revenue ≥$500m · publicly listed) against the playbook version (P/E 10–20 ·
positive dividend). That is true of the *documents*, but it is already settled **in code,
for the playbook version**, under Ben's standing ruling on that repo: *"you are not to
change the scoring system — how it works is how you will make it."* The correct integration
is therefore **this engine emits tickers → the scorecard scores them**. A second
implementation here would diverge from the one that is load-bearing.

⚠️ **Expect the gate to reject nearly the entire 13F list, and do not treat that as a bug
in either repo.** The scorecard's own run across 28 companies: **trailing P/E 10–20 passes
2/28; NPM 5–10% passes 3/28; no company reaches a full Pillar 1.** This engine's output is
dominated by US large-cap growth — KLAC, BKNG, NVDA, AMD, MU, TSM lead Q2'26 on consensus —
which fails P/E and dividend by construction. That collision is the unresolved
"stated benchmarks vs the workbook's typed cells" question recorded against the scorecard,
and it is **Ben's to settle**, not something to work around by loosening thresholds here.

**Still genuinely unresolved:** the PDS lists **NYSE · LSE · HKSE · TSE · ASX**, but the
book already trades Paris, Copenhagen, Amsterdam and Toronto. That defines the searchable
universe and nobody has ruled on it.

### 9.6 Nice-to-haves (not started — future ideas)
- Hide the Target column automatically when no targets are present (until the key is set).
- Add a second price fallback now that Stooq is walled (e.g. Tiingo/Alpha Vantage with a key).
- Bound the Finnhub price loop (currently refreshes all idea tickers each run).
- Trim `data/ideas.json` from the committed set if repo size becomes a concern (the site is self-contained in `index.html`).
- Reconcile `discover_managers.py`'s curated `CANDIDATES` with the broader 274-name `managers.json` so roster refreshes don't shrink it.

---

## 10. How to operate it going forward

**Run locally** (standard library only):
```bash
python3 scripts/build.py         # pull + diff + price + score  -> data/ideas.json
python3 scripts/targets.py       # (optional) analyst targets
python3 scripts/render.py        # bake ideas.json -> index.html
open index.html                  # (macOS) view it

# with reliable prices/targets:
FINNHUB_KEY=xxxx SEC_CONTACT="Your Name your@email" python3 scripts/build.py

# fast methodology iteration (no SEC refetch):
python3 scripts/refine.py

# refresh the roster (CAUTION: overwrites managers.json with the curated set):
python3 scripts/discover_managers.py            # dry run
python3 scripts/discover_managers.py --write    # rewrite managers.json
```

**Automated:** runs itself every weekday 22:00 UTC. Trigger on demand from the repo's
**Actions** tab → *Refresh 13F Idea Engine* → *Run workflow*, or
`gh workflow run update.yml --repo <YOUR_USERNAME>/13f-idea-engine`.

**Secrets** (repo → Settings → Secrets and variables → Actions):
- `FINNHUB_KEY` (required for targets), `SEC_CONTACT` (optional).

---

## 11. Methodology & limitations

- **Idea** = a fund newly opened a position, or grew an existing one by ≥25% shares.
- **Consensus** = number of distinct tracked funds that did so this quarter.
- **Conviction** blends consensus, position weight, and whether it's a fresh buy.
- **Est. buy** = average daily close over the quarter a fund *first opened* the position
  (13F has no trade date/price — "≥" flags positions opened before our data window).
  **Return** is to the latest close.
- **AUM** = the fund's US-listed 13F book value (excludes cash, bonds, shorts, non-US).
- **Excluded:** pure quant/market-maker shops (Citadel, Renaissance, Millennium…) — their
  thousand-name books drown the signal.
- **Caveats:** long-only, US-listed; 13F lags up to 45 days; cost basis is an approximation;
  analyst targets are best-effort. **Idea generator, not investment advice.**

---

## 12. Recovery

Full single-file backup (complete history) at `~/13f-idea-engine-backup.bundle`:
```bash
git clone ~/13f-idea-engine-backup.bundle 13f-idea-engine-restored
```
Regenerate the bundle any time:
```bash
git bundle create ~/13f-idea-engine-backup.bundle --all
```
