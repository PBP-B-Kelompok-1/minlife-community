from django.urls import path
from . import views

app_name = "posts"

urlpatterns = [
    path("api", views.get_posts_json, name="get_posts_json"), # TODO: get a better url (this is included as post/)
    path("create", views.create_post, name="create_post"),
]