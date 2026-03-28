from decimal import Decimal

from django.conf import settings
from django.db import models

from .base import TimeStampedModel
from .product import Product


class CartStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    SUBMITTED = "SUBMITTED", "Submitted"
    CONVERTED = "CONVERTED", "Converted"


class Cart(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name="cart", on_delete=models.CASCADE
    )
    status = models.CharField(
        max_length=20, choices=CartStatus.choices, default=CartStatus.OPEN
    )
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_price__gte=0), name="cart_total_price_gte_0"
            ),
        ]

    def __str__(self):
        return f"Cart<{self.user_id}>"

    def recompute_total(self):
        self.total_price = sum(
            (item.subtotal for item in self.items.all()), Decimal("0.00")
        )
        self.save(update_fields=["total_price"])
        return self.total_price

    def add_product(self, product, quantity=1):
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        cart_item, created = CartItem.objects.get_or_create(
            cart=self,
            product=product,
            defaults={"quantity": 0},
        )
        cart_item.quantity += quantity
        cart_item.unit_price = product.price
        cart_item.subtotal = cart_item.unit_price * cart_item.quantity
        cart_item.save()

        self.recompute_total()
        return cart_item, created


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(Cart, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(
        Product, related_name="cart_items", on_delete=models.PROTECT
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"], name="unique_cart_product"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="cart_item_quantity_gte_1"
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0), name="cart_item_unit_price_gte_0"
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0), name="cart_item_subtotal_gte_0"
            ),
        ]

    def __str__(self):
        return f"CartItem<cart={self.cart_id}, product={self.product_id}>"
