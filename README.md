# BrandGuard AI

**An Intelligent AI-Powered Brand Governance and Content Compliance Platform**

BrandGuard AI checks whether content follows an organisation's approved brand rules **before publication**. It finds
problems, explains each one by pointing to the exact stored rule, suggests corrections, and sends the content to a
**human reviewer** for the final decision. The AI assists; it never approves content.

Team: Mahesh Khadilkar · Janhvi Wadaskar · Pranay Rajkondawar

> All company data in the demo (**TechNova Solutions**, prices, claims, documents) is **fictional demonstration data**.

---

## What works today

The complete workflow works end to end (tested): admin sets up rules → creator uploads text/TXT/PDF/DOCX/image →
automatic compliance check → issues with severity, explanation and source rule → correction suggestions
(accept / edit / reject) → submit → reviewer approves, rejects or requests changes → history and dashboards.

See **[docs/FEATURE_STATUS.md](docs/FEATURE_STATUS.md)** for an honest list of what is implemented, partial and planned,
and **[docs/TEST_RESULTS.md](docs/TEST_RESULTS.md)** for what was actually tested.

The compliance engine is **rule-based and works with no AI key and no internet**. An optional AI layer can be switched
on with an API key (see "Optional AI layer").

---

## Requirements (Windows)

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11 or newer | tick "Add Python to PATH" in the installer |
| Node.js | 20 or newer | includes npm |
| PostgreSQL | 15 or 16 | or use Docker Desktop (see below) |
| Tesseract OCR | any recent | **only for reading text from images**; installer: "UB Mannheim Tesseract". Everything else works without it |
| Git | any | for GitHub |

## Setup – step by step (PowerShell)

Open PowerShell in the project folder `brandguard-ai`.

### 1. Database

Option A – Docker Desktop (easiest):
```powershell
docker compose up -d db
```
Option B – installed PostgreSQL: open *SQL Shell (psql)* as the `postgres` user and run:
```sql
CREATE USER brandguard WITH PASSWORD 'brandguard';
CREATE DATABASE brandguard OWNER brandguard;
```

### 2. Backend
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
copy .env.example .env
```
Open `backend\.env` in VS Code and set `SECRET_KEY` to a long random value. Create one with:
```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
If Tesseract is installed but not on PATH, uncomment `TESSERACT_CMD` in `.env`.

Create the tables, load the demo data and start the API:
```powershell
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```
API documentation (Swagger): <http://localhost:8000/docs>

### 3. Frontend (a second PowerShell window)
```powershell
cd frontend
npm install
npm run dev
```
Open <http://localhost:5173>.

### One-server mode (optional)
`cd frontend; npm run build` creates `frontend/dist`. FastAPI then serves the app at <http://localhost:8000> too.

---

## Demonstration logins (fictional data)

| Role | Email | Password |
|---|---|---|
| Admin | admin@technova.demo | Admin@123 |
| Content Creator | creator@technova.demo | Creator@123 |
| Reviewer | reviewer@technova.demo | Reviewer@123 |

The login page has buttons that fill these in. **Change or delete these accounts before any real use.**
Reset demo data at any time: `python -m app.seed --reset`

## Two-minute demo for judges

1. **Admin** → *Brand Guidelines* and *Facts & Terminology*: see the TechNova rules (product name, price ₹999 per month,
   prohibited "100% guaranteed results", claim "India's No. 1 cloud platform" needing evidence).
2. **Creator** → *My Content* → open **"DEMO: TechNova Cloud launch announcement"** → **Run compliance check**.
   You see ~10 issues: wrong product name, wrong price, wrong launch year and trial length, an unsupported claim, a prohibited
   guarantee, informal tone, and missing "Terms and conditions apply". Each shows its **source rule**. The approved
   "99.9% uptime SLA" claim is correctly *not* flagged.
3. **Review suggestions** → accept, edit or reject → *Apply accepted suggestions* (the original text is kept) → run the check again.
4. **Submit for review**.
5. **Reviewer** → *Review Queue* → open the item → comment → **Approve / Request changes / Reject**.
6. **Dashboards, Analytics, Content History** (and the admin's *Users & Audit*) show the result.

Sample files for upload testing are in `docs/sample_content/` (TXT, DOCX, PDF, PNG).

## Roles and permissions

| Action | Admin | Creator | Reviewer |
|---|:-:|:-:|:-:|
| Manage rules, users, organisation | ✔ | | |
| Read rules | ✔ | ✔ | ✔ |
| Upload, analyse, edit own content, accept suggestions, submit | | ✔ | |
| See content | all | own only | all |
| Approve / reject / request changes | | | ✔ |
| Analytics | ✔ | | ✔ |
| Audit log | ✔ | | |

Self-registration always creates a **Creator**. Only the first user of an empty installation becomes Admin.
Admins create Reviewers and other Admins.

## Optional AI layer

In `backend\.env`:
```
LLM_PROVIDER=openai_compatible
LLM_API_BASE=https://api.openai.com/v1      # or any OpenAI-compatible endpoint, e.g. a local Ollama server
LLM_API_KEY=your-key
LLM_MODEL=model-name
```
AI findings must cite a stored rule and quote text that really exists, otherwise they are discarded. They are always marked
*AI-assisted* and *Requires human verification*. If the provider fails, the rule-based result is still returned.
**This layer has been tested only with a mocked provider, not a live one.**

## Tests

```powershell
cd backend
pip install -r requirements-dev.txt
pytest
```
Runs on a temporary SQLite file by default. To test on PostgreSQL use a **separate, empty** database
(the tests drop and recreate all tables in it):
```powershell
$env:TEST_DATABASE_URL="postgresql+psycopg://brandguard:brandguard@localhost:5432/brandguard_test"
pytest
```
With the server running, `python scripts/live_smoke_test.py http://localhost:8000` replays the whole demo over real HTTP.

## Project structure
```
brandguard-ai/
  backend/app/{core,models,schemas,routers,services,utils}   FastAPI application
  backend/migrations/                                        Alembic migrations
  backend/tests/  backend/scripts/                           automated tests, live smoke test
  frontend/src/{components,pages,services,context}           React application
  database/  docs/  docker-compose.yml  Dockerfile
```
More: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) · [docs/GITHUB_SETUP.md](docs/GITHUB_SETUP.md)

## Limitations (please read)

* The engine only knows what an admin has stored; it does not invent rules or facts and is **not** legal advice.
* Tone checks are simple heuristics. OCR can misread images. Logo/visual checking is **not implemented yet** (planned).
* Logout is stateless: the token is discarded by the browser and stays technically valid until it expires (default 8 h).
* No rate limiting, password reset or e-mail features yet. Use HTTPS in any real deployment.
