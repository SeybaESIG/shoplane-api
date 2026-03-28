"""
Concurrency stress test for stock reservation.

Multiple threads race on checkout for a product with limited stock to verify
that select_for_update() prevents overselling and stock never goes negative.

Requires transaction=True so each thread operates in its own real transaction
rather than the test-scoped savepoint used by default.
"""

import threading
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from shoplane.models import Cart, CartItem, CartStatus, Category, Product

User = get_user_model()

THREAD_COUNT = 10


def _make_user(suffix):
    return User.objects.create_user(
        email=f"concurrent_{suffix}@example.com",
        password="pass",
        first_name="User",
        last_name=str(suffix),
    )


def _make_cart_with_item(user, product, quantity=1):
    cart = Cart.objects.create(user=user, status=CartStatus.OPEN)
    CartItem.objects.create(
        cart=cart,
        product=product,
        quantity=quantity,
        unit_price=product.price,
        subtotal=product.price * quantity,
    )
    return cart


@pytest.mark.django_db(transaction=True)
def test_concurrent_orders_never_oversell():
    """
    THREAD_COUNT threads each attempt to order the last unit of a product.
    Exactly one should succeed; the rest should be rejected with a stock error.
    Stock must never drop below zero.
    """
    from rest_framework.test import APIClient

    category = Category.objects.create(name="Electronics Concurrent", slug="electronics-concurrent")
    product = Product.objects.create(
        name="Limited Widget",
        slug="limited-widget",
        price=Decimal("19.99"),
        stock=1,
        category=category,
    )

    users = [_make_user(i) for i in range(THREAD_COUNT)]
    for user in users:
        _make_cart_with_item(user, product, quantity=1)

    results = []
    errors = []

    def attempt_order(user):
        client = APIClient()
        client.force_authenticate(user=user)
        try:
            resp = client.post(
                "/api/v1/orders/",
                data={"shipping_address": "123 Main St"},
                format="json",
            )
            results.append(resp.status_code)
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=attempt_order, args=(u,)) for u in users]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Unexpected exceptions: {errors}"

    product.refresh_from_db()
    assert product.stock >= 0, "Stock went negative — oversell detected."

    successful = [s for s in results if s == 201]
    assert len(successful) == 1, (
        f"Expected exactly 1 successful order, got {len(successful)}. All statuses: {results}"
    )
