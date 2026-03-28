from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .api.responses import error_response, success_response
from .api.serializers import AddItemSerializer, CartSerializer, UpdateItemSerializer
from .models import Cart, CartItem, CartStatus


def _get_or_create_cart(user):
    """Return the user's cart, creating it if it doesn't exist yet."""
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def _fetch_cart_for_response(cart):
    """
    Re-fetch the cart with prefetched items for serialization.
    Called after any mutation so the response always reflects current DB state
    rather than a stale prefetch cache.
    """
    return Cart.objects.prefetch_related("items__product").get(pk=cart.pk)


def _require_open_cart(cart):
    """Raise a clear error if the cart is no longer modifiable."""
    if cart.status != CartStatus.OPEN:
        raise PermissionDenied(f"Cart cannot be modified because its status is '{cart.status}'.")


def _get_cart_item(cart, product_slug):
    """Fetch a CartItem by product slug within a cart. Raises 404 if not found."""
    try:
        return CartItem.objects.select_related("product").get(cart=cart, product__slug=product_slug)
    except CartItem.DoesNotExist:
        raise NotFound(f"No item with product slug '{product_slug}' in your cart.")


class CartView(APIView):
    """
    Handles reading and clearing the authenticated user's cart.
    The cart is auto-created on first access -- no explicit creation needed.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: CartSerializer},
        summary="Get own cart",
        tags=["cart"],
    )
    def get(self, request):
        """Return the user's cart with all nested items and computed total."""
        cart = _get_or_create_cart(request.user)
        return success_response(
            message="Cart retrieved successfully",
            data=CartSerializer(_fetch_cart_for_response(cart)).data,
        )

    @extend_schema(
        responses={200: CartSerializer},
        summary="Clear all items from cart",
        tags=["cart"],
    )
    def delete(self, request):
        """Remove all items and reset the total. The cart record itself is kept."""
        cart = _get_or_create_cart(request.user)
        _require_open_cart(cart)
        cart.items.all().delete()
        cart.recompute_total()
        return success_response(
            message="Cart cleared successfully",
            data=CartSerializer(_fetch_cart_for_response(cart)).data,
        )


class CartItemView(APIView):
    """
    Handles add, update quantity, and remove for individual cart items.
    Items are addressed by product slug to keep URLs readable.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=AddItemSerializer,
        responses={200: CartSerializer},
        summary="Add a product to the cart",
        tags=["cart"],
    )
    def post(self, request):
        """
        Add a product to the cart or increment its quantity if already present.
        Auto-creates the cart if the user has none yet.
        Validates product availability and stock before adding.
        """
        serializer = AddItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product = serializer.validated_data["product_slug"]
        quantity = serializer.validated_data["quantity"]

        cart = _get_or_create_cart(request.user)
        _require_open_cart(cart)

        cart.add_product(product=product, quantity=quantity)

        return success_response(
            message="Item added to cart",
            data=CartSerializer(_fetch_cart_for_response(cart)).data,
            status_code=status.HTTP_200_OK,
        )

    @extend_schema(
        request=UpdateItemSerializer,
        responses={200: CartSerializer},
        summary="Update quantity of a cart item",
        tags=["cart"],
    )
    def patch(self, request, product_slug=None):
        """
        Set the quantity of an existing item to the provided value.
        Validates that the new quantity does not exceed available stock.
        """
        serializer = UpdateItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_quantity = serializer.validated_data["quantity"]

        cart = _get_or_create_cart(request.user)
        _require_open_cart(cart)
        item = _get_cart_item(cart, product_slug)

        if new_quantity > item.product.stock:
            return error_response(
                message=f"Only {item.product.stock} unit(s) in stock.",
                code="insufficient_stock",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        item.quantity = new_quantity
        item.subtotal = item.unit_price * new_quantity
        item.save()
        cart.recompute_total()

        return success_response(
            message="Cart item updated",
            data=CartSerializer(_fetch_cart_for_response(cart)).data,
        )

    @extend_schema(
        responses={200: CartSerializer},
        summary="Remove an item from the cart",
        tags=["cart"],
    )
    def delete(self, request, product_slug=None):
        """Remove a single item from the cart and recompute the total."""
        cart = _get_or_create_cart(request.user)
        _require_open_cart(cart)
        item = _get_cart_item(cart, product_slug)
        item.delete()
        cart.recompute_total()

        return success_response(
            message="Item removed from cart",
            data=CartSerializer(_fetch_cart_for_response(cart)).data,
        )
