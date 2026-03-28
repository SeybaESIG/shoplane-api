"""
Tests for analytics management commands.

DB-source tests use the Django ORM against the test database.
CSV-source tests write a temporary file and verify the command reads it correctly.
"""
import csv
import os
import tempfile
from collections import defaultdict
from decimal import Decimal
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.utils.timezone import now

from shoplane.models import Category, Order, OrderItem, OrderStatus, Product, User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user(db):
    suffix = uuid4().hex[:8]
    return User.objects.create_user(
        email=f"cmd-user-{suffix}@example.com",
        password="Pass123!",
        first_name="A",
        last_name="B",
    )


@pytest.fixture
def user2(db):
    suffix = uuid4().hex[:8]
    return User.objects.create_user(
        email=f"cmd-user2-{suffix}@example.com",
        password="Pass123!",
        first_name="C",
        last_name="D",
    )


@pytest.fixture
def category(user):
    return Category.objects.create(name=f"Cat-{uuid4().hex[:6]}", updated_by=user)


@pytest.fixture
def product(category, user):
    return Product.objects.create(
        name=f"Prod-{uuid4().hex[:6]}",
        category=category,
        price=Decimal("10.00"),
        stock=100,
        updated_by=user,
    )


def _confirmed_order(user, product, total, qty=1, days_ago=0):
    from datetime import timedelta
    order = Order.objects.create(
        user=user,
        order_number=f"ORD-{uuid4().hex[:10]}",
        total_price=Decimal(str(total)),
        shipping_address="1 Test St",
        status=OrderStatus.CONFIRMED,
    )
    if days_ago:
        Order.objects.filter(pk=order.pk).update(
            created_at=now() - timedelta(days=days_ago)
        )
        order.refresh_from_db()
    OrderItem.objects.create(
        order=order,
        product=product,
        quantity=qty,
        unit_price=product.price,
        subtotal=product.price * qty,
    )
    return order


def _csv_file(rows, header):
    """Write rows to a temp CSV file and return its path."""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8"
    )
    writer = csv.DictWriter(f, fieldnames=header)
    writer.writeheader()
    writer.writerows(rows)
    f.close()
    return f.name


# ---------------------------------------------------------------------------
# analytics_top_products
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAnalyticsTopProductsCommand:
    def test_db_source_produces_output(self, capsys, product, user):
        _confirmed_order(user, product, total="10", qty=5)
        call_command("analytics_top_products")
        captured = capsys.readouterr()
        assert product.slug in captured.out

    def test_db_source_rank_order(self, capsys, category, user):
        s1, s2 = uuid4().hex[:6], uuid4().hex[:6]
        p1 = Product.objects.create(
            name=f"Pop-{s1}", slug=f"pop-{s1}", category=category,
            price=Decimal("10"), stock=100, updated_by=user,
        )
        p2 = Product.objects.create(
            name=f"Nic-{s2}", slug=f"nic-{s2}", category=category,
            price=Decimal("10"), stock=100, updated_by=user,
        )
        _confirmed_order(user, p1, total="100", qty=10)
        _confirmed_order(user, p2, total="20", qty=2)
        call_command("analytics_top_products")
        out = capsys.readouterr().out
        assert out.index(p1.slug) < out.index(p2.slug)

    def test_db_source_limit(self, capsys, category, user):
        products = []
        for _ in range(5):
            s = uuid4().hex[:6]
            p = Product.objects.create(
                name=f"P-{s}", slug=f"p-{s}", category=category,
                price=Decimal("5"), stock=10, updated_by=user,
            )
            _confirmed_order(user, p, total="5", qty=1)
            products.append(p)
        call_command("analytics_top_products", limit=2)
        out = capsys.readouterr().out
        present = sum(1 for p in products if p.slug in out)
        assert present <= 2

    def test_csv_source(self, capsys):
        path = _csv_file(
            [
                {"product_slug": "slug-a", "product_name": "A", "quantity": "8"},
                {"product_slug": "slug-b", "product_name": "B", "quantity": "3"},
                {"product_slug": "slug-a", "product_name": "A", "quantity": "2"},
            ],
            ["product_slug", "product_name", "quantity"],
        )
        try:
            call_command("analytics_top_products", source="csv", file=path)
            out = capsys.readouterr().out
            assert "slug-a" in out
            assert out.index("slug-a") < out.index("slug-b")
        finally:
            os.unlink(path)

    def test_csv_output_writes_file(self, product, user):
        _confirmed_order(user, product, total="10", qty=3)
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            out_path = f.name
        try:
            call_command("analytics_top_products", output="csv", file=out_path)
            with open(out_path, newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            assert len(rows) >= 1
            assert "product_slug" in rows[0]
        finally:
            os.unlink(out_path)


# ---------------------------------------------------------------------------
# analytics_sales
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAnalyticsSalesCommand:
    def test_db_source_day_period(self, capsys, product, user):
        _confirmed_order(user, product, total="30")
        _confirmed_order(user, product, total="20")
        call_command("analytics_sales", period="day")
        out = capsys.readouterr().out
        assert "50" in out

    def test_db_source_date_range_filter(self, capsys, product, user):
        _confirmed_order(user, product, total="99", days_ago=10)
        _confirmed_order(user, product, total="1")
        today = now().date().isoformat()
        call_command("analytics_sales", period="day", date_from=today, date_to=today)
        out = capsys.readouterr().out
        assert "1" in out
        assert "99" not in out

    def test_csv_source(self, capsys):
        path = _csv_file(
            [
                {"created_at": "2024-01-15 10:00:00", "total_price": "50.00", "status": "CONFIRMED"},
                {"created_at": "2024-01-15 12:00:00", "total_price": "30.00", "status": "CONFIRMED"},
                {"created_at": "2024-01-15 14:00:00", "total_price": "99.00", "status": "PENDING"},
            ],
            ["created_at", "total_price", "status"],
        )
        try:
            call_command("analytics_sales", source="csv", file=path, period="day")
            out = capsys.readouterr().out
            assert "80" in out
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# analytics_average_cart
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAnalyticsAverageCartCommand:
    def test_db_overall(self, capsys, product, user):
        _confirmed_order(user, product, total="30")
        _confirmed_order(user, product, total="50")
        call_command("analytics_average_cart")
        out = capsys.readouterr().out
        assert "40" in out

    def test_db_no_orders(self, capsys):
        call_command("analytics_average_cart")
        out = capsys.readouterr().out
        assert "None" in out or "no data" in out.lower() or "0" in out

    def test_db_period_breakdown(self, capsys, product, user):
        _confirmed_order(user, product, total="20")
        _confirmed_order(user, product, total="40")
        call_command("analytics_average_cart", period="day")
        out = capsys.readouterr().out
        assert "30" in out

    def test_csv_source_overall(self, capsys):
        path = _csv_file(
            [
                {"created_at": "2024-02-01 10:00:00", "total_price": "100.00", "status": "CONFIRMED"},
                {"created_at": "2024-02-01 11:00:00", "total_price": "60.00", "status": "CONFIRMED"},
                {"created_at": "2024-02-01 12:00:00", "total_price": "999.00", "status": "PENDING"},
            ],
            ["created_at", "total_price", "status"],
        )
        try:
            call_command("analytics_average_cart", source="csv", file=path)
            out = capsys.readouterr().out
            assert "80" in out
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# analytics_orders_per_customer
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAnalyticsOrdersPerCustomerCommand:
    def test_db_distribution(self, capsys, product, user, user2):
        _confirmed_order(user, product, total="10")
        _confirmed_order(user, product, total="10")
        _confirmed_order(user2, product, total="10")
        call_command("analytics_orders_per_customer")
        out = capsys.readouterr().out
        assert "2" in out
        assert "1.5" in out

    def test_db_no_orders(self, capsys):
        call_command("analytics_orders_per_customer")
        out = capsys.readouterr().out
        assert "0" in out or "no data" in out.lower()

    def test_csv_source(self, capsys):
        path = _csv_file(
            [
                {"user_email": "a@x.com", "status": "CONFIRMED"},
                {"user_email": "a@x.com", "status": "CONFIRMED"},
                {"user_email": "b@x.com", "status": "CONFIRMED"},
                {"user_email": "c@x.com", "status": "PENDING"},
            ],
            ["user_email", "status"],
        )
        try:
            call_command("analytics_orders_per_customer", source="csv", file=path)
            out = capsys.readouterr().out
            assert "2" in out
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# analytics_customer_recurrence
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAnalyticsCustomerRecurrenceCommand:
    def test_db_mixed(self, capsys, product, user, user2):
        _confirmed_order(user, product, total="10")
        _confirmed_order(user2, product, total="10")
        _confirmed_order(user2, product, total="10")
        call_command("analytics_customer_recurrence")
        out = capsys.readouterr().out
        assert "50.0" in out

    def test_db_all_new(self, capsys, product, user, user2):
        _confirmed_order(user, product, total="10")
        _confirmed_order(user2, product, total="10")
        call_command("analytics_customer_recurrence")
        out = capsys.readouterr().out
        assert "0.0" in out

    def test_db_no_orders(self, capsys):
        call_command("analytics_customer_recurrence")
        out = capsys.readouterr().out
        assert "N/A" in out or "0" in out

    def test_csv_source(self, capsys):
        path = _csv_file(
            [
                {"user_email": "a@x.com", "status": "CONFIRMED"},
                {"user_email": "a@x.com", "status": "CONFIRMED"},
                {"user_email": "b@x.com", "status": "CONFIRMED"},
            ],
            ["user_email", "status"],
        )
        try:
            call_command("analytics_customer_recurrence", source="csv", file=path)
            out = capsys.readouterr().out
            assert "50.0" in out
        finally:
            os.unlink(path)

    def test_csv_output_writes_file(self, product, user, user2):
        _confirmed_order(user, product, total="10")
        _confirmed_order(user2, product, total="10")
        _confirmed_order(user2, product, total="10")
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            out_path = f.name
        try:
            call_command("analytics_customer_recurrence", output="csv", file=out_path)
            with open(out_path, newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            assert len(rows) == 1
            assert "recurrence_rate_pct" in rows[0]
        finally:
            os.unlink(out_path)
