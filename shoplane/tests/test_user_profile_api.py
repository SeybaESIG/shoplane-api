import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from shoplane.models import User


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def auth_client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ---------------------------------------------------------------------------
# GET /users/me/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_get_profile_returns_own_data(auth_client, user):
    response = auth_client.get(reverse("user-me"))
    assert response.status_code == 200
    assert response.data["data"]["email"] == user.email
    assert response.data["data"]["first_name"] == user.first_name


@pytest.mark.django_db
def test_get_profile_requires_auth(client):
    response = client.get(reverse("user-me"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_get_profile_excludes_sensitive_fields(auth_client):
    """Password, is_staff, and is_superuser must never appear in the response."""
    response = auth_client.get(reverse("user-me"))
    data = response.data["data"]
    assert "password" not in data
    assert "is_staff" not in data
    assert "is_superuser" not in data


@pytest.mark.django_db
def test_get_profile_includes_expected_fields(auth_client):
    response = auth_client.get(reverse("user-me"))
    data = response.data["data"]
    for field in ["id", "email", "first_name", "last_name", "address", "role", "is_active", "created_at"]:
        assert field in data


# ---------------------------------------------------------------------------
# PATCH /users/me/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_update_first_name(auth_client, user):
    response = auth_client.patch(reverse("user-me"), {"first_name": "Updated"})
    assert response.status_code == 200
    assert response.data["data"]["first_name"] == "Updated"
    user.refresh_from_db()
    assert user.first_name == "Updated"


@pytest.mark.django_db
def test_update_address(auth_client, user):
    response = auth_client.patch(reverse("user-me"), {"address": "123 New Street"})
    assert response.status_code == 200
    assert response.data["data"]["address"] == "123 New Street"


@pytest.mark.django_db
def test_update_email_valid(auth_client, user):
    response = auth_client.patch(reverse("user-me"), {"email": "newemail@example.com"})
    assert response.status_code == 200
    assert response.data["data"]["email"] == "newemail@example.com"


@pytest.mark.django_db
def test_update_email_normalised_to_lowercase(auth_client):
    response = auth_client.patch(reverse("user-me"), {"email": "UPPER@EXAMPLE.COM"})
    assert response.status_code == 200
    assert response.data["data"]["email"] == "upper@example.com"


@pytest.mark.django_db
def test_update_email_duplicate_rejected(auth_client, user):
    """Cannot claim another user's email."""
    other = User.objects.create_user(
        email="taken@example.com", password="StrongPass123!",
        first_name="Other", last_name="User",
    )
    response = auth_client.patch(reverse("user-me"), {"email": other.email})
    assert response.status_code == 400


@pytest.mark.django_db
def test_update_email_same_as_own_is_allowed(auth_client, user):
    """Re-submitting the same email (e.g. updating only address) must not be rejected."""
    response = auth_client.patch(reverse("user-me"), {"email": user.email})
    assert response.status_code == 200


@pytest.mark.django_db
def test_update_blank_first_name_rejected(auth_client):
    response = auth_client.patch(reverse("user-me"), {"first_name": "   "})
    assert response.status_code == 400


@pytest.mark.django_db
def test_update_blank_last_name_rejected(auth_client):
    response = auth_client.patch(reverse("user-me"), {"last_name": ""})
    assert response.status_code == 400


@pytest.mark.django_db
def test_role_field_is_ignored_on_update(auth_client, user):
    """Users must not be able to escalate their own role."""
    response = auth_client.patch(reverse("user-me"), {"role": "ADMIN"})
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.role != "ADMIN"


@pytest.mark.django_db
def test_is_active_field_is_ignored_on_update(auth_client, user):
    """Users must not be able to deactivate or reactivate their own account."""
    response = auth_client.patch(reverse("user-me"), {"is_active": False})
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.is_active is True


@pytest.mark.django_db
def test_update_profile_requires_auth(client):
    response = client.patch(reverse("user-me"), {"first_name": "Hacker"})
    assert response.status_code == 401
