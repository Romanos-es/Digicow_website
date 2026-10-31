from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import DecimalField, ExpressionWrapper, F

from training.models import Farmer, TrainingSession

# SQL expression for "quantity x unit price", reused by reports and dashboards.
LINE_TOTAL = ExpressionWrapper(
    F("quantity") * F("unit_price"),
    output_field=DecimalField(max_digits=12, decimal_places=2),
)


class Brand(models.Model):
    """A product brand Digicow sells: Juanco, CKL, Greenlife, Asili."""

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=60, help_text="e.g. 50 kg bag, 1 litre, 100 g packet")
    price = models.DecimalField(
        "Price (KES)", max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["brand__name", "name"]

    def __str__(self):
        return f"{self.brand.name} {self.name} ({self.unit})"


class Order(models.Model):
    """An order a trainer takes from a farmer, to be approved and delivered."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending approval"
        APPROVED = "approved", "Approved"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="orders"
    )
    farmer = models.ForeignKey(Farmer, on_delete=models.PROTECT, related_name="orders")
    session = models.ForeignKey(
        TrainingSession,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
        help_text="The training session where the order was taken (optional).",
    )
    delivery_location = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference

    @property
    def reference(self):
        return f"DC-{self.pk:05d}" if self.pk else "DC-new"

    @property
    def total(self):
        # Uses prefetched items when the view provides them.
        return sum((item.line_total for item in self.items.all()), Decimal("0"))


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    # Price at the time of ordering, so later price changes don't rewrite history.
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.quantity} x {self.product}"

    def save(self, *args, **kwargs):
        if not self.unit_price:
            self.unit_price = self.product.price
        super().save(*args, **kwargs)

    @property
    def line_total(self):
        return self.quantity * self.unit_price
