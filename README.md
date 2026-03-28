# Shoplane API

Production-ready e-commerce backend built with Django REST Framework, PostgreSQL, and Docker Compose.

---

## Stack

| Layer | Technology |
|---|---|
| Framework | Django 6 + Django REST Framework 3 |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Auth | JWT (SimpleJWT) with refresh rotation and blacklist |
| Docs | drf-spectacular (OpenAPI / Swagger) |
| Observability | Structured JSON logs, Sentry |
| CI | GitHub Actions |
| Container | Docker Compose |

---

## Architecture

```
shoplane-api/
├── shoplane/               # Main Django application
│   ├── models/             # Domain models (User, Product, Cart, Order, Payment)
│   ├── api/                # Serializers, filters, pagination, responses, throttles
│   ├── management/         # Analytics CLI commands
│   ├── migrations/         # Database migrations
│   └── tests/              # Full test suite (333 tests, 98% coverage)
├── shoplane_api/
│   └── settings/           # Base + dev / staging / prod overrides
├── docs/                   # Architecture, deployment, runbooks
├── .github/workflows/      # CI pipeline
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

### Data flow

```
Client → JWT Auth → DRF View → ORM (select_for_update on stock) → PostgreSQL
                                   ↓
                              Redis cache (product listings, categories)
                                   ↓
                            Structured JSON logs → stdout → log aggregator
                                   ↓ (on error)
                                 Sentry
```

---

## Local setup

### With Docker Compose (recommended)

```bash
git clone https://github.com/your-org/shoplane-api.git
cd shoplane-api

cp .env.example .env         # fill in DJANGO_SECRET_KEY at minimum

docker compose up --build    # starts db, redis, runs migrations, starts web
```

The API is available at `http://localhost:8000/api/v1/`.

### Without Docker

```bash
cp .env.example .env

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start Postgres and Redis (or use docker compose up db redis -d)
python manage.py migrate
python manage.py runserver
```

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DJANGO_ENV` | Yes | `dev` | `dev`, `staging`, or `prod` |
| `DJANGO_SECRET_KEY` | Yes | — | Unique secret per environment |
| `DJANGO_ALLOWED_HOSTS` | Prod | `localhost` | Comma-separated hostnames |
| `POSTGRES_DB` | Yes | `shoplane` | Database name |
| `POSTGRES_USER` | Yes | `shoplane_user` | Database user |
| `POSTGRES_PASSWORD` | Yes | — | Database password |
| `POSTGRES_HOST` | Yes | `localhost` | `db` inside Docker |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Redis connection URL |
| `CORS_ALLOWED_ORIGINS` | Prod | localhost ports | Comma-separated frontend origins |
| `LOG_LEVEL` | No | `INFO` | App log level |
| `DB_LOG_LEVEL` | No | `WARNING` | SQL log level (`DEBUG` to see all queries) |
| `SENTRY_DSN` | No | `` | Leave empty to disable Sentry |
| `SENTRY_TRACES_SAMPLE_RATE` | No | `0.1` | Fraction of requests traced |

See `.env.example`, `.env.staging.example`, `.env.prod.example` for full references.

---

## API endpoints

All endpoints are prefixed with `/api/v1/`. Authentication uses `Authorization: Bearer <access_token>`.

### Auth

| Method | Endpoint | Access | Description |
|---|---|---|---|
| POST | `/auth/register/` | Public | Create a user account |
| POST | `/auth/login/` | Public | Obtain access + refresh tokens |
| POST | `/auth/refresh/` | Public | Rotate refresh token |
| POST | `/auth/verify/` | Public | Verify an access token |
| POST | `/auth/logout/` | Auth | Blacklist the refresh token |

### Catalogue

| Method | Endpoint | Access | Description |
|---|---|---|---|
| GET | `/categories/` | Public | List categories |
| POST | `/categories/` | Admin | Create category |
| GET/PATCH/DELETE | `/categories/<slug>/` | Public/Admin | Retrieve or manage a category |
| GET | `/products/` | Public | List products (filter, search, paginate) |
| POST | `/products/` | Admin | Create product |
| GET/PATCH/DELETE | `/products/<slug>/` | Public/Admin | Retrieve or manage a product |

### Cart

| Method | Endpoint | Access | Description |
|---|---|---|---|
| GET/DELETE | `/cart/` | Auth | Get or clear the current user's cart |
| POST | `/cart/items/` | Auth | Add a product to the cart |
| PATCH/DELETE | `/cart/items/<slug>/` | Auth | Update quantity or remove an item |

### Orders

| Method | Endpoint | Access | Description |
|---|---|---|---|
| GET/POST | `/orders/` | Auth | List own orders or create from cart |
| GET/PATCH | `/orders/<order_number>/` | Auth | Retrieve or cancel an order |

### Payments

| Method | Endpoint | Access | Description |
|---|---|---|---|
| GET/POST | `/orders/<order_number>/payment/` | Auth | Retrieve or initiate payment |
| GET | `/orders/<order_number>/payment/logs/` | Admin | Payment event log |

### Analytics & exports (admin only)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/stats/top-products/` | Top-selling products |
| GET | `/stats/sales/` | Sales by day/week/month |
| GET | `/stats/average-cart/` | Average cart value |
| GET | `/stats/orders-per-customer/` | Orders per customer |
| GET | `/stats/customer-recurrence/` | Customer recurrence rate |
| GET | `/exports/orders/` | Orders CSV export |
| GET | `/exports/customers/` | Customers CSV export |

### Other

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health/` | Health check |
| GET | `/api/schema/swagger-ui/` | Interactive API docs |
| GET | `/api/schema/` | Raw OpenAPI schema |

---

## Testing

```bash
# Run the full test suite
pytest -q

# Run with coverage report
pytest --cov=shoplane --cov-report=term-missing -q

# Run a specific file
pytest shoplane/tests/test_order_api.py -v
```

**333 tests, 98% coverage.** The CI pipeline enforces a minimum of 75%.

Coverage highlights:
- Domain rules: cart totals, stock constraints, order status transitions
- Ownership: users can only access their own cart, orders, payments
- Security: JWT flow, token expiry, blacklist, role escalation blocked
- Concurrency: `select_for_update` prevents stock oversell under load
- DB constraints: `stock >= 0`, `quantity >= 1` enforced at database level
- Response envelope: all 400/401/403/404 errors use the standard format

---

## Analytics CLI

Management commands mirror the API stats endpoints and support DB or CSV sources:

```bash
# Top products from the database, output as a table
python manage.py analytics_top_products

# Sales report from a CSV file, output as CSV
python manage.py analytics_sales --source csv --file sales.csv --output csv

# Average cart for a date range
python manage.py analytics_average_cart --from 2026-01-01 --to 2026-03-31

# All commands support: --source (db|csv) --file --output (table|csv|json) --from --to
```

See [docs/analytics.md](docs/analytics.md) for full documentation.

---

## Documentation

| Document | Description |
|---|---|
| [docs/deployment.md](docs/deployment.md) | Local setup, Docker, env vars, migration guide, production checklist |
| [docs/analytics.md](docs/analytics.md) | Analytics API endpoints and CLI commands |
| [docs/migration-hardening.md](docs/migration-hardening.md) | Zero-downtime migration patterns, RLS assessment |
| [docs/data-retention-policy.md](docs/data-retention-policy.md) | PII, data retention, GDPR procedures |
| [docs/api-versioning-policy.md](docs/api-versioning-policy.md) | API versioning and deprecation policy |
| [docs/schema.md](docs/schema.md) | ER diagram and data model |
| [docs/runbooks/](docs/runbooks/) | Operational runbooks for common incidents |
