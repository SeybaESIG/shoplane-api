# Deployment Guide

---

## Local development

```bash
# 1. Clone and enter the project
git clone https://github.com/your-org/shoplane-api.git
cd shoplane-api

# 2. Create your local env file
cp .env.example .env
# Edit .env and fill in DJANGO_SECRET_KEY and database credentials

# 3. Start the database and Redis
docker compose up db redis -d

# 4. Create a virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 5. Run migrations
python manage.py migrate

# 6. Start the dev server
python manage.py runserver
```

The API is available at `http://localhost:8000/api/v1/`.
OpenAPI docs: `http://localhost:8000/api/schema/swagger-ui/`

---

## Running with Docker Compose

```bash
# Start all services (runs migrations automatically before web starts)
docker compose up --build

# Start with Stripe CLI webhook forwarder (requires STRIPE_SECRET_KEY in .env)
docker compose --profile stripe up --build
```

Services:
| Service | Description |
|---|---|
| `db` | PostgreSQL 16 |
| `redis` | Redis 7 |
| `migrate` | Runs `manage.py migrate` once, then exits |
| `web` | Django dev server on port 8000 |
| `stripe-cli` | Stripe webhook forwarder (profile: `stripe`) |

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DJANGO_ENV` | Yes | `dev`, `staging`, or `prod` |
| `DJANGO_SECRET_KEY` | Yes | Django secret key — must be unique per environment |
| `DJANGO_ALLOWED_HOSTS` | Yes (prod) | Comma-separated list of allowed hostnames |
| `POSTGRES_DB` | Yes | Database name |
| `POSTGRES_USER` | Yes | Database user |
| `POSTGRES_PASSWORD` | Yes | Database password |
| `POSTGRES_HOST` | Yes | Database host (`db` inside Docker) |
| `POSTGRES_PORT` | No | Database port (default: 5432) |
| `CORS_ALLOWED_ORIGINS` | Yes (prod) | Comma-separated list of allowed frontend origins |
| `REDIS_URL` | Yes | Redis connection URL |
| `LOG_LEVEL` | No | Log level for app and Django (default: `INFO`) |
| `DB_LOG_LEVEL` | No | Log level for SQL queries (default: `WARNING`) |
| `SENTRY_DSN` | No | Sentry DSN — leave empty to disable error tracking |
| `SENTRY_ENVIRONMENT` | No | Sentry environment tag (defaults to `DJANGO_ENV`) |
| `SENTRY_TRACES_SAMPLE_RATE` | No | Fraction of transactions traced (default: `0.1`) |

---

## Running migrations safely

### Standard migration (dev / staging)

```bash
python manage.py migrate
```

### Zero-downtime migration (production)

For large tables, follow the patterns in [migration-hardening.md](./migration-hardening.md):

```bash
# 1. Apply the migration (non-blocking constraints use NOT VALID)
python manage.py migrate

# 2. For indexes added with CONCURRENTLY, the migration must have atomic = False
# 3. Validate any NOT VALID constraints during a low-traffic window
```

### Rolling back a migration

```bash
# Roll back to a specific migration
python manage.py migrate shoplane 0002

# Then revert the code deployment
```

Always take a database snapshot before applying migrations to production.

---

## Production checklist

Before going live:

- [ ] `DJANGO_ENV=prod` is set
- [ ] `DJANGO_SECRET_KEY` is a strong, unique random value
- [ ] `DEBUG` is not set to `True` in prod settings
- [ ] `DJANGO_ALLOWED_HOSTS` lists only your production domain(s)
- [ ] `CORS_ALLOWED_ORIGINS` lists only your production frontend(s)
- [ ] Database and Redis are not exposed to the public internet
- [ ] `SENTRY_DSN` is configured for error tracking
- [ ] All migrations have been applied: `python manage.py migrate --check`
- [ ] Static files collected: `python manage.py collectstatic`
- [ ] A database backup policy is in place (see [data-retention-policy.md](./data-retention-policy.md))
- [ ] The production server runs behind a reverse proxy (nginx/caddy) with HTTPS

---

## Rolling back a deployment

1. Redeploy the previous Docker image tag
2. If the new migration is destructive, run `manage.py migrate shoplane <previous_migration>` first
3. Verify the health endpoint responds: `GET /api/v1/health/`
4. Check Sentry for any new errors after rollback
