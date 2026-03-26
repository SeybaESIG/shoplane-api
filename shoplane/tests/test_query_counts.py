"""
N+1 query audit tests.

Each test creates N objects, calls the list/retrieve endpoint, and asserts that
the number of database queries does not grow with N. A fixed upper bound is
asserted instead of an exact count so that minor internal changes (e.g. session
lookups, permission checks) don't break the suite.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from shoplane.models import Cart, CartItem, Category, Product


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_product(category, user, suffix=None):
    s = suffix or uuid4().hex[:6]
    return Product.objects.create(
        name=f"Product {s}",
        slug=f"product-{s}",
        category=category,
        price=Decimal("19.99"),
        stock=10,
        updated_by=user,
    )


# ---------------------------------------------------------------------------
# Products list -- select_related("category")
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProductListQueryCount:
    def test_product_list_does_not_produce_n_plus_1(self, user, category):
        """
        Listing products must execute a constant number of queries regardless of N.
        Without select_related("category") this would be 1 + N (one per product).
        The cache is cleared before each measurement so both requests hit the DB.
        """
        for i in range(15):
            _make_product(category, user, suffix=f"qc-{i:03d}")

        client = APIClient()

        cache.clear()
        with CaptureQueriesContext(connection) as ctx_15:
            client.get(reverse("product-list"))

        query_count_15 = len(ctx_15)

        # Add 15 more products (30 total) and ensure the count doesn't grow.
        for i in range(15, 30):
            _make_product(category, user, suffix=f"qc-{i:03d}")

        cache.clear()
        with CaptureQueriesContext(connection) as ctx_30:
            client.get(reverse("product-list"))

        query_count_30 = len(ctx_30)

        assert query_count_15 == query_count_30, (
            f"Query count grew from {query_count_15} (15 products) "
            f"to {query_count_30} (30 products) -- N+1 detected."
        )

    def test_product_list_query_count_is_bounded(self, user, category):
        """The full list endpoint must stay within a reasonable fixed ceiling."""
        for i in range(20):
            _make_product(category, user, suffix=f"bound-{i:03d}")

        client = APIClient()

        cache.clear()
        with CaptureQueriesContext(connection) as ctx:
            response = client.get(reverse("product-list"))

        assert response.status_code == 200
        # Ceiling: pagination count query + main SELECT (with JOIN) = at most 5
        assert len(ctx) <= 5, (
            f"Expected ≤5 queries for product list, got {len(ctx)}."
        )


# ---------------------------------------------------------------------------
# Cart retrieve -- prefetch_related("items__product")
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCartRetrieveQueryCount:
    def test_cart_retrieve_does_not_produce_n_plus_1(self, user):
        """
        Retrieving a cart with N items must execute a constant number of queries.
        Without prefetch_related("items__product") this would be 1 + N (one per item).
        """
        category = Category.objects.create(
            name=f"Cat {uuid4().hex[:6]}", updated_by=user
        )
        cart = Cart.objects.create(user=user)

        for i in range(5):
            s = uuid4().hex[:6]
            product = Product.objects.create(
                name=f"Item {s}", slug=f"item-{s}", category=category,
                price=Decimal("9.99"), stock=20, updated_by=user,
            )
            CartItem.objects.create(
                cart=cart, product=product, quantity=1,
                unit_price=product.price, subtotal=product.price,
            )

        client = APIClient()
        client.force_authenticate(user=user)

        with CaptureQueriesContext(connection) as ctx_5:
            client.get(reverse("cart"))

        query_count_5 = len(ctx_5)

        # Add 5 more items (10 total).
        for i in range(5):
            s = uuid4().hex[:6]
            product = Product.objects.create(
                name=f"Item2 {s}", slug=f"item2-{s}", category=category,
                price=Decimal("9.99"), stock=20, updated_by=user,
            )
            CartItem.objects.create(
                cart=cart, product=product, quantity=1,
                unit_price=product.price, subtotal=product.price,
            )

        # Re-authenticate on a fresh client to avoid cached state.
        client2 = APIClient()
        client2.force_authenticate(user=user)

        with CaptureQueriesContext(connection) as ctx_10:
            client2.get(reverse("cart"))

        query_count_10 = len(ctx_10)

        assert query_count_5 == query_count_10, (
            f"Query count grew from {query_count_5} (5 items) "
            f"to {query_count_10} (10 items) -- N+1 detected."
        )

    def test_cart_retrieve_query_count_is_bounded(self, user):
        """The cart endpoint must stay within a reasonable fixed ceiling."""
        category = Category.objects.create(
            name=f"BoundCat {uuid4().hex[:6]}", updated_by=user
        )
        cart = Cart.objects.create(user=user)

        for i in range(8):
            s = uuid4().hex[:6]
            product = Product.objects.create(
                name=f"BoundItem {s}", slug=f"bound-{s}", category=category,
                price=Decimal("5.00"), stock=10, updated_by=user,
            )
            CartItem.objects.create(
                cart=cart, product=product, quantity=1,
                unit_price=product.price, subtotal=product.price,
            )

        client = APIClient()
        client.force_authenticate(user=user)

        with CaptureQueriesContext(connection) as ctx:
            response = client.get(reverse("cart"))

        assert response.status_code == 200
        # Ceiling: auth lookup + cart get_or_create + items prefetch + products prefetch = at most 8
        assert len(ctx) <= 8, (
            f"Expected ≤8 queries for cart retrieve, got {len(ctx)}."
        )
