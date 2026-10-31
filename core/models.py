from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

from training.models import Attendance


class ContactMessage(models.Model):
    """A message sent through the public contact form."""

    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.created_at:%Y-%m-%d})"


class FarmerReview(models.Model):
    """A trainee's feedback about one completed training session."""

    attendance = models.OneToOneField(
        Attendance,
        on_delete=models.CASCADE,
        related_name="farmer_review",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(max_length=1000)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.attendance.farmer.full_name}'s training review"
