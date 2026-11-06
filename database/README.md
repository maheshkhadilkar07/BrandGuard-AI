# Database

* The schema is managed by **Alembic** (`backend/migrations`). Never edit tables by hand.
* Create the database and user (psql as the postgres superuser):

```sql
CREATE USER brandguard WITH PASSWORD 'brandguard';
CREATE DATABASE brandguard OWNER brandguard;
```

* Apply the schema:  `cd backend && alembic upgrade head`
* Load the fictional demonstration data:  `python -m app.seed`  (add `--reset` to rebuild it)
* Quick local PostgreSQL with Docker:  `docker compose up -d db`
