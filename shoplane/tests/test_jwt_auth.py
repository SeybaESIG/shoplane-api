import pytest
from rest_framework.test import APIClient

from shoplane.models import User


@pytest.mark.django_db
def test_jwt_login_returns_access_and_refresh_tokens():
    User.objects.create_user(
        email="jwt-user@example.com",
        password="StrongPass123!",
        first_name="JWT",
        last_name="User",
    )
    client = APIClient()

    response = client.post(
        "/api/v1/auth/login/",
        {"email": "jwt-user@example.com", "password": "StrongPass123!"},
        format="json",
    )

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["message"] == "Login successful"
    assert "access" in body["data"]
    assert "refresh" in body["data"]


@pytest.mark.django_db
def test_jwt_refresh_rotates_refresh_token():
    User.objects.create_user(
        email="rotate@example.com",
        password="StrongPass123!",
        first_name="Rotate",
        last_name="Token",
    )
    client = APIClient()

    login_response = client.post(
        "/api/v1/auth/login/",
        {"email": "rotate@example.com", "password": "StrongPass123!"},
        format="json",
    )
    original_refresh = login_response.json()["data"]["refresh"]

    refresh_response = client.post(
        "/api/v1/auth/refresh/",
        {"refresh": original_refresh},
        format="json",
    )

    body = refresh_response.json()
    assert refresh_response.status_code == 200
    assert body["success"] is True
    assert body["message"] == "Token refreshed successfully"
    assert "access" in body["data"]
    assert "refresh" in body["data"]
    assert body["data"]["refresh"] != original_refresh


@pytest.mark.django_db
def test_jwt_verify_accepts_valid_access_token():
    User.objects.create_user(
        email="verify@example.com",
        password="StrongPass123!",
        first_name="Verify",
        last_name="Token",
    )
    client = APIClient()

    login_response = client.post(
        "/api/v1/auth/login/",
        {"email": "verify@example.com", "password": "StrongPass123!"},
        format="json",
    )
    access = login_response.json()["data"]["access"]

    verify_response = client.post(
        "/api/v1/auth/verify/",
        {"token": access},
        format="json",
    )

    body = verify_response.json()
    assert verify_response.status_code == 200
    assert body == {
        "success": True,
        "message": "Token is valid",
        "data": {},
    }


@pytest.mark.django_db
def test_jwt_logout_blacklists_refresh_token():
    User.objects.create_user(
        email="logout@example.com",
        password="StrongPass123!",
        first_name="Logout",
        last_name="Token",
    )
    client = APIClient()

    login_response = client.post(
        "/api/v1/auth/login/",
        {"email": "logout@example.com", "password": "StrongPass123!"},
        format="json",
    )
    access = login_response.json()["data"]["access"]
    refresh = login_response.json()["data"]["refresh"]

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    logout_response = client.post(
        "/api/v1/auth/logout/",
        {"refresh": refresh},
        format="json",
    )

    assert logout_response.status_code == 200
    assert logout_response.json() == {
        "success": True,
        "message": "Logout successful",
        "data": {},
    }

    refresh_response = client.post(
        "/api/v1/auth/refresh/",
        {"refresh": refresh},
        format="json",
    )
    error_body = refresh_response.json()
    assert refresh_response.status_code == 401
    assert error_body["success"] is False
    assert error_body["code"] == "token_not_valid"


@pytest.mark.django_db
def test_jwt_login_with_wrong_password_is_rejected():
    User.objects.create_user(
        email="wrongpass@example.com",
        password="StrongPass123!",
        first_name="Wrong",
        last_name="Pass",
    )
    client = APIClient()

    response = client.post(
        "/api/v1/auth/login/",
        {"email": "wrongpass@example.com", "password": "BadPassword"},
        format="json",
    )

    body = response.json()
    assert response.status_code == 401
    assert body["success"] is False


@pytest.mark.django_db
def test_jwt_login_with_nonexistent_email_is_rejected():
    client = APIClient()

    response = client.post(
        "/api/v1/auth/login/",
        {"email": "ghost@example.com", "password": "Irrelevant1!"},
        format="json",
    )

    body = response.json()
    assert response.status_code == 401
    assert body["success"] is False


@pytest.mark.django_db
def test_jwt_logout_without_authentication_is_rejected():
    client = APIClient()

    response = client.post(
        "/api/v1/auth/logout/",
        {"refresh": "fake-token"},
        format="json",
    )

    assert response.status_code == 401
    assert response.json()["success"] is False


@pytest.mark.django_db
def test_jwt_refresh_with_invalid_token_is_rejected():
    client = APIClient()

    response = client.post(
        "/api/v1/auth/refresh/",
        {"refresh": "not-a-real-token"},
        format="json",
    )

    body = response.json()
    assert response.status_code == 401
    assert body["success"] is False
    assert body["code"] == "token_not_valid"
