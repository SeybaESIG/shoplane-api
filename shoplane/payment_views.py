from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.views import APIView

from .api.responses import error_response, success_response
from .api.serializers import InitiatePaymentSerializer, PaymentLogSerializer, PaymentSerializer
from .models import Order, OrderStatus, Payment, PaymentStatus


def _get_order_for_user(order_number, user):
    """
    Fetch an order by order_number, enforcing ownership.
    Non-admin users can only access their own orders.
    Returns 404 in both not-found and forbidden cases to avoid leaking existence.
    """
    try:
        order = Order.objects.get(order_number=order_number)
    except Order.DoesNotExist:
        raise NotFound(f"No order found with number '{order_number}'.")

    if not user.is_staff and order.user != user:
        raise NotFound(f"No order found with number '{order_number}'.")

    return order


class PaymentView(APIView):
    """
    Handles initiating and retrieving the payment for a specific order.
    Nested under /orders/{order_number}/payment/ to make the relationship explicit.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: PaymentSerializer},
        summary="Retrieve payment for an order",
        tags=["payments"],
    )
    def get(self, request, order_number=None):
        """Return the payment record for the given order. Owner or admin only."""
        order = _get_order_for_user(order_number, request.user)
        try:
            payment = order.payment
        except Payment.DoesNotExist:
            raise NotFound("No payment has been initiated for this order yet.")
        return success_response(
            message="Payment retrieved successfully",
            data=PaymentSerializer(payment).data,
        )

    @extend_schema(
        request=InitiatePaymentSerializer,
        responses={201: PaymentSerializer},
        summary="Initiate payment for an order",
        tags=["payments"],
    )
    def post(self, request, order_number=None):
        """
        Initiate a payment for a PENDING order.
        - One payment per order is enforced (409 if one already exists).
        - Amount is taken from the order, never from the client.
        """
        order = _get_order_for_user(order_number, request.user)

        if order.status != OrderStatus.PENDING:
            return error_response(
                message=f"Cannot initiate payment for an order with status '{order.status}'.",
                code="invalid_order_status",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if hasattr(order, "payment"):
            return error_response(
                message="A payment has already been initiated for this order.",
                code="payment_already_exists",
                status_code=status.HTTP_409_CONFLICT,
            )

        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payment = Payment.objects.create(
            order=order,
            provider=serializer.validated_data["provider"],
            amount=order.total_price,
            status=PaymentStatus.PENDING,
            updated_by=request.user,
        )

        return success_response(
            message="Payment initiated successfully",
            data=PaymentSerializer(payment).data,
            status_code=status.HTTP_201_CREATED,
        )


class PaymentLogView(APIView):
    """
    Returns the audit log for a specific payment. Admin only.
    Logs are written internally by the system -- never by clients.
    """

    permission_classes = [IsAdminUser]

    @extend_schema(
        responses={200: PaymentLogSerializer(many=True)},
        summary="List payment logs for an order (admin only)",
        tags=["payments"],
    )
    def get(self, request, order_number=None):
        """Return all log entries for the payment, newest first."""
        order = _get_order_for_user(order_number, request.user)
        try:
            payment = order.payment
        except Payment.DoesNotExist:
            raise NotFound("No payment has been initiated for this order yet.")

        logs = payment.logs.all()
        return success_response(
            message="Payment logs retrieved successfully",
            data=PaymentLogSerializer(logs, many=True).data,
        )
