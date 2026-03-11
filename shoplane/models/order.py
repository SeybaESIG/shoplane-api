from django.conf import settings
from django.db import models

from .base import TimeStampedModel
from .product import Product


class OrderStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    CONFIRMED = "CONFIRMED", "Confirmed"
    CANCELLED = "CANCELLED", "Cancelled"


class Order(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="orders", on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING
    )
    order_number = models.CharField(max_length=80, unique=True)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_address = models.TextField()
    billing_address = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_price__gte=0), name="order_total_price_gte_0"
            ),
        ]

    def __str__(self):
        return f"Order<{self.id}>"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="order_items", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0), name="order_item_unit_price_gte_0"
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0), name="order_item_subtotal_gte_0"
            ),
        ]

    def __str__(self):
        return f"OrderItem<order={self.order_id}, product={self.product_id}>"
