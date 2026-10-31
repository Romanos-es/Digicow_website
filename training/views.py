from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from accounts.mixins import RoleRequiredMixin, role_required
from accounts.models import User

from .forms import AttendanceRegistrationForm, FarmerForm, TopicForm, TrainingSessionForm
from .models import Attendance, County, Farmer, Topic, TrainingSession

COORDINATOR = (User.Role.COORDINATOR,)
COORDINATOR_OR_TRAINER = (User.Role.COORDINATOR, User.Role.TRAINER)
ANY_STAFF = (User.Role.COORDINATOR, User.Role.TRAINER, User.Role.QA)


def sessions_visible_to(user):
    """Coordinators see every session; trainers only their own."""
    qs = TrainingSession.objects.select_related("topic", "county", "trainer")
    return qs if user.is_coordinator else qs.filter(trainer=user)


# --- Topics -----------------------------------------------------------------
class TopicListView(RoleRequiredMixin, ListView):
    allowed_roles = COORDINATOR
    template_name = "training/topic_list.html"
    context_object_name = "topics"
    paginate_by = 20

    def get_queryset(self):
        return Topic.objects.annotate(session_count=Count("sessions"))


class TopicCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = COORDINATOR
    form_class = TopicForm
    template_name = "training/topic_form.html"
    success_url = reverse_lazy("training:topic_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Topic added.")
        return super().form_valid(form)


class TopicUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = COORDINATOR
    model = Topic
    form_class = TopicForm
    template_name = "training/topic_form.html"
    success_url = reverse_lazy("training:topic_list")

    def form_valid(self, form):
        messages.success(self.request, "Topic updated.")
        return super().form_valid(form)


# --- Sessions ---------------------------------------------------------------
class SessionListView(RoleRequiredMixin, ListView):
    allowed_roles = COORDINATOR_OR_TRAINER
    template_name = "training/session_list.html"
    context_object_name = "sessions"
    paginate_by = 20

    def get_queryset(self):
        qs = sessions_visible_to(self.request.user).annotate(attendee_count=Count("attendances"))
        status = self.request.GET.get("status")
        county = self.request.GET.get("county")
        if status in TrainingSession.Status.values:
            qs = qs.filter(status=status)
        if county and county.isdigit():
            qs = qs.filter(county_id=int(county))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["counties"] = County.objects.all()
        context["statuses"] = TrainingSession.Status.choices
        context["selected_status"] = self.request.GET.get("status", "")
        context["selected_county"] = self.request.GET.get("county", "")
        return context


class SessionCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = COORDINATOR
    form_class = TrainingSessionForm
    template_name = "training/session_form.html"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Training session scheduled.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("training:session_detail", args=[self.object.pk])


class SessionUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = COORDINATOR
    model = TrainingSession
    form_class = TrainingSessionForm
    template_name = "training/session_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Session updated.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("training:session_detail", args=[self.object.pk])


class SessionDetailView(RoleRequiredMixin, DetailView):
    allowed_roles = COORDINATOR_OR_TRAINER
    template_name = "training/session_detail.html"
    context_object_name = "session"

    def get_queryset(self):
        return sessions_visible_to(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attendances = self.object.attendances.select_related("farmer")
        context["attendances"] = attendances
        context["status_counts"] = {
            "total": attendances.count(),
            "confirmed": attendances.filter(status=Attendance.Status.CONFIRMED).count(),
            "not_attended": attendances.filter(status=Attendance.Status.NOT_ATTENDED).count(),
            "awaiting": attendances.filter(
                status__in=[Attendance.Status.PENDING, Attendance.Status.UNREACHABLE]
            ).count(),
        }
        return context


@role_required(*COORDINATOR_OR_TRAINER)
@require_POST
def session_complete(request, pk):
    session = get_object_or_404(sessions_visible_to(request.user), pk=pk)
    if session.status == TrainingSession.Status.SCHEDULED:
        session.status = TrainingSession.Status.COMPLETED
        session.save(update_fields=["status"])
        messages.success(
            request,
            "Session marked as completed. Attendees are in the Q&A call queue and "
            "the QA training review list.",
        )
    return redirect("training:session_detail", pk=session.pk)


@role_required(*COORDINATOR_OR_TRAINER)
def register_attendance(request, pk):
    session = get_object_or_404(sessions_visible_to(request.user), pk=pk)
    if session.status == TrainingSession.Status.CANCELLED:
        messages.error(request, "This session was cancelled, so attendance cannot be registered.")
        return redirect("training:session_detail", pk=session.pk)

    if request.method == "POST":
        form = AttendanceRegistrationForm(request.POST, request.FILES, session=session)
        if form.is_valid():
            created = form.save(registered_by=request.user)
            messages.success(request, f"{created} farmer(s) registered for this session.")
            return redirect("training:session_detail", pk=session.pk)
    else:
        form = AttendanceRegistrationForm(session=session)
    return render(request, "training/attendance_form.html", {"session": session, "form": form})


# --- Farmers ----------------------------------------------------------------
class FarmerListView(RoleRequiredMixin, ListView):
    allowed_roles = ANY_STAFF
    template_name = "training/farmer_list.html"
    context_object_name = "farmers"
    paginate_by = 25

    def get_queryset(self):
        qs = Farmer.objects.select_related("county").annotate(
            sessions_attended=Count("attendances")
        )
        query = self.request.GET.get("q", "").strip()
        county = self.request.GET.get("county")
        if query:
            qs = qs.filter(
                Q(full_name__icontains=query)
                | Q(phone__icontains=query)
                | Q(location__icontains=query)
            )
        if county and county.isdigit():
            qs = qs.filter(county_id=int(county))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["counties"] = County.objects.all()
        context["q"] = self.request.GET.get("q", "")
        context["selected_county"] = self.request.GET.get("county", "")
        return context


class FarmerCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = COORDINATOR_OR_TRAINER
    form_class = FarmerForm
    template_name = "training/farmer_form.html"
    success_url = reverse_lazy("training:farmer_list")

    def form_valid(self, form):
        form.instance.registered_by = self.request.user
        messages.success(self.request, "Farmer added.")
        return super().form_valid(form)


class FarmerUpdateView(RoleRequiredMixin, UpdateView):
    allowed_roles = COORDINATOR
    model = Farmer
    form_class = FarmerForm
    template_name = "training/farmer_form.html"
    success_url = reverse_lazy("training:farmer_list")

    def form_valid(self, form):
        messages.success(self.request, "Farmer updated.")
        return super().form_valid(form)
