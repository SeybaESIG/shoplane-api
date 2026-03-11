from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from shoplane.models import Cart, CartItem, CartStatus


@pytest.mark.django_db
def test_cart_defaults_for_new_user(user):
    cart = Cart.objects.create(user=user)

    assert cart.status == CartStatus.OPEN
    assert cart.total_price == Decimal("0")


@pytest.mark.django_db
def test_cart_total_price_cannot_be_negative(user):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Cart.objects.create(user=user, total_price=Decimal("-0.01"))


@pytest.mark.django_db
def test_cart_item_is_unique_per_cart_and_product(cart, product):
    CartItem.objects.create(
        cart=cart,
        product=product,
        quantity=1,
        unit_price=Decimal("10.00"),
        subtotal=Decimal("10.00"),
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CartItem.objects.create(
                cart=cart,
                product=product,
                quantity=2,
                unit_price=Decimal("10.00"),
                subtotal=Decimal("20.00"),
            )


@pytest.mark.django_db
def test_cart_item_amount_fields_cannot_be_negative(cart, product):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CartItem.objects.create(
                cart=cart,
                product=product,
                quantity=1,
                unit_price=Decimal("-1.00"),
                subtotal=Decimal("1.00"),
            )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CartItem.objects.create(
                cart=cart,
                product=product,
                quantity=1,
                unit_price=Decimal("1.00"),
                subtotal=Decimal("-1.00"),
            )


@pytest.mark.django_db
def test_product_delete_is_blocked_if_referenced_by_cart_item(cart, product):
    CartItem.objects.create(
        cart=cart,
        product=product,
        quantity=1,
        unit_price=Decimal("10.00"),
        subtotal=Decimal("10.00"),
    )

    with pytest.raises(ProtectedError):
        product.delete()


@pytest.mark.django_db
def test_adding_same_product_twice_updates_quantity_and_cart_total(cart, product):
    item, created = cart.add_product(product=product, quantity=1)

    assert created is True
    assert item.quantity == 1
    assert cart.total_price == Decimal("19.99")

    item, created = cart.add_product(product=product, quantity=2)
    cart.refresh_from_db()

    assert created is False
    assert item.quantity == 3
    assert item.subtotal == Decimal("59.97")
    assert cart.total_price == Decimal("59.97")
    assert CartItem.objects.filter(cart=cart, product=product).count() == 1
