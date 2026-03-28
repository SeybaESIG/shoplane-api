"""
Additional gap tests — edge cases not covered by the main test suites.

Covers:
  - New DB constraints (stock >= 0, quantity >= 1)
  - Cart.add_product() boundary conditions
  - Order checkout blocked when product becomes inactive or soft-deleted
  - Expired JWT access token returns 401
  - Response envelope format consistency across all error codes
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from shoplane.models import (
    Cart,
    CartItem,
    Category,
    Order,
    OrderItem,
    Product,
    User,
)


# ---------------------------------------------------------------------------
# DB constraint: CartItem quantity >= 1
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_cart_item_quantity_zero_violates_constraint(cart, product):
    """DB must reject a CartItem with quantity=0."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CartItem.objects.create(
                cart=cart,
                product=product,
                quantity=0,
                unit_price=product.price,
                subtotal=Decimal("0.00"),
            )


# ---------------------------------------------------------------------------
# DB constraint: OrderItem quantity >= 1
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_order_item_quantity_zero_violates_constraint(order, product):
    """DB must reject an OrderItem with quantity=0."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=0,
                unit_price=product.price,
                subtotal=Decimal("0.00"),
            )


# ---------------------------------------------------------------------------
# DB constraint: Product stock >= 0
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_product_stock_cannot_go_negative(product):
    """DB must reject a product stock update that would result in a negative value."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            product.stock = -1
            product.save(update_fields=["stock"])


# ---------------------------------------------------------------------------
# Cart.add_product() boundary conditions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_add_product_with_zero_quantity_raises_value_error(cart, product):
    with pytest.raises(ValueError, match="Quantity must be greater than zero"):
        cart.add_product(product=product, quantity=0)


@pytest.mark.django_db
def test_add_product_with_negative_quantity_raises_value_error(cart, product):
    with pytest.raises(ValueError, match="Quantity must be greater than zero"):
        cart.add_product(product=product, quantity=-3)


@pytest.mark.django_db
def test_add_product_first_call_creates_item_with_correct_quantity(cart, product):
    """First call to add_product must not produce an intermediate row with quantity=0."""
    item, created = cart.add_product(product=product, quantity=2)
    assert created is True
    assert item.quantity == 2
    assert item.subtotal == product.price * 2


@pytest.mark.django_db
def test_add_product_second_call_accumulates_quantity(cart, product):
    cart.add_product(product=product, quantity=1)
    item, created = cart.add_product(product=product, quantity=3)
    assert created is False
    assert item.quantity == 4
    cart.refresh_from_db()
    assert cart.total_price == product.price * 4


# ---------------------------------------------------------------------------
# Order checkout: product deactivated or soft-deleted after add-to-cart
# ---------------------------------------------------------------------------

@pytest.fixture
def checkout_client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.mark.django_db
def test_checkout_blocked_when_product_becomes_inactive(checkout_client, user, category, admin_user):
    """
    If a product is deactivated between add-to-cart and checkout,
    the order creation must be rejected with 400.
    """
    p = Product.objects.create(
        name="Goes Inactive",
        category=category,
        price=Decimal("9.99"),
        stock=5,
        is_active=True,
        updated_by=admin_user,
    )
    cart = Cart.objects.get_or_create(user=user)[0]
    cart.add_product(product=p, quantity=1)

    p.is_active = False
    p.save(update_fields=["is_active"])

    response = checkout_client.post(
        reverse("order-list"), {"shipping_address": "5 Test Rd"}
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_checkout_blocked_when_product_is_soft_deleted(checkout_client, user, category, admin_user):
    """
    If a product is soft-deleted between add-to-cart and checkout,
    the order creation must be rejected with 400.
    """
    p = Product.objects.create(
        name="Soon Deleted",
        category=category,
        price=Decimal("14.99"),
        stock=5,
        is_active=True,
        updated_by=admin_user,
    )
    cart = Cart.objects.get_or_create(user=user)[0]
    cart.add_product(product=p, quantity=1)

    p.is_deleted = True
    p.save(update_fields=["is_deleted"])

    response = checkout_client.post(
        reverse("order-list"), {"shipping_address": "5 Test Rd"}
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Expired JWT access token → 401
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_expired_access_token_returns_401():
    """A token with a past expiry must be rejected with 401 and envelope format."""
    from rest_framework_simplejwt.tokens import AccessToken

    u = User.objects.create_user(
        email="expired-token@example.com",
        password="StrongPass123!",
        first_name="Exp",
        last_name="Ired",
    )
    token = AccessToken.for_user(u)
    token.set_exp(from_time=timezone.now() - timedelta(hours=2))

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    response = client.get(reverse("user-me"))

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert "message" in body


# ---------------------------------------------------------------------------
# Response envelope consistency across error codes
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_401_error_uses_envelope_format():
    client = APIClient()
    response = client.get(reverse("cart"))
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert "message" in body


@pytest.mark.django_db
def test_403_error_uses_envelope_format(user):
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(reverse("category-list"), {"name": "Blocked"})
    assert response.status_code == 403
    body = response.json()
    assert body["success"] is False
    assert "message" in body


@pytest.mark.django_db
def test_404_error_uses_envelope_format(user):
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get(
        reverse("order-detail", kwargs={"order_number": "ORD-DOESNOTEXIST"})
    )
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert "message" in body


@pytest.mark.django_db
def test_400_error_uses_envelope_format():
    client = APIClient()
    response = client.post(
        "/api/v1/auth/login/",
        {"email": "notanemail", "password": ""},
        format="json",
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert "message" in body
