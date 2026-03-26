from datetime import date

from django.db.models import Count, DecimalField, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

from .api.responses import success_response
from .models import OrderItem, OrderStatus, Order


_TRUNC_FUNCTIONS = {
    "day": TruncDay,
    "week": TruncWeek,
    "month": TruncMonth,
}

TOP_PRODUCTS_MAX_LIMIT = 50
TOP_PRODUCTS_DEFAULT_LIMIT = 10


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
            OrderItem.objects
            .filter(order__status=OrderStatus.CONFIRMED)
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

        date_from = self._parse_date(request.query_params.get("from"), "from")
        date_to = self._parse_date(request.query_params.get("to"), "to")

        orders = Order.objects.filter(status=OrderStatus.CONFIRMED)

        if date_from:
            orders = orders.filter(created_at__date__gte=date_from)
        if date_to:
            orders = orders.filter(created_at__date__lte=date_to)

        trunc_fn = _TRUNC_FUNCTIONS[period]
        results = (
            orders
            .annotate(period=trunc_fn("created_at"))
            .values("period")
            .annotate(
                total_sales=Sum("total_price", output_field=DecimalField()),
                order_count=Count("id"),
            )
            .order_by("period")
        )

        data = [
            {
                "period": row["period"].strftime(self._fmt(period)),
                "total_sales": row["total_sales"],
                "order_count": row["order_count"],
            }
            for row in results
        ]

        return success_response(
            message="Sales stats retrieved successfully",
            data=data,
        )

    @staticmethod
    def _parse_date(value, param_name):
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValidationError(
                {param_name: f"Invalid date '{value}'. Expected format: YYYY-MM-DD."}
            )

    @staticmethod
    def _fmt(period):
        return {"day": "%Y-%m-%d", "week": "%Y-%m-%d", "month": "%Y-%m"}[period]
