from django.urls import path
from posts.views import get_posts_json

app_name = "api"

urlpatterns = [
    path("posts", get_posts_json, name="get_posts_json"),
]