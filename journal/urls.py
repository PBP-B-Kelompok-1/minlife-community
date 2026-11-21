from django.urls import path

from . import views

app_name = "journal"

# Di-include di minlife/urls.py sebagai path("journal/", include("journal.urls")),
# jadi semua path di sini relatif terhadap /journal/.
urlpatterns = [
    path("", views.show_journal, name="show_journal"),
    path("entry/<str:date_str>/", views.entry_detail, name="entry"),
]
