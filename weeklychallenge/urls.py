from django.urls import path

from . import views

app_name = "weeklychallenge"

urlpatterns = [
    path("", views.show_weekly_challenge, name="show_weekly_challenge"),
    path("list/", views.challenge_list, name="challenge_list"),
    path("list-partial/", views.challenge_list_partial, name="challenge_list_partial"),
    path("create/", views.challenge_create, name="challenge_create"),
    path("tasks/form-row/", views.task_form_row, name="task_form_row"),
    path(
        "tasks/form-row/<int:index>/toggle-delete/",
        views.toggle_task_form_delete,
        name="toggle_task_form_delete",
    ),
    path("<int:pk>/submissions/", views.submission_list_partial, name="submission_list_partial"),
    path("<int:pk>/edit/", views.challenge_update, name="challenge_update"),
    path("<int:pk>/delete/", views.challenge_delete, name="challenge_delete"),
    path("<int:pk>/", views.challenge_detail, name="challenge_detail"),
]