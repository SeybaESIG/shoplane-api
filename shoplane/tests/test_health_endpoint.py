import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_endpoint_returns_expected_payload():
    client = APIClient()

    response = client.get("/api/v1/health/")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Health check successful",
        "data": {"service": "shoplane-api", "status": "ok"},
    }


@pytest.mark.django_db
def test_health_endpoint_allows_unauthenticated_access():
    client = APIClient()

    response = client.get("/api/v1/health/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_health_endpoint_rejects_unsupported_method():
    client = APIClient()

    response = client.post("/api/v1/health/", {})

    assert response.status_code == 405
    assert response.json() == {
        "success": False,
        "message": "Method \"POST\" not allowed.",
        "errors": None,
        "code": "method_not_allowed",
    }
