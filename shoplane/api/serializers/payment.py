from rest_framework import serializers

from shoplane.models import Payment, PaymentLog, PaymentProvider


class PaymentLogSerializer(serializers.ModelSerializer):
    """Read-only output for a single payment log entry. Used by admins for audit/debug."""

    class Meta:
        model = PaymentLog
        fields = ["id", "event_type", "message", "data", "created_at"]


class PaymentSerializer(serializers.ModelSerializer):
    """
    Full read-only representation of a payment.
    Logs are excluded here -- they have their own endpoint.
    """

    class Meta:
        model = Payment
        fields = [
            "id", "provider", "status", "amount",
            "transaction_ref", "paid_at", "refunded_at",
            "created_at", "updated_at",
        ]


class InitiatePaymentSerializer(serializers.Serializer):
    """
    Input shape for initiating a payment.
    Only the provider is submitted by the client.
    Amount is derived from the order -- never trusted from the request.
    """

    provider = serializers.ChoiceField(choices=PaymentProvider.choices)
