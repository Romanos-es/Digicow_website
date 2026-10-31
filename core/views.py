import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, Prefetch, Q, Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, TemplateView

from accounts.mixins import role_required
from accounts.models import User
from qa.models import QACall
from qa.services import call_queue
from shop.models import LINE_TOTAL, Brand, Order, OrderItem, Product
from training.models import Attendance, Farmer, TrainingSession

from .forms import ContactForm, FarmerReviewForm
from .models import FarmerReview


# --- Public pages -----------------------------------------------------------
class HomeView(TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        completed = TrainingSession.objects.filter(status=TrainingSession.Status.COMPLETED)
        context["brands"] = Brand.objects.filter(active=True)
        context["farmer_reviews"] = (
            FarmerReview.objects.filter(is_published=True)
            .select_related("attendance__farmer", "attendance__session__topic")
            [:6]
        )
        context["upcoming"] = (
            TrainingSession.objects.filter(status=TrainingSession.Status.SCHEDULED, date__gte=today)
            .select_related("topic", "county")
            .order_by("date", "start_time")[:3]
        )
        context["stats"] = {
            "sessions": completed.count(),
            "counties": "8+",
            "farmers": Attendance.objects.filter(status=Attendance.Status.CONFIRMED)
            .values("farmer")
            .distinct()
            .count(),
        }
        return context


class AboutView(TemplateView):
    template_name = "core/about.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["brands"] = Brand.objects.filter(active=True)
        return context


class ProductsView(TemplateView):
    template_name = "core/products.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        products = Product.objects.filter(active=True).order_by("name")
        context["brands"] = Brand.objects.filter(active=True).prefetch_related(
            Prefetch("products", queryset=products, to_attr="live_products")
        )
        return context


class TrainingsView(TemplateView):
    template_name = "core/trainings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["upcoming"] = (
            TrainingSession.objects.filter(
                status=TrainingSession.Status.SCHEDULED, date__gte=timezone.localdate()
            )
            .select_related("topic", "county")
            .order_by("date", "start_time")
        )
        return context


class ContactView(CreateView):
    form_class = ContactForm
    template_name = "core/contact.html"
    success_url = reverse_lazy("core:contact")

    def form_valid(self, form):
        messages.success(self.request, "Thank you. We have received your message.")
        return super().form_valid(form)


@login_required(login_url="accounts:farmer_login")
def submit_farmer_review(request):
    if not request.user.is_farmer:
        raise PermissionDenied

    farmer = Farmer.objects.filter(user=request.user).first()
    if not farmer:
        messages.error(request, "Your farmer profile is not linked. Please contact Digicow for help.")
        return render(
            request,
            "core/farmer_review_form.html",
            {"form": None, "has_training": False},
        )

    if request.method == "POST":
        form = FarmerReviewForm(request.POST, farmer=farmer)
        if form.is_valid():
            review = form.save(commit=False)
            review.is_published = False
            review.save()
            messages.success(
                request,
                "Thank you for sharing your experience. Your review will appear after it is approved.",
            )
            return redirect("core:home")
    else:
        form = FarmerReviewForm(farmer=farmer)

    return render(
        request,
        "core/farmer_review_form.html",
        {"form": form, "has_training": form.fields["attendance"].queryset.exists()},
    )


# --- Dashboards -------------------------------------------------------------
@login_required
def dashboard(request):
    user = request.user
    today = timezone.localdate()
    if user.is_coordinator:
        return _coordinator_dashboard(request, today)
    if user.is_trainer:
        return _trainer_dashboard(request, today)
    if user.is_qa:
        return _qa_dashboard(request, today)
    if user.is_farmer:
        return _farmer_dashboard(request, today)
    return render(request, "core/dashboard_empty.html")


def _coordinator_dashboard(request, today):
    sessions = TrainingSession.objects
    pending_orders = Order.objects.filter(status=Order.Status.PENDING)
    answered = Attendance.objects.filter(
        status__in=[Attendance.Status.CONFIRMED, Attendance.Status.NOT_ATTENDED]
    )
    confirmed = answered.filter(status=Attendance.Status.CONFIRMED).count()
    total_answered = answered.count()
    context = {
        "upcoming": sessions.filter(status=TrainingSession.Status.SCHEDULED, date__gte=today)
        .select_related("topic", "county", "trainer")
        .order_by("date", "start_time")[:6],
        "pending_orders": pending_orders.select_related("trainer", "farmer").prefetch_related(
            "items"
        )[:6],
        "pending_order_count": pending_orders.count(),
        "queue_count": call_queue().count(),
        "farmer_count": Farmer.objects.count(),
        "sessions_this_month": sessions.filter(
            date__year=today.year, date__month=today.month
        ).count(),
        "confirm_rate": round(confirmed * 100 / total_answered) if total_answered else None,
        "recent_questions": QACall.objects.exclude(farmer_question="").select_related(
            "attendance__farmer", "attendance__session__topic"
        )[:5],
    }
    return render(request, "core/dashboard_coordinator.html", context)


def _trainer_dashboard(request, today):
    user = request.user
    mine = TrainingSession.objects.filter(trainer=user).select_related("topic", "county")
    my_orders = Order.objects.filter(trainer=user)
    order_value = (
        OrderItem.objects.filter(order__trainer=user)
        .exclude(order__status=Order.Status.CANCELLED)
        .aggregate(total=Sum(LINE_TOTAL))["total"]
        or 0
    )
    context = {
        "upcoming": mine.filter(
            status=TrainingSession.Status.SCHEDULED, date__gt=today
        ).order_by("date", "start_time")[:6],
        "due_today": mine.filter(
            status=TrainingSession.Status.SCHEDULED, date__lte=today
        ).order_by("date"),
        "recent_orders": my_orders.select_related("farmer").prefetch_related("items")[:5],
        "sessions_done": mine.filter(status=TrainingSession.Status.COMPLETED).count(),
        "farmers_registered": Attendance.objects.filter(session__trainer=user)
        .values("farmer")
        .distinct()
        .count(),
        "order_count": my_orders.exclude(status=Order.Status.CANCELLED).count(),
        "order_value": order_value,
    }
    return render(request, "core/dashboard_trainer.html", context)


def _qa_dashboard(request, today):
    user = request.user
    calls_today = QACall.objects.filter(agent=user, called_at__date=today)
    context = {
        "queue_count": call_queue().count(),
        "next_up": call_queue()[:5],
        "calls_today": calls_today.count(),
        "confirmed_today": calls_today.filter(outcome=QACall.Outcome.CONFIRMED).count(),
        "recent_calls": QACall.objects.filter(agent=user).select_related(
            "attendance__farmer", "attendance__session__topic"
        )[:5],
    }
    return render(request, "core/dashboard_qa.html", context)


def _farmer_dashboard(request, today):
    farmer = Farmer.objects.filter(user=request.user).select_related("county").first()
    attendances = (
        Attendance.objects.filter(farmer=farmer)
        .select_related("session__topic", "session__county")
        .order_by("-session__date")[:10]
        if farmer
        else Attendance.objects.none()
    )
    upcoming = TrainingSession.objects.none()
    if farmer:
        upcoming = TrainingSession.objects.filter(
            county=farmer.county,
            status=TrainingSession.Status.SCHEDULED,
            date__gte=today,
        ).select_related("topic", "county").order_by("date", "start_time")[:6]
    return render(
        request,
        "core/dashboard_farmer.html",
        {"farmer": farmer, "attendances": attendances, "upcoming": upcoming},
    )


# --- Reports (coordinators) -------------------------------------------------
@role_required(User.Role.COORDINATOR)
def reports(request):
    A = Attendance.Status
    session_stats = (
        TrainingSession.objects.filter(status=TrainingSession.Status.COMPLETED)
        .select_related("topic", "county", "trainer")
        .annotate(
            total=Count("attendances"),
            confirmed=Count("attendances", filter=Q(attendances__status=A.CONFIRMED)),
            not_attended=Count("attendances", filter=Q(attendances__status=A.NOT_ATTENDED)),
            awaiting=Count(
                "attendances", filter=Q(attendances__status__in=[A.PENDING, A.UNREACHABLE])
            ),
        )
        .order_by("-date")[:50]
    )
    county_reach = (
        Attendance.objects.filter(status=A.CONFIRMED)
        .values(name=F("session__county__name"))
        .annotate(
            farmers=Count("farmer", distinct=True),
            sessions=Count("session", distinct=True),
        )
        .order_by("-farmers")[:15]
    )
    brand_sales = (
        OrderItem.objects.exclude(order__status=Order.Status.CANCELLED)
        .values(name=F("product__brand__name"))
        .annotate(units=Sum("quantity"), value=Sum(LINE_TOTAL))
        .order_by("-value")
    )
    return render(
        request,
        "core/reports.html",
        {"session_stats": session_stats, "county_reach": county_reach, "brand_sales": brand_sales},
    )


def _csv_response(filename):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@role_required(User.Role.COORDINATOR)
def export_attendance(request):
    response = _csv_response("digicow-attendance.csv")
    writer = csv.writer(response)
    writer.writerow(["Date", "Topic", "County", "Venue", "Trainer", "Farmer", "Phone", "Status"])
    rows = Attendance.objects.select_related(
        "farmer", "session__topic", "session__county", "session__trainer"
    ).order_by("-session__date", "farmer__full_name")
    for a in rows:
        trainer = a.session.trainer.display_name if a.session.trainer else ""
        writer.writerow(
            [
                a.session.date,
                a.session.topic.title,
                a.session.county.name,
                a.session.venue,
                trainer,
                a.farmer.full_name,
                a.farmer.phone,
                a.get_status_display(),
            ]
        )
    return response


@role_required(User.Role.COORDINATOR)
def export_orders(request):
    response = _csv_response("digicow-orders.csv")
    writer = csv.writer(response)
    writer.writerow(
        [
            "Order", "Date", "Status", "Trainer", "Farmer", "Phone",
            "Brand", "Product", "Unit", "Quantity", "Unit price (KES)", "Line total (KES)",
        ]
    )
    items = OrderItem.objects.select_related(
        "order__trainer", "order__farmer", "product__brand"
    ).order_by("-order__created_at", "order_id")
    for item in items:
        order = item.order
        writer.writerow(
            [
                order.reference,
                timezone.localtime(order.created_at).date(),
                order.get_status_display(),
                order.trainer.display_name if order.trainer else "",
                order.farmer.full_name,
                order.farmer.phone,
                item.product.brand.name,
                item.product.name,
                item.product.unit,
                item.quantity,
                item.unit_price,
                item.line_total,
            ]
        )
    return response
