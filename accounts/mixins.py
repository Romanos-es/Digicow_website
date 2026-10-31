from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Class-based views: allow only users holding one of `allowed_roles`.

    Administrators always pass. Anonymous users are sent to the login page and
    signed-in users with the wrong role get a 403 page.
    """

    allowed_roles = ()

    def test_func(self):
        return self.request.user.has_role(*self.allowed_roles)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return redirect_to_login(self.request.get_full_path())


def role_required(*roles):
    """Function-based views: same rules as RoleRequiredMixin."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not request.user.has_role(*roles):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
