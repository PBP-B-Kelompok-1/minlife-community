from django.urls import path

from . import views

app_name = "journal"

urlpatterns = [
    path("", views.show_journal, name="show_journal"),
]