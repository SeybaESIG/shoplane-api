from django.conf import settings
from django.core.cache import cache
from django.db.models.deletion import ProtectedError
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.viewsets import ViewSet

from .api.cache import build_list_cache_key, invalidate_list_cache
from .api.filters import filter_categories
from .api.pagination import StandardPagination
from .api.responses import error_response, success_response
from .api.serializers import CategoryReadSerializer, CategoryWriteSerializer
from .models import Category

CACHE_NS = "categories"


@extend_schema_view(
    list=extend_schema(summary="List active categories", tags=["categories"]),
    retrieve=extend_schema(summary="Retrieve a category by slug", tags=["categories"]),
    create=extend_schema(summary="Create a category (admin only)", tags=["categories"]),
    partial_update=extend_schema(summary="Update a category (admin only)", tags=["categories"]),
    destroy=extend_schema(summary="Delete a category (admin only)", tags=["categories"]),
)
class CategoryViewSet(ViewSet):
    """
    Handles all Category CRUD operations.
    Read actions (list, retrieve) are public. Write actions require admin.
    """

    lookup_field = "slug"

    def get_permissions(self):
        """Public read, admin-only write."""
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAdminUser()]

    def _get_object(self, slug, active_only=False):
        """
        Fetch a category by slug. Raises 404 if not found.
        Pass active_only=True on public endpoints to hide inactive categories.
        """
        qs = Category.objects.filter(slug=slug)
        if active_only:
            qs = qs.filter(is_active=True)
        try:
            return qs.get()
        except Category.DoesNotExist:
            raise NotFound(f"No category found with slug '{slug}'.")

    def list(self, request):
        """
        Return all active categories with optional sorting and pagination.
        """
        cache_key = build_list_cache_key(CACHE_NS, request)
        cached = cache.get(cache_key)
        if cached is not None:
            return success_response(**cached)

        queryset = Category.objects.filter(is_active=True)
        queryset = filter_categories(queryset, request)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        payload = {
            "message": "Categories retrieved successfully",
            "data": CategoryReadSerializer(page, many=True).data,
            "meta": paginator.get_meta(),
        }

        cache.set(cache_key, payload, settings.CACHE_TTL)
        return success_response(**payload)

    def retrieve(self, request, slug=None):
        """Return a single active category by slug."""
        category = self._get_object(slug, active_only=True)
        serializer = CategoryReadSerializer(category)
        return success_response(
            message="Category retrieved successfully",
            data=serializer.data,
        )

    def create(self, request):
        """Create a new category. Slug is auto-generated from the name."""
        serializer = CategoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save(updated_by=request.user)
        invalidate_list_cache(CACHE_NS)
        return success_response(
            message="Category created successfully",
            data=CategoryReadSerializer(category).data,
            status_code=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, slug=None):
        """Partially update a category. Admins can update inactive categories too."""
        category = self._get_object(slug)
        serializer = CategoryWriteSerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = serializer.save(updated_by=request.user)
        invalidate_list_cache(CACHE_NS)
        return success_response(
            message="Category updated successfully",
            data=CategoryReadSerializer(category).data,
        )

    def destroy(self, request, slug=None):
        """
        Delete a category. Blocked with 409 if any products are still assigned to it.
        Products must be reassigned or deleted first.
        """
        category = self._get_object(slug)
        try:
            category.delete()
            invalidate_list_cache(CACHE_NS)
        except ProtectedError:
            return error_response(
                message="Cannot delete this category because it still has products assigned to it.",
                code="category_has_products",
                status_code=status.HTTP_409_CONFLICT,
            )
        return success_response(
            message="Category deleted successfully",
            data={},
            status_code=status.HTTP_200_OK,
        )
