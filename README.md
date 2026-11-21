# bounty-hunter

A tiny GitHub Action that scans GitHub every morning for open, unassigned
bounty issues, ranks them (amount, freshness, low competition), commits the
list to `BOUNTIES.md`, and opens a digest issue so GitHub emails you.

No servers, no cost, runs while you're away.

## Setup (5 minutes)

1. Create a new **public or private** repo on GitHub named `bounty-hunter`.
2. Upload every file from this folder (keep the same folder structure), or:
   ```bash
   cd bounty-hunter
   git init && git add . && git commit -m "init"
   git branch -M main
   git remote add origin https://github.com/<your-username>/bounty-hunter.git
   git push -u origin main
   ```
3. In the repo: **Settings → Actions → General → Workflow permissions →
   "Read and write permissions"** → Save.
4. Go to the **Actions** tab → "Scan for bounties" → **Run workflow**.
5. After ~1 minute open `BOUNTIES.md`. It then refreshes daily at 08:00 IST.
6. Turn on email notifications: **GitHub → Settings → Notifications**.

## Tuning

- Filter languages: uncomment `LANGS` in `.github/workflows/scan.yml`
  (e.g. `"python,typescript"`).
- Change schedule: edit the `cron` line.
- Add more bounty labels/queries: edit `QUERIES` in `scanner/scan.py`.

Read `GUIDE.md` for how to actually pick and solve bounties.
