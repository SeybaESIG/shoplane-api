from rest_framework import serializers

from shoplane.models import Category, Product


class ProductReadSerializer(serializers.ModelSerializer):
    """Output shape for product responses. Exposes category as a nested slug+name pair."""

    category_slug = serializers.SlugField(source="category.slug", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "price",
            "stock",
            "is_active",
            "is_deleted",
            "category_slug",
            "category_name",
            "created_at",
            "updated_at",
        ]


class ProductWriteSerializer(serializers.ModelSerializer):
    """
    Input shape for create and update requests.
    Slug is excluded -- auto-generated on save.
    is_deleted is excluded -- use the DELETE endpoint for soft-deletion.
    category accepts the category slug to keep URLs human-readable.
    """

    category = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=Category.objects.filter(is_active=True),
    )

    class Meta:
        model = Product
        fields = ["name", "description", "price", "stock", "is_active", "category"]

    def validate_price(self, value):
        """Price must be zero or positive."""
        if value < 0:
            raise serializers.ValidationError("Price must be zero or greater.")
        return value

    def validate_stock(self, value):
        """Stock must be zero or positive. Negative stock is never valid."""
        if value < 0:
            raise serializers.ValidationError("Stock must be zero or greater.")
        return value
