"""
python manage.py analytics_orders_per_customer
    [--from YYYY-MM-DD] [--to YYYY-MM-DD]
    [--source db|csv] [--file path] [--output stdout|csv]

Reports how many customers placed exactly N orders (distribution table)
and the mean order count per customer.

--source csv expects a CSV with at least: user_email, status
"""
from collections import Counter, defaultdict
from decimal import Decimal

from django.db.models import Count

from shoplane.models import Order, OrderStatus

from ._base import AnalyticsCommand


class Command(AnalyticsCommand):
    help = "Distribution of order counts per customer from CONFIRMED orders."

    def run(self, options):
        if options["source"] == "csv":
            distribution, total_customers, mean = self._from_csv(options)
        else:
            distribution, total_customers, mean = self._from_db(options)

        summary_header = ["total_customers", "mean_orders_per_customer"]
        summary_rows = [[total_customers, mean]]

        dist_header = ["order_count", "customer_count"]
        dist_rows = [[k, v] for k, v in sorted(distribution.items())]

        self.stdout.write("\n-- Summary --")
        self._print_table(summary_header, summary_rows)
        self.stdout.write("\n-- Distribution --")
        self._print_table(dist_header, dist_rows)

        if options["output"] == "csv":
            combined_header = dist_header
            return combined_header, dist_rows
        return dist_header, dist_rows

    def handle(self, *args, **options):
        if options["output"] != "csv":
            self.run(options)
        else:
            super().handle(*args, **options)

    def _from_db(self, options):
        qs = Order.objects.filter(status=OrderStatus.CONFIRMED)
        qs = self.apply_date_range(qs, options)

        per_user = list(
            qs.values("user_id").annotate(order_count=Count("id"))
        )
        if not per_user:
            return Counter(), 0, None

        distribution = Counter(r["order_count"] for r in per_user)
        total = len(per_user)
        total_orders = sum(r["order_count"] for r in per_user)
        mean = round(total_orders / total, 2)
        return distribution, total, mean

    def _from_csv(self, options):
        records = self.read_csv(options)
        per_user = defaultdict(int)
        for row in records:
            if row.get("status", "").upper() != "CONFIRMED":
                continue
            email = row.get("user_email", "")
            if email:
                per_user[email] += 1

        if not per_user:
            return Counter(), 0, None

        distribution = Counter(per_user.values())
        total = len(per_user)
        total_orders = sum(per_user.values())
        mean = round(total_orders / total, 2)
        return distribution, total, mean
