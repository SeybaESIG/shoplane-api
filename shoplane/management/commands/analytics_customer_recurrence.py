"""
python manage.py analytics_customer_recurrence
    [--from YYYY-MM-DD] [--to YYYY-MM-DD]
    [--source db|csv] [--file path] [--output stdout|csv]

Reports the split between new customers (exactly 1 CONFIRMED order in the
selected window) and returning customers (2+ orders in the window).

--source csv expects a CSV with at least: user_email, status
"""

from collections import defaultdict

from django.db.models import Count

from shoplane.models import Order, OrderStatus

from ._base import AnalyticsCommand


class Command(AnalyticsCommand):
    help = "New vs returning customer split from CONFIRMED orders."

    def run(self, options):
        if options["source"] == "csv":
            per_user = self._per_user_from_csv(options)
        else:
            per_user = self._per_user_from_db(options)

        new = sum(1 for c in per_user.values() if c == 1)
        returning = sum(1 for c in per_user.values() if c > 1)
        total = new + returning
        rate = round(returning / total * 100, 1) if total else None

        header = ["new_customers", "returning_customers", "total_customers", "recurrence_rate_pct"]
        rows = [[new, returning, total, rate if rate is not None else "N/A"]]
        return header, rows

    def _per_user_from_db(self, options):
        qs = Order.objects.filter(status=OrderStatus.CONFIRMED)
        qs = self.apply_date_range(qs, options)
        per_user = qs.values("user_id").annotate(order_count=Count("id"))
        return {r["user_id"]: r["order_count"] for r in per_user}

    def _per_user_from_csv(self, options):
        records = self.read_csv(options)
        per_user = defaultdict(int)
        for row in records:
            if row.get("status", "").upper() != "CONFIRMED":
                continue
            email = row.get("user_email", "")
            if email:
                per_user[email] += 1
        return dict(per_user)
