from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from shoplane.models import Payment, PaymentLog, PaymentLogEventType, PaymentStatus


@pytest.mark.django_db
def test_payment_defaults_and_string_representation(order):
    payment = Payment.objects.create(
        order=order,
        provider="STRIPE",
        amount=Decimal("49.99"),
    )

    assert payment.status == PaymentStatus.PENDING
    assert str(payment).startswith("Payment<")


@pytest.mark.django_db
def test_payment_amount_cannot_be_negative(order):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Payment.objects.create(
                order=order,
                provider="STRIPE",
                amount=Decimal("-1.00"),
            )


@pytest.mark.django_db
def test_transaction_ref_is_unique(user):
    first_order = user.orders.create(
        order_number=f"ORD-{uuid4().hex[:8]}",
        total_price=Decimal("10.00"),
        shipping_address="Address 1",
    )
    second_order = user.orders.create(
        order_number=f"ORD-{uuid4().hex[:8]}",
        total_price=Decimal("11.00"),
        shipping_address="Address 2",
    )
    transaction_ref = f"tx-{uuid4().hex[:8]}"

    Payment.objects.create(
        order=first_order,
        provider="STRIPE",
        amount=Decimal("10.00"),
        transaction_ref=transaction_ref,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Payment.objects.create(
                order=second_order,
                provider="TWINT",
                amount=Decimal("11.00"),
                transaction_ref=transaction_ref,
            )


@pytest.mark.django_db
def test_order_delete_is_blocked_when_payment_exists(payment):
    with pytest.raises(ProtectedError):
        payment.order.delete()


@pytest.mark.django_db
def test_payment_log_defaults_and_meta_ordering(payment):
    log = PaymentLog.objects.create(payment=payment, message="Info event")

    assert log.event_type == PaymentLogEventType.INFO
    assert PaymentLog._meta.ordering == ["-created_at"]
