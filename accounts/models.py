from django.contrib.auth.models import AbstractUser
from django.db import models

from core.validators import phone_validator


class User(AbstractUser):
    """Digicow staff account. Every user has exactly one role."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        COORDINATOR = "coordinator", "Training coordinator"
        TRAINER = "trainer", "Trainer"
        QA = "qa", "Q&A agent"
        FARMER = "farmer", "Farmer"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.TRAINER)
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])

    def save(self, *args, **kwargs):
        # `createsuperuser` does not ask for a role; make such users administrators.
        if self._state.adding and self.is_superuser and self.role == self.Role.TRAINER:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def is_admin(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    def has_role(self, *roles):
        """True if the user is an administrator or holds any of `roles`."""
        return self.is_admin or self.role in roles

    # Convenience flags used by templates and views.
    @property
    def is_coordinator(self):
        return self.has_role(self.Role.COORDINATOR)

    @property
    def is_trainer(self):
        return self.role == self.Role.TRAINER and not self.is_admin

    @property
    def is_qa(self):
        return self.role == self.Role.QA and not self.is_admin

    @property
    def is_farmer(self):
        return self.role == self.Role.FARMER and not self.is_admin
