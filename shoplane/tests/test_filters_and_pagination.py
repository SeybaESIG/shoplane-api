"""
Tests for product/category/order filtering, search, sorting, and pagination.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from shoplane.models import Category, Order, Product, User


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def make_product(category, user, name, price, stock=10, is_active=True):
    suffix = uuid4().hex[:6]
    return Product.objects.create(
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{suffix}",
        category=category,
        price=Decimal(str(price)),
        stock=stock,
        is_active=is_active,
        updated_by=user,
    )


def make_category(user, name):
    suffix = uuid4().hex[:6]
    return Category.objects.create(
        name=f"{name} {suffix}",
        slug=f"{name.lower().replace(' ', '-')}-{suffix}",
        updated_by=user,
    )


# ---------------------------------------------------------------------------
# Product filtering
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProductFiltering:
    @pytest.fixture(autouse=True)
    def setup(self, user):
        self.client = APIClient()
        electronics = make_category(user, "Electronics")
        clothing = make_category(user, "Clothing")

        self.laptop = make_product(electronics, user, "Laptop", 999.00)
        self.shirt = make_product(clothing, user, "Blue Shirt", 29.99)
        self.headphones = make_product(electronics, user, "Headphones", 49.99, stock=0)
        self.hidden = make_product(electronics, user, "Hidden Item", 10.00, is_active=False)

        self.electronics_slug = electronics.slug
        self.clothing_slug = clothing.slug

    def _get(self, **params):
        return self.client.get(reverse("product-list"), params)

    def test_filter_by_category(self):
        res = self._get(category=self.electronics_slug)
        names = [p["name"] for p in res.data["data"]]
        assert self.laptop.name in names
        assert self.shirt.name not in names

    def test_filter_by_min_price(self):
        res = self._get(min_price="50")
        prices = [Decimal(p["price"]) for p in res.data["data"]]
        assert all(p >= Decimal("50") for p in prices)

    def test_filter_by_max_price(self):
        res = self._get(max_price="50")
        prices = [Decimal(p["price"]) for p in res.data["data"]]
        assert all(p <= Decimal("50") for p in prices)

    def test_filter_by_price_range(self):
        res = self._get(min_price="30", max_price="100")
        prices = [Decimal(p["price"]) for p in res.data["data"]]
        assert all(Decimal("30") <= p <= Decimal("100") for p in prices)

    def test_filter_in_stock_excludes_zero_stock(self):
        res = self._get(in_stock="true")
        slugs = [p["slug"] for p in res.data["data"]]
        assert self.headphones.slug not in slugs
        assert self.laptop.slug in slugs

    def test_search_by_name(self):
        res = self._get(search="headphones")
        slugs = [p["slug"] for p in res.data["data"]]
        assert self.headphones.slug in slugs
        assert self.laptop.slug not in slugs

    def test_search_is_case_insensitive(self):
        res = self._get(search="LAPTOP")
        slugs = [p["slug"] for p in res.data["data"]]
        assert self.laptop.slug in slugs

    def test_invalid_price_param_is_ignored(self):
        """Non-numeric min_price must not raise a 500; it is silently ignored."""
        res = self._get(min_price="not-a-number")
        assert res.status_code == 200

    def test_inactive_products_not_returned_to_public(self):
        res = self._get()
        slugs = [p["slug"] for p in res.data["data"]]
        assert self.hidden.slug not in slugs


# ---------------------------------------------------------------------------
# Product sorting
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProductSorting:
    @pytest.fixture(autouse=True)
    def setup(self, user, category):
        self.client = APIClient()
        self.p1 = make_product(category, user, "Aardvark", 100.00)
        self.p2 = make_product(category, user, "Zebra", 10.00)
        self.p3 = make_product(category, user, "Mango", 50.00)

    def _get(self, **params):
        return self.client.get(reverse("product-list"), params)

    def test_sort_by_price_ascending(self):
        res = self._get(ordering="price")
        prices = [Decimal(p["price"]) for p in res.data["data"]]
        assert prices == sorted(prices)

    def test_sort_by_price_descending(self):
        res = self._get(ordering="-price")
        prices = [Decimal(p["price"]) for p in res.data["data"]]
        assert prices == sorted(prices, reverse=True)

    def test_sort_by_name_ascending(self):
        res = self._get(ordering="name")
        names = [p["name"] for p in res.data["data"]]
        assert names == sorted(names)

    def test_invalid_ordering_field_is_ignored(self):
        """An unknown field must not raise an error; default ordering is preserved."""
        res = self._get(ordering="not_a_field")
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# Category sorting
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCategorySorting:
    @pytest.fixture(autouse=True)
    def setup(self, user):
        self.client = APIClient()
        make_category(user, "Zucchini")
        make_category(user, "Apple")
        make_category(user, "Mango")

    def _get(self, **params):
        return self.client.get(reverse("category-list"), params)

    def test_sort_by_name_ascending(self):
        res = self._get(ordering="name")
        names = [c["name"] for c in res.data["data"]]
        assert names == sorted(names)

    def test_sort_by_name_descending(self):
        res = self._get(ordering="-name")
        names = [c["name"] for c in res.data["data"]]
        assert names == sorted(names, reverse=True)


# ---------------------------------------------------------------------------
# Order filtering and sorting
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOrderFiltering:
    @pytest.fixture(autouse=True)
    def setup(self, user):
        self.user = user
        self.client = APIClient()
        self.client.force_authenticate(user=user)
        suffix = uuid4().hex[:6]
        self.pending_order = Order.objects.create(
            user=user,
            order_number=f"ORD-PEND-{suffix}",
            total_price=Decimal("30.00"),
            shipping_address="1 A St",
            status="PENDING",
        )
        self.confirmed_order = Order.objects.create(
            user=user,
            order_number=f"ORD-CONF-{suffix}",
            total_price=Decimal("80.00"),
            shipping_address="2 B St",
            status="CONFIRMED",
        )

    def _get(self, **params):
        return self.client.get(reverse("order-list"), params)

    def test_filter_by_status(self):
        res = self._get(status="PENDING")
        numbers = [o["order_number"] for o in res.data["data"]]
        assert self.pending_order.order_number in numbers
        assert self.confirmed_order.order_number not in numbers

    def test_filter_by_status_case_insensitive_input(self):
        """Status value is uppercased server-side."""
        res = self._get(status="pending")
        assert res.status_code == 200
        numbers = [o["order_number"] for o in res.data["data"]]
        assert self.pending_order.order_number in numbers

    def test_sort_orders_by_total_price(self):
        res = self._get(ordering="total_price")
        prices = [Decimal(o["total_price"]) for o in res.data["data"]]
        assert prices == sorted(prices)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPagination:
    @pytest.fixture(autouse=True)
    def setup(self, user, category):
        self.client = APIClient()
        for i in range(25):
            suffix = uuid4().hex[:6]
            Product.objects.create(
                name=f"Product {i:03d} {suffix}",
                slug=f"product-{i:03d}-{suffix}",
                category=category,
                price=Decimal("9.99"),
                stock=5,
                updated_by=user,
            )

    def _get(self, **params):
        return self.client.get(reverse("product-list"), params)

    def test_response_includes_meta(self):
        res = self._get()
        assert "meta" in res.data
        meta = res.data["meta"]
        assert "count" in meta
        assert "page" in meta
        assert "page_size" in meta
        assert "total_pages" in meta
        assert "next" in meta
        assert "previous" in meta

    def test_default_page_size_is_20(self):
        res = self._get()
        assert len(res.data["data"]) == 20
        assert res.data["meta"]["page_size"] == 20

    def test_custom_page_size(self):
        res = self._get(page_size=5)
        assert len(res.data["data"]) == 5
        assert res.data["meta"]["page_size"] == 5

    def test_second_page_has_remaining_items(self):
        res = self._get(page=2)
        assert len(res.data["data"]) == 5
        assert res.data["meta"]["page"] == 2

    def test_next_and_previous_links(self):
        res = self._get(page=2, page_size=10)
        meta = res.data["meta"]
        assert meta["next"] is not None
        assert meta["previous"] is not None

    def test_first_page_has_no_previous(self):
        res = self._get(page=1)
        assert res.data["meta"]["previous"] is None

    def test_last_page_has_no_next(self):
        first = self._get()
        last_page = first.data["meta"]["total_pages"]
        res = self._get(page=last_page)
        assert res.data["meta"]["next"] is None

    def test_page_size_capped_at_100(self):
        res = self._get(page_size=999)
        assert res.data["meta"]["page_size"] == 100
