# Bounty & open-source guide (step by step)

## 0. One-time setup

1. Install: Git, your language toolchain, and the GitHub CLI (`gh`).
2. `gh auth login` (choose GitHub.com → HTTPS → browser).
3. Set your identity:
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```
4. Create payout accounts where bounties are paid:
   - **Algora** (algora.io) — most common for GitHub `/bounty` issues; pays via Stripe
   - **IssueHunt**, **Polar**, **Gitcoin/Open Collective** — project-specific
   - A Stripe or Wise account that supports payouts to India
5. Start with small/easy ones to build a reputation. Maintainers pay people they trust.

## 1. Pick a bounty (use BOUNTIES.md)

Choose issues that are:
- Unassigned, updated recently, and few comments (low competition)
- In a language you know well
- Clearly scoped ("fix X", not "redesign Y")
- From a project with recent merged PRs (check the repo's Pull requests tab)

### Spot fake bounties (important)
- The amount must be in a **maintainer's** comment or an official bounty bot (Algora, IssueHunt) — not a random user.
- Check the project actually pays: look for *closed* bounties with a "rewarded" note.
- Never pay anything to claim a bounty. Never run code/links someone sends in comments.
- Be wary of issues whose only "bounty" is a Telegram/Discord DM offer.

## 2. Claim it politely

Read CONTRIBUTING.md first. Then comment:

> Hi! I'd like to work on this. My plan: <1–2 lines>. ETA: <X days>. Okay if I take it?

Some projects use `/attempt #<issue-number>` (Algora). Wait for a yes if the
project asks for it. Don't hoard — release it if you can't finish.

## 3. Set up the project

```bash
gh repo fork OWNER/REPO --clone
cd REPO
git remote -v                     # origin = your fork, upstream = original
git checkout -b fix/issue-123
```
Follow the README to install dependencies and **run the tests before changing
anything** so you know the baseline.

## 4. Solve it

1. Reproduce the bug / understand the feature.
2. Find the relevant code (`grep -rn "keyword" .`).
3. Make the smallest change that solves it. Match the project's style.
4. Add or update a test that fails before and passes after.
5. Run the full test suite + linter.

**Where I can help:** paste the issue link and the relevant code/error to me
in chat, and I'll walk you through the cause, suggest the fix, review your
diff, and draft the PR text. You write and submit it.

## 5. Open the pull request

```bash
git add -A
git commit -m "fix: <short description> (#123)"
git push -u origin fix/issue-123
gh pr create --fill
```
In the PR body: link `Closes #123`, explain what/why, how you tested it.
Keep it small, respond to review within a day, and be gracious about feedback.

## 6. Get paid

- Algora: once merged, the maintainer releases the bounty; complete your payout profile.
- Otherwise ask the maintainer how/when they pay (in the issue, not DMs).
- Keep records for tax purposes (India: income from this is taxable; check with an accountant).

## 7. Build a routine

- Morning: skim BOUNTIES.md, pick 1 target
- Work: 1 bounty at a time
- Also grab `good first issue` PRs in projects you like — they lead to bigger paid work.
