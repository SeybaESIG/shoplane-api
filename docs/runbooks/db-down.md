# Runbook: Database Down

## Symptoms

- API returns `500` on all endpoints that query the database
- Health endpoint (`GET /api/v1/health/`) returns a non-200 response or times out
- Logs contain: `django.db.utils.OperationalError: connection failed` or `could not connect to server`
- Sentry receives `OperationalError` events in bulk

## Immediate actions

### 1. Confirm the database is unreachable

```bash
# Inside the web container
docker compose exec web python -c "
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'shoplane_api.settings'
django.setup()
from django.db import connection
connection.ensure_connection()
print('connected')
"

# Or directly against Postgres
docker compose exec db pg_isready -U $POSTGRES_USER -d $POSTGRES_DB
```

### 2. Check container health

```bash
docker compose ps          # look for db status
docker compose logs db --tail 50
```

### 3. Restart the database container

```bash
docker compose restart db
# Wait for the healthcheck to pass, then verify
docker compose ps db
```

### 4. If the container is healthy but connections are exhausted

PostgreSQL has a `max_connections` limit. Check active connections:

```sql
SELECT count(*) FROM pg_stat_activity WHERE datname = 'shoplane_db';
```

If connections are at the limit, restart the web service to reset its connection pool:

```bash
docker compose restart web
```

## Restoring from backup

If the database volume is corrupt or data is lost:

```bash
# Stop the web service to prevent writes during restore
docker compose stop web

# Drop and recreate the database
docker compose exec db psql -U $POSTGRES_USER -c "DROP DATABASE shoplane_db;"
docker compose exec db psql -U $POSTGRES_USER -c "CREATE DATABASE shoplane_db;"

# Restore from backup file
cat backup.sql | docker compose exec -T db psql -U $POSTGRES_USER -d shoplane_db

# Re-run migrations to ensure schema is current
docker compose run --rm migrate

# Restart web
docker compose start web
```

## After recovery

- Verify the health endpoint responds: `GET /api/v1/health/`
- Check Sentry to confirm no new `OperationalError` events are arriving
- Review logs for any orders or payments that may have been affected during the outage window
- If any payments were in a `PENDING` state during the outage, verify their status manually against the payment provider dashboard
