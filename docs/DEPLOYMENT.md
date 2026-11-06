# Deployment (public demo)

> These steps were written but **not executed** (no public server or Docker was available while developing). Test them early.

The Docker image serves the API **and** the built React app on one port, so one web service + one database is enough.

## Option 1 – Render.com (free tier available)
1. Push the repository to GitHub (see GITHUB_SETUP.md).
2. Render → **New → PostgreSQL** (free). Copy the *Internal Database URL*.
   Change its start from `postgres://` to `postgresql+psycopg://`.
3. Render → **New → Web Service** → connect the repo → Runtime **Docker** (uses the root `Dockerfile`).
4. Environment variables:
   * `SECRET_KEY` – a long random value
   * `DATABASE_URL` – the URL from step 2 (with `postgresql+psycopg://`)
   * `CORS_ORIGINS` – your service URL, e.g. `https://brandguard-ai.onrender.com`
5. Deploy. The container runs migrations, loads the demo data once, and starts the server.
6. Open the URL; log in with the demo accounts. **Before real use delete the demo accounts.**

Note: uploads are stored on the container disk; free tiers reset it on restart. Good enough for a demo.

## Option 2 – any VPS with Docker
```bash
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
docker compose up --build -d
```
Put a reverse proxy with HTTPS (Caddy or Nginx + Let's Encrypt) in front of port 8000.

## Checklist before showing it publicly
* HTTPS enabled · strong `SECRET_KEY` · demo passwords changed or accounts removed
* `LLM_API_KEY` (if used) set only as an environment variable
* Back up the PostgreSQL database
