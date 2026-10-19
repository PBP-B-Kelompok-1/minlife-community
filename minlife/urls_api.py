from django.urls import path
from posts.views import get_posts_json, vote_post

app_name = "api"

urlpatterns = [
    path("posts", get_posts_json, name="get_posts_json"),
    path("post/<uuid:post_id>/vote", vote_post, name="vote_post"),
]