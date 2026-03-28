from django.conf import settings
from django.db import models

from .base import TimeStampedModel
from .order import Order


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PAID = "PAID", "Paid"
    FAILED = "FAILED", "Failed"
    REFUNDED = "REFUNDED", "Refunded"


class PaymentProvider(models.TextChoices):
    STRIPE = "STRIPE", "Stripe"
    TWINT = "TWINT", "Twint"


class PaymentLogEventType(models.TextChoices):
    INFO = "INFO", "Info"
    SUCCESS = "SUCCESS", "Success"
    WARNING = "WARNING", "Warning"
    ERROR = "ERROR", "Error"


class Payment(TimeStampedModel):
    order = models.OneToOneField(Order, related_name="payment", on_delete=models.PROTECT)
    provider = models.CharField(max_length=20, choices=PaymentProvider.choices)
    status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_ref = models.CharField(max_length=120, unique=True, blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    refunded_at = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="updated_payments",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gte=0), name="payment_amount_gte_0"),
        ]

    def __str__(self):
        return f"Payment<{self.id}>"


class PaymentLog(models.Model):
    payment = models.ForeignKey(Payment, related_name="logs", on_delete=models.CASCADE)
    event_type = models.CharField(
        max_length=20,
        choices=PaymentLogEventType.choices,
        default=PaymentLogEventType.INFO,
    )
    message = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PaymentLog<{self.id}>"
