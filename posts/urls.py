from django.urls import path
from . import views

app_name = "posts"

urlpatterns = [
    path("<uuid:post_id>", views.show_post, name="show_post"),
    path("create", views.create_post, name="create_post"),
]
