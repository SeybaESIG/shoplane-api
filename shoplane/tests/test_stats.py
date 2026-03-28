from decimal import Decimal
from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from shoplane.models import Category, Order, OrderItem, OrderStatus, Product


def _make_confirmed_order(user, product, quantity, unit_price, total, days_ago=0):
    """Create a CONFIRMED order with one item, optionally backdated."""
    from datetime import timedelta

    from django.utils import timezone

    suffix = uuid4().hex[:8]
    order = Order.objects.create(
        user=user,
        order_number=f"ORD-{suffix}",
        total_price=Decimal(str(total)),
        shipping_address="1 Test St",
        status=OrderStatus.CONFIRMED,
    )
    if days_ago:
        Order.objects.filter(pk=order.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago)
        )
        order.refresh_from_db()

    OrderItem.objects.create(
        order=order,
        product=product,
        quantity=quantity,
        unit_price=Decimal(str(unit_price)),
        subtotal=Decimal(str(unit_price)) * quantity,
    )
    return order


# ---------------------------------------------------------------------------
# Top products
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTopProducts:
    @pytest.fixture(autouse=True)
    def setup(self, user, admin_user, category):
        self.admin = APIClient()
        self.admin.force_authenticate(user=admin_user)
        self.regular = APIClient()
        self.regular.force_authenticate(user=user)
        self.user = user

        s1, s2 = uuid4().hex[:6], uuid4().hex[:6]
        self.p1 = Product.objects.create(
            name=f"Popular {s1}",
            slug=f"popular-{s1}",
            category=category,
            price=Decimal("10.00"),
            stock=100,
            updated_by=user,
        )
        self.p2 = Product.objects.create(
            name=f"Niche {s2}",
            slug=f"niche-{s2}",
            category=category,
            price=Decimal("10.00"),
            stock=100,
            updated_by=user,
        )

    def test_returns_200(self):
        response = self.admin.get(reverse("stats-top-products"))
        assert response.status_code == 200

    def test_ranks_by_quantity_descending(self):
        _make_confirmed_order(self.user, self.p1, quantity=10, unit_price="10", total="100")
        _make_confirmed_order(self.user, self.p2, quantity=3, unit_price="10", total="30")

        data = self.admin.get(reverse("stats-top-products")).data["data"]
        slugs = [row["product_slug"] for row in data]
        assert slugs.index(self.p1.slug) < slugs.index(self.p2.slug)

    def test_total_quantity_sums_across_orders(self):
        _make_confirmed_order(self.user, self.p1, quantity=4, unit_price="10", total="40")
        _make_confirmed_order(self.user, self.p1, quantity=6, unit_price="10", total="60")

        data = self.admin.get(reverse("stats-top-products")).data["data"]
        row = next(r for r in data if r["product_slug"] == self.p1.slug)
        assert row["total_quantity"] == 10

    def test_pending_orders_excluded(self):
        suffix = uuid4().hex[:8]
        pending_order = Order.objects.create(
            user=self.user,
            order_number=f"ORD-P-{suffix}",
            total_price=Decimal("50.00"),
            shipping_address="1 St",
            status=OrderStatus.PENDING,
        )
        OrderItem.objects.create(
            order=pending_order,
            product=self.p2,
            quantity=100,
            unit_price=Decimal("10"),
            subtotal=Decimal("1000"),
        )
        _make_confirmed_order(self.user, self.p1, quantity=1, unit_price="10", total="10")

        data = self.admin.get(reverse("stats-top-products")).data["data"]
        slugs = [r["product_slug"] for r in data]
        assert self.p1.slug in slugs
        assert self.p2.slug not in slugs

    def test_limit_param_respected(self):
        for i in range(5):
            s = uuid4().hex[:6]
            p = Product.objects.create(
                name=f"Extra {s}",
                slug=f"extra-{s}",
                category=Category.objects.first(),
                price=Decimal("5"),
                stock=10,
                updated_by=self.user,
            )
            _make_confirmed_order(self.user, p, quantity=1, unit_price="5", total="5")

        data = self.admin.get(reverse("stats-top-products"), {"limit": 2}).data["data"]
        assert len(data) <= 2

    def test_limit_capped_at_50(self):
        response = self.admin.get(reverse("stats-top-products"), {"limit": 999})
        assert response.status_code == 200

    def test_unauthenticated_returns_401(self):
        assert APIClient().get(reverse("stats-top-products")).status_code == 401

    def test_regular_user_returns_403(self):
        assert self.regular.get(reverse("stats-top-products")).status_code == 403


# ---------------------------------------------------------------------------
# Sales stats
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSalesStats:
    @pytest.fixture(autouse=True)
    def setup(self, user, admin_user, category):
        self.admin = APIClient()
        self.admin.force_authenticate(user=admin_user)
        self.regular = APIClient()
        self.regular.force_authenticate(user=user)
        self.user = user

        s = uuid4().hex[:6]
        self.product = Product.objects.create(
            name=f"Prod {s}",
            slug=f"prod-{s}",
            category=category,
            price=Decimal("10.00"),
            stock=100,
            updated_by=user,
        )

    def test_returns_200_with_day_period(self):
        response = self.admin.get(reverse("stats-sales"))
        assert response.status_code == 200

    def test_invalid_period_returns_400(self):
        response = self.admin.get(reverse("stats-sales"), {"period": "quarter"})
        assert response.status_code == 400

    def test_invalid_date_returns_400(self):
        response = self.admin.get(reverse("stats-sales"), {"from": "not-a-date"})
        assert response.status_code == 400

    def test_empty_result_when_no_orders(self):
        data = self.admin.get(reverse("stats-sales")).data["data"]
        assert data == []

    def test_sums_confirmed_orders_by_day(self):
        _make_confirmed_order(self.user, self.product, quantity=1, unit_price="10", total="30.00")
        _make_confirmed_order(self.user, self.product, quantity=1, unit_price="10", total="20.00")

        data = self.admin.get(reverse("stats-sales"), {"period": "day"}).data["data"]
        assert len(data) >= 1
        today_row = data[-1]
        assert Decimal(str(today_row["total_sales"])) == Decimal("50.00")
        assert today_row["order_count"] == 2

    def test_pending_orders_excluded(self):
        suffix = uuid4().hex[:8]
        Order.objects.create(
            user=self.user,
            order_number=f"ORD-PEND-{suffix}",
            total_price=Decimal("999.00"),
            shipping_address="1 St",
            status=OrderStatus.PENDING,
        )
        data = self.admin.get(reverse("stats-sales")).data["data"]
        assert data == []

    def test_date_range_filter(self):
        _make_confirmed_order(
            self.user, self.product, quantity=1, unit_price="10", total="99.00", days_ago=10
        )
        _make_confirmed_order(self.user, self.product, quantity=1, unit_price="10", total="1.00")

        from django.utils import timezone

        today_str = timezone.now().date().isoformat()
        data = self.admin.get(
            reverse("stats-sales"), {"period": "day", "from": today_str, "to": today_str}
        ).data["data"]

        assert len(data) == 1
        assert Decimal(str(data[0]["total_sales"])) == Decimal("1.00")

    def test_week_period_groups_correctly(self):
        _make_confirmed_order(self.user, self.product, quantity=1, unit_price="10", total="10.00")
        _make_confirmed_order(self.user, self.product, quantity=1, unit_price="10", total="10.00")

        data = self.admin.get(reverse("stats-sales"), {"period": "week"}).data["data"]
        assert len(data) >= 1
        assert data[-1]["order_count"] == 2

    def test_month_period_groups_correctly(self):
        _make_confirmed_order(self.user, self.product, quantity=1, unit_price="10", total="15.00")

        data = self.admin.get(reverse("stats-sales"), {"period": "month"}).data["data"]
        assert len(data) >= 1
        assert Decimal(str(data[-1]["total_sales"])) == Decimal("15.00")

    def test_unauthenticated_returns_401(self):
        assert APIClient().get(reverse("stats-sales")).status_code == 401

    def test_regular_user_returns_403(self):
        assert self.regular.get(reverse("stats-sales")).status_code == 403


# ---------------------------------------------------------------------------
# Average cart
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAverageCart:
    @pytest.fixture(autouse=True)
    def setup(self, user, admin_user, category):
        self.admin = APIClient()
        self.admin.force_authenticate(user=admin_user)
        self.regular = APIClient()
        self.regular.force_authenticate(user=user)
        self.user = user

        s = uuid4().hex[:6]
        self.product = Product.objects.create(
            name=f"Prod {s}",
            slug=f"prod-{s}",
            category=category,
            price=Decimal("10.00"),
            stock=100,
            updated_by=user,
        )

    def test_returns_200(self):
        response = self.admin.get(reverse("stats-average-cart"))
        assert response.status_code == 200

    def test_overall_average_no_orders(self):
        data = self.admin.get(reverse("stats-average-cart")).data["data"]
        assert data["average_order_value"] is None
        assert data["order_count"] == 0

    def test_overall_average_with_orders(self):
        _make_confirmed_order(self.user, self.product, quantity=1, unit_price="10", total="30.00")
        _make_confirmed_order(self.user, self.product, quantity=1, unit_price="10", total="50.00")

        data = self.admin.get(reverse("stats-average-cart")).data["data"]
        assert Decimal(str(data["average_order_value"])) == Decimal("40.00")
        assert data["order_count"] == 2

    def test_pending_orders_excluded(self):
        suffix = uuid4().hex[:8]
        Order.objects.create(
            user=self.user,
            order_number=f"ORD-P-{suffix}",
            total_price=Decimal("999.00"),
            shipping_address="1 St",
            status=OrderStatus.PENDING,
        )
        data = self.admin.get(reverse("stats-average-cart")).data["data"]
        assert data["average_order_value"] is None
        assert data["order_count"] == 0

    def test_period_breakdown_by_day(self):
        _make_confirmed_order(self.user, self.product, quantity=1, unit_price="10", total="20.00")
        _make_confirmed_order(self.user, self.product, quantity=1, unit_price="10", total="40.00")

        data = self.admin.get(reverse("stats-average-cart"), {"period": "day"}).data["data"]
        assert len(data) >= 1
        today_row = data[-1]
        assert Decimal(str(today_row["average_order_value"])) == Decimal("30.00")
        assert today_row["order_count"] == 2

    def test_invalid_period_returns_400(self):
        response = self.admin.get(reverse("stats-average-cart"), {"period": "quarter"})
        assert response.status_code == 400

    def test_date_range_filter(self):
        _make_confirmed_order(
            self.user, self.product, quantity=1, unit_price="10", total="99.00", days_ago=10
        )
        _make_confirmed_order(self.user, self.product, quantity=1, unit_price="10", total="10.00")

        from django.utils import timezone

        today_str = timezone.now().date().isoformat()
        data = self.admin.get(
            reverse("stats-average-cart"), {"from": today_str, "to": today_str}
        ).data["data"]
        assert Decimal(str(data["average_order_value"])) == Decimal("10.00")

    def test_unauthenticated_returns_401(self):
        assert APIClient().get(reverse("stats-average-cart")).status_code == 401

    def test_regular_user_returns_403(self):
        assert self.regular.get(reverse("stats-average-cart")).status_code == 403


# ---------------------------------------------------------------------------
# Orders per customer
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOrdersPerCustomer:
    @pytest.fixture(autouse=True)
    def setup(self, user, admin_user, category):
        from shoplane.models import User

        self.admin = APIClient()
        self.admin.force_authenticate(user=admin_user)
        self.regular = APIClient()
        self.regular.force_authenticate(user=user)
        self.user = user

        s = uuid4().hex[:6]
        self.product = Product.objects.create(
            name=f"Prod {s}",
            slug=f"prod-{s}",
            category=category,
            price=Decimal("10.00"),
            stock=100,
            updated_by=user,
        )

        # Second user for multi-customer scenarios
        suffix = uuid4().hex[:6]
        self.user2 = User.objects.create_user(
            email=f"user2-{suffix}@example.com",
            password="StrongPass123!",
            first_name="B",
            last_name="User",
        )

    def test_returns_200(self):
        assert self.admin.get(reverse("stats-orders-per-customer")).status_code == 200

    def test_no_orders_returns_empty(self):
        data = self.admin.get(reverse("stats-orders-per-customer")).data["data"]
        assert data["total_customers"] == 0
        assert data["distribution"] == []
        assert data["mean_orders_per_customer"] is None

    def test_distribution_single_order_customers(self):
        _make_confirmed_order(self.user, self.product, quantity=1, unit_price="10", total="10")
        _make_confirmed_order(self.user2, self.product, quantity=1, unit_price="10", total="10")

        data = self.admin.get(reverse("stats-orders-per-customer")).data["data"]
        assert data["total_customers"] == 2
        assert data["mean_orders_per_customer"] == 1.0
        dist = {row["order_count"]: row["customer_count"] for row in data["distribution"]}
        assert dist[1] == 2

    def test_distribution_mixed(self):
        # user1 → 3 orders, user2 → 1 order
        for _ in range(3):
            _make_confirmed_order(self.user, self.product, quantity=1, unit_price="10", total="10")
        _make_confirmed_order(self.user2, self.product, quantity=1, unit_price="10", total="10")

        data = self.admin.get(reverse("stats-orders-per-customer")).data["data"]
        assert data["total_customers"] == 2
        assert data["mean_orders_per_customer"] == 2.0  # (3 + 1) / 2
        dist = {row["order_count"]: row["customer_count"] for row in data["distribution"]}
        assert dist[1] == 1
        assert dist[3] == 1

    def test_pending_orders_excluded(self):
        suffix = uuid4().hex[:8]
        Order.objects.create(
            user=self.user,
            order_number=f"ORD-P-{suffix}",
            total_price=Decimal("10.00"),
            shipping_address="1 St",
            status=OrderStatus.PENDING,
        )
        data = self.admin.get(reverse("stats-orders-per-customer")).data["data"]
        assert data["total_customers"] == 0

    def test_date_range_filter(self):
        _make_confirmed_order(
            self.user, self.product, quantity=1, unit_price="10", total="10", days_ago=10
        )
        _make_confirmed_order(self.user2, self.product, quantity=1, unit_price="10", total="10")

        from django.utils import timezone

        today_str = timezone.now().date().isoformat()
        data = self.admin.get(
            reverse("stats-orders-per-customer"), {"from": today_str, "to": today_str}
        ).data["data"]
        assert data["total_customers"] == 1

    def test_unauthenticated_returns_401(self):
        assert APIClient().get(reverse("stats-orders-per-customer")).status_code == 401

    def test_regular_user_returns_403(self):
        assert self.regular.get(reverse("stats-orders-per-customer")).status_code == 403


# ---------------------------------------------------------------------------
# Customer recurrence
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCustomerRecurrence:
    @pytest.fixture(autouse=True)
    def setup(self, user, admin_user, category):
        from shoplane.models import User

        self.admin = APIClient()
        self.admin.force_authenticate(user=admin_user)
        self.regular = APIClient()
        self.regular.force_authenticate(user=user)
        self.user = user

        s = uuid4().hex[:6]
        self.product = Product.objects.create(
            name=f"Prod {s}",
            slug=f"prod-{s}",
            category=category,
            price=Decimal("10.00"),
            stock=100,
            updated_by=user,
        )

        suffix = uuid4().hex[:6]
        self.user2 = User.objects.create_user(
            email=f"user2-{suffix}@example.com",
            password="StrongPass123!",
            first_name="C",
            last_name="User",
        )

    def test_returns_200(self):
        assert self.admin.get(reverse("stats-customer-recurrence")).status_code == 200

    def test_no_orders_returns_zeros(self):
        data = self.admin.get(reverse("stats-customer-recurrence")).data["data"]
        assert data["new_customers"] == 0
        assert data["returning_customers"] == 0
        assert data["total_customers"] == 0
        assert data["recurrence_rate_pct"] is None

    def test_all_new_customers(self):
        _make_confirmed_order(self.user, self.product, quantity=1, unit_price="10", total="10")
        _make_confirmed_order(self.user2, self.product, quantity=1, unit_price="10", total="10")

        data = self.admin.get(reverse("stats-customer-recurrence")).data["data"]
        assert data["new_customers"] == 2
        assert data["returning_customers"] == 0
        assert data["recurrence_rate_pct"] == 0.0

    def test_mixed_new_and_returning(self):
        # user1 → 1 order (new), user2 → 2 orders (returning)
        _make_confirmed_order(self.user, self.product, quantity=1, unit_price="10", total="10")
        _make_confirmed_order(self.user2, self.product, quantity=1, unit_price="10", total="10")
        _make_confirmed_order(self.user2, self.product, quantity=1, unit_price="10", total="10")

        data = self.admin.get(reverse("stats-customer-recurrence")).data["data"]
        assert data["new_customers"] == 1
        assert data["returning_customers"] == 1
        assert data["total_customers"] == 2
        assert data["recurrence_rate_pct"] == 50.0

    def test_all_returning_customers(self):
        for _ in range(2):
            _make_confirmed_order(self.user, self.product, quantity=1, unit_price="10", total="10")
            _make_confirmed_order(self.user2, self.product, quantity=1, unit_price="10", total="10")

        data = self.admin.get(reverse("stats-customer-recurrence")).data["data"]
        assert data["new_customers"] == 0
        assert data["returning_customers"] == 2
        assert data["recurrence_rate_pct"] == 100.0

    def test_pending_orders_excluded(self):
        suffix = uuid4().hex[:8]
        Order.objects.create(
            user=self.user,
            order_number=f"ORD-P-{suffix}",
            total_price=Decimal("10.00"),
            shipping_address="1 St",
            status=OrderStatus.PENDING,
        )
        data = self.admin.get(reverse("stats-customer-recurrence")).data["data"]
        assert data["total_customers"] == 0

    def test_date_range_filter(self):
        # user1 ordered 10 days ago, user2 ordered today
        _make_confirmed_order(
            self.user, self.product, quantity=1, unit_price="10", total="10", days_ago=10
        )
        _make_confirmed_order(self.user2, self.product, quantity=1, unit_price="10", total="10")

        from django.utils import timezone

        today_str = timezone.now().date().isoformat()
        data = self.admin.get(
            reverse("stats-customer-recurrence"), {"from": today_str, "to": today_str}
        ).data["data"]
        assert data["total_customers"] == 1
        assert data["new_customers"] == 1

    def test_unauthenticated_returns_401(self):
        assert APIClient().get(reverse("stats-customer-recurrence")).status_code == 401

    def test_regular_user_returns_403(self):
        assert self.regular.get(reverse("stats-customer-recurrence")).status_code == 403
