from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from training.models import Attendance


class QACall(models.Model):
    """One confirmation call to a farmer about a training session they were registered for."""

    class Outcome(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed: the farmer attended"
        NOT_ATTENDED = "not_attended", "The farmer says they did not attend"
        NO_ANSWER = "no_answer", "No answer / phone off"
        WRONG_NUMBER = "wrong_number", "Wrong number"

    # How each call outcome updates the attendance record.
    OUTCOME_TO_STATUS = {
        Outcome.CONFIRMED: Attendance.Status.CONFIRMED,
        Outcome.NOT_ATTENDED: Attendance.Status.NOT_ATTENDED,
        Outcome.NO_ANSWER: Attendance.Status.UNREACHABLE,
        Outcome.WRONG_NUMBER: Attendance.Status.UNREACHABLE,
    }

    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name="calls")
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="qa_calls",
    )
    outcome = models.CharField(max_length=14, choices=Outcome.choices)
    rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="How the farmer rated the training, 1 (poor) to 5 (excellent).",
    )
    feedback = models.TextField(blank=True, help_text="What the farmer said about the training.")
    farmer_question = models.TextField(
        blank=True, help_text="Any question the farmer wants the trainers to answer."
    )
    called_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-called_at"]

    def __str__(self):
        return f"{self.attendance.farmer.full_name}: {self.get_outcome_display()}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.attendance.status = self.OUTCOME_TO_STATUS[self.outcome]
        self.attendance.save(update_fields=["status"])
