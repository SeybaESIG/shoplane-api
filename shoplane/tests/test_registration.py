import pytest
from rest_framework.test import APIClient

from shoplane.models import User

REGISTER_URL = "/api/v1/auth/register/"


@pytest.mark.django_db
def test_register_creates_user_and_returns_envelope():
    client = APIClient()

    response = client.post(
        REGISTER_URL,
        {
            "email": "newuser@example.com",
            "password": "StrongPass123!",
            "first_name": "New",
            "last_name": "User",
        },
        format="json",
    )

    body = response.json()
    assert response.status_code == 201
    assert body["success"] is True
    assert body["message"] == "Registration successful"
    assert body["data"]["email"] == "newuser@example.com"
    assert body["data"]["first_name"] == "New"
    assert User.objects.filter(email="newuser@example.com").exists()


@pytest.mark.django_db
def test_register_normalizes_email_to_lowercase():
    client = APIClient()

    response = client.post(
        REGISTER_URL,
        {
            "email": "MixedCase@Example.COM",
            "password": "StrongPass123!",
            "first_name": "Mixed",
            "last_name": "Case",
        },
        format="json",
    )

    body = response.json()
    assert response.status_code == 201
    assert body["data"]["email"] == "mixedcase@example.com"


@pytest.mark.django_db
def test_register_rejects_duplicate_email():
    User.objects.create_user(
        email="taken@example.com",
        password="StrongPass123!",
        first_name="First",
        last_name="Owner",
    )
    client = APIClient()

    response = client.post(
        REGISTER_URL,
        {
            "email": "taken@example.com",
            "password": "StrongPass123!",
            "first_name": "Second",
            "last_name": "Try",
        },
        format="json",
    )

    body = response.json()
    assert response.status_code == 400
    assert body["success"] is False
    assert body["message"] == "Validation failed"
    assert "email" in body["errors"]
    assert "already exists" in body["errors"]["email"][0].lower()


@pytest.mark.django_db
def test_register_rejects_duplicate_email_case_insensitive():
    User.objects.create_user(
        email="unique@example.com",
        password="StrongPass123!",
        first_name="First",
        last_name="Owner",
    )
    client = APIClient()

    response = client.post(
        REGISTER_URL,
        {
            "email": "UNIQUE@example.com",
            "password": "StrongPass123!",
            "first_name": "Second",
            "last_name": "Try",
        },
        format="json",
    )

    body = response.json()
    assert response.status_code == 400
    assert body["success"] is False
    assert "email" in body["errors"]
    assert "already exists" in body["errors"]["email"][0].lower()


@pytest.mark.django_db
def test_register_rejects_weak_password():
    client = APIClient()

    response = client.post(
        REGISTER_URL,
        {
            "email": "weakpass@example.com",
            "password": "123",
            "first_name": "Weak",
            "last_name": "Pass",
        },
        format="json",
    )

    body = response.json()
    assert response.status_code == 400
    assert body["success"] is False
    assert body["message"] == "Validation failed"
    assert "password" in body["errors"]


@pytest.mark.django_db
def test_register_rejects_missing_required_fields():
    client = APIClient()

    response = client.post(
        REGISTER_URL,
        {"email": "incomplete@example.com"},
        format="json",
    )

    body = response.json()
    assert response.status_code == 400
    assert body["success"] is False
    assert body["message"] == "Validation failed"
    assert "password" in body["errors"]
    assert "first_name" in body["errors"]
    assert "last_name" in body["errors"]


@pytest.mark.django_db
def test_registered_user_can_login_immediately():
    client = APIClient()

    client.post(
        REGISTER_URL,
        {
            "email": "loginafter@example.com",
            "password": "StrongPass123!",
            "first_name": "Login",
            "last_name": "After",
        },
        format="json",
    )

    login_response = client.post(
        "/api/v1/auth/login/",
        {"email": "loginafter@example.com", "password": "StrongPass123!"},
        format="json",
    )

    body = login_response.json()
    assert login_response.status_code == 200
    assert body["success"] is True
    assert "access" in body["data"]
