from django.urls import path
from announcements.views import get_announcements_json, get_announcement_json

app_name = "api"

urlpatterns = [
    path("announcements", get_announcements_json, name="get_announcements_json"),
    path(
        "announcement/<uuid:announcement_id>",
        get_announcement_json,
        name="get_announcement_json",
    ),
]
