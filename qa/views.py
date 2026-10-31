from itertools import groupby
import mimetypes

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import ListView

from accounts.mixins import RoleRequiredMixin, role_required
from accounts.models import User
from training.models import Attendance, County, TrainingSession

from .forms import QACallForm, TrainingReviewForm
from .models import QACall
from .services import call_queue


class QueueView(RoleRequiredMixin, ListView):
    """Farmers waiting for a confirmation call (Q&A agents)."""

    allowed_roles = (User.Role.QA,)
    template_name = "qa/queue.html"
    context_object_name = "queue"
    paginate_by = 25

    def get_queryset(self):
        qs = call_queue()
        county = self.request.GET.get("county")
        if county and county.isdigit():
            qs = qs.filter(session__county_id=int(county))
        search = self.request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(
                Q(farmer__full_name__icontains=search)
                | Q(farmer__phone__icontains=search)
                | Q(session__topic__title__icontains=search)
                | Q(session__county__name__icontains=search)
                | Q(session__trainer__first_name__icontains=search)
                | Q(session__trainer__last_name__icontains=search)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["counties"] = County.objects.all()
        context["selected_county"] = self.request.GET.get("county", "")
        context["search_query"] = self.request.GET.get("q", "").strip()
        return context


@role_required(User.Role.QA)
def make_call(request, attendance_id):
    attendance = get_object_or_404(
        call_queue().filter(pk=attendance_id),
    )
    previous_calls = attendance.calls.select_related("agent")

    if request.method == "POST":
        form = QACallForm(request.POST)
        if form.is_valid():
            call = form.save(commit=False)
            call.attendance = attendance
            call.agent = request.user
            call.save()
            messages.success(
                request, f"Call logged for {attendance.farmer.full_name}: {call.get_outcome_display()}."
            )
            return redirect("qa:queue")
    else:
        form = QACallForm()

    return render(
        request,
        "qa/call_form.html",
        {"attendance": attendance, "form": form, "previous_calls": previous_calls},
    )


class HistoryView(RoleRequiredMixin, ListView):
    """Log of all calls. Coordinators use it to follow up farmer questions."""

    allowed_roles = (User.Role.QA, User.Role.COORDINATOR)
    template_name = "qa/history.html"
    context_object_name = "calls"
    paginate_by = 30

    def get_queryset(self):
        qs = QACall.objects.select_related(
            "agent",
            "attendance__farmer",
            "attendance__session__topic",
            "attendance__session__county",
        )
        outcome = self.request.GET.get("outcome")
        if outcome in QACall.Outcome.values:
            qs = qs.filter(outcome=outcome)
        if self.request.GET.get("questions"):
            qs = qs.exclude(farmer_question="")
        search = self.request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(
                Q(attendance__farmer__full_name__icontains=search)
                | Q(attendance__farmer__phone__icontains=search)
                | Q(attendance__session__topic__title__icontains=search)
                | Q(attendance__session__county__name__icontains=search)
                | Q(feedback__icontains=search)
                | Q(farmer_question__icontains=search)
                | Q(agent__first_name__icontains=search)
                | Q(agent__last_name__icontains=search)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["outcomes"] = QACall.Outcome.choices
        context["selected_outcome"] = self.request.GET.get("outcome", "")
        context["only_questions"] = bool(self.request.GET.get("questions"))
        context["search_query"] = self.request.GET.get("q", "").strip()
        return context


class TrainingReviewListView(RoleRequiredMixin, ListView):
    """Completed trainer sessions awaiting or carrying QA review."""

    allowed_roles = (User.Role.QA,)
    template_name = "qa/training_list.html"
    context_object_name = "trainer_groups"

    def get_queryset(self):
        sessions = (
            TrainingSession.objects.filter(status=TrainingSession.Status.COMPLETED)
            .select_related("trainer", "topic", "county")
            .annotate(
                attendee_count=Count("attendances"),
                pending_count=Count(
                    "attendances",
                    filter=Q(attendances__review_status=Attendance.ReviewStatus.PENDING),
                ),
                approved_count=Count(
                    "attendances",
                    filter=Q(attendances__review_status=Attendance.ReviewStatus.APPROVED),
                ),
                rejected_count=Count(
                    "attendances",
                    filter=Q(attendances__review_status=Attendance.ReviewStatus.REJECTED),
                ),
            )
            .order_by("trainer__first_name", "trainer__last_name", "trainer__username", "-date")
        )
        trainer_groups = []
        for _, grouped_sessions in groupby(sessions, key=lambda session: session.trainer_id):
            grouped_sessions = list(grouped_sessions)
            trainer_groups.append(
                {
                    "trainer": grouped_sessions[0].trainer,
                    "sessions": grouped_sessions,
                }
            )
        return trainer_groups


class TrainingReviewDetailView(RoleRequiredMixin, ListView):
    """Training group photo and individual trainees for QA review."""

    allowed_roles = (User.Role.QA,)
    template_name = "qa/training_review.html"
    context_object_name = "attendances"

    def get_queryset(self):
        self.session = get_object_or_404(
            TrainingSession.objects.select_related("trainer", "topic", "county").filter(
                status=TrainingSession.Status.COMPLETED
            ),
            pk=self.kwargs["pk"],
        )
        return self.session.attendances.select_related(
            "farmer", "reviewed_by"
        ).order_by("farmer__full_name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["session"] = self.session
        context["review_form"] = TrainingReviewForm()
        context["review_statuses"] = Attendance.ReviewStatus
        context["review_counts"] = {
            "pending": self.object_list.filter(
                review_status=Attendance.ReviewStatus.PENDING
            ).count(),
            "approved": self.object_list.filter(
                review_status=Attendance.ReviewStatus.APPROVED
            ).count(),
            "rejected": self.object_list.filter(
                review_status=Attendance.ReviewStatus.REJECTED
            ).count(),
        }
        return context


@role_required(User.Role.QA)
def review_training_group(request, pk):
    if request.method != "POST":
        return redirect("qa:training_review", pk=pk)

    form = TrainingReviewForm(request.POST)
    with transaction.atomic():
        session = get_object_or_404(
            TrainingSession.objects.select_for_update().filter(
                status=TrainingSession.Status.COMPLETED
            ),
            pk=pk,
        )
        if not form.is_valid():
            messages.error(request, "Choose approve or reject and provide a reason.")
            return redirect("qa:training_review", pk=session.pk)

        attendances = list(session.attendances.select_for_update())
        if not attendances:
            messages.error(request, "This training has no trainees to review.")
            return redirect("qa:training_review", pk=session.pk)

        reviewed_at = timezone.now()
        for attendance in attendances:
            attendance.review_status = form.cleaned_data["decision"]
            attendance.review_reason = form.cleaned_data["reason"]
            attendance.reviewed_by = request.user
            attendance.reviewed_at = reviewed_at
        Attendance.objects.bulk_update(
            attendances,
            ("review_status", "review_reason", "reviewed_by", "reviewed_at"),
        )

    messages.success(
        request,
        f"All {len(attendances)} trainees were {form.cleaned_data['decision']} "
        "with the reason recorded.",
    )
    return redirect("qa:training_review", pk=session.pk)


@role_required(User.Role.QA)
def review_trainee(request, pk):
    if request.method != "POST":
        return redirect("qa:training_list")

    with transaction.atomic():
        attendance = get_object_or_404(
            Attendance.objects.select_for_update().select_related("session").filter(
                session__status=TrainingSession.Status.COMPLETED
            ),
            pk=pk,
        )
        form = TrainingReviewForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Choose approve or reject and provide a reason.")
            return redirect("qa:training_review", pk=attendance.session_id)

        attendance.review_status = form.cleaned_data["decision"]
        attendance.review_reason = form.cleaned_data["reason"]
        attendance.reviewed_by = request.user
        attendance.reviewed_at = timezone.now()
        attendance.save(
            update_fields=("review_status", "review_reason", "reviewed_by", "reviewed_at")
        )

    messages.success(
        request,
        f"{attendance.farmer.full_name} was {form.cleaned_data['decision']} "
        "with the reason recorded.",
    )
    return redirect("qa:training_review", pk=attendance.session_id)


@role_required(User.Role.QA, User.Role.COORDINATOR, User.Role.TRAINER)
def training_photo(request, pk):
    sessions = TrainingSession.objects.all()
    if request.user.is_trainer:
        sessions = sessions.filter(trainer=request.user)
    session = get_object_or_404(sessions.exclude(group_photo=""), pk=pk)

    content_type = mimetypes.guess_type(session.group_photo.name)[0] or "application/octet-stream"
    return FileResponse(session.group_photo.open("rb"), content_type=content_type)
