"""
Concurrency stress tests for stock reservation and webhook idempotency.

These tests spin up multiple threads that hit the database simultaneously to
verify that row-level locking and idempotency checks hold under load.

All tests require transaction=True so that each thread operates in its own
real transaction rather than the test-scoped savepoint used by default.
"""

import threading
from decimal import Decimal

import pytest

from shoplane.models import (
    Cart,
    CartItem,
    CartStatus,
    Category,
    Order,
    OrderStatus,
    Payment,
    PaymentLog,
    PaymentProvider,
    PaymentStatus,
    Product,
)
from django.contrib.auth import get_user_model

User = get_user_model()

THREAD_COUNT = 10


def _make_user(suffix):
    return User.objects.create_user(
        username=f"user_{suffix}",
        email=f"user_{suffix}@example.com",
        password="pass",
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


# ---------------------------------------------------------------------------
# Stock oversell prevention
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_concurrent_orders_never_oversell():
    """
    THREAD_COUNT threads each attempt to order the last unit of a product.
    Exactly one should succeed; the rest should be rejected with a stock error.
    Stock must never drop below zero.
    """
    from rest_framework.test import APIClient

    category = Category.objects.create(name="Electronics", slug="electronics")
    product = Product.objects.create(
        name="Limited Widget",
        slug="limited-widget",
        price=Decimal("19.99"),
        stock=1,
        category=category,
    )

    users = [_make_user(f"stock_{i}") for i in range(THREAD_COUNT)]
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
        f"Expected exactly 1 successful order, got {len(successful)}. "
        f"All statuses: {results}"
    )


# ---------------------------------------------------------------------------
# Webhook idempotency under concurrent delivery
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_concurrent_webhook_delivery_is_idempotent():
    """
    The same Stripe webhook event delivered by THREAD_COUNT concurrent requests
    must result in exactly one PAID status update and exactly one log entry
    carrying that event id.
    """
    from unittest.mock import patch

    from django.test import Client

    from shoplane.services.payments.result import WebhookEvent

    user = _make_user("webhook_concurrent")
    category = Category.objects.create(name="Books", slug="books")
    product = Product.objects.create(
        name="Novel",
        slug="novel",
        price=Decimal("9.99"),
        stock=10,
        category=category,
    )
    cart = _make_cart_with_item(user, product)

    order = Order.objects.create(
        user=user,
        order_number="ORD-CONCURRENT01",
        total_price=Decimal("9.99"),
        shipping_address="456 Side St",
        billing_address="456 Side St",
        status=OrderStatus.PENDING,
    )
    payment = Payment.objects.create(
        order=order,
        provider=PaymentProvider.STRIPE,
        amount=Decimal("9.99"),
        currency="CHF",
        status=PaymentStatus.PENDING,
        transaction_ref="pi_concurrent_test",
    )

    stripe_event_id = "evt_concurrent_unique"
    fake_event = WebhookEvent(
        event_id=stripe_event_id,
        event_type="payment_intent.succeeded",
        transaction_ref="pi_concurrent_test",
    )

    responses = []

    def send_webhook():
        client = Client()
        with patch(
            "shoplane.webhook_views.StripeWebhookView._parse_event",
            return_value=fake_event,
        ):
            resp = client.post(
                "/api/v1/webhooks/stripe/",
                data=b'{"id":"evt_concurrent_unique"}',
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="dummy",
            )
            responses.append(resp.status_code)

    threads = [threading.Thread(target=send_webhook) for _ in range(THREAD_COUNT)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PAID, (
        f"Payment status should be PAID, got {payment.status}"
    )

    paid_logs = PaymentLog.objects.filter(
        payment=payment,
        data__stripe_event_id=stripe_event_id,
    )
    assert paid_logs.count() == 1, (
        f"Expected exactly 1 log entry for event {stripe_event_id}, "
        f"got {paid_logs.count()}."
    )
