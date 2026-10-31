from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("about/", views.AboutView.as_view(), name="about"),
    path("products/", views.ProductsView.as_view(), name="products"),
    path("trainings/", views.TrainingsView.as_view(), name="trainings"),
    path("contact/", views.ContactView.as_view(), name="contact"),
    path("reviews/new/", views.submit_farmer_review, name="submit_review"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("reports/", views.reports, name="reports"),
    path("reports/attendance.csv", views.export_attendance, name="export_attendance"),
    path("reports/orders.csv", views.export_orders, name="export_orders"),
]
