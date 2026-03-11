from decimal import Decimal
from uuid import uuid4

import pytest

from shoplane.models import (
    Cart,
    Category,
    Order,
    Payment,
    PaymentProvider,
    Product,
    User,
)


@pytest.fixture
def user():
    suffix = uuid4().hex[:8]
    return User.objects.create_user(
        email=f"user-{suffix}@example.com",
        password="StrongPass123!",
        first_name="John",
        last_name="Doe",
    )


@pytest.fixture
def admin_user():
    suffix = uuid4().hex[:8]
    return User.objects.create_superuser(
        email=f"admin-{suffix}@example.com",
        password="StrongPass123!",
        first_name="Admin",
        last_name="User",
    )


@pytest.fixture
def category(user):
    suffix = uuid4().hex[:8]
    return Category.objects.create(name=f"Category {suffix}", updated_by=user)


@pytest.fixture
def product(category, user):
    suffix = uuid4().hex[:8]
    return Product.objects.create(
        name=f"Product {suffix}",
        category=category,
        price=Decimal("19.99"),
        stock=10,
        updated_by=user,
    )


@pytest.fixture
def cart(user):
    return Cart.objects.create(user=user)


@pytest.fixture
def order(user):
    suffix = uuid4().hex[:8]
    return Order.objects.create(
        user=user,
        order_number=f"ORD-{suffix}",
        total_price=Decimal("49.99"),
        shipping_address="1 Test Street",
    )


@pytest.fixture
def payment(order, user):
    suffix = uuid4().hex[:8]
    return Payment.objects.create(
        order=order,
        provider=PaymentProvider.STRIPE,
        amount=Decimal("49.99"),
        transaction_ref=f"tx-{suffix}",
        updated_by=user,
    )
