from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from shoplane.models import Cart, Order, OrderStatus, Payment, PaymentLog, PaymentLogEventType, PaymentProvider, PaymentStatus


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def auth_client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def admin_client(admin_user):
    c = APIClient()
    c.force_authenticate(user=admin_user)
    return c


@pytest.fixture
def pending_order(user, product):
    """A PENDING order belonging to the test user, with stock decremented."""
    cart = Cart.objects.get_or_create(user=user)[0]
    cart.add_product(product=product, quantity=1)
    order = Order.objects.create(
        user=user,
        order_number="ORD-TESTPAY001",
        total_price=cart.total_price,
        shipping_address="1 Pay Street",
    )
    product.stock -= 1
    product.save()
    cart.status = "CONVERTED"
    cart.save()
    return order


@pytest.fixture
def stripe_payload():
    return {"provider": PaymentProvider.STRIPE}


# ---------------------------------------------------------------------------
# POST /orders/{order_number}/payment/ -- initiate payment
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_initiate_payment_with_stripe(auth_client, pending_order, stripe_payload):
    response = auth_client.post(
        reverse("payment", kwargs={"order_number": pending_order.order_number}),
        stripe_payload,
    )
    assert response.status_code == 201
    data = response.data["data"]
    assert data["status"] == PaymentStatus.PENDING
    assert data["provider"] == PaymentProvider.STRIPE
    assert Decimal(data["amount"]) == pending_order.total_price
    assert data["transaction_ref"] is None
    assert data["paid_at"] is None


@pytest.mark.django_db
def test_initiate_payment_with_twint(auth_client, pending_order):
    """Twint must be accepted as a valid provider with the same shell behaviour as Stripe."""
    response = auth_client.post(
        reverse("payment", kwargs={"order_number": pending_order.order_number}),
        {"provider": PaymentProvider.TWINT},
    )
    assert response.status_code == 201
    data = response.data["data"]
    assert data["provider"] == PaymentProvider.TWINT
    assert data["status"] == PaymentStatus.PENDING
    assert Decimal(data["amount"]) == pending_order.total_price


@pytest.mark.django_db
def test_initiate_payment_requires_auth(client, pending_order, stripe_payload):
    response = client.post(
        reverse("payment", kwargs={"order_number": pending_order.order_number}),
        stripe_payload,
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_initiate_payment_on_other_users_order_returns_404(pending_order, stripe_payload):
    """Non-owner gets 404 to avoid leaking order existence."""
    from uuid import uuid4
    from shoplane.models import User
    stranger = User.objects.create_user(
        email=f"stranger-{uuid4().hex[:6]}@example.com",
        password="StrongPass123!", first_name="S", last_name="T",
    )
    c = APIClient()
    c.force_authenticate(user=stranger)
    response = c.post(
        reverse("payment", kwargs={"order_number": pending_order.order_number}),
        stripe_payload,
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_initiate_payment_duplicate_returns_409(auth_client, pending_order, stripe_payload):
    """Cannot initiate a second payment for the same order."""
    auth_client.post(
        reverse("payment", kwargs={"order_number": pending_order.order_number}),
        stripe_payload,
    )
    response = auth_client.post(
        reverse("payment", kwargs={"order_number": pending_order.order_number}),
        stripe_payload,
    )
    assert response.status_code == 409


@pytest.mark.django_db
def test_initiate_payment_on_cancelled_order_returns_400(auth_client, pending_order, stripe_payload):
    pending_order.status = OrderStatus.CANCELLED
    pending_order.save()
    response = auth_client.post(
        reverse("payment", kwargs={"order_number": pending_order.order_number}),
        stripe_payload,
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_initiate_payment_invalid_provider_returns_400(auth_client, pending_order):
    response = auth_client.post(
        reverse("payment", kwargs={"order_number": pending_order.order_number}),
        {"provider": "PAYPAL"},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_initiate_payment_missing_provider_returns_400(auth_client, pending_order):
    response = auth_client.post(
        reverse("payment", kwargs={"order_number": pending_order.order_number}),
        {},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /orders/{order_number}/payment/ -- retrieve payment
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_retrieve_payment(auth_client, pending_order, stripe_payload):
    auth_client.post(
        reverse("payment", kwargs={"order_number": pending_order.order_number}),
        stripe_payload,
    )
    response = auth_client.get(
        reverse("payment", kwargs={"order_number": pending_order.order_number})
    )
    assert response.status_code == 200
    assert response.data["data"]["provider"] == PaymentProvider.STRIPE


@pytest.mark.django_db
def test_retrieve_payment_before_initiation_returns_404(auth_client, pending_order):
    response = auth_client.get(
        reverse("payment", kwargs={"order_number": pending_order.order_number})
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_retrieve_payment_requires_auth(client, pending_order):
    response = client.get(
        reverse("payment", kwargs={"order_number": pending_order.order_number})
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_retrieve_payment_for_nonexistent_order_returns_404(auth_client):
    response = auth_client.get(
        reverse("payment", kwargs={"order_number": "ORD-DOESNOTEXIST"})
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /orders/{order_number}/payment/logs/ -- payment logs (admin only)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_get_payment_logs_as_admin(admin_client, pending_order, admin_user):
    payment = Payment.objects.create(
        order=pending_order,
        provider=PaymentProvider.STRIPE,
        amount=pending_order.total_price,
        updated_by=admin_user,
    )
    PaymentLog.objects.create(
        payment=payment,
        event_type=PaymentLogEventType.INFO,
        message="Payment initiated",
    )
    response = admin_client.get(
        reverse("payment-logs", kwargs={"order_number": pending_order.order_number})
    )
    assert response.status_code == 200
    assert len(response.data["data"]) == 1
    assert response.data["data"][0]["message"] == "Payment initiated"


@pytest.mark.django_db
def test_get_payment_logs_requires_admin(auth_client, pending_order):
    response = auth_client.get(
        reverse("payment-logs", kwargs={"order_number": pending_order.order_number})
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_get_payment_logs_requires_auth(client, pending_order):
    response = client.get(
        reverse("payment-logs", kwargs={"order_number": pending_order.order_number})
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_get_payment_logs_before_payment_returns_404(admin_client, pending_order):
    response = admin_client.get(
        reverse("payment-logs", kwargs={"order_number": pending_order.order_number})
    )
    assert response.status_code == 404
