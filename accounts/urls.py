from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views
from .forms import StyledAuthenticationForm

app_name = "accounts"

urlpatterns = [
    path(
        "login/",
        LoginView.as_view(
            template_name="accounts/login.html",
            authentication_form=StyledAuthenticationForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("farmer/login/", views.FarmerLoginView.as_view(), name="farmer_login"),
    path("farmer/sign-up/", views.FarmerSignUpView.as_view(), name="farmer_signup"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password/", views.PasswordChangeWithMessage.as_view(), name="password_change"),
    path("staff/", views.StaffListView.as_view(), name="staff_list"),
    path("staff/new/", views.StaffCreateView.as_view(), name="staff_create"),
    path("staff/<int:pk>/toggle/", views.staff_toggle_active, name="staff_toggle"),
]
