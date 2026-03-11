import pytest
from django.db import IntegrityError, transaction

from shoplane.models import User, UserRole


@pytest.mark.django_db
def test_create_user_applies_defaults():
    raw_password = "StrongPass123!"
    user = User.objects.create_user(
        email="person@example.com",
        password=raw_password,
        first_name="Jane",
        last_name="Doe",
    )

    assert user.role == UserRole.USER
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.check_password(raw_password)
    assert user.password != raw_password


@pytest.mark.django_db
def test_create_user_normalizes_email_domain():
    user = User.objects.create_user(
        email="MixedCase@EXAMPLE.COM",
        password="StrongPass123!",
        first_name="Jane",
        last_name="Doe",
    )

    assert user.email == "MixedCase@example.com"


@pytest.mark.django_db
def test_create_user_with_duplicate_email_raises_integrity_error():
    User.objects.create_user(
        email="duplicate@example.com",
        password="StrongPass123!",
        first_name="First",
        last_name="User",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            User.objects.create_user(
                email="duplicate@example.com",
                password="StrongPass123!",
                first_name="Second",
                last_name="User",
            )


@pytest.mark.django_db
def test_create_user_without_email_raises_value_error():
    with pytest.raises(ValueError, match="email field must be set"):
        User.objects.create_user(
            email="",
            password="StrongPass123!",
            first_name="No",
            last_name="Email",
        )


@pytest.mark.django_db
def test_create_superuser_applies_admin_defaults():
    admin = User.objects.create_superuser(
        email="admin@example.com",
        password="StrongPass123!",
        first_name="Admin",
        last_name="Root",
    )

    assert admin.role == UserRole.ADMIN
    assert admin.is_staff is True
    assert admin.is_superuser is True
    assert admin.is_active is True


@pytest.mark.django_db
def test_create_superuser_with_invalid_flags_raises_value_error():
    with pytest.raises(ValueError, match="is_staff=True"):
        User.objects.create_superuser(
            email="bad-admin@example.com",
            password="StrongPass123!",
            first_name="Bad",
            last_name="Flags",
            is_staff=False,
        )


@pytest.mark.django_db
def test_user_str_returns_email():
    user = User.objects.create_user(
        email="display@example.com",
        password="StrongPass123!",
        first_name="Display",
        last_name="Name",
    )

    assert str(user) == "display@example.com"
