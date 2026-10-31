from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from accounts.mixins import RoleRequiredMixin, role_required
from accounts.models import User

from .forms import OrderForm, OrderItemFormSet
from .models import Order

ORDER_STAFF = (User.Role.COORDINATOR, User.Role.TRAINER)

# Which status changes are allowed from each status.
TRANSITIONS = {
    Order.Status.PENDING: {Order.Status.APPROVED, Order.Status.CANCELLED},
    Order.Status.APPROVED: {Order.Status.DELIVERED, Order.Status.CANCELLED},
}


def orders_visible_to(user):
    qs = Order.objects.select_related("trainer", "farmer", "session__topic").prefetch_related(
        "items__product__brand"
    )
    return qs if user.is_coordinator else qs.filter(trainer=user)


class OrderListView(RoleRequiredMixin, ListView):
    allowed_roles = ORDER_STAFF
    template_name = "shop/order_list.html"
    context_object_name = "orders"
    paginate_by = 20

    def get_queryset(self):
        qs = orders_visible_to(self.request.user)
        status = self.request.GET.get("status")
        query = self.request.GET.get("q", "").strip()
        if status in Order.Status.values:
            qs = qs.filter(status=status)
        if query:
            qs = qs.filter(
                Q(farmer__full_name__icontains=query) | Q(farmer__phone__icontains=query)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["statuses"] = Order.Status.choices
        context["selected_status"] = self.request.GET.get("status", "")
        context["q"] = self.request.GET.get("q", "")
        return context


@role_required(User.Role.TRAINER)
def order_create(request):
    order = Order(trainer=request.user)
    if request.method == "POST":
        form = OrderForm(request.POST, user=request.user, instance=order)
        formset = OrderItemFormSet(request.POST, instance=order)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                order = form.save()
                formset.instance = order
                formset.save()
            messages.success(request, f"Order {order.reference} sent for approval.")
            return redirect("shop:order_detail", pk=order.pk)
    else:
        form = OrderForm(user=request.user, instance=order)
        formset = OrderItemFormSet(instance=order)
    return render(request, "shop/order_form.html", {"form": form, "formset": formset})


class OrderDetailView(RoleRequiredMixin, DetailView):
    allowed_roles = ORDER_STAFF
    template_name = "shop/order_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return orders_visible_to(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        allowed = TRANSITIONS.get(self.object.status, set())
        if not user.is_coordinator:
            # Trainers may only cancel their own pending orders.
            allowed = {Order.Status.CANCELLED} & allowed if self.object.status == Order.Status.PENDING else set()
        context["actions"] = [(value, label) for value, label in Order.Status.choices if value in allowed]
        return context


@role_required(*ORDER_STAFF)
@require_POST
def order_set_status(request, pk, status):
    order = get_object_or_404(orders_visible_to(request.user), pk=pk)
    allowed = TRANSITIONS.get(order.status, set())
    if status not in allowed:
        messages.error(request, "That status change is not allowed for this order.")
        return redirect("shop:order_detail", pk=order.pk)
    if not request.user.is_coordinator and not (
        order.status == Order.Status.PENDING and status == Order.Status.CANCELLED
    ):
        raise PermissionDenied
    order.status = status
    order.save(update_fields=["status", "updated_at"])
    messages.success(request, f"Order {order.reference} is now {order.get_status_display().lower()}.")
    return redirect("shop:order_detail", pk=order.pk)
