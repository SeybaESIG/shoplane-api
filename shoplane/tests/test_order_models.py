from decimal import Decimal
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from shoplane.models import Order, OrderItem, OrderStatus


@pytest.mark.django_db
def test_order_defaults_and_string_representation(user):
    order = Order.objects.create(
        user=user,
        order_number=f"ORD-{uuid4().hex[:8]}",
        total_price=Decimal("30.00"),
        shipping_address="5 Main Road",
    )

    assert order.status == OrderStatus.PENDING
    assert str(order).startswith("Order<")


@pytest.mark.django_db
def test_order_number_is_unique(user):
    order_number = f"ORD-{uuid4().hex[:8]}"
    Order.objects.create(
        user=user,
        order_number=order_number,
        total_price=Decimal("10.00"),
        shipping_address="Address 1",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Order.objects.create(
                user=user,
                order_number=order_number,
                total_price=Decimal("12.00"),
                shipping_address="Address 2",
            )


@pytest.mark.django_db
def test_order_total_price_cannot_be_negative(user):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Order.objects.create(
                user=user,
                order_number=f"ORD-{uuid4().hex[:8]}",
                total_price=Decimal("-1.00"),
                shipping_address="Address",
            )


@pytest.mark.django_db
def test_order_item_amount_fields_cannot_be_negative(order, product):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=1,
                unit_price=Decimal("-1.00"),
                subtotal=Decimal("1.00"),
            )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=1,
                unit_price=Decimal("1.00"),
                subtotal=Decimal("-1.00"),
            )


@pytest.mark.django_db
def test_user_delete_is_blocked_when_orders_exist(order):
    with pytest.raises(ProtectedError):
        order.user.delete()


@pytest.mark.django_db
def test_order_requires_non_empty_shipping_address(user):
    order = Order(
        user=user,
        order_number=f"ORD-{uuid4().hex[:8]}",
        total_price=Decimal("15.00"),
        shipping_address="",
    )

    with pytest.raises(ValidationError):
        order.full_clean()
