from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView

from .forms import (
    FarmerAuthenticationForm,
    FarmerSignUpForm,
    StaffCreateForm,
    StyledPasswordChangeForm,
)
from .mixins import RoleRequiredMixin, role_required
from .models import User


class PasswordChangeWithMessage(LoginRequiredMixin, SuccessMessageMixin, PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("core:dashboard")
    success_message = "Your password was changed."


class FarmerLoginView(LoginView):
    template_name = "accounts/farmer_login.html"
    form_class = FarmerAuthenticationForm
    redirect_authenticated_user = True


class FarmerSignUpView(CreateView):
    form_class = FarmerSignUpForm
    template_name = "accounts/farmer_signup.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("core:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(request=self.request, user=user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(self.request, "Your Digicow farmer account is ready.")
        return redirect("core:dashboard")


class StaffListView(RoleRequiredMixin, ListView):
    allowed_roles = (User.Role.COORDINATOR,)
    template_name = "accounts/staff_list.html"
    context_object_name = "staff"

    def get_queryset(self):
        return User.objects.order_by("role", "first_name", "username")


class StaffCreateView(RoleRequiredMixin, CreateView):
    allowed_roles = (User.Role.COORDINATOR,)
    form_class = StaffCreateForm
    template_name = "accounts/staff_form.html"
    success_url = reverse_lazy("accounts:staff_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["creator"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Account created for {self.object.display_name}.")
        return response


@role_required(User.Role.COORDINATOR)
@require_POST
def staff_toggle_active(request, pk):
    """Activate or deactivate a staff account (never your own, never an admin's)."""
    target = get_object_or_404(User, pk=pk)
    if target == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("accounts:staff_list")
    if target.is_admin and not request.user.is_admin:
        raise PermissionDenied
    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])
    state = "activated" if target.is_active else "deactivated"
    messages.success(request, f"{target.display_name} was {state}.")
    return redirect("accounts:staff_list")
