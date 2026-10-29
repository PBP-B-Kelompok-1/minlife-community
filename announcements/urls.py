from django.urls import path

from . import views


app_name = "announcements"

urlpatterns = [
    path("", views.announcement_list, name="list"),
    path("create/", views.create_announcement, name="create"),
    path(
        "<uuid:announcement_id>/edit/",
        views.update_announcement,
        name="update",
    ),
    path(
        "<uuid:announcement_id>/delete/",
        views.delete_announcement,
        name="delete",
    ),
    path("<uuid:announcement_id>/", views.announcement_detail, name="detail"),
]
