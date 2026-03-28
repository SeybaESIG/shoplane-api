from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from shoplane.models import Cart, CartItem, CartStatus


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def auth_client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def other_client(django_db_setup):
    """A second authenticated user with their own client."""
    from shoplane.models import User

    other = User.objects.create_user(
        email="other@example.com",
        password="StrongPass123!",
        first_name="Other",
        last_name="User",
    )
    c = APIClient()
    c.force_authenticate(user=other)
    return c


# ---------------------------------------------------------------------------
# GET /cart/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_cart_auto_creates_cart(auth_client):
    """Cart should be auto-created on first GET if it doesn't exist yet."""
    response = auth_client.get(reverse("cart"))
    assert response.status_code == 200
    assert response.data["data"]["status"] == CartStatus.OPEN
    assert response.data["data"]["items"] == []
    assert Decimal(response.data["data"]["total_price"]) == Decimal("0.00")


@pytest.mark.django_db
def test_get_cart_requires_auth(client):
    response = client.get(reverse("cart"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_get_cart_returns_items(auth_client, user, product):
    cart = Cart.objects.get_or_create(user=user)[0]
    cart.add_product(product=product, quantity=2)
    response = auth_client.get(reverse("cart"))
    assert response.status_code == 200
    assert len(response.data["data"]["items"]) == 1
    assert response.data["data"]["items"][0]["product_slug"] == product.slug
    assert response.data["data"]["items"][0]["quantity"] == 2


# ---------------------------------------------------------------------------
# POST /cart/items/ -- add item
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_add_item_to_cart(auth_client, product):
    response = auth_client.post(
        reverse("cart-item-add"),
        {"product_slug": product.slug, "quantity": 1},
    )
    assert response.status_code == 200
    assert len(response.data["data"]["items"]) == 1
    assert Decimal(response.data["data"]["total_price"]) == product.price


@pytest.mark.django_db
def test_add_item_increments_quantity_if_already_in_cart(auth_client, user, product):
    """Adding the same product twice accumulates quantity."""
    cart = Cart.objects.get_or_create(user=user)[0]
    cart.add_product(product=product, quantity=1)
    response = auth_client.post(
        reverse("cart-item-add"),
        {"product_slug": product.slug, "quantity": 2},
    )
    assert response.status_code == 200
    items = response.data["data"]["items"]
    assert items[0]["quantity"] == 3
    assert CartItem.objects.filter(cart=cart, product=product).count() == 1


@pytest.mark.django_db
def test_add_item_requires_auth(client, product):
    response = client.post(
        reverse("cart-item-add"),
        {"product_slug": product.slug, "quantity": 1},
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_add_nonexistent_product_returns_400(auth_client):
    response = auth_client.post(
        reverse("cart-item-add"),
        {"product_slug": "ghost-product", "quantity": 1},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_add_inactive_product_returns_400(auth_client, category, user):
    from shoplane.models import Product

    inactive = Product.objects.create(
        name="Inactive Item",
        category=category,
        price=Decimal("5.00"),
        stock=10,
        is_active=False,
        updated_by=user,
    )
    response = auth_client.post(
        reverse("cart-item-add"),
        {"product_slug": inactive.slug, "quantity": 1},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_add_item_exceeding_stock_returns_400(auth_client, product):
    response = auth_client.post(
        reverse("cart-item-add"),
        {"product_slug": product.slug, "quantity": product.stock + 1},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_add_item_zero_quantity_returns_400(auth_client, product):
    response = auth_client.post(
        reverse("cart-item-add"),
        {"product_slug": product.slug, "quantity": 0},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_add_item_to_submitted_cart_returns_403(auth_client, user, product):
    """A submitted cart cannot be modified."""
    cart = Cart.objects.get_or_create(user=user)[0]
    cart.status = CartStatus.SUBMITTED
    cart.save()
    response = auth_client.post(
        reverse("cart-item-add"),
        {"product_slug": product.slug, "quantity": 1},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /cart/items/{product_slug}/ -- update quantity
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_update_item_quantity(auth_client, user, product):
    cart = Cart.objects.get_or_create(user=user)[0]
    cart.add_product(product=product, quantity=1)
    response = auth_client.patch(
        reverse("cart-item-detail", kwargs={"product_slug": product.slug}),
        {"quantity": 3},
    )
    assert response.status_code == 200
    items = response.data["data"]["items"]
    assert items[0]["quantity"] == 3
    assert Decimal(items[0]["subtotal"]) == product.price * 3


@pytest.mark.django_db
def test_update_item_recomputes_cart_total(auth_client, user, product):
    cart = Cart.objects.get_or_create(user=user)[0]
    cart.add_product(product=product, quantity=1)
    auth_client.patch(
        reverse("cart-item-detail", kwargs={"product_slug": product.slug}),
        {"quantity": 5},
    )
    cart.refresh_from_db()
    assert cart.total_price == product.price * 5


@pytest.mark.django_db
def test_update_item_exceeding_stock_returns_400(auth_client, user, product):
    cart = Cart.objects.get_or_create(user=user)[0]
    cart.add_product(product=product, quantity=1)
    response = auth_client.patch(
        reverse("cart-item-detail", kwargs={"product_slug": product.slug}),
        {"quantity": product.stock + 1},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_update_nonexistent_item_returns_404(auth_client, product):
    response = auth_client.patch(
        reverse("cart-item-detail", kwargs={"product_slug": product.slug}),
        {"quantity": 1},
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_update_item_requires_auth(client, product):
    response = client.patch(
        reverse("cart-item-detail", kwargs={"product_slug": product.slug}),
        {"quantity": 1},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /cart/items/{product_slug}/ -- remove item
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_remove_item_from_cart(auth_client, user, product):
    cart = Cart.objects.get_or_create(user=user)[0]
    cart.add_product(product=product, quantity=2)
    response = auth_client.delete(
        reverse("cart-item-detail", kwargs={"product_slug": product.slug})
    )
    assert response.status_code == 200
    assert response.data["data"]["items"] == []
    assert Decimal(response.data["data"]["total_price"]) == Decimal("0.00")


@pytest.mark.django_db
def test_remove_nonexistent_item_returns_404(auth_client, product):
    response = auth_client.delete(
        reverse("cart-item-detail", kwargs={"product_slug": product.slug})
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_remove_item_requires_auth(client, product):
    response = client.delete(reverse("cart-item-detail", kwargs={"product_slug": product.slug}))
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /cart/ -- clear cart
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_clear_cart(auth_client, user, product):
    cart = Cart.objects.get_or_create(user=user)[0]
    cart.add_product(product=product, quantity=3)
    response = auth_client.delete(reverse("cart"))
    assert response.status_code == 200
    assert response.data["data"]["items"] == []
    assert Decimal(response.data["data"]["total_price"]) == Decimal("0.00")


@pytest.mark.django_db
def test_clear_cart_requires_auth(client):
    response = client.delete(reverse("cart"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_clear_submitted_cart_returns_403(auth_client, user, product):
    cart = Cart.objects.get_or_create(user=user)[0]
    cart.add_product(product=product, quantity=1)
    cart.status = CartStatus.SUBMITTED
    cart.save()
    response = auth_client.delete(reverse("cart"))
    assert response.status_code == 403
