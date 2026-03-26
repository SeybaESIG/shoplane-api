from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from shoplane.models import Cart, CartStatus, Order, OrderStatus, Product


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
def open_cart_with_product(user, product):
    """Cart with one item ready for checkout."""
    cart = Cart.objects.get_or_create(user=user)[0]
    cart.add_product(product=product, quantity=2)
    return cart


@pytest.fixture
def checkout_payload():
    return {"shipping_address": "10 Test Avenue"}


# ---------------------------------------------------------------------------
# POST /orders/ -- create order
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_create_order_from_cart(auth_client, open_cart_with_product, checkout_payload, product):
    initial_stock = product.stock
    response = auth_client.post(reverse("order-list"), checkout_payload)
    assert response.status_code == 201
    data = response.data["data"]
    assert data["status"] == OrderStatus.PENDING
    assert data["shipping_address"] == "10 Test Avenue"
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 2
    # Stock must be decremented
    product.refresh_from_db()
    assert product.stock == initial_stock - 2


@pytest.mark.django_db
def test_create_order_sets_billing_address_to_shipping_when_omitted(
    auth_client, open_cart_with_product, checkout_payload
):
    response = auth_client.post(reverse("order-list"), checkout_payload)
    data = response.data["data"]
    assert data["billing_address"] == checkout_payload["shipping_address"]


@pytest.mark.django_db
def test_create_order_accepts_separate_billing_address(
    auth_client, open_cart_with_product
):
    response = auth_client.post(reverse("order-list"), {
        "shipping_address": "10 Ship St",
        "billing_address": "20 Bill Ave",
    })
    assert response.status_code == 201
    assert response.data["data"]["billing_address"] == "20 Bill Ave"


@pytest.mark.django_db
def test_create_order_converts_cart(auth_client, open_cart_with_product, checkout_payload, user):
    auth_client.post(reverse("order-list"), checkout_payload)
    open_cart_with_product.refresh_from_db()
    assert open_cart_with_product.status == CartStatus.CONVERTED


@pytest.mark.django_db
def test_create_order_requires_auth(client, open_cart_with_product, checkout_payload):
    response = client.post(reverse("order-list"), checkout_payload)
    assert response.status_code == 401


@pytest.mark.django_db
def test_create_order_with_empty_cart_returns_400(auth_client, user, checkout_payload):
    Cart.objects.get_or_create(user=user)
    response = auth_client.post(reverse("order-list"), checkout_payload)
    assert response.status_code == 400


@pytest.mark.django_db
def test_create_order_without_cart_returns_400(auth_client, checkout_payload):
    response = auth_client.post(reverse("order-list"), checkout_payload)
    assert response.status_code == 400


@pytest.mark.django_db
def test_create_order_missing_shipping_address_returns_400(
    auth_client, open_cart_with_product
):
    response = auth_client.post(reverse("order-list"), {})
    assert response.status_code == 400


@pytest.mark.django_db
def test_create_order_with_blank_shipping_address_returns_400(
    auth_client, open_cart_with_product
):
    response = auth_client.post(reverse("order-list"), {"shipping_address": "   "})
    assert response.status_code == 400


@pytest.mark.django_db
def test_create_order_with_insufficient_stock_returns_400(
    auth_client, user, category, admin_user, checkout_payload
):
    """Stock check at checkout time blocks order if stock dropped since add-to-cart."""
    low_stock = Product.objects.create(
        name="Low Stock Item", category=category,
        price=Decimal("10.00"), stock=1, updated_by=admin_user,
    )
    cart = Cart.objects.get_or_create(user=user)[0]
    cart.add_product(product=low_stock, quantity=1)
    # Simulate stock being depleted between add-to-cart and checkout.
    low_stock.stock = 0
    low_stock.save()
    response = auth_client.post(reverse("order-list"), checkout_payload)
    assert response.status_code == 400


@pytest.mark.django_db
def test_create_order_with_converted_cart_returns_400(
    auth_client, open_cart_with_product, checkout_payload
):
    """Cannot check out an already-converted cart."""
    open_cart_with_product.status = CartStatus.CONVERTED
    open_cart_with_product.save()
    response = auth_client.post(reverse("order-list"), checkout_payload)
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /orders/ -- list orders
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_list_orders_returns_own_orders_only(
    auth_client, open_cart_with_product, checkout_payload, user
):
    auth_client.post(reverse("order-list"), checkout_payload)
    response = auth_client.get(reverse("order-list"))
    assert response.status_code == 200
    assert len(response.data["data"]) == 1


@pytest.mark.django_db
def test_list_orders_requires_auth(client):
    response = client.get(reverse("order-list"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_admin_can_list_all_orders(admin_client, order):
    response = admin_client.get(reverse("order-list"))
    assert response.status_code == 200
    assert any(o["order_number"] == order.order_number for o in response.data["data"])


# ---------------------------------------------------------------------------
# GET /orders/{order_number}/ -- retrieve order
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_retrieve_own_order(auth_client, open_cart_with_product, checkout_payload):
    create_resp = auth_client.post(reverse("order-list"), checkout_payload)
    order_number = create_resp.data["data"]["order_number"]
    response = auth_client.get(reverse("order-detail", kwargs={"order_number": order_number}))
    assert response.status_code == 200
    assert response.data["data"]["order_number"] == order_number


@pytest.mark.django_db
def test_retrieve_other_users_order_returns_404(admin_user, category):
    """Non-owner gets 404 (not 403) to avoid leaking order existence."""
    from uuid import uuid4
    from shoplane.models import User, Order, OrderStatus
    # Create two separate users with separate clients.
    owner = User.objects.create_user(
        email=f"owner-{uuid4().hex[:6]}@example.com",
        password="StrongPass123!", first_name="Owner", last_name="User",
    )
    stranger = User.objects.create_user(
        email=f"stranger-{uuid4().hex[:6]}@example.com",
        password="StrongPass123!", first_name="Stranger", last_name="User",
    )
    owner_order = Order.objects.create(
        user=owner,
        order_number=f"ORD-{uuid4().hex[:12].upper()}",
        total_price=Decimal("10.00"),
        shipping_address="1 Owner St",
    )
    stranger_client = APIClient()
    stranger_client.force_authenticate(user=stranger)
    response = stranger_client.get(
        reverse("order-detail", kwargs={"order_number": owner_order.order_number})
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_admin_can_retrieve_any_order(admin_client, order):
    response = admin_client.get(
        reverse("order-detail", kwargs={"order_number": order.order_number})
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# PATCH /orders/{order_number}/ -- cancel order
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_user_can_cancel_order_within_window(
    auth_client, open_cart_with_product, checkout_payload, product
):
    create_resp = auth_client.post(reverse("order-list"), checkout_payload)
    order_number = create_resp.data["data"]["order_number"]
    product.refresh_from_db()
    stock_after_order = product.stock

    response = auth_client.patch(
        reverse("order-detail", kwargs={"order_number": order_number}),
        {"status": "CANCELLED"},
    )
    assert response.status_code == 200
    assert response.data["data"]["status"] == OrderStatus.CANCELLED
    # Stock must be restored
    product.refresh_from_db()
    assert product.stock == stock_after_order + 2


@pytest.mark.django_db
def test_user_cannot_cancel_order_after_window(
    auth_client, open_cart_with_product, checkout_payload
):
    create_resp = auth_client.post(reverse("order-list"), checkout_payload)
    order_number = create_resp.data["data"]["order_number"]

    # Backdate the order past the 24-hour window.
    order = Order.objects.get(order_number=order_number)
    order.created_at = timezone.now() - timedelta(hours=25)
    order.save(update_fields=["created_at"])

    response = auth_client.patch(
        reverse("order-detail", kwargs={"order_number": order_number}),
        {"status": "CANCELLED"},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_can_cancel_order_after_window(
    admin_client, order
):
    """Admins bypass the 24-hour window."""
    order.created_at = timezone.now() - timedelta(hours=48)
    order.save(update_fields=["created_at"])
    response = admin_client.patch(
        reverse("order-detail", kwargs={"order_number": order.order_number}),
        {"status": "CANCELLED"},
    )
    assert response.status_code == 200
    assert response.data["data"]["status"] == OrderStatus.CANCELLED


@pytest.mark.django_db
def test_cancel_already_cancelled_order_returns_400(
    auth_client, open_cart_with_product, checkout_payload
):
    create_resp = auth_client.post(reverse("order-list"), checkout_payload)
    order_number = create_resp.data["data"]["order_number"]
    auth_client.patch(
        reverse("order-detail", kwargs={"order_number": order_number}),
        {"status": "CANCELLED"},
    )
    response = auth_client.patch(
        reverse("order-detail", kwargs={"order_number": order_number}),
        {"status": "CANCELLED"},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_invalid_status_transition_returns_400(
    auth_client, open_cart_with_product, checkout_payload
):
    create_resp = auth_client.post(reverse("order-list"), checkout_payload)
    order_number = create_resp.data["data"]["order_number"]
    response = auth_client.patch(
        reverse("order-detail", kwargs={"order_number": order_number}),
        {"status": "CONFIRMED"},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_cancel_order_requires_auth(client, order):
    response = client.patch(
        reverse("order-detail", kwargs={"order_number": order.order_number}),
        {"status": "CANCELLED"},
    )
    assert response.status_code == 401
