# Shoplane API

Backend API for the Shoplane project built with Django, DRF, PostgreSQL, and Docker Compose.

## Stack

- Django 6
- Django REST Framework
- PostgreSQL 16
- Pytest + pytest-django
- Docker Compose

## Quick Start (Docker)

1. Copy env file:
   - `cp .env.example .env`
2. Build and start services:
   - `docker compose up --build -d`
3. Run migrations:
   - `docker compose exec web python manage.py migrate`
4. Check health endpoint:
   - `http://localhost:8000/api/v1/health/`

## Testing

### Run Tests

- In Docker:
  - `docker compose exec web pytest -q`
- Locally (venv):
  - `./.venv/bin/pytest -q`

### Current Coverage 

- Health/API smoke checks:
  - `/api/v1/health/` payload, unauthenticated access, method restrictions
- User model and manager behavior:
  - defaults for `create_user`/`create_superuser`
  - password hashing checks (no raw password storage)
  - email normalization behavior and duplicate email protection
- Category/Product domain rules:
  - slug auto-generation and slug uniqueness suffixing
  - non-negative constraints (price, stock)
  - FK protection when products are referenced
- Cart domain rules:
  - defaults and non-negative totals
  - `cart + product` uniqueness at item level
  - repeated add behavior increments quantity and recalculates totals
- Order/Payment domain rules:
  - order defaults, unique order number, non-negative totals
  - non-empty shipping address validation
  - payment amount and transaction reference constraints
  - delete protections and payment log defaults/ordering

## Schema

- Base UML/ER schema: `docs/schema.md`
