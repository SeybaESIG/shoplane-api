from collections import Counter
from datetime import date
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

from .api.responses import success_response
from .models import Order, OrderItem, OrderStatus

_TRUNC_FUNCTIONS = {
    "day": TruncDay,
    "week": TruncWeek,
    "month": TruncMonth,
}

TOP_PRODUCTS_MAX_LIMIT = 50
TOP_PRODUCTS_DEFAULT_LIMIT = 10


def _parse_date(value, param_name):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError({param_name: f"Invalid date '{value}'. Expected format: YYYY-MM-DD."})


def _apply_date_range(queryset, request):
    """Filter a queryset by ?from= and ?to= query params on created_at."""
    date_from = _parse_date(request.query_params.get("from"), "from")
    date_to = _parse_date(request.query_params.get("to"), "to")
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    return queryset


def _period_fmt(period):
    return {"day": "%Y-%m-%d", "week": "%Y-%m-%d", "month": "%Y-%m"}[period]


class TopProductsView(APIView):
    """
    Return the best-selling products by total quantity sold.
    Only items from CONFIRMED orders are counted.
    """

    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Top-selling products by quantity (admin only)",
        tags=["stats"],
    )
    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", TOP_PRODUCTS_DEFAULT_LIMIT))
        except (ValueError, TypeError):
            limit = TOP_PRODUCTS_DEFAULT_LIMIT

        limit = min(max(limit, 1), TOP_PRODUCTS_MAX_LIMIT)

        results = (
            OrderItem.objects.filter(order__status=OrderStatus.CONFIRMED)
            .values("product__slug", "product__name")
            .annotate(total_quantity=Sum("quantity"))
            .order_by("-total_quantity")[:limit]
        )

        data = [
            {
                "product_slug": row["product__slug"],
                "product_name": row["product__name"],
                "total_quantity": row["total_quantity"],
            }
            for row in results
        ]

        return success_response(
            message="Top products retrieved successfully",
            data=data,
        )


class SalesStatsView(APIView):
    """
    Return total sales grouped by day, week, or month.
    Only CONFIRMED orders are included.
    Optional ?from= and ?to= date range filters (format: YYYY-MM-DD).
    """

    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Sales totals grouped by period (admin only)",
        tags=["stats"],
    )
    def get(self, request):
        period = request.query_params.get("period", "day").lower()
        if period not in _TRUNC_FUNCTIONS:
            raise ValidationError(
                {"period": f"Invalid period '{period}'. Choose from: day, week, month."}
            )

        orders = Order.objects.filter(status=OrderStatus.CONFIRMED)
        orders = _apply_date_range(orders, request)

        trunc_fn = _TRUNC_FUNCTIONS[period]
        results = (
            orders.annotate(period=trunc_fn("created_at"))
            .values("period")
            .annotate(
                total_sales=Sum("total_price", output_field=DecimalField()),
                order_count=Count("id"),
            )
            .order_by("period")
        )

        data = [
            {
                "period": row["period"].strftime(_period_fmt(period)),
                "total_sales": row["total_sales"],
                "order_count": row["order_count"],
            }
            for row in results
        ]

        return success_response(
            message="Sales stats retrieved successfully",
            data=data,
        )


class AverageCartView(APIView):
    """
    Return the average order value for CONFIRMED orders.

    Without ?period=: returns a single overall average.
    With ?period=day|week|month: breaks the average down by period.
    Optional ?from= / ?to= date range filter in both modes.
    """

    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Average order value (admin only)",
        tags=["stats"],
    )
    def get(self, request):
        period = request.query_params.get("period", "").lower()
        if period and period not in _TRUNC_FUNCTIONS:
            raise ValidationError(
                {"period": f"Invalid period '{period}'. Choose from: day, week, month."}
            )

        orders = Order.objects.filter(status=OrderStatus.CONFIRMED)
        orders = _apply_date_range(orders, request)

        if period:
            trunc_fn = _TRUNC_FUNCTIONS[period]
            results = (
                orders.annotate(bucket=trunc_fn("created_at"))
                .values("bucket")
                .annotate(
                    average_order_value=Avg("total_price", output_field=DecimalField()),
                    order_count=Count("id"),
                )
                .order_by("bucket")
            )
            data = [
                {
                    "period": row["bucket"].strftime(_period_fmt(period)),
                    "average_order_value": (
                        round(Decimal(str(row["average_order_value"])), 2)
                        if row["average_order_value"] is not None
                        else None
                    ),
                    "order_count": row["order_count"],
                }
                for row in results
            ]
            return success_response(
                message="Average cart by period retrieved successfully",
                data=data,
            )

        agg = orders.aggregate(
            average_order_value=Avg("total_price", output_field=DecimalField()),
            order_count=Count("id"),
        )
        avg = agg["average_order_value"]
        return success_response(
            message="Average cart retrieved successfully",
            data={
                "average_order_value": (round(Decimal(str(avg)), 2) if avg is not None else None),
                "order_count": agg["order_count"],
            },
        )


class OrdersPerCustomerView(APIView):
    """
    Return the distribution of CONFIRMED order counts per customer.

    Each row in `distribution` shows how many customers placed exactly
    that many orders.  Also returns the mean order count per customer.

    Optional ?from= / ?to= date range filter (applied to order creation date).
    """

    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Orders-per-customer distribution (admin only)",
        tags=["stats"],
    )
    def get(self, request):
        orders = Order.objects.filter(status=OrderStatus.CONFIRMED)
        orders = _apply_date_range(orders, request)

        per_user = list(orders.values("user_id").annotate(order_count=Count("id")))

        if not per_user:
            return success_response(
                message="Orders per customer retrieved successfully",
                data={
                    "mean_orders_per_customer": None,
                    "total_customers": 0,
                    "distribution": [],
                },
            )

        distribution = Counter(row["order_count"] for row in per_user)
        total_customers = len(per_user)
        total_orders = sum(row["order_count"] for row in per_user)
        mean = round(total_orders / total_customers, 2)

        return success_response(
            message="Orders per customer retrieved successfully",
            data={
                "mean_orders_per_customer": mean,
                "total_customers": total_customers,
                "distribution": [
                    {"order_count": count, "customer_count": num_customers}
                    for count, num_customers in sorted(distribution.items())
                ],
            },
        )


class CustomerRecurrenceView(APIView):
    """
    Return the split between new customers (exactly 1 CONFIRMED order ever)
    and returning customers (2+ CONFIRMED orders ever).

    `recurrence_rate_pct` is the percentage of customers who have ordered more
    than once.

    Optional ?from= / ?to= date range filter scopes which orders are counted
    (useful for "of people who ordered in Q1, how many had ordered before?").
    """

    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="New vs returning customer split (admin only)",
        tags=["stats"],
    )
    def get(self, request):
        orders = Order.objects.filter(status=OrderStatus.CONFIRMED)
        orders = _apply_date_range(orders, request)

        per_user = list(orders.values("user_id").annotate(order_count=Count("id")))

        if not per_user:
            return success_response(
                message="Customer recurrence retrieved successfully",
                data={
                    "new_customers": 0,
                    "returning_customers": 0,
                    "total_customers": 0,
                    "recurrence_rate_pct": None,
                },
            )

        new_customers = sum(1 for r in per_user if r["order_count"] == 1)
        returning_customers = sum(1 for r in per_user if r["order_count"] > 1)
        total = new_customers + returning_customers
        recurrence_rate = round(returning_customers / total * 100, 1) if total else None

        return success_response(
            message="Customer recurrence retrieved successfully",
            data={
                "new_customers": new_customers,
                "returning_customers": returning_customers,
                "total_customers": total,
                "recurrence_rate_pct": recurrence_rate,
            },
        )
