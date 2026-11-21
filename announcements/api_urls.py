from django.urls import path

from . import api_views


app_name = "announcements_api"

urlpatterns = [
    path("", api_views.announcement_list_create, name="announcement-list"),
    path("capabilities/", api_views.announcement_capabilities, name="announcement-capabilities"),
    path("notifications/subscribe/", api_views.notification_subscribe, name="notification-subscribe"),
    path("notifications/unsubscribe/", api_views.notification_unsubscribe, name="notification-unsubscribe"),
    path("<uuid:announcement_id>/", api_views.announcement_detail, name="announcement-detail"),
]
