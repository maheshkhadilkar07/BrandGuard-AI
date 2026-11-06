# Preparing the GitHub repository

1. Create an empty repository on GitHub (no README, no .gitignore).
2. In PowerShell, inside `brandguard-ai`:
```powershell
git init
git add .
git status          # check that .env and node_modules are NOT listed (they are in .gitignore)
git commit -m "BrandGuard AI: working MVP"
git branch -M main
git remote add origin https://github.com/<your-account>/brandguard-ai.git
git push -u origin main
```
3. Never commit `backend/.env` or any API key. If a secret was committed by mistake, change it immediately.
4. Useful extras: add the repository link to the submission form, add screenshots to `docs/`, and tag the release
   (`git tag round2-mvp && git push --tags`).
