import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from shoplane.models import Category


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


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_list_categories_is_public(client, category):
    response = client.get(reverse("category-list"))
    assert response.status_code == 200
    assert response.data["success"] is True
    assert any(c["slug"] == category.slug for c in response.data["data"])


@pytest.mark.django_db
def test_list_only_returns_active_categories(client, user):
    active = Category.objects.create(name="Active Cat", updated_by=user)
    inactive = Category.objects.create(name="Inactive Cat", is_active=False, updated_by=user)
    response = client.get(reverse("category-list"))
    slugs = [c["slug"] for c in response.data["data"]]
    assert active.slug in slugs
    assert inactive.slug not in slugs


# ---------------------------------------------------------------------------
# RETRIEVE
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_retrieve_category_is_public(client, category):
    response = client.get(reverse("category-detail", kwargs={"slug": category.slug}))
    assert response.status_code == 200
    assert response.data["data"]["slug"] == category.slug


@pytest.mark.django_db
def test_retrieve_inactive_category_returns_404(client, user):
    cat = Category.objects.create(name="Hidden Cat", is_active=False, updated_by=user)
    response = client.get(reverse("category-detail", kwargs={"slug": cat.slug}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_retrieve_nonexistent_category_returns_404(client):
    response = client.get(reverse("category-detail", kwargs={"slug": "does-not-exist"}))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_create_category_as_admin(admin_client):
    response = admin_client.post(reverse("category-list"), {"name": "New Category"})
    assert response.status_code == 201
    assert response.data["data"]["slug"] == "new-category"


@pytest.mark.django_db
def test_create_category_requires_admin(auth_client):
    response = auth_client.post(reverse("category-list"), {"name": "Blocked"})
    assert response.status_code == 403


@pytest.mark.django_db
def test_create_category_requires_auth(client):
    response = client.post(reverse("category-list"), {"name": "Blocked"})
    assert response.status_code == 401


@pytest.mark.django_db
def test_create_category_duplicate_name_is_rejected(admin_client, category):
    response = admin_client.post(reverse("category-list"), {"name": category.name})
    assert response.status_code == 400


@pytest.mark.django_db
def test_create_category_duplicate_name_case_insensitive(admin_client, category):
    response = admin_client.post(reverse("category-list"), {"name": category.name.upper()})
    assert response.status_code == 400


@pytest.mark.django_db
def test_create_category_without_name_is_rejected(admin_client):
    response = admin_client.post(reverse("category-list"), {})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# PARTIAL UPDATE
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_update_category_as_admin(admin_client, category):
    response = admin_client.patch(
        reverse("category-detail", kwargs={"slug": category.slug}),
        {"description": "Updated description"},
    )
    assert response.status_code == 200
    assert response.data["data"]["description"] == "Updated description"


@pytest.mark.django_db
def test_update_category_requires_admin(auth_client, category):
    response = auth_client.patch(
        reverse("category-detail", kwargs={"slug": category.slug}),
        {"description": "Blocked"},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_update_category_name_duplicate_rejected(admin_client, user):
    existing = Category.objects.create(name="Already Exists", updated_by=user)
    other = Category.objects.create(name="Other Category", updated_by=user)
    response = admin_client.patch(
        reverse("category-detail", kwargs={"slug": other.slug}),
        {"name": existing.name},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_delete_category_as_admin(admin_client, user):
    cat = Category.objects.create(name="To Delete", updated_by=user)
    response = admin_client.delete(reverse("category-detail", kwargs={"slug": cat.slug}))
    assert response.status_code == 200
    assert not Category.objects.filter(slug=cat.slug).exists()


@pytest.mark.django_db
def test_delete_category_with_products_returns_409(admin_client, category, product):
    response = admin_client.delete(reverse("category-detail", kwargs={"slug": category.slug}))
    assert response.status_code == 409
    assert response.data["success"] is False


@pytest.mark.django_db
def test_delete_category_requires_admin(auth_client, category):
    response = auth_client.delete(reverse("category-detail", kwargs={"slug": category.slug}))
    assert response.status_code == 403
