from django.urls import path

from . import views

app_name = "weeklychallenge"

urlpatterns = [
    path("", views.show_weekly_challenge, name="show_weekly_challenge"),
]