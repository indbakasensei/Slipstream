# Pushing Slipstream to GitHub (Windows / PowerShell)

> **Historical record.** This documents the *original* v0.8.0 first push to
> GitHub. The repository already exists and has an established history and
> remote — the "Create the empty repository" / `git init` steps below no
> longer apply for ongoing work. See "Everyday updates" at the bottom for
> the actual day-to-day workflow, or `docs/RELEASE_CHECKLIST.md` for
> release tagging.

## One-time prerequisites
1. Install Git: https://git-scm.com/download/win  (defaults are fine).
   Verify in a new PowerShell:  `git --version`
2. Tell git who you are (once per machine):
   ```powershell
   git config --global user.name  "Tejas"
   git config --global user.email "your-github-email@example.com"
   ```
3. Create the empty repository on GitHub: github.com → **New repository** →
   name `slipstream` → **Public** → do NOT add a README/license (we have them)
   → Create.

## First push
```powershell
cd C:\Users\tejas\Desktop\CFD_Auto\slipstream

git init -b main
git add .
git status              # sanity: runs/, venv/ must NOT appear (gitignored)
git commit -m "Slipstream v0.8.0 — desktop GUI foundation over cfdauto engine"

git remote add origin https://github.com/<YOUR-USERNAME>/slipstream.git
git push -u origin main
```
On the first push a browser window signs you into GitHub (Git Credential
Manager). That's it — the included GitHub Actions workflow will run the whole
test suite (engine + offscreen GUI) on Ubuntu and Windows automatically; look
for the green check under the *Actions* tab.

## Tag the release
```powershell
git tag -a v0.8.0 -m "v0.8.0 — GUI foundation"
git push origin v0.8.0
```

## Everyday updates
```powershell
git add -A
git commit -m "what changed"
git push
```

## Notes
- `runs/` (meshes, transcripts, logs) is gitignored on purpose — artifacts are
  data, not code. `experiments.xlsx` and `config/config.yaml` ARE committed by
  default so the project is reproducible; uncomment the lines at the bottom of
  `.gitignore` if you'd rather keep your study data private.
- Prefer a GUI? **GitHub Desktop** (free) does the same: File → Add local
  repository → Publish.
