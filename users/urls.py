from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    path("<uuid:user_id>", views.show_profile, name="show_profile"),
    path("me", views.show_my_profile, name="show_my_profile"),
]