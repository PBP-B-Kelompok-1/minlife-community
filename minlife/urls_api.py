from django.urls import path
from posts.views import get_posts_json, get_post_json, vote_post,\
    get_comments_json, create_comment, vote_comment
from announcements.views import get_announcements_json, get_announcement_json

app_name = "api"

urlpatterns = [
    path("posts", get_posts_json, name="get_posts_json"),
    path("post/<uuid:post_id>", get_post_json, name="get_post_json"),
    path("announcements", get_announcements_json, name="get_announcements_json"),
    path(
        "announcement/<uuid:announcement_id>",
        get_announcement_json,
        name="get_announcement_json",
    ),
    path("post/<uuid:post_id>/comments", get_comments_json, name="get_comments_json"),
    path("post/<uuid:post_id>/comment/create", create_comment, name="create_comment"),
    path("post/<uuid:post_id>/vote", vote_post, name="vote_post"),
    path("comment/<uuid:comment_id>/vote", vote_comment, name="vote_comment"),
]
