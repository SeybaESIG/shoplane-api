import csv
import io
from decimal import Decimal
from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from shoplane.models import Order, User


def _parse_csv(response):
    """Consume the streaming response and return a list of dicts (one per row)."""
    content = b"".join(response.streaming_content).decode("utf-8")
    return list(csv.DictReader(io.StringIO(content)))


def _make_order(user, status="PENDING", total="49.99"):
    suffix = uuid4().hex[:8]
    return Order.objects.create(
        user=user,
        order_number=f"ORD-{suffix}",
        total_price=Decimal(total),
        shipping_address="1 Test St",
        status=status,
    )


# ---------------------------------------------------------------------------
# Order export
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOrderExport:
    @pytest.fixture(autouse=True)
    def setup(self, user, admin_user):
        self.admin = APIClient()
        self.admin.force_authenticate(user=admin_user)
        self.regular = APIClient()
        self.regular.force_authenticate(user=user)
        self.user = user
        self.url = reverse("export-orders")

    def test_returns_csv_content_type(self):
        response = self.admin.get(self.url)
        assert response.status_code == 200
        assert "text/csv" in response["Content-Type"]

    def test_returns_attachment_header(self):
        response = self.admin.get(self.url)
        assert "attachment" in response["Content-Disposition"]
        assert "orders.csv" in response["Content-Disposition"]

    def test_csv_contains_expected_columns(self):
        _make_order(self.user)
        rows = _parse_csv(self.admin.get(self.url))
        assert len(rows) >= 1
        assert set(rows[0].keys()) == {
            "order_number", "status", "total_price",
            "user_email", "shipping_address", "billing_address", "created_at",
        }

    def test_csv_row_matches_order_data(self):
        order = _make_order(self.user, total="123.45")
        rows = _parse_csv(self.admin.get(self.url))
        matching = [r for r in rows if r["order_number"] == order.order_number]
        assert len(matching) == 1
        row = matching[0]
        assert row["status"] == "PENDING"
        assert Decimal(row["total_price"]) == Decimal("123.45")
        assert row["user_email"] == self.user.email

    def test_filter_by_status(self):
        confirmed = _make_order(self.user, status="CONFIRMED")
        _make_order(self.user, status="PENDING")
        rows = _parse_csv(self.admin.get(self.url, {"status": "CONFIRMED"}))
        numbers = [r["order_number"] for r in rows]
        assert confirmed.order_number in numbers
        assert all(r["status"] == "CONFIRMED" for r in rows)

    def test_unauthenticated_returns_401(self):
        response = APIClient().get(self.url)
        assert response.status_code == 401

    def test_regular_user_returns_403(self):
        response = self.regular.get(self.url)
        assert response.status_code == 403

    def test_empty_export_returns_header_only(self):
        rows = _parse_csv(self.admin.get(self.url))
        assert isinstance(rows, list)


# ---------------------------------------------------------------------------
# Customer export
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCustomerExport:
    @pytest.fixture(autouse=True)
    def setup(self, user, admin_user):
        self.admin = APIClient()
        self.admin.force_authenticate(user=admin_user)
        self.regular = APIClient()
        self.regular.force_authenticate(user=user)
        self.user = user
        self.url = reverse("export-customers")

    def test_returns_csv_content_type(self):
        _make_order(self.user)
        response = self.admin.get(self.url)
        assert response.status_code == 200
        assert "text/csv" in response["Content-Type"]

    def test_returns_attachment_header(self):
        _make_order(self.user)
        response = self.admin.get(self.url)
        assert "attachment" in response["Content-Disposition"]
        assert "customers.csv" in response["Content-Disposition"]

    def test_csv_contains_expected_columns(self):
        _make_order(self.user)
        rows = _parse_csv(self.admin.get(self.url))
        assert len(rows) >= 1
        assert set(rows[0].keys()) == {
            "email", "first_name", "last_name", "order_count", "total_spend",
        }

    def test_csv_row_aggregates_correctly(self):
        _make_order(self.user, total="30.00")
        _make_order(self.user, total="20.00")
        rows = _parse_csv(self.admin.get(self.url))
        matching = [r for r in rows if r["email"] == self.user.email]
        assert len(matching) == 1
        assert int(matching[0]["order_count"]) == 2
        assert Decimal(matching[0]["total_spend"]) == Decimal("50.00")

    def test_users_without_orders_excluded(self, admin_user):
        suffix = uuid4().hex[:8]
        no_orders_user = User.objects.create_user(
            email=f"noorders-{suffix}@example.com",
            password="Pass123!",
            first_name="No",
            last_name="Orders",
        )
        rows = _parse_csv(self.admin.get(self.url))
        emails = [r["email"] for r in rows]
        assert no_orders_user.email not in emails

    def test_unauthenticated_returns_401(self):
        response = APIClient().get(self.url)
        assert response.status_code == 401

    def test_regular_user_returns_403(self):
        response = self.regular.get(self.url)
        assert response.status_code == 403
