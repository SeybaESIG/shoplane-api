"""
python manage.py analytics_average_cart [--period day|week|month]
    [--from YYYY-MM-DD] [--to YYYY-MM-DD]
    [--source db|csv] [--file path] [--output stdout|csv]

Reports the average order value for CONFIRMED orders.
Without --period: prints a single overall summary row.
With --period: breaks the average down per period.

--source csv expects a CSV with at least: created_at, total_price, status
"""
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Avg, Count, DecimalField

from shoplane.models import Order, OrderStatus
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek

from ._base import AnalyticsCommand

_TRUNC = {"day": TruncDay, "week": TruncWeek, "month": TruncMonth}
_FMT = {"day": "%Y-%m-%d", "week": "%Y-%m-%d", "month": "%Y-%m"}


class Command(AnalyticsCommand):
    help = "Average order value for CONFIRMED orders, overall or broken down by period."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--period",
            choices=["day", "week", "month"],
            default=None,
            help="Optional grouping period. Omit for a single overall figure.",
        )

    def run(self, options):
        period = options.get("period")

        if options["source"] == "csv":
            rows = self._from_csv(options, period)
        else:
            rows = self._from_db(options, period)

        if period:
            header = ["period", "average_order_value", "order_count"]
        else:
            header = ["average_order_value", "order_count"]
        return header, rows

    def _from_db(self, options, period):
        qs = Order.objects.filter(status=OrderStatus.CONFIRMED)
        qs = self.apply_date_range(qs, options)

        if period:
            results = (
                qs.annotate(bucket=_TRUNC[period]("created_at"))
                .values("bucket")
                .annotate(
                    avg=Avg("total_price", output_field=DecimalField()),
                    cnt=Count("id"),
                )
                .order_by("bucket")
            )
            return [
                [
                    r["bucket"].strftime(_FMT[period]),
                    round(Decimal(str(r["avg"])), 2) if r["avg"] else None,
                    r["cnt"],
                ]
                for r in results
            ]

        agg = qs.aggregate(
            avg=Avg("total_price", output_field=DecimalField()),
            cnt=Count("id"),
        )
        avg = round(Decimal(str(agg["avg"])), 2) if agg["avg"] else None
        return [[avg, agg["cnt"]]]

    def _from_csv(self, options, period):
        records = self.read_csv(options)
        if period:
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
                [
                    key,
                    round(buckets[key]["total"] / buckets[key]["count"], 2),
                    buckets[key]["count"],
                ]
                for key in sorted(buckets)
                if buckets[key]["count"] > 0
            ]

        totals = [
            Decimal(r.get("total_price", "0"))
            for r in records
            if r.get("status", "").upper() == "CONFIRMED"
        ]
        if not totals:
            return [[None, 0]]
        avg = round(sum(totals) / len(totals), 2)
        return [[avg, len(totals)]]
