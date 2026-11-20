from django.urls import path

from . import views

app_name = "journal"

# Di-include di minlife/urls.py sebagai path("journal/", include("journal.urls")),
# jadi semua path di sini relatif terhadap /journal/.
urlpatterns = [
    path("", views.show_journal, name="show_journal"),
    path("entry/<str:date_str>/", views.entry_detail, name="entry"),

    # API untuk Flutter
    path("api/month/", views.month_api, name="api_month"),
    path("api/entry/<str:date_str>/", views.entry_api, name="api_entry"),
    path("api/entry/<str:date_str>/delete/", views.entry_delete_api, name="api_entry_delete"),
]