# Data Retention & Privacy Policy for Exported Files

This document covers how exported data and analytics outputs must be handled once they leave the API or the management commands.

---

## What data is exported

### Order export (`GET /api/v1/exports/orders/`)

| Column | PII? | Notes |
|--------|------|-------|
| `order_number` | No | Internal identifier |
| `status` | No | |
| `total_price` | No | |
| `user_email` | **Yes** | Directly identifies the customer |
| `shipping_address` | **Yes** | Physical location |
| `billing_address` | **Yes** | Physical location |
| `created_at` | No | |

### Customer export (`GET /api/v1/exports/customers/`)

| Column | PII? | Notes |
|--------|------|-------|
| `email` | **Yes** | |
| `first_name` | **Yes** | |
| `last_name` | **Yes** | |
| `order_count` | No | Aggregate |
| `total_spend` | No | Aggregate |

### Analytics outputs (management commands / stat endpoints)

Stats and analytics outputs are aggregated — they contain **no PII** (no email, name, or address). They may be stored or shared freely within the organisation.

---

## Who can produce exports

All export and stats endpoints are restricted to **admin users** (`IsAdminUser`), enforced at the API level. Management commands require server access, which is itself restricted to the operations team.

There is no self-serve export path for regular users.

---

## Retention limits for downloaded files

| File type | Maximum retention | Rationale |
|-----------|-------------------|-----------|
| Order CSV (contains PII) | **90 days** | Minimise exposure window |
| Customer CSV (contains PII) | **90 days** | Minimise exposure window |
| Analytics CSV (no PII) | No hard limit | Aggregated data carries no personal risk |

Files must be deleted at or before the retention limit. If a longer retention period is operationally required, the file must be anonymised first (see below).

---

## Storage requirements for PII exports

- Store on **encrypted volumes** only (at rest encryption required).
- Do not commit export files to version control.
- Do not attach export files to email or messaging tools without password protection.
- Access must be limited to the individuals who requested the export.
- The `/tmp` path used in command examples is suitable for short-lived on-server processing only — move or delete the file immediately after use.

---

## Anonymisation

To retain an export beyond 90 days, remove or hash the PII columns before archiving:

**Columns to remove or hash**

- `user_email` → replace with a SHA-256 hash of the email (one-way, not reversible)
- `first_name`, `last_name` → remove entirely
- `shipping_address`, `billing_address` → remove entirely or reduce to city/country

A hashed email allows cross-referencing records within the same dataset without re-identifying the customer.

---

## Right to erasure (GDPR Article 17)

If a customer requests deletion of their personal data:

1. Delete or anonymise the `User` record in the database (`email`, `first_name`, `last_name`, `address`).
2. Locate and delete or anonymise any downloaded CSV files that contain that customer's email address.
3. Log the erasure request and the actions taken, including file locations checked.

There is currently no automated erasure pipeline. This is a manual process performed by an admin.

---

## Audit trail

- Every export request is authenticated and logged by Django's request cycle.
- The admin JWT required to call export endpoints provides an audit trail of who made the request and when.
- If detailed audit logging is required, consider adding middleware that records export endpoint calls to a dedicated audit log table.

---

## Summary checklist for admins

- [ ] Downloaded PII export files are stored on encrypted volumes.
- [ ] Files are deleted within 90 days of creation.
- [ ] Files are not shared via unencrypted channels.
- [ ] Erasure requests trigger a check of all stored export files.
- [ ] Analytics-only outputs (no PII) are labelled clearly to avoid confusion with raw exports.
