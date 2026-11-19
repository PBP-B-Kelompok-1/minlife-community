from django.urls import include, path
from announcements.views import get_announcements_json, get_announcement_json
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

app_name = "api"

urlpatterns = [
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='api:schema'), name='docs'),
    path('redoc/', SpectacularRedocView.as_view(url_name='api:schema'), name='redoc'),
    path("", include("posts.api_urls")),
    path("announcements", get_announcements_json, name="get_announcements_json"),
    path(
        "announcement/<uuid:announcement_id>",
        get_announcement_json,
        name="get_announcement_json",
    ),
]
