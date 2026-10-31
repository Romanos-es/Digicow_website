from django.urls import path

from . import views

app_name = "shop"

urlpatterns = [
    path("orders/", views.OrderListView.as_view(), name="order_list"),
    path("orders/new/", views.order_create, name="order_create"),
    path("orders/<int:pk>/", views.OrderDetailView.as_view(), name="order_detail"),
    path("orders/<int:pk>/status/<str:status>/", views.order_set_status, name="order_status"),
]
