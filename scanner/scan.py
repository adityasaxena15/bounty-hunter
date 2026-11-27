#!/usr/bin/env python3
"""Scan GitHub for (1) beginner-friendly issues in healthy projects and
(2) bounties from repos that pass basic trust checks.

Writes BOUNTIES.md (full feed) and digest.md (short email digest).

Env:
  GITHUB_TOKEN  provided automatically in GitHub Actions
  LANGS         optional comma list, e.g. "python,typescript" (default: any)
  MAX_FIRST     max good-first-issue rows (default 25)
  MAX_BOUNTY    max bounty rows (default 20)
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

TOKEN = os.environ.get("GITHUB_TOKEN", "")
LANGS = [l.strip() for l in os.environ.get("LANGS", "").split(",") if l.strip()]
MAX_FIRST = int(os.environ.get("MAX_FIRST", "25"))
MAX_BOUNTY = int(os.environ.get("MAX_BOUNTY", "20"))

NOW = datetime.now(timezone.utc)
SINCE = (NOW - timedelta(days=45)).strftime("%Y-%m-%d")

# ---- trust rules (tweak freely) ------------------------------------------
MIN_STARS_FIRST = 100        # good-first-issue repos
MIN_STARS_BOUNTY = 30        # bounty repos
MIN_REPO_AGE_DAYS = 90       # brand-new repos are a classic scam signal
MAX_PUSH_AGE_DAYS = 30       # must be actively maintained
MAX_PLAUSIBLE_BOUNTY = 3000  # above this is flagged, not ranked high
MAX_BOUNTIES_PER_REPO_SEEN = 8   # a repo with a flood of bounties = spam
PER_REPO_CAP = 3             # max rows per repo in the output
BLOCKLIST = {r.lower() for r in os.environ.get("BLOCKLIST", "ClankerNation/OpenAgents").split(",") if r}
# --------------------------------------------------------------------------

BASE = f"is:issue is:open no:assignee archived:false updated:>{SINCE}"
FIRST_QUERIES = [
    f'{BASE} label:"good first issue" comments:<3',
    f'{BASE} label:"help wanted" label:"good first issue" comments:<3',
    f'{BASE} label:"good-first-issue" comments:<3',
]
BOUNTY_QUERIES = [
    f'{BASE} label:bounty',
    f'{BASE} label:algora',
    f'{BASE} label:"💎 Bounty"',
    f'{BASE} "/bounty" in:comments',
    f'{BASE} label:bounty-hunt',
    f'{BASE} label:reward',
    f'{BASE} label:bounty-hunter',
    f'{BASE} "bounty" in:title',
]
if LANGS:
    FIRST_QUERIES = [f"{q} language:{l}" for q in FIRST_QUERIES for l in LANGS]
    BOUNTY_QUERIES = [f"{q} language:{l}" for q in BOUNTY_QUERIES for l in LANGS]

AMOUNT_RE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)\s?(k\b)?", re.I)


def api(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "bounty-hunter",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def search(q):
    url = "https://api.github.com/search/issues?" + urllib.parse.urlencode(
        {"q": q, "sort": "updated", "order": "desc", "per_page": 50})
    try:
        items = api(url).get("items", [])
    except Exception as e:
        print(f"query failed: {q!r}: {e}", file=sys.stderr)
        items = []
    time.sleep(2.5)  # stay under the search rate limit
    return items


_repo_cache = {}


def repo_info(full):
    """Repo metadata + trust signals. Returns None if repo can't be read."""
    if full in _repo_cache:
        return _repo_cache[full]
    info = None
    try:
        r = api(f"https://api.github.com/repos/{full}")
        created = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
        pushed = datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00"))
        info = {
            "stars": r["stargazers_count"],
            "age_days": (NOW - created).days,
            "push_days": (NOW - pushed).days,
            "fork": r["fork"],
            "lang": r.get("language") or "",
            "has_contributing": False,
        }
        try:
            prof = api(f"https://api.github.com/repos/{full}/community/profile")
            info["has_contributing"] = bool((prof.get("files") or {}).get("contributing"))
        except Exception:
            pass
    except Exception as e:
        print(f"repo lookup failed {full}: {e}", file=sys.stderr)
    _repo_cache[full] = info
    return info


def healthy(info, min_stars):
    return (info and not info["fork"] and info["stars"] >= min_stars
            and info["age_days"] >= MIN_REPO_AGE_DAYS
            and info["push_days"] <= MAX_PUSH_AGE_DAYS)


def amount_of(item):
    """Prefer an amount in the title/labels (most reliable), else the body."""
    def best(text):
        vals = []
        for num, k in AMOUNT_RE.findall(text):
            v = float(num.replace(",", ""))
            vals.append(v * 1000 if k else v)
        return max(vals) if vals else 0.0
    head = best(" ".join([item["title"]] + [l["name"] for l in item.get("labels", [])]))
    return head or best((item.get("body") or "")[:1500])

def verify_bounty(item):
    """Check if bounty has funding indicators in body or comments."""
    # Check issue body
    body = (item.get("body") or "").lower()
    if any(indicator in body for indicator in ["$", "usd", "dollar", "payment", "reward", "bounty", "compensation"]):
        return True
    
    # For now, assume bounties with amounts are verified
    # In a real implementation, we could fetch comments to verify further
    return amount_of(item) > 0


def repo_of(item):
    return item["repository_url"].split("repos/")[1]


def trust_score(info):
    s = min(info["stars"], 5000) ** 0.5            # diminishing returns on stars
    s += 10 if info["has_contributing"] else 0
    s += max(0, 30 - info["push_days"]) / 3
    return s


def collect(queries):
    seen, items = set(), []
    for q in queries:
        for it in search(q):
            if it["html_url"] not in seen:
                seen.add(it["html_url"])
                items.append(it)
    return items


def cap_per_repo(rows):
    out, counts = [], {}
    for r in rows:
        counts[r["repo"]] = counts.get(r["repo"], 0) + 1
        if counts[r["repo"]] <= PER_REPO_CAP:
            out.append(r)
    return out


def first_issues():
    rows = []
    for it in collect(FIRST_QUERIES):
        repo = repo_of(it)
        if repo.lower() in BLOCKLIST:
            continue
        info = repo_info(repo)
        if not healthy(info, MIN_STARS_FIRST):
            continue
        updated = datetime.fromisoformat(it["updated_at"].replace("Z", "+00:00"))
        fresh = max(0, 30 - (NOW - updated).days)
        rows.append({
            "repo": repo, "title": it["title"], "url": it["html_url"],
            "stars": info["stars"], "lang": info["lang"],
            "contrib": "yes" if info["has_contributing"] else "-",
            "comments": it["comments"], "updated": it["updated_at"][:10],
            "score": trust_score(info) + fresh - it["comments"] * 4,
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return cap_per_repo(rows)[:MAX_FIRST]


def bounties():
    items = collect(BOUNTY_QUERIES)
    per_repo = {}
    for it in items:
        per_repo[repo_of(it)] = per_repo.get(repo_of(it), 0) + 1
    rows = []
    for it in items:
        repo = repo_of(it)
        if repo.lower() in BLOCKLIST or per_repo[repo] > MAX_BOUNTIES_PER_REPO_SEEN:
            continue  # blocklisted, or flooded with bounties (spam signal)
        info = repo_info(repo)
        if not healthy(info, MIN_STARS_BOUNTY):
            continue
        amt = amount_of(it)
        if amt > MAX_PLAUSIBLE_BOUNTY:
            continue  # implausible for small tasks: skip rather than tempt
        # Only include verified bounties
        if not verify_bounty(it):
            continue
        rows.append({
            "repo": repo, "title": it["title"], "url": it["html_url"],
            "amount": amt, "stars": info["stars"],
            "comments": it["comments"], "updated": it["updated_at"][:10],
            "verified": True,  # Add verification status
            "score": trust_score(info) + min(amt, 1500) / 30 - it["comments"] * 3,
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return cap_per_repo(rows)[:MAX_BOUNTY]


def md_escape(s, n=80):
    return s.replace("|", "\\|").replace("\n", " ")[:n]


def main():
    firsts = first_issues()
    bnts = bounties()
    now = NOW.strftime("%Y-%m-%d %H:%M UTC")

    L = ["# Bounty & contribution feed\n", f"_Updated {now}_\n",
         "## 1. Start here: good first issues (build trust first)\n",
         "Active repos, 100+ stars, no one assigned, few comments.\n",
         "| # | Repo | Issue | Stars | Lang | CONTRIBUTING | Comments | Updated |",
         "|---|------|-------|-------|------|--------------|----------|---------|"]
    for i, r in enumerate(firsts, 1):
        L.append(f"| {i} | {r['repo']} | [{md_escape(r['title'])}]({r['url']}) | "
                 f"{r['stars']:,} | {r['lang']} | {r['contrib']} | {r['comments']} | {r['updated']} |")
    if not firsts:
        L.append("| - | none found today | | | | | | |")

    L += ["\n## 2. Bounties (filtered for trust)\n",
          f"Repos with {MIN_STARS_BOUNTY}+ stars, active, older than {MIN_REPO_AGE_DAYS} days, "
          f"amounts up to ${MAX_PLAUSIBLE_BOUNTY:,}. Verified for funding indicators.\n",
          "| # | Amount | Verified | Repo | Issue | Stars | Comments | Updated |",
          "|---|--------|----------|------|-------|-------|----------|---------|"]
    for i, r in enumerate(bnts, 1):
        amt = f"${r['amount']:,.0f}" if r["amount"] else "?"
        verified = "✓" if r.get("verified", False) else "✗"
        L.append(f"| {i} | {amt} | {verified} | {r['repo']} | [{md_escape(r['title'])}]({r['url'])} | "
                 f"{r['stars']:,} | {r['comments']} | {r['updated']} |")
    if not bnts:
        L.append("| - | none passed the filters today | | | | | |")

    with open("BOUNTIES.md", "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

    D = [f"Picks as of {now}. Full list: BOUNTIES.md\n", "**Start here (good first issues)**"]
    D += [f"- {r['repo']} ({r['stars']:,}★) — {r['url']}" for r in firsts[:7]] or ["- none today"]
    D += ["\n**Bounties**"]
    D += [f"- {('$%d' % r['amount']) if r['amount'] else '?'} — {r['repo']} — {r['url']}"
          for r in bnts[:5]] or ["- none passed the filters"]
    with open("digest.md", "w", encoding="utf-8") as f:
        f.write("\n".join(D) + "\n")
    print(f"wrote {len(firsts)} first issues, {len(bnts)} bounties")


if __name__ == "__main__":
    main()
