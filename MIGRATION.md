# Moving this project to your own GitHub account

Everything you need to move the 13F Idea Engine off the current account
(`benwortho1`) and onto your own. The full project already lives on this Mac at
`~/13f-idea-engine`, and there's a complete single-file backup at
`~/13f-idea-engine-backup.bundle` (a full clone incl. history).

Replace `<you>` below with your GitHub username throughout.

---

## Method A — fresh repo under your account (recommended, cleanest)

This machine's `gh` is signed in as `benwortho1`. First sign in as **you**:

```bash
gh auth login          # GitHub.com > HTTPS > your account
# already have both accounts added? just switch:
# gh auth switch --user <you>
```

Then create your repo and push everything:

```bash
cd ~/13f-idea-engine
git remote rename origin benwortho1                 # keep old remote for reference (optional)
gh repo create <you>/13f-idea-engine --public --source=. --remote=origin --push
```

Turn on the self-updating site + secrets:

```bash
# GitHub Pages, built by the workflow
gh api --method POST repos/<you>/13f-idea-engine/pages -f build_type=workflow

# analyst-target key (free from finnhub.io) — enables the Target/upside column
gh secret set FINNHUB_KEY --repo <you>/13f-idea-engine

# optional: your SEC contact string (name/email or URL) for the User-Agent
gh secret set SEC_CONTACT --repo <you>/13f-idea-engine

# run it now (otherwise it runs itself every weekday 22:00 UTC)
gh workflow run update.yml --repo <you>/13f-idea-engine
```

Your live site: **https://\<you\>.github.io/13f-idea-engine/**

---

## Method B — GitHub transfer (keeps history, stars, issues, the same repo)

Run **while signed in as `benwortho1`** (the current owner):

```bash
gh api --method POST repos/benwortho1/13f-idea-engine/transfer -f new_owner=<you>
```

Accept the transfer from `<you>`'s GitHub notifications/email if prompted. Then,
as `<you>`, re-add what doesn't transfer (secrets + Pages), and repoint your
local clone:

```bash
gh api --method POST repos/<you>/13f-idea-engine/pages -f build_type=workflow
gh secret set FINNHUB_KEY --repo <you>/13f-idea-engine
cd ~/13f-idea-engine && git remote set-url origin https://github.com/<you>/13f-idea-engine.git
```

---

## After the move

- Confirm the run is green: `gh run list --repo <you>/13f-idea-engine`
- The workflow commits refreshed `index.html` + `data/ideas.json` and deploys to
  Pages every weekday (and on demand via the Actions tab → *Refresh 13F Idea Engine*
  → *Run workflow*).
- Update the live-site URL in `README.md` to your username.

## Clean up the old copy (once yours is verified working)

```bash
gh repo delete benwortho1/13f-idea-engine --yes
```

## Disaster recovery — restore from the backup bundle

```bash
git clone ~/13f-idea-engine-backup.bundle 13f-idea-engine-restored
```
