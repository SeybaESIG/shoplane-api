from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from shoplane.models import Category, Product


@pytest.mark.django_db
def test_category_slug_is_auto_generated(user):
    category = Category.objects.create(name="Home Appliances", updated_by=user)

    assert category.slug == "home-appliances"


@pytest.mark.django_db
def test_category_slug_is_unique_when_names_conflict(user):
    first = Category.objects.create(name="Summer Deals", updated_by=user)
    second = Category.objects.create(name="Summer Deals!", updated_by=user)

    assert first.slug == "summer-deals"
    assert second.slug == "summer-deals-2"


@pytest.mark.django_db
def test_product_slug_is_auto_generated(category, user):
    product = Product.objects.create(
        name="Wireless Mouse",
        category=category,
        price=Decimal("49.90"),
        stock=8,
        updated_by=user,
    )

    assert product.slug == "wireless-mouse"


@pytest.mark.django_db
def test_product_slug_is_unique_when_names_conflict(category, user):
    first = Product.objects.create(
        name="Mechanical Keyboard",
        category=category,
        price=Decimal("149.00"),
        stock=4,
        updated_by=user,
    )
    second = Product.objects.create(
        name="Mechanical Keyboard",
        category=category,
        price=Decimal("129.00"),
        stock=5,
        updated_by=user,
    )

    assert first.slug == "mechanical-keyboard"
    assert second.slug == "mechanical-keyboard-2"


@pytest.mark.django_db
def test_product_price_cannot_be_negative(category, user):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Product.objects.create(
                name="Invalid Product",
                category=category,
                price=Decimal("-1.00"),
                stock=1,
                updated_by=user,
            )


@pytest.mark.django_db
def test_product_stock_cannot_be_negative(category, user):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Product.objects.create(
                name="Invalid Stock Product",
                category=category,
                price=Decimal("1.00"),
                stock=-1,
                updated_by=user,
            )


@pytest.mark.django_db
def test_category_delete_is_blocked_when_products_exist(category, product):
    with pytest.raises(ProtectedError):
        category.delete()

    assert Product.objects.filter(pk=product.pk).exists()
