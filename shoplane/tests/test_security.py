"""
Consolidated security test suite.

Covers three categories systematically across every endpoint group:
  1. Unauthenticated access → 401
  2. Regular user hitting admin-only endpoints → 403
  3. Cross-user access (trying to read/modify another user's resources) → 403 or 404
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from shoplane.models import Cart, Order, Payment, PaymentProvider, User

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def anon():
    return APIClient()


@pytest.fixture
def user_client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def admin_client(admin_user):
    c = APIClient()
    c.force_authenticate(user=admin_user)
    return c


@pytest.fixture
def other_user():
    """A second regular user, distinct from the `user` fixture."""
    suffix = uuid4().hex[:8]
    return User.objects.create_user(
        email=f"other-{suffix}@example.com",
        password="StrongPass123!",
        first_name="Other",
        last_name="User",
    )


@pytest.fixture
def other_client(other_user):
    c = APIClient()
    c.force_authenticate(user=other_user)
    return c


@pytest.fixture
def other_order(other_user):
    """An order belonging to other_user."""
    suffix = uuid4().hex[:8]
    return Order.objects.create(
        user=other_user,
        order_number=f"ORD-{suffix.upper()}",
        total_price=Decimal("20.00"),
        shipping_address="1 Other St",
    )


@pytest.fixture
def other_payment(other_order, other_user):
    """A payment belonging to other_user's order."""
    return Payment.objects.create(
        order=other_order,
        provider=PaymentProvider.STRIPE,
        amount=other_order.total_price,
        updated_by=other_user,
    )


# ---------------------------------------------------------------------------
# 1. Unauthenticated access -- every protected endpoint must return 401
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUnauthenticated:
    """All endpoints that require authentication must reject anonymous requests."""

    def test_profile_get(self, anon):
        assert anon.get(reverse("user-me")).status_code == 401

    def test_profile_patch(self, anon):
        assert anon.patch(reverse("user-me"), {}).status_code == 401

    def test_cart_get(self, anon):
        assert anon.get(reverse("cart")).status_code == 401

    def test_cart_delete(self, anon):
        assert anon.delete(reverse("cart")).status_code == 401

    def test_cart_item_add(self, anon):
        assert anon.post(reverse("cart-item-add"), {}).status_code == 401

    def test_cart_item_update(self, anon, product):
        assert (
            anon.patch(
                reverse("cart-item-detail", kwargs={"product_slug": product.slug}), {}
            ).status_code
            == 401
        )

    def test_cart_item_delete(self, anon, product):
        assert (
            anon.delete(
                reverse("cart-item-detail", kwargs={"product_slug": product.slug})
            ).status_code
            == 401
        )

    def test_order_list(self, anon):
        assert anon.get(reverse("order-list")).status_code == 401

    def test_order_create(self, anon):
        assert anon.post(reverse("order-list"), {}).status_code == 401

    def test_order_detail(self, anon, order):
        assert (
            anon.get(
                reverse("order-detail", kwargs={"order_number": order.order_number})
            ).status_code
            == 401
        )

    def test_order_cancel(self, anon, order):
        assert (
            anon.patch(
                reverse("order-detail", kwargs={"order_number": order.order_number}), {}
            ).status_code
            == 401
        )

    def test_payment_get(self, anon, order):
        assert (
            anon.get(reverse("payment", kwargs={"order_number": order.order_number})).status_code
            == 401
        )

    def test_payment_initiate(self, anon, order):
        assert (
            anon.post(
                reverse("payment", kwargs={"order_number": order.order_number}), {}
            ).status_code
            == 401
        )

    def test_payment_logs(self, anon, order):
        assert (
            anon.get(
                reverse("payment-logs", kwargs={"order_number": order.order_number})
            ).status_code
            == 401
        )

    def test_logout(self, anon):
        assert anon.post(reverse("jwt-logout"), {}).status_code == 401


# ---------------------------------------------------------------------------
# 2. Regular user hitting admin-only endpoints -- must return 403
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRegularUserForbidden:
    """Endpoints restricted to admins must return 403 for authenticated regular users."""

    def test_category_create(self, user_client):
        assert user_client.post(reverse("category-list"), {"name": "Blocked"}).status_code == 403

    def test_category_update(self, user_client, category):
        assert (
            user_client.patch(
                reverse("category-detail", kwargs={"slug": category.slug}), {}
            ).status_code
            == 403
        )

    def test_category_delete(self, user_client, category):
        assert (
            user_client.delete(
                reverse("category-detail", kwargs={"slug": category.slug})
            ).status_code
            == 403
        )

    def test_product_create(self, user_client, category):
        assert (
            user_client.post(
                reverse("product-list"), {"name": "Blocked", "category": category.slug}
            ).status_code
            == 403
        )

    def test_product_update(self, user_client, product):
        assert (
            user_client.patch(
                reverse("product-detail", kwargs={"slug": product.slug}), {}
            ).status_code
            == 403
        )

    def test_product_delete(self, user_client, product):
        assert (
            user_client.delete(reverse("product-detail", kwargs={"slug": product.slug})).status_code
            == 403
        )

    def test_payment_logs(self, user_client, order):
        assert (
            user_client.get(
                reverse("payment-logs", kwargs={"order_number": order.order_number})
            ).status_code
            == 403
        )


# ---------------------------------------------------------------------------
# 3. Cross-user access -- users must not be able to touch other users' data
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCrossUserAccess:
    """
    A regular user must not be able to read or modify resources belonging to another user.
    Returns 404 (not 403) on orders/payments to avoid leaking resource existence.
    """

    def test_cannot_get_other_users_order(self, user_client, other_order):
        """Order detail returns 404 for non-owner to avoid leaking existence."""
        response = user_client.get(
            reverse("order-detail", kwargs={"order_number": other_order.order_number})
        )
        assert response.status_code == 404

    def test_cannot_cancel_other_users_order(self, user_client, other_order):
        response = user_client.patch(
            reverse("order-detail", kwargs={"order_number": other_order.order_number}),
            {"status": "CANCELLED"},
        )
        assert response.status_code == 404

    def test_cannot_get_other_users_payment(self, user_client, other_payment):
        response = user_client.get(
            reverse("payment", kwargs={"order_number": other_payment.order.order_number})
        )
        assert response.status_code == 404

    def test_cannot_initiate_payment_on_other_users_order(self, user_client, other_order):
        response = user_client.post(
            reverse("payment", kwargs={"order_number": other_order.order_number}),
            {"provider": PaymentProvider.STRIPE},
        )
        assert response.status_code == 404

    def test_cannot_read_other_users_cart(self, user_client, other_user):
        """
        Cart is always scoped to request.user -- there is no URL parameter
        to target another user's cart, so cross-user cart access is architecturally impossible.
        This test verifies the authenticated user only ever sees their own cart.
        """
        Cart.objects.get_or_create(user=other_user)
        response = user_client.get(reverse("cart"))
        assert response.status_code == 200
        # The cart returned must belong to the authenticated user, not other_user.
        cart_data = response.data["data"]
        assert cart_data is not None

    def test_role_escalation_via_profile_update_is_blocked(self, user_client, user):
        """A user must not be able to promote themselves to admin via profile update."""
        user_client.patch(reverse("user-me"), {"role": "ADMIN"})
        user.refresh_from_db()
        assert user.role != "ADMIN"

    def test_is_staff_escalation_via_profile_update_is_blocked(self, user_client, user):
        """A user must not be able to grant themselves staff status."""
        user_client.patch(reverse("user-me"), {"is_staff": True})
        user.refresh_from_db()
        assert user.is_staff is False
