# Migration Hardening Guide

Zero- and low-downtime migration patterns for Shoplane's PostgreSQL database.

---

## General principles

- Every migration runs inside a transaction by default in PostgreSQL.  
  Full-table locks are held for the duration. For large tables, break large
  operations into smaller, non-locking alternatives.
- Test every migration on a production-sized data copy before applying it.
- Use `--fake` only to mark already-applied manual changes — never to skip
  a real migration.

---

## Safe patterns

### Adding a nullable column

Adding a nullable column is instantaneous in PostgreSQL 11+. No rewrite occurs.

```sql
ALTER TABLE shoplane_product ADD COLUMN notes TEXT;
```

Django equivalent: `field = models.TextField(null=True, blank=True)`.

### Adding a non-nullable column with a default

PostgreSQL 11+ stores the default in the catalog; existing rows are not
rewritten immediately.

```python
# models.py
stock_reserved = models.PositiveIntegerField(default=0)
```

For older PostgreSQL versions, split into three migrations:
1. Add as nullable, no default.
2. Backfill existing rows in batches.
3. Add NOT NULL constraint and set the application default.

### Renaming a column

Never rename in a single step across a deployment boundary.

1. Add the new column alongside the old one.
2. Write to both columns during the transition window.
3. Backfill the new column from the old one.
4. Switch reads to the new column.
5. Drop the old column in a follow-up deployment.

### Creating an index

Plain `CREATE INDEX` takes a full `SHARE` lock and blocks writes.
Always use `CONCURRENTLY` in production.

```sql
CREATE INDEX CONCURRENTLY product_category_id_idx
    ON shoplane_product (category_id);
```

Django migration equivalent:

```python
from django.db import migrations, models

class Migration(migrations.Migration):
    atomic = False  # required for CONCURRENTLY

    operations = [
        migrations.AddIndex(
            model_name="product",
            index=models.Index(
                fields=["category_id"],
                name="product_category_id_idx",
            ),
            concurrently=True,
        ),
    ]
```

### Adding a CHECK constraint without a full-table scan

Use `NOT VALID` to add the constraint without scanning existing rows, then
validate in a second step with a weaker lock.

```sql
-- Step 1: add without scanning existing rows (does not block reads/writes)
ALTER TABLE shoplane_product
    ADD CONSTRAINT product_stock_gte_0
    CHECK (stock >= 0) NOT VALID;

-- Step 2: validate existing rows (ShareUpdateExclusiveLock — allows reads/writes)
ALTER TABLE shoplane_product
    VALIDATE CONSTRAINT product_stock_gte_0;
```

> **Note**: The constraints added in migration `0003` used the standard
> Django `CheckConstraint` API, which performs a full-table scan. For the
> current dataset size this is acceptable. Apply the `NOT VALID` pattern
> when the table exceeds ~1M rows or the deployment window is tight.

---

## Dangerous operations

| Operation | Risk | Safer alternative |
|---|---|---|
| `DROP COLUMN` | Immediate data loss | Rename → stop using → drop in later release |
| `ALTER COLUMN TYPE` | Full table rewrite | Add new column, migrate, drop old |
| `ADD CONSTRAINT` (without NOT VALID) | Full table scan, `ACCESS EXCLUSIVE` lock | `NOT VALID` + `VALIDATE` in two steps |
| `CREATE INDEX` (without CONCURRENTLY) | Blocks writes for the duration | `CREATE INDEX CONCURRENTLY` |
| Truncate or bulk delete | Lock contention, autovacuum pressure | Soft-delete first; batch-delete off-peak |

---

## Row-level security (RLS) assessment

PostgreSQL's RLS allows policies to be defined directly in the database so
that every query automatically filters rows by the authenticated role.

**RLS is not implemented in Shoplane.** The reasons are:

1. **Single application role**: The Django application connects with one
   PostgreSQL role (`shoplane_user`). RLS policies enforce access per
   database role, not per application user. Supporting per-user RLS would
   require either a dedicated role per user (operationally impractical) or
   passing `app.current_user_id` as a session-level variable — adding
   complexity with marginal benefit.

2. **ORM ownership checks cover the threat model**: Every view that touches
   user-owned data (`Cart`, `Order`, `Payment`) enforces ownership in the
   queryset. Admin endpoints are gated by `IsAdminUser`. A SQL injection
   attack would be the only way to bypass ORM-level filtering, and that risk
   is already mitigated by Django's parameterised queries.

3. **Auditability**: RLS policies live outside version control. Django model
   constraints and view-layer checks are in the codebase, reviewed in PRs,
   and tested by the test suite.

Revisit RLS if the deployment architecture changes to a multi-tenant model
where different tenants share a single database and full isolation is a
compliance requirement.
