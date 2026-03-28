# Analytics Reference

Five analytics metrics are available through two interfaces: **REST API endpoints** (live queries, admin-only) and **Django management commands** (DB or CSV source, suitable for offline analysis, scripting, and scheduled jobs).

---

## REST API Endpoints

All endpoints require an admin JWT (`Authorization: Bearer <access_token>`).  
Base prefix: `/api/v1/`

### Common query parameters

| Parameter | Format | Description |
|-----------|--------|-------------|
| `from` | `YYYY-MM-DD` | Inclusive start date (applied to `created_at`) |
| `to` | `YYYY-MM-DD` | Inclusive end date |

All endpoints return the standard envelope:

```json
{
  "success": true,
  "message": "...",
  "data": { ... }
}
```

---

### GET /api/v1/stats/top-products/

Best-selling products by total quantity sold from CONFIRMED orders.

**Query parameters**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `limit` | `10` | Number of products to return (max 50) |
| `from` / `to` | — | Date range filter |

**Example request**

```
GET /api/v1/stats/top-products/?limit=5&from=2024-01-01&to=2024-03-31
```

**Example response**

```json
{
  "success": true,
  "message": "Top products retrieved successfully",
  "data": [
    { "product_slug": "wireless-headphones", "product_name": "Wireless Headphones", "total_quantity": 142 },
    { "product_slug": "usb-c-cable",         "product_name": "USB-C Cable",          "total_quantity": 98  }
  ]
}
```

---

### GET /api/v1/stats/sales/

Total sales and order count grouped by period from CONFIRMED orders.

**Query parameters**

| Parameter | Default | Values | Description |
|-----------|---------|--------|-------------|
| `period` | `day` | `day`, `week`, `month` | Grouping bucket |
| `from` / `to` | — | | Date range filter |

**Example request**

```
GET /api/v1/stats/sales/?period=month&from=2024-01-01&to=2024-06-30
```

**Example response**

```json
{
  "success": true,
  "message": "Sales stats retrieved successfully",
  "data": [
    { "period": "2024-01", "total_sales": "12450.00", "order_count": 87 },
    { "period": "2024-02", "total_sales": "9830.50",  "order_count": 64 }
  ]
}
```

---

### GET /api/v1/stats/average-cart/

Average order value for CONFIRMED orders.

Without `?period=`: returns a single overall figure.  
With `?period=`: returns one row per bucket.

**Query parameters**

| Parameter | Default | Values | Description |
|-----------|---------|--------|-------------|
| `period` | *(none)* | `day`, `week`, `month` | Optional breakdown |
| `from` / `to` | — | | Date range filter |

**Example — overall**

```
GET /api/v1/stats/average-cart/?from=2024-01-01
```

```json
{
  "success": true,
  "message": "Average cart retrieved successfully",
  "data": { "average_order_value": "143.20", "order_count": 151 }
}
```

**Example — by month**

```
GET /api/v1/stats/average-cart/?period=month&from=2024-01-01
```

```json
{
  "success": true,
  "message": "Average cart by period retrieved successfully",
  "data": [
    { "period": "2024-01", "average_order_value": "155.00", "order_count": 87 },
    { "period": "2024-02", "average_order_value": "130.40", "order_count": 64 }
  ]
}
```

---

### GET /api/v1/stats/orders-per-customer/

Distribution of how many CONFIRMED orders each customer has placed, plus the mean.

**Query parameters**: `from` / `to` only.

**Example response**

```json
{
  "success": true,
  "message": "Orders per customer retrieved successfully",
  "data": {
    "mean_orders_per_customer": 2.3,
    "total_customers": 120,
    "distribution": [
      { "order_count": 1, "customer_count": 55 },
      { "order_count": 2, "customer_count": 38 },
      { "order_count": 3, "customer_count": 27 }
    ]
  }
}
```

---

### GET /api/v1/stats/customer-recurrence/

Split between new customers (exactly 1 CONFIRMED order in the window) and returning customers (2+).

**Query parameters**: `from` / `to` only.

`recurrence_rate_pct` is `returning / total * 100`, rounded to one decimal place.  
Returns `null` when there are no customers in the window.

**Example response**

```json
{
  "success": true,
  "message": "Customer recurrence retrieved successfully",
  "data": {
    "new_customers": 55,
    "returning_customers": 65,
    "total_customers": 120,
    "recurrence_rate_pct": 54.2
  }
}
```

---

## Management Commands

Commands run inside the Django process and require no extra dependencies.

### Running in Docker

```bash
docker compose exec web python manage.py <command> [flags]
```

### Running locally (venv)

```bash
source .venv/bin/activate
python manage.py <command> [flags]
```

### Common flags (all commands)

| Flag | Default | Description |
|------|---------|-------------|
| `--source db\|csv` | `db` | `db` queries the database; `csv` reads from `--file` |
| `--file PATH` | — | Input CSV path (`--source csv`) or output CSV path (`--output csv`) |
| `--output stdout\|csv` | `stdout` | Print an aligned table or write a CSV file |
| `--from YYYY-MM-DD` | — | Inclusive start date filter |
| `--to YYYY-MM-DD` | — | Inclusive end date filter |

---

### analytics_top_products

```
python manage.py analytics_top_products [--limit N] [--source db|csv] [--file PATH]
    [--output stdout|csv] [--from DATE] [--to DATE]
```

Extra flag: `--limit N` (default 10, max 50).

**CSV input columns**: `product_slug`, `product_name`, `quantity`

**Example — DB, top 5 this quarter, output to file**

```bash
python manage.py analytics_top_products \
    --limit 5 \
    --from 2024-01-01 --to 2024-03-31 \
    --output csv --file /tmp/top_products_q1.csv
```

**Example — read from a previously exported CSV**

```bash
python manage.py analytics_top_products \
    --source csv --file order_items_export.csv \
    --limit 10
```

---

### analytics_sales

```
python manage.py analytics_sales [--period day|week|month] [--source db|csv] [--file PATH]
    [--output stdout|csv] [--from DATE] [--to DATE]
```

Extra flag: `--period day|week|month` (default `day`).

**CSV input columns**: `created_at` (`YYYY-MM-DD HH:MM:SS`), `total_price`, `status`

**Example — monthly sales for 2024**

```bash
python manage.py analytics_sales \
    --period month \
    --from 2024-01-01 --to 2024-12-31 \
    --output csv --file /tmp/sales_2024_monthly.csv
```

---

### analytics_average_cart

```
python manage.py analytics_average_cart [--period day|week|month] [--source db|csv]
    [--file PATH] [--output stdout|csv] [--from DATE] [--to DATE]
```

Extra flag: `--period` is optional; omit for a single overall figure.

**CSV input columns**: `created_at`, `total_price`, `status`

**Example — overall average for last 90 days**

```bash
python manage.py analytics_average_cart \
    --from $(date -v-90d +%Y-%m-%d)
```

**Example — weekly breakdown**

```bash
python manage.py analytics_average_cart --period week --from 2024-01-01
```

---

### analytics_orders_per_customer

```
python manage.py analytics_orders_per_customer [--source db|csv] [--file PATH]
    [--output stdout|csv] [--from DATE] [--to DATE]
```

Prints a summary row (total customers, mean) and a distribution table.  
`--output csv` writes the distribution table only.

**CSV input columns**: `user_email`, `status`

**Example**

```bash
python manage.py analytics_orders_per_customer \
    --from 2024-01-01 \
    --output csv --file /tmp/orders_per_customer.csv
```

---

### analytics_customer_recurrence

```
python manage.py analytics_customer_recurrence [--source db|csv] [--file PATH]
    [--output stdout|csv] [--from DATE] [--to DATE]
```

**CSV input columns**: `user_email`, `status`

**Example — full year**

```bash
python manage.py analytics_customer_recurrence \
    --from 2024-01-01 --to 2024-12-31 \
    --output csv --file /tmp/recurrence_2024.csv
```

---

## CSV Input Format Reference

When using `--source csv`, the command reads the file produced by the matching export endpoint. The expected columns per command are:

| Command | Required columns | Matching export |
|---------|-----------------|-----------------|
| `analytics_top_products` | `product_slug`, `product_name`, `quantity` | Order items (custom export) |
| `analytics_sales` | `created_at`, `total_price`, `status` | `GET /api/v1/exports/orders/` |
| `analytics_average_cart` | `created_at`, `total_price`, `status` | `GET /api/v1/exports/orders/` |
| `analytics_orders_per_customer` | `user_email`, `status` | `GET /api/v1/exports/orders/` |
| `analytics_customer_recurrence` | `user_email`, `status` | `GET /api/v1/exports/orders/` |

Extra columns in the CSV are silently ignored.
