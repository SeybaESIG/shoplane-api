import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .api.filters import filter_orders
from .api.pagination import StandardPagination
from .api.responses import success_response
from .api.serializers import CancelOrderSerializer, CreateOrderSerializer, OrderSerializer
from .models import Cart, CartStatus, Order, OrderItem, OrderStatus, Product

CANCELLATION_WINDOW_HOURS = 24


def _generate_order_number():
    """Generate a unique, human-readable order number."""
    return f"ORD-{uuid.uuid4().hex[:12].upper()}"


def _get_order(order_number, user):
    """
    Fetch an order by order_number. Raises 404 if not found.
    Non-admin users can only access their own orders.
    """
    try:
        order = Order.objects.prefetch_related("items__product").get(order_number=order_number)
    except Order.DoesNotExist:
        raise NotFound(f"No order found with number '{order_number}'.")

    if not user.is_staff and order.user != user:
        raise NotFound(f"No order found with number '{order_number}'.")

    return order


def _can_user_cancel(order, user):
    """
    Check whether the user is allowed to cancel this order.
    Admins can cancel anytime. Users can cancel within the 24-hour window.
    """
    if user.is_staff:
        return True
    deadline = order.created_at + timedelta(hours=CANCELLATION_WINDOW_HOURS)
    return timezone.now() <= deadline


class OrderListCreateView(APIView):
    """Handles listing the user's orders and creating a new order from the cart."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: OrderSerializer(many=True)},
        summary="List own orders",
        tags=["orders"],
    )
    def get(self, request):
        """
        Return orders belonging to the authenticated user, with optional filtering and pagination.
        Admins see all orders.
        """
        if request.user.is_staff:
            orders = Order.objects.prefetch_related("items__product").all()
        else:
            orders = Order.objects.prefetch_related("items__product").filter(user=request.user)
        orders = filter_orders(orders, request)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(orders, request)
        return success_response(
            message="Orders retrieved successfully",
            data=OrderSerializer(page, many=True).data,
            meta=paginator.get_meta(),
        )

    @extend_schema(
        request=CreateOrderSerializer,
        responses={201: OrderSerializer},
        summary="Create an order from the current cart",
        tags=["orders"],
    )
    def post(self, request):
        """
        Create an order from the user's current cart.

        - Cart must be OPEN and non-empty.
        - Stock is re-checked and decremented atomically per item.
        - Prices are snapshotted from the product at time of checkout.
        - Cart is marked CONVERTED on success.
        - Order is created with status PENDING (awaiting payment).
        """
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        shipping_address = serializer.validated_data["shipping_address"]
        billing_address = serializer.validated_data["billing_address"] or shipping_address

        try:
            cart = Cart.objects.prefetch_related("items__product").get(user=request.user)
        except Cart.DoesNotExist:
            raise ValidationError("You have no active cart.")

        if cart.status != CartStatus.OPEN:
            raise ValidationError(
                f"Cart cannot be checked out because its status is '{cart.status}'."
            )

        cart_items = list(cart.items.select_related("product").all())
        if not cart_items:
            raise ValidationError("Your cart is empty.")

        product_ids = [item.product_id for item in cart_items]

        with transaction.atomic():
            # Acquire row-level locks on all products before reading stock.
            # Concurrent checkouts block here until the first transaction commits,
            # then re-read the committed stock value -- preventing overselling.
            locked_products = {
                p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)
            }

            for item in cart_items:
                product = locked_products[item.product_id]
                if not product.is_active or product.is_deleted:
                    raise ValidationError(f"'{product.name}' is no longer available.")
                if item.quantity > product.stock:
                    raise ValidationError(
                        f"Only {product.stock} unit(s) of '{product.name}' in stock."
                    )

            # All checks passed -- create the order.
            order = Order.objects.create(
                user=request.user,
                order_number=_generate_order_number(),
                total_price=cart.total_price,
                shipping_address=shipping_address,
                billing_address=billing_address,
                status=OrderStatus.PENDING,
            )

            # Snapshot cart items and decrement stock.
            for item in cart_items:
                product = locked_products[item.product_id]
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    subtotal=item.subtotal,
                )
                product.stock -= item.quantity
                product.save(update_fields=["stock"])

            # Lock the cart so it cannot be modified after checkout.
            cart.status = CartStatus.CONVERTED
            cart.save(update_fields=["status"])

        order.refresh_from_db()
        return success_response(
            message="Order created successfully",
            data=OrderSerializer(order).data,
            status_code=status.HTTP_201_CREATED,
        )


class OrderDetailView(APIView):
    """Handles retrieving and cancelling a specific order."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: OrderSerializer},
        summary="Retrieve an order by order number",
        tags=["orders"],
    )
    def get(self, request, order_number=None):
        """Return a single order. Non-admin users can only access their own orders."""
        order = _get_order(order_number, request.user)
        return success_response(
            message="Order retrieved successfully",
            data=OrderSerializer(order).data,
        )

    @extend_schema(
        request=CancelOrderSerializer,
        responses={200: OrderSerializer},
        summary="Cancel an order",
        tags=["orders"],
    )
    def patch(self, request, order_number=None):
        """
        Cancel an order. Users have a 24-hour window from creation.
        Admins can cancel at any time.
        Stock is restored atomically on cancellation.
        """
        order = _get_order(order_number, request.user)

        serializer = CancelOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if order.status == OrderStatus.CANCELLED:
            raise ValidationError("This order is already cancelled.")

        if not _can_user_cancel(order, request.user):
            raise PermissionDenied("The 24-hour cancellation window has passed for this order.")

        with transaction.atomic():
            # Restore stock for every item.
            for item in order.items.select_related("product").all():
                product = item.product
                product.stock += item.quantity
                product.save(update_fields=["stock"])

            order.status = OrderStatus.CANCELLED
            order.save(update_fields=["status"])

        order.refresh_from_db()
        return success_response(
            message="Order cancelled successfully",
            data=OrderSerializer(order).data,
        )
