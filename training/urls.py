from django.urls import path

from . import views

app_name = "training"

urlpatterns = [
    path("topics/", views.TopicListView.as_view(), name="topic_list"),
    path("topics/new/", views.TopicCreateView.as_view(), name="topic_create"),
    path("topics/<int:pk>/edit/", views.TopicUpdateView.as_view(), name="topic_edit"),
    path("sessions/", views.SessionListView.as_view(), name="session_list"),
    path("sessions/new/", views.SessionCreateView.as_view(), name="session_create"),
    path("sessions/<int:pk>/", views.SessionDetailView.as_view(), name="session_detail"),
    path("sessions/<int:pk>/edit/", views.SessionUpdateView.as_view(), name="session_edit"),
    path("sessions/<int:pk>/attendance/", views.register_attendance, name="attendance"),
    path("sessions/<int:pk>/complete/", views.session_complete, name="session_complete"),
    path("farmers/", views.FarmerListView.as_view(), name="farmer_list"),
    path("farmers/new/", views.FarmerCreateView.as_view(), name="farmer_create"),
    path("farmers/<int:pk>/edit/", views.FarmerUpdateView.as_view(), name="farmer_edit"),
]
