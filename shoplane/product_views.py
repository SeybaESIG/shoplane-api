from django.conf import settings
from django.core.cache import cache
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.viewsets import ViewSet

from .api.cache import build_list_cache_key, invalidate_list_cache
from .api.filters import filter_products
from .api.pagination import StandardPagination
from .api.responses import success_response
from .api.serializers import ProductReadSerializer, ProductWriteSerializer
from .models import Product

CACHE_NS = "products"


@extend_schema_view(
    list=extend_schema(summary="List active products", tags=["products"]),
    retrieve=extend_schema(summary="Retrieve a product by slug", tags=["products"]),
    create=extend_schema(summary="Create a product (admin only)", tags=["products"]),
    partial_update=extend_schema(summary="Update a product (admin only)", tags=["products"]),
    destroy=extend_schema(summary="Soft-delete a product (admin only)", tags=["products"]),
)
class ProductViewSet(ViewSet):
    """
    Handles all Product CRUD operations.
    Read actions are public. Write actions require admin.
    Deletion is always soft (is_deleted=True), never hard.
    """

    lookup_field = "slug"

    def get_permissions(self):
        """Public read, admin-only write."""
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAdminUser()]

    def _get_public_queryset(self):
        """Base queryset for public access: active and not soft-deleted."""
        return Product.objects.select_related("category").filter(is_active=True, is_deleted=False)

    def _get_admin_queryset(self):
        """Base queryset for admin access: all products including inactive and soft-deleted."""
        return Product.objects.select_related("category").all()

    def _get_object(self, slug, admin=False):
        """
        Fetch a product by slug. Raises 404 if not found.
        Admin access uses the full queryset; public access is restricted.
        """
        qs = self._get_admin_queryset() if admin else self._get_public_queryset()
        try:
            return qs.get(slug=slug)
        except Product.DoesNotExist:
            raise NotFound(f"No product found with slug '{slug}'.")

    def list(self, request):
        """
        Return products based on caller role, with filtering, search, sorting, and pagination.
        Admins can pass ?all=true to include inactive and soft-deleted products.
        Public callers always get active, non-deleted products only.
        """
        is_admin = request.user and request.user.is_staff
        show_all = is_admin and request.query_params.get("all") == "true"

        queryset = self._get_admin_queryset() if show_all else self._get_public_queryset()
        queryset = filter_products(queryset, request)

        # Serve cached response when available. Admin requests with ?all=true
        # bypass the cache so stale data is never shown to admins.
        cache_key = None
        if not show_all:
            cache_key = build_list_cache_key(CACHE_NS, request)
            cached = cache.get(cache_key)
            if cached is not None:
                return success_response(**cached)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        payload = {
            "message": "Products retrieved successfully",
            "data": ProductReadSerializer(page, many=True).data,
            "meta": paginator.get_meta(),
        }

        if cache_key:
            cache.set(cache_key, payload, settings.CACHE_TTL)

        return success_response(**payload)

    def retrieve(self, request, slug=None):
        """Return a single product. Public callers cannot see inactive or deleted products."""
        is_admin = request.user and request.user.is_staff
        product = self._get_object(slug, admin=is_admin)
        serializer = ProductReadSerializer(product)
        return success_response(
            message="Product retrieved successfully",
            data=serializer.data,
        )

    def create(self, request):
        """Create a new product. Slug is auto-generated from the name."""
        serializer = ProductWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save(updated_by=request.user)
        invalidate_list_cache(CACHE_NS)
        return success_response(
            message="Product created successfully",
            data=ProductReadSerializer(product).data,
            status_code=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, slug=None):
        """Partially update a product. Admins can update inactive or soft-deleted products."""
        product = self._get_object(slug, admin=True)
        serializer = ProductWriteSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = serializer.save(updated_by=request.user)
        invalidate_list_cache(CACHE_NS)
        return success_response(
            message="Product updated successfully",
            data=ProductReadSerializer(product).data,
        )

    def destroy(self, request, slug=None):
        """
        Soft-delete a product by setting is_deleted=True.
        This hides the product from all public endpoints without removing DB data.
        Hard deletion is intentionally not supported via the API.
        """
        product = self._get_object(slug, admin=True)
        product.is_deleted = True
        product.updated_by = request.user
        product.save()
        invalidate_list_cache(CACHE_NS)
        return success_response(
            message="Product deleted successfully",
            data={},
            status_code=status.HTTP_200_OK,
        )
