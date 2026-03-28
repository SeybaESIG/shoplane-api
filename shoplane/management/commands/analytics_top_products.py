"""
python manage.py analytics_top_products [--limit N] [--source db|csv] [--file path]
    [--output stdout|csv] [--from YYYY-MM-DD] [--to YYYY-MM-DD]

Reports the best-selling products by total quantity sold from CONFIRMED orders.

--source csv expects a CSV with at least these columns:
    product_slug, product_name, quantity
"""
from collections import defaultdict

from django.core.management.base import CommandError
from django.db.models import Sum

from shoplane.models import OrderItem, OrderStatus

from ._base import AnalyticsCommand

DEFAULT_LIMIT = 10
MAX_LIMIT = 50


class Command(AnalyticsCommand):
    help = "Top-selling products by quantity sold from CONFIRMED orders."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--limit",
            type=int,
            default=DEFAULT_LIMIT,
            help=f"Maximum number of products to show (default {DEFAULT_LIMIT}, max {MAX_LIMIT}).",
        )

    def run(self, options):
        limit = min(max(options["limit"], 1), MAX_LIMIT)

        if options["source"] == "csv":
            rows = self._from_csv(options, limit)
        else:
            rows = self._from_db(options, limit)

        header = ["rank", "product_slug", "product_name", "total_quantity"]
        return header, [[i + 1] + list(r) for i, r in enumerate(rows)]

    def _from_db(self, options, limit):
        qs = (
            OrderItem.objects
            .filter(order__status=OrderStatus.CONFIRMED)
        )
        qs = self.apply_date_range(qs, options, field="order__created_at")
        results = (
            qs.values("product__slug", "product__name")
            .annotate(total_quantity=Sum("quantity"))
            .order_by("-total_quantity")[:limit]
        )
        return [
            [r["product__slug"], r["product__name"], r["total_quantity"]]
            for r in results
        ]

    def _from_csv(self, options, limit):
        records = self.read_csv(options)
        totals = defaultdict(lambda: {"name": "", "qty": 0})
        for row in records:
            slug = row.get("product_slug", "")
            totals[slug]["name"] = row.get("product_name", slug)
            try:
                totals[slug]["qty"] += int(row.get("quantity", 0))
            except (ValueError, TypeError):
                pass
        ranked = sorted(totals.items(), key=lambda x: x[1]["qty"], reverse=True)
        return [[slug, info["name"], info["qty"]] for slug, info in ranked[:limit]]
