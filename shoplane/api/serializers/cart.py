from rest_framework import serializers

from shoplane.models import Cart, CartItem, Product


class CartItemSerializer(serializers.ModelSerializer):
    """Read-only output shape for a single cart item. Exposes product info inline."""

    product_slug = serializers.SlugField(source="product.slug", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = CartItem
        fields = ["id", "product_slug", "product_name", "quantity", "unit_price", "subtotal"]


class CartSerializer(serializers.ModelSerializer):
    """Read-only output shape for the full cart, including all nested items."""

    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Cart
        fields = ["id", "status", "total_price", "items", "created_at", "updated_at"]


class AddItemSerializer(serializers.Serializer):
    """Input shape for adding a product to the cart."""

    product_slug = serializers.SlugField()
    quantity = serializers.IntegerField(min_value=1)

    def validate_product_slug(self, value):
        """Product must exist, be active, and not be soft-deleted."""
        try:
            product = Product.objects.get(slug=value, is_active=True, is_deleted=False)
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or unavailable.")
        return product

    def validate(self, data):
        """Stock check: requested quantity must not exceed available stock."""
        product = data["product_slug"]
        quantity = data["quantity"]
        if quantity > product.stock:
            raise serializers.ValidationError(
                {"quantity": f"Only {product.stock} unit(s) in stock."}
            )
        return data


class UpdateItemSerializer(serializers.Serializer):
    """Input shape for updating the quantity of an existing cart item."""

    quantity = serializers.IntegerField(min_value=1)

    def validate_quantity(self, value):
        """
        Stock check is done in the view where we have the product instance.
        This only enforces the minimum value constraint.
        """
        return value
