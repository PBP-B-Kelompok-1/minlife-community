from django.urls import path

from . import api

app_name = "posts_api"

urlpatterns = [
    path("posts", api.PostListAPIView.as_view(), name="get_posts_json"),
    path("posts/create", api.PostCreateAPIView.as_view(), name="create_post"),
    path("posts/<uuid:post_id>", api.PostDetailAPIView.as_view(), name="get_post_json"),
    path("posts/<uuid:post_id>/update", api.PostUpdateAPIView.as_view(), name="update_post"),
    path("posts/<uuid:post_id>/delete", api.PostDeleteAPIView.as_view(), name="delete_post"),
    path("posts/<uuid:post_id>/vote", api.PostVoteAPIView.as_view(), name="vote_post"),
    path("posts/<uuid:post_id>/comments", api.CommentListAPIView.as_view(), name="get_comments_json"),
    path("posts/<uuid:post_id>/comments/create", api.CommentCreateAPIView.as_view(), name="create_comment"),
    path("comments/<uuid:comment_id>/delete", api.CommentDeleteAPIView.as_view(), name="delete_comment"),
    path("comments/<uuid:comment_id>/vote", api.CommentVoteAPIView.as_view(), name="vote_comment"),
]
