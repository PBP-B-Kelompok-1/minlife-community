from django.urls import path

from . import views

app_name = "journal_api"

urlpatterns = [
    # API untuk Flutter
    path("month/", views.month_api, name="month"),
    path("entry/<str:date_str>/", views.entry_api, name="entry"),
    path("entry/<str:date_str>/delete/", views.entry_delete_api, name="entry_delete"),
]
