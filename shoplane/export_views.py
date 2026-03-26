import csv
import io

from django.db.models import Count, Sum
from django.http import StreamingHttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

from .api.filters import filter_orders
from .models import Order, User


class _Echo:
    """Minimal write-only object forwarded to csv.writer for streaming."""

    def write(self, value):
        return value


def _stream_csv(header, rows):
    """
    Yield CSV lines one at a time using StreamingHttpResponse.
    Nothing is buffered in memory beyond a single row at a time.
    """
    writer = csv.writer(_Echo())
    yield writer.writerow(header)
    for row in rows:
        yield writer.writerow(row)


class OrderExportView(APIView):
    """
    Stream all orders as a CSV file.
    Supports the same ?status= and ?ordering= filters as the order list endpoint.
    """

    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Export orders as CSV (admin only)",
        tags=["exports"],
        responses={"200": {"type": "string", "format": "binary"}},
    )
    def get(self, request):
        orders = Order.objects.select_related("user")
        orders = filter_orders(orders, request)

        header = [
            "order_number",
            "status",
            "total_price",
            "user_email",
            "shipping_address",
            "billing_address",
            "created_at",
        ]

        def rows():
            for order in orders.iterator():
                yield [
                    order.order_number,
                    order.status,
                    order.total_price,
                    order.user.email,
                    order.shipping_address,
                    order.billing_address,
                    order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                ]

        response = StreamingHttpResponse(
            _stream_csv(header, rows()),
            content_type="text/csv",
        )
        response["Content-Disposition"] = 'attachment; filename="orders.csv"'
        return response


class CustomerExportView(APIView):
    """
    Stream a customer summary as a CSV file.
    Each row represents one user with their order count and total spend.
    Only users who have placed at least one order are included.
    """

    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Export customer summary as CSV (admin only)",
        tags=["exports"],
        responses={"200": {"type": "string", "format": "binary"}},
    )
    def get(self, request):
        customers = (
            User.objects
            .filter(orders__isnull=False)
            .annotate(
                order_count=Count("orders", distinct=True),
                total_spend=Sum("orders__total_price"),
            )
            .order_by("email")
        )

        header = ["email", "first_name", "last_name", "order_count", "total_spend"]

        def rows():
            for user in customers.iterator():
                yield [
                    user.email,
                    user.first_name,
                    user.last_name,
                    user.order_count,
                    user.total_spend,
                ]

        response = StreamingHttpResponse(
            _stream_csv(header, rows()),
            content_type="text/csv",
        )
        response["Content-Disposition"] = 'attachment; filename="customers.csv"'
        return response
