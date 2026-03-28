"""
python manage.py analytics_sales [--period day|week|month]
    [--from YYYY-MM-DD] [--to YYYY-MM-DD]
    [--source db|csv] [--file path] [--output stdout|csv]

Reports total sales and order count grouped by the chosen period.
Only CONFIRMED orders are included when using --source db.

--source csv expects a CSV with at least: created_at, total_price, status
"""
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.core.management.base import CommandError
from django.db.models import Count, DecimalField, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek

from shoplane.models import Order, OrderStatus

from ._base import AnalyticsCommand

_TRUNC = {"day": TruncDay, "week": TruncWeek, "month": TruncMonth}
_FMT = {"day": "%Y-%m-%d", "week": "%Y-%m-%d", "month": "%Y-%m"}
_PARSE_FMT = {"day": "%Y-%m-%d", "week": "%Y-%m-%d", "month": "%Y-%m"}


class Command(AnalyticsCommand):
    help = "Sales totals grouped by day, week, or month from CONFIRMED orders."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--period",
            choices=["day", "week", "month"],
            default="day",
            help="Grouping period (default: day).",
        )

    def run(self, options):
        period = options["period"]

        if options["source"] == "csv":
            rows = self._from_csv(options, period)
        else:
            rows = self._from_db(options, period)

        header = ["period", "total_sales", "order_count"]
        return header, rows

    def _from_db(self, options, period):
        qs = Order.objects.filter(status=OrderStatus.CONFIRMED)
        qs = self.apply_date_range(qs, options)
        results = (
            qs.annotate(bucket=_TRUNC[period]("created_at"))
            .values("bucket")
            .annotate(
                total_sales=Sum("total_price", output_field=DecimalField()),
                order_count=Count("id"),
            )
            .order_by("bucket")
        )
        return [
            [
                r["bucket"].strftime(_FMT[period]),
                r["total_sales"],
                r["order_count"],
            ]
            for r in results
        ]

    def _from_csv(self, options, period):
        records = self.read_csv(options)
        buckets = defaultdict(lambda: {"total": Decimal("0"), "count": 0})
        for row in records:
            if row.get("status", "").upper() != "CONFIRMED":
                continue
            raw_date = row.get("created_at", "")
            try:
                dt = datetime.strptime(raw_date, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            if period == "month":
                key = dt.strftime("%Y-%m")
            elif period == "week":
                monday = dt.date() - timedelta(days=dt.weekday())
                key = monday.strftime("%Y-%m-%d")
            else:
                key = dt.strftime("%Y-%m-%d")
            try:
                buckets[key]["total"] += Decimal(row.get("total_price", "0"))
                buckets[key]["count"] += 1
            except (InvalidOperation, ValueError):
                pass
        return [
            [key, buckets[key]["total"], buckets[key]["count"]]
            for key in sorted(buckets)
        ]
