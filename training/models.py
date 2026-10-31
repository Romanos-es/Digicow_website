import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.validators import normalize_phone, phone_validator


class County(models.Model):
    name = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "counties"

    def __str__(self):
        return self.name


class Topic(models.Model):
    """A training topic set by the training coordinator."""

    title = models.CharField(max_length=150)
    summary = models.TextField(blank=True, help_text="What trainers should cover.")
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="topics_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class Farmer(models.Model):
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, unique=True, validators=[phone_validator])
    county = models.ForeignKey(County, on_delete=models.PROTECT, related_name="farmers")
    location = models.CharField("Ward / village", max_length=150, blank=True)
    farm_focus = models.CharField(
        "What they farm", max_length=150, blank=True, help_text="e.g. dairy, maize, poultry"
    )
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="farmers_registered",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="farmer_profile",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"

    def clean(self):
        # Runs before the uniqueness check, so 0712... and +254712... collide.
        self.phone = normalize_phone(self.phone)

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        super().save(*args, **kwargs)


class TrainingSession(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    topic = models.ForeignKey(Topic, on_delete=models.PROTECT, related_name="sessions")
    county = models.ForeignKey(County, on_delete=models.PROTECT, related_name="sessions")
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="sessions",
        limit_choices_to={"role": "trainer"},
    )
    venue = models.CharField(max_length=200, help_text="Ward, centre or farm where it is held.")
    date = models.DateField()
    start_time = models.TimeField(default=datetime.time(9, 0))
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED)
    notes = models.TextField(blank=True)
    group_photo = models.ImageField(
        upload_to="training/group_photos/%Y/%m/",
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sessions_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-start_time"]

    def __str__(self):
        return f"{self.topic} – {self.county} ({self.date})"

    @property
    def is_upcoming(self):
        return self.status == self.Status.SCHEDULED and self.date >= timezone.localdate()


class Attendance(models.Model):
    """A farmer registered by the trainer as present at a session.

    `status` starts as PENDING and is updated by the Q&A agent's confirmation call.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting call"
        CONFIRMED = "confirmed", "Confirmed"
        NOT_ATTENDED = "not_attended", "Did not attend"
        UNREACHABLE = "unreachable", "Unreachable"

    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Awaiting QA review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    session = models.ForeignKey(
        TrainingSession, on_delete=models.CASCADE, related_name="attendances"
    )
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="attendances")
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.PENDING)
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendances_registered",
    )
    review_status = models.CharField(
        max_length=10,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    review_reason = models.TextField(blank=True, max_length=1000)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_reviews",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["farmer__full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "farmer"], name="unique_farmer_per_session"
            )
        ]

    def __str__(self):
        return f"{self.farmer.full_name} @ {self.session}"
