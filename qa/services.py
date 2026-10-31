from django.db.models import Count
from django.utils import timezone

from training.models import Attendance, TrainingSession


def call_queue():
    """Attendance records still waiting for a confirmation call.

    Includes farmers who could not be reached earlier, but lists those with the
    fewest attempts first so fresh farmers are called before repeat attempts.
    """
    return (
        Attendance.objects.filter(
            status__in=[Attendance.Status.PENDING, Attendance.Status.UNREACHABLE],
            session__date__lte=timezone.localdate(),
        )
        .exclude(session__status=TrainingSession.Status.CANCELLED)
        .select_related("farmer", "session__topic", "session__county", "session__trainer")
        .annotate(attempts=Count("calls"))
        .order_by("attempts", "session__date", "id")
    )
