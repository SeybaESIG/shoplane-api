from rest_framework import serializers

from shoplane.models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    """Read-only snapshot of a product at the time the order was placed."""

    product_slug = serializers.SlugField(source="product.slug", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product_slug", "product_name", "quantity", "unit_price", "subtotal"]


class OrderSerializer(serializers.ModelSerializer):
    """Full read-only representation of an order including all nested items."""

    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "order_number", "status", "total_price",
            "shipping_address", "billing_address",
            "items", "created_at", "updated_at",
        ]


class CreateOrderSerializer(serializers.Serializer):
    """
    Input shape for order creation.
    The total and items are derived from the cart snapshot -- not trusted from the client.
    billing_address falls back to shipping_address if omitted.
    """

    shipping_address = serializers.CharField(min_length=1)
    billing_address = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_shipping_address(self, value):
        """Prevent blank or whitespace-only shipping addresses."""
        if not value.strip():
            raise serializers.ValidationError("Shipping address cannot be blank.")
        return value


class CancelOrderSerializer(serializers.Serializer):
    """Input shape for order cancellation. Only CANCELLED is accepted as the target status."""

    status = serializers.ChoiceField(choices=["CANCELLED"])
