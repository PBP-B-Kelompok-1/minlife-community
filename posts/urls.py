from django.urls import path
from . import views

app_name = "posts"

urlpatterns = [
    path("create", views.create_post, name="create_post"),
    path("<uuid:post_id>/update", views.update_post, name="update_post"),
    path("<uuid:post_id>", views.show_post, name="show_post"),
]
