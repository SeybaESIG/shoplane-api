from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from shoplane.models import Product


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
def product_payload(category):
    """Valid payload for creating a product."""
    return {
        "name": "Test Product",
        "description": "A test product",
        "price": "29.99",
        "stock": 10,
        "category": category.slug,
    }


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_list_products_is_public(client, product):
    response = client.get(reverse("product-list"))
    assert response.status_code == 200
    assert response.data["success"] is True
    assert any(p["slug"] == product.slug for p in response.data["data"])


@pytest.mark.django_db
def test_list_excludes_inactive_products(client, category, user):
    inactive = Product.objects.create(
        name="Inactive Product",
        category=category,
        price=Decimal("9.99"),
        stock=5,
        is_active=False,
        updated_by=user,
    )
    response = client.get(reverse("product-list"))
    slugs = [p["slug"] for p in response.data["data"]]
    assert inactive.slug not in slugs


@pytest.mark.django_db
def test_list_excludes_soft_deleted_products(client, category, user):
    deleted = Product.objects.create(
        name="Deleted Product",
        category=category,
        price=Decimal("9.99"),
        stock=5,
        is_deleted=True,
        updated_by=user,
    )
    response = client.get(reverse("product-list"))
    slugs = [p["slug"] for p in response.data["data"]]
    assert deleted.slug not in slugs


@pytest.mark.django_db
def test_list_admin_all_param_returns_all_products(admin_client, category, admin_user):
    """Admin with ?all=true should see inactive and soft-deleted products."""
    inactive = Product.objects.create(
        name="Invisible Product",
        category=category,
        price=Decimal("9.99"),
        stock=5,
        is_active=False,
        updated_by=admin_user,
    )
    response = admin_client.get(reverse("product-list") + "?all=true")
    slugs = [p["slug"] for p in response.data["data"]]
    assert inactive.slug in slugs


# ---------------------------------------------------------------------------
# RETRIEVE
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_retrieve_product_is_public(client, product):
    response = client.get(reverse("product-detail", kwargs={"slug": product.slug}))
    assert response.status_code == 200
    assert response.data["data"]["slug"] == product.slug


@pytest.mark.django_db
def test_retrieve_inactive_product_returns_404_for_public(client, category, user):
    p = Product.objects.create(
        name="Hidden Product",
        category=category,
        price=Decimal("9.99"),
        stock=5,
        is_active=False,
        updated_by=user,
    )
    response = client.get(reverse("product-detail", kwargs={"slug": p.slug}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_retrieve_soft_deleted_product_returns_404_for_public(client, category, user):
    p = Product.objects.create(
        name="Gone Product",
        category=category,
        price=Decimal("9.99"),
        stock=5,
        is_deleted=True,
        updated_by=user,
    )
    response = client.get(reverse("product-detail", kwargs={"slug": p.slug}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_retrieve_nonexistent_product_returns_404(client):
    response = client.get(reverse("product-detail", kwargs={"slug": "does-not-exist"}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_retrieve_soft_deleted_product_visible_to_admin(admin_client, category, admin_user):
    p = Product.objects.create(
        name="Admin Visible",
        category=category,
        price=Decimal("9.99"),
        stock=5,
        is_deleted=True,
        updated_by=admin_user,
    )
    response = admin_client.get(reverse("product-detail", kwargs={"slug": p.slug}))
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_product_as_admin(admin_client, product_payload):
    response = admin_client.post(reverse("product-list"), product_payload)
    assert response.status_code == 201
    assert response.data["data"]["slug"] == "test-product"
    assert response.data["data"]["price"] == "29.99"


@pytest.mark.django_db
def test_create_product_requires_admin(auth_client, product_payload):
    response = auth_client.post(reverse("product-list"), product_payload)
    assert response.status_code == 403


@pytest.mark.django_db
def test_create_product_requires_auth(client, product_payload):
    response = client.post(reverse("product-list"), product_payload)
    assert response.status_code == 401


@pytest.mark.django_db
def test_create_product_with_negative_price_rejected(admin_client, product_payload):
    product_payload["price"] = "-5.00"
    response = admin_client.post(reverse("product-list"), product_payload)
    assert response.status_code == 400


@pytest.mark.django_db
def test_create_product_with_negative_stock_rejected(admin_client, product_payload):
    product_payload["stock"] = -1
    response = admin_client.post(reverse("product-list"), product_payload)
    assert response.status_code == 400


@pytest.mark.django_db
def test_create_product_with_inactive_category_rejected(admin_client, product_payload, category):
    """Category must be active. Inactive categories cannot receive new products."""
    category.is_active = False
    category.save()
    response = admin_client.post(reverse("product-list"), product_payload)
    assert response.status_code == 400


@pytest.mark.django_db
def test_create_product_missing_required_fields(admin_client):
    response = admin_client.post(reverse("product-list"), {})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# PARTIAL UPDATE
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_update_product_as_admin(admin_client, product):
    response = admin_client.patch(
        reverse("product-detail", kwargs={"slug": product.slug}),
        {"stock": 99},
    )
    assert response.status_code == 200
    assert response.data["data"]["stock"] == 99


@pytest.mark.django_db
def test_update_product_price(admin_client, product):
    response = admin_client.patch(
        reverse("product-detail", kwargs={"slug": product.slug}),
        {"price": "149.99"},
    )
    assert response.status_code == 200
    assert response.data["data"]["price"] == "149.99"


@pytest.mark.django_db
def test_update_product_requires_admin(auth_client, product):
    response = auth_client.patch(
        reverse("product-detail", kwargs={"slug": product.slug}),
        {"stock": 1},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_update_product_negative_price_rejected(admin_client, product):
    response = admin_client.patch(
        reverse("product-detail", kwargs={"slug": product.slug}),
        {"price": "-10.00"},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_update_product_negative_stock_rejected(admin_client, product):
    response = admin_client.patch(
        reverse("product-detail", kwargs={"slug": product.slug}),
        {"stock": -1},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# SOFT DELETE
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_soft_delete_product_as_admin(admin_client, product):
    response = admin_client.delete(reverse("product-detail", kwargs={"slug": product.slug}))
    assert response.status_code == 200
    product.refresh_from_db()
    assert product.is_deleted is True


@pytest.mark.django_db
def test_soft_deleted_product_no_longer_visible_publicly(admin_client, client, product):
    admin_client.delete(reverse("product-detail", kwargs={"slug": product.slug}))
    response = client.get(reverse("product-detail", kwargs={"slug": product.slug}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_soft_delete_requires_admin(auth_client, product):
    response = auth_client.delete(reverse("product-detail", kwargs={"slug": product.slug}))
    assert response.status_code == 403
