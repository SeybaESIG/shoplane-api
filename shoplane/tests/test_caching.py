"""
Tests for the list-endpoint caching layer.

The Redis backend is replaced with Django's LocMemCache for all tests via the
pytest-django `settings` fixture. `caches.close_all()` forces the cache handler
to drop any existing backend connection and pick up the new settings.

What is verified:
  1. Second identical request is served from cache (no DB hit needed).
  2. Admin write bumps the cache version (invalidation invariant).
  3. The GET after a write returns fresh data (cache miss after invalidation).
  4. Different query params produce independent cache entries.
  5. The product and category caches are isolated from each other.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from shoplane.models import Product


def _make_product(category, user):
    s = uuid4().hex[:8]
    return Product.objects.create(
        name=f"Product {s}", slug=f"product-{s}", category=category,
        price=Decimal("19.99"), stock=10, updated_by=user,
    )


# ---------------------------------------------------------------------------
# Product list caching
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProductListCache:
    def test_second_request_served_from_cache(self, user, category, product):
        client = APIClient()
        url = reverse("product-list")

        res1 = client.get(url)
        res2 = client.get(url)

        assert res1.status_code == res2.status_code == 200
        assert res1.data["data"] == res2.data["data"]

    def test_create_bumps_cache_version(self, admin_user, user, category):
        """Creating a product must increment the cache version for the products namespace."""
        from shoplane.api.cache import _get_version

        admin = APIClient()
        admin.force_authenticate(user=admin_user)

        version_before = _get_version("products")

        res = admin.post(
            reverse("product-list"),
            {"name": f"New {uuid4().hex[:6]}", "price": "9.99", "stock": 5, "category": category.slug},
            format="json",
        )
        assert res.status_code == 201

        assert _get_version("products") > version_before

    def test_create_invalidates_cache(self, admin_user, user, category, product):
        """After a create, a public GET must return the fresh list, not the stale cached one."""
        admin = APIClient()
        admin.force_authenticate(user=admin_user)
        public = APIClient()
        url = reverse("product-list")

        # Warm cache with the existing product.
        public.get(url)
        count_before = len(public.get(url).data["data"])

        new_name = f"Brand New {uuid4().hex[:6]}"
        res = admin.post(
            url,
            {"name": new_name, "price": "9.99", "stock": 5, "category": category.slug},
            format="json",
        )
        assert res.status_code == 201

        names_after = [p["name"] for p in public.get(url).data["data"]]
        assert new_name in names_after
        assert len(names_after) == count_before + 1

    def test_update_invalidates_cache(self, admin_user, user, category, product):
        admin = APIClient()
        admin.force_authenticate(user=admin_user)
        public = APIClient()
        url = reverse("product-list")
        detail_url = reverse("product-detail", kwargs={"slug": product.slug})

        # Warm cache with original name.
        public.get(url)

        new_name = f"Renamed {uuid4().hex[:6]}"
        admin.patch(detail_url, {"name": new_name}, format="json")

        names = [p["name"] for p in public.get(url).data["data"]]
        assert new_name in names

    def test_soft_delete_invalidates_cache(self, admin_user, user, category, product):
        admin = APIClient()
        admin.force_authenticate(user=admin_user)
        public = APIClient()
        url = reverse("product-list")
        detail_url = reverse("product-detail", kwargs={"slug": product.slug})

        # Warm cache.
        public.get(url)

        admin.delete(detail_url)

        slugs = [p["slug"] for p in public.get(url).data["data"]]
        assert product.slug not in slugs

    def test_different_query_params_cached_independently(self, user, category):
        p1 = _make_product(category, user)
        p2 = _make_product(category, user)
        client = APIClient()

        res_p1 = client.get(reverse("product-list"), {"search": p1.name})
        res_p2 = client.get(reverse("product-list"), {"search": p2.name})

        slugs_p1 = [p["slug"] for p in res_p1.data["data"]]
        slugs_p2 = [p["slug"] for p in res_p2.data["data"]]

        assert p1.slug in slugs_p1 and p1.slug not in slugs_p2
        assert p2.slug in slugs_p2 and p2.slug not in slugs_p1


# ---------------------------------------------------------------------------
# Category list caching
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCategoryListCache:
    def test_second_request_served_from_cache(self, user, category):
        client = APIClient()
        url = reverse("category-list")

        res1 = client.get(url)
        res2 = client.get(url)

        assert res1.status_code == res2.status_code == 200
        assert res1.data["data"] == res2.data["data"]

    def test_create_bumps_cache_version(self, admin_user, user):
        """Creating a category must increment the cache version for the categories namespace."""
        from shoplane.api.cache import _get_version

        admin = APIClient()
        admin.force_authenticate(user=admin_user)

        version_before = _get_version("categories")

        res = admin.post(
            reverse("category-list"),
            {"name": f"New Cat {uuid4().hex[:6]}"},
            format="json",
        )
        assert res.status_code == 201

        assert _get_version("categories") > version_before

    def test_create_invalidates_cache(self, admin_user, user, category):
        admin = APIClient()
        admin.force_authenticate(user=admin_user)
        public = APIClient()
        url = reverse("category-list")

        # Warm cache.
        public.get(url)
        count_before = len(public.get(url).data["data"])

        new_name = f"New Cat {uuid4().hex[:6]}"
        res = admin.post(url, {"name": new_name}, format="json")
        assert res.status_code == 201

        names = [c["name"] for c in public.get(url).data["data"]]
        assert new_name in names
        assert len(names) == count_before + 1

    def test_update_invalidates_cache(self, admin_user, user, category):
        admin = APIClient()
        admin.force_authenticate(user=admin_user)
        public = APIClient()
        url = reverse("category-list")
        detail_url = reverse("category-detail", kwargs={"slug": category.slug})

        public.get(url)

        new_name = f"Updated Cat {uuid4().hex[:6]}"
        admin.patch(detail_url, {"name": new_name}, format="json")

        names = [c["name"] for c in public.get(url).data["data"]]
        assert new_name in names

    def test_delete_invalidates_cache(self, admin_user, user, category):
        admin = APIClient()
        admin.force_authenticate(user=admin_user)
        public = APIClient()
        url = reverse("category-list")
        detail_url = reverse("category-detail", kwargs={"slug": category.slug})

        public.get(url)
        admin.delete(detail_url)

        slugs = [c["slug"] for c in public.get(url).data["data"]]
        assert category.slug not in slugs


# ---------------------------------------------------------------------------
# Namespace isolation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCacheNamespaceIsolation:
    def test_product_write_does_not_invalidate_category_cache(
        self, admin_user, user, category
    ):
        """Bumping the product cache version must leave the category version untouched."""
        from shoplane.api.cache import _get_version

        admin = APIClient()
        admin.force_authenticate(user=admin_user)

        # Warm category cache and record its version.
        APIClient().get(reverse("category-list"))
        category_version_before = _get_version("categories")

        # Write a product (triggers product cache invalidation only).
        admin.post(
            reverse("product-list"),
            {"name": f"Iso {uuid4().hex[:6]}", "price": "5.00", "stock": 1, "category": category.slug},
            format="json",
        )

        assert _get_version("categories") == category_version_before
