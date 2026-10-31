from django.urls import path

from . import views

app_name = "qa"

urlpatterns = [
    path("trainings/", views.TrainingReviewListView.as_view(), name="training_list"),
    path("trainings/<int:pk>/", views.TrainingReviewDetailView.as_view(), name="training_review"),
    path(
        "trainings/<int:pk>/review/",
        views.review_training_group,
        name="review_training_group",
    ),
    path("trainings/<int:pk>/photo/", views.training_photo, name="training_photo"),
    path("trainees/<int:pk>/review/", views.review_trainee, name="review_trainee"),
    path("queue/", views.QueueView.as_view(), name="queue"),
    path("call/<int:attendance_id>/", views.make_call, name="call"),
    path("history/", views.HistoryView.as_view(), name="history"),
]
