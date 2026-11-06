# Test results

Everything below was **actually run** during development (Python 3.12, PostgreSQL 16, Node 22, Tesseract 5.3, Linux).
Re-run them yourself with the commands in README.md.

## 1. Automated backend tests (`pytest`)
**35 tests, 35 passed** – on SQLite *and* on PostgreSQL 16 (same 35, no skips).

| File | Tests | What it covers |
|---|:-:|---|
| `test_compliance_engine.py` | 17 | demo scenario (terminology, price, claim, prohibited phrase); every finding cites a stored rule; price formats (₹999 / Rs. 999/month / INR 999 monthly); approved claims allowed; prohibited phrase allowed when approved as a claim; case/whitespace-insensitive matching; unverifiable claims labelled for human verification; no stored guideline → nothing invented; tone checks; missing required wording; expired facts; custom regex facts; invalid regex handled; long sentences and missing alt text; capitalisation; deterministic output |
| `test_workflow.py` | 13 | the full workflow (admin adds rule → creator analyses → suggestions accepted/edited/rejected → revised preview → apply → re-analyse → submit → locked → reviewer requests changes → creator revises → reviewer approves → dashboard, history, analytics, audit); rejection needs a reason; **RBAC** (no token, bad token, creator/reviewer cannot manage rules/users, only creators upload/analyse/submit, admin and creator cannot approve, creators cannot see others' content); registration rules (always Creator, duplicate e-mail, weak password); deactivated user loses access; rule CRUD and validation; inactive rules ignored; clean content has no issues; **uploads** (TXT, DOCX, PDF, unsupported type, fake PDF, empty file, oversize file, path-traversal file name, blank text); DOCX alt-text detection; **image OCR upload** (real Tesseract); image without text gives a clear error |
| `test_llm.py` | 5 | AI layer off without a key; AI findings discarded unless they cite a real rule and quote real text; JSON parsing; mocked provider success; provider failure never breaks the rule-based result |

## 2. Live end-to-end smoke test (`scripts/live_smoke_test.py`)
Run against a **running Uvicorn server and a real PostgreSQL database** over HTTP with the seeded demo accounts:
**18 of 18 checks passed**, including: demo content produced **10 issues** (critical prohibited guarantee; wrong product name,
price, launch year and trial length; unsupported "No. 1" claim; missing terms notice; tone issues); applying the accepted
suggestions reduced them to **2**; submit → reviewer approval → dashboard and audit history updated; admin approval attempt refused (403).

## 3. Database
`alembic upgrade head` applied cleanly on PostgreSQL 16 (13 tables). Seed script runs and can be reset.

## 4. Frontend
`npm run build` (Vite) compiles all 13 screens without errors. The built app is served correctly by FastAPI
(root and client-side routes return the app; Swagger lists 35 API paths).

## 5. NOT tested (be honest with judges)
* **The React screens were not opened in a browser by the developer** (no browser was available in the build environment).
  They compile and talk to a tested API, but layout and click-through should be checked on first run.
* The optional AI layer was never run against a real AI provider (mocked only).
* Docker images/compose and public deployment were not run.
* Windows-specific commands were written from the standard procedure but not executed on Windows.
* No load, penetration or accessibility-audit testing.
