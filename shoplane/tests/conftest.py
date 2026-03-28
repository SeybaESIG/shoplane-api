from decimal import Decimal
from uuid import uuid4

import pytest
from django.core.cache import cache, caches

# Models are imported after the autouse fixture so Django's app registry is
# fully initialised before the first import of shoplane.models.
from shoplane.models import (  # noqa: E402
    Cart,
    Category,
    Order,
    Payment,
    PaymentProvider,
    Product,
    User,
)


@pytest.fixture(autouse=True)
def use_locmem_cache(settings):
    """
    Use in-memory cache for all tests so no Redis server is required.
    caches.close_all() drops any existing backend connection so the handler
    picks up the new settings on its next access.
    """
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    caches.close_all()
    cache.clear()
    yield
    cache.clear()
    caches.close_all()


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
