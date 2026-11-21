#!/usr/bin/env python3
"""Scan GitHub for open, unassigned bounty issues and write BOUNTIES.md + digest.md.

Env:
  GITHUB_TOKEN  (provided automatically in GitHub Actions)
  MAX_RESULTS   (optional, default 40)
  LANGS         (optional, comma list, e.g. "python,typescript"; default = any)
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
MAX_RESULTS = int(os.environ.get("MAX_RESULTS", "40"))
LANGS = [l.strip() for l in os.environ.get("LANGS", "").split(",") if l.strip()]
SINCE = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")

# Each query = a different way projects mark bounties.
BASE = f"is:issue is:open no:assignee archived:false updated:>{SINCE}"
QUERIES = [
    f'{BASE} label:bounty',
    f'{BASE} label:"💎 Bounty"',
    f'{BASE} label:"bounty:" ',
    f'{BASE} label:algora',
    f'{BASE} "/bounty" in:comments',
    f'{BASE} label:bounty label:"good first issue"',
]
if LANGS:
    QUERIES = [f"{q} language:{l}" for q in QUERIES for l in LANGS]

AMOUNT_RE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)")


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
        {"q": q.strip(), "sort": "updated", "order": "desc", "per_page": 50})
    try:
        return api(url).get("items", [])
    except Exception as e:  # keep going if one query fails / is rate limited
        print(f"query failed: {q!r}: {e}", file=sys.stderr)
        return []


def amount_of(item):
    text = " ".join([item["title"]] + [l["name"] for l in item.get("labels", [])]
                    + [(item.get("body") or "")[:1500]])
    vals = [float(m.replace(",", "")) for m in AMOUNT_RE.findall(text)]
    return max(vals) if vals else 0.0


def score(item, amt):
    updated = datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00"))
    age_days = (datetime.now(timezone.utc) - updated).days
    s = min(amt, 2000) / 20            # money matters, capped
    s += max(0, 30 - age_days)          # fresher is better
    s -= item["comments"] * 3           # many comments = crowded
    return s


def main():
    seen, rows = set(), []
    for q in QUERIES:
        for it in search(q):
            if it["html_url"] in seen:
                continue
            seen.add(it["html_url"])
            amt = amount_of(it)
            repo = it["repository_url"].split("repos/")[1]
            rows.append({
                "repo": repo, "title": it["title"], "url": it["html_url"],
                "amount": amt, "comments": it["comments"],
                "updated": it["updated_at"][:10], "score": score(it, amt),
                "labels": ", ".join(l["name"] for l in it.get("labels", []))[:60],
            })
        time.sleep(2.5)  # be gentle with the search API

    rows.sort(key=lambda r: r["score"], reverse=True)
    rows = rows[:MAX_RESULTS]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [f"# Bounty feed\n", f"_Updated {now} — {len(rows)} open, unassigned issues._\n",
             "| # | Amount | Repo | Issue | Comments | Updated |",
             "|---|--------|------|-------|----------|---------|"]
    for i, r in enumerate(rows, 1):
        amt = f"${r['amount']:,.0f}" if r["amount"] else "?"
        title = r["title"].replace("|", "\\|")[:80]
        lines.append(f"| {i} | {amt} | {r['repo']} | [{title}]({r['url']}) | "
                     f"{r['comments']} | {r['updated']} |")
    lines.append("\n> Always verify the bounty is real (see GUIDE.md → 'Spot fake bounties') "
                 "before spending time.")
    with open("BOUNTIES.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    top = rows[:10]
    digest = [f"Top {len(top)} picks as of {now}. Full list: BOUNTIES.md\n"]
    for r in top:
        amt = f"${r['amount']:,.0f}" if r["amount"] else "amount unknown"
        digest.append(f"- **{amt}** — {r['repo']} — {r['url']} ({r['comments']} comments)")
    with open("digest.md", "w", encoding="utf-8") as f:
        f.write("\n".join(digest) + "\n")
    print(f"wrote {len(rows)} rows")


if __name__ == "__main__":
    main()
