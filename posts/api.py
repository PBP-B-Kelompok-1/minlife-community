from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import serializers, status
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_field

from weeklychallenge.services import award_badge_if_eligible

from .forms import CommentForm
from .models import Comment, Post, Vote


class PostSerializer(serializers.ModelSerializer):
    """The post representation consumed by the existing post UI."""

    user_id = serializers.UUIDField(source="author_id", read_only=True)
    username = serializers.CharField(source="author.username", read_only=True)
    avatar_url = serializers.SerializerMethodField()
    challenge_image_url = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    vote_count = serializers.SerializerMethodField()
    user_vote_value = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    can_update = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id", "user_id", "username", "avatar_url", "title",
            "challenge_image_url", "content", "tags", "vote_count",
            "user_vote_value", "comment_count", "created_at", "updated_at",
            "can_update", "can_delete",
        )

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_avatar_url(self, post):
        return post.author.avatar_url or post.author.avatar_src

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_challenge_image_url(self, post):
        return post.challenge_image.url if post.challenge_image else None

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_tags(self, post):
        return [{"id": str(tag.pk), "title": tag.title} for tag in post.tags.all()]

    @extend_schema_field(serializers.IntegerField())
    def get_vote_count(self, post):
        return post.get_vote_count()

    @extend_schema_field(serializers.IntegerField())
    def get_user_vote_value(self, post):
        return post.get_user_vote_value(self.context["request"].user)

    @extend_schema_field(serializers.IntegerField())
    def get_comment_count(self, post):
        return post.comments.count()

    @extend_schema_field(serializers.BooleanField())
    def get_can_update(self, post):
        user = self.context["request"].user
        return user.is_authenticated and (user == post.author or user.has_perm("posts.change_post"))

    @extend_schema_field(serializers.BooleanField())
    def get_can_delete(self, post):
        user = self.context["request"].user
        return user.is_authenticated and (user == post.author or user.has_perm("posts.delete_post"))


class CommentSerializer(serializers.ModelSerializer):
    user_id = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    user_vote_value = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()
    vote_count = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = (
            "id", "user_id", "username", "avatar_url", "content", "is_deleted",
            "user_vote_value", "replies", "reply_count", "vote_count", "can_delete",
        )

    @extend_schema_field(serializers.UUIDField(allow_null=True))
    def get_user_id(self, comment):
        return None if comment.is_deleted else comment.user_id

    @extend_schema_field(serializers.CharField())
    def get_username(self, comment):
        return "[deleted comment]" if comment.is_deleted else comment.user.username

    @extend_schema_field(serializers.URLField())
    def get_avatar_url(self, comment):
        return "" if comment.is_deleted else (comment.user.avatar_url or comment.user.avatar_src)

    @extend_schema_field(serializers.IntegerField())
    def get_user_vote_value(self, comment):
        return comment.get_user_vote_value(self.context["request"].user)

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_replies(self, comment):
        return CommentSerializer(comment.replies.all(), many=True, context=self.context).data

    @extend_schema_field(serializers.IntegerField())
    def get_reply_count(self, comment):
        return sum(1 + self.get_reply_count(reply) for reply in comment.replies.all())

    @extend_schema_field(serializers.IntegerField())
    def get_vote_count(self, comment):
        return comment.get_vote_count()

    @extend_schema_field(serializers.BooleanField())
    def get_can_delete(self, comment):
        user = self.context["request"].user
        return not comment.is_deleted and user.is_authenticated and (
            user == comment.user or user.has_perm("posts.delete_comment")
        )


class PostListResponseSerializer(serializers.Serializer):
    data = PostSerializer(many=True)


class PostDetailResponseSerializer(serializers.Serializer):
    data = PostSerializer()


class CommentListResponseSerializer(serializers.Serializer):
    data = CommentSerializer(many=True)


class CommentCreateRequestSerializer(serializers.Serializer):
    content = serializers.CharField()
    replies_to_comment = serializers.UUIDField(required=False)


class CommentCreateResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    comment_id = serializers.UUIDField()


class VoteResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    vote_value = serializers.IntegerField()
    vote_count = serializers.IntegerField()


class MessageResponseSerializer(serializers.Serializer):
    message = serializers.CharField()


class ErrorResponseSerializer(serializers.Serializer):
    error = serializers.CharField()


class LoginRequiredAPIView(APIView):
    """Return the login information expected by the browser client for mutations."""

    def require_authenticated_user(self, request):
        if request.user.is_authenticated:
            return None
        return Response(
            {"message": "Please log in first!", "login_url": reverse("login")},
            status=status.HTTP_401_UNAUTHORIZED,
        )


class PostListAPIView(APIView):
    @extend_schema(
        operation_id="posts_list",
        tags=["Posts"],
        responses={200: PostListResponseSerializer},
    )
    def get(self, request):
        posts = Post.objects.select_related("author").prefetch_related("tags")
        return Response({"data": PostSerializer(posts, many=True, context={"request": request}).data})


class PostDetailAPIView(APIView):
    @extend_schema(
        operation_id="posts_retrieve",
        tags=["Posts"],
        responses={200: PostDetailResponseSerializer, 404: ErrorResponseSerializer},
    )
    def get(self, request, post_id):
        post = get_object_or_404(Post.objects.select_related("author").prefetch_related("tags"), pk=post_id)
        return Response({"data": PostSerializer(post, context={"request": request}).data})


class PostDeleteAPIView(LoginRequiredAPIView):
    @extend_schema(
        operation_id="posts_delete",
        tags=["Posts"],
        request=None,
        responses={200: MessageResponseSerializer, 401: MessageResponseSerializer, 403: ErrorResponseSerializer},
    )
    def post(self, request, post_id):
        unauthenticated = self.require_authenticated_user(request)
        if unauthenticated:
            return unauthenticated
        post = get_object_or_404(Post, pk=post_id)
        if request.user != post.author and not request.user.has_perm("posts.delete_post"):
            raise PermissionDenied
        post.delete()
        return Response({"message": "Post deleted successfully."})


class VoteSerializer(serializers.Serializer):
    vote_value = serializers.IntegerField()

    def validate_vote_value(self, value):
        if value not in (1, -1):
            raise serializers.ValidationError("value must be 1 or -1")
        return value


def get_vote_value(request):
    """Keep malformed and missing JSON compatible with the previous client API."""
    try:
        serializer = VoteSerializer(data=request.data)
    except ParseError:
        return None, Response({"error": "value is required"}, status=status.HTTP_400_BAD_REQUEST)
    if not serializer.is_valid():
        error = serializer.errors.get("vote_value", [])
        message = "value is required" if error and error[0].code == "required" else "value must be 1 or -1"
        return None, Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)
    return serializer.validated_data["vote_value"], None


class PostVoteAPIView(LoginRequiredAPIView):
    @extend_schema(
        operation_id="posts_vote",
        tags=["Posts"],
        request=VoteSerializer,
        responses={200: VoteResponseSerializer, 400: ErrorResponseSerializer, 401: MessageResponseSerializer},
    )
    def post(self, request, post_id):
        unauthenticated = self.require_authenticated_user(request)
        if unauthenticated:
            return unauthenticated
        post = get_object_or_404(Post, pk=post_id)
        vote_value, error_response = get_vote_value(request)
        if error_response:
            return error_response
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            vote = Vote.objects.filter(user=request.user, post=post).first()
            if not vote:
                Vote.objects.create(user=request.user, post=post, value=vote_value)
            elif vote.value != vote_value:
                vote.value = vote_value
                vote.save(update_fields=["value"])
            else:
                vote_value = 0
                vote.delete()
        award_badge_if_eligible(post)
        return Response({"message": "Upvoted successfully!", "vote_value": vote_value, "vote_count": post.get_vote_count()})


class CommentListAPIView(APIView):
    @extend_schema(
        operation_id="posts_comments_list",
        tags=["Posts"],
        responses={200: CommentListResponseSerializer, 404: ErrorResponseSerializer},
    )
    def get(self, request, post_id):
        post = get_object_or_404(Post, pk=post_id)
        comments = Comment.objects.filter(post=post, replies_to_comment__isnull=True).select_related("user")
        return Response({"data": CommentSerializer(comments, many=True, context={"request": request}).data})


class CommentCreateAPIView(LoginRequiredAPIView):
    @extend_schema(
        operation_id="posts_comments_create",
        tags=["Posts"],
        request=CommentCreateRequestSerializer,
        responses={201: CommentCreateResponseSerializer, 400: ErrorResponseSerializer, 401: MessageResponseSerializer},
    )
    def post(self, request, post_id):
        unauthenticated = self.require_authenticated_user(request)
        if unauthenticated:
            return unauthenticated
        form = CommentForm(request.data)
        if not form.is_valid():
            return Response(
                {"message": "Please fill the fields as specified!", "errors": form.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        post = get_object_or_404(Post, pk=post_id)
        reply_to_id = request.data.get("replies_to_comment")
        reply_to = get_object_or_404(Comment, pk=reply_to_id, post=post) if reply_to_id else None
        comment = form.save(commit=False)
        comment.user = request.user
        comment.post = post
        comment.replies_to_comment = reply_to
        comment.save()
        return Response({"message": "Successfully posted comment!", "comment_id": comment.pk}, status=status.HTTP_201_CREATED)


class CommentDeleteAPIView(LoginRequiredAPIView):
    @extend_schema(
        operation_id="comments_delete",
        tags=["Posts"],
        request=None,
        responses={200: MessageResponseSerializer, 401: MessageResponseSerializer, 403: ErrorResponseSerializer},
    )
    def post(self, request, comment_id):
        unauthenticated = self.require_authenticated_user(request)
        if unauthenticated:
            return unauthenticated
        comment = get_object_or_404(Comment, pk=comment_id)
        if request.user != comment.user and not request.user.has_perm("posts.delete_comment"):
            raise PermissionDenied
        comment.content = "✖ This comment has been deleted"
        comment.is_deleted = True
        comment.save(update_fields=["content", "is_deleted"])
        return Response({"message": "Comment deleted successfully."})


class CommentVoteAPIView(LoginRequiredAPIView):
    @extend_schema(
        operation_id="comments_vote",
        tags=["Posts"],
        request=VoteSerializer,
        responses={200: VoteResponseSerializer, 400: ErrorResponseSerializer, 401: MessageResponseSerializer},
    )
    def post(self, request, comment_id):
        unauthenticated = self.require_authenticated_user(request)
        if unauthenticated:
            return unauthenticated
        comment = get_object_or_404(Comment, pk=comment_id)
        if comment.is_deleted:
            return Response({"error": "can't vote on a deleted comment"}, status=status.HTTP_400_BAD_REQUEST)
        vote_value, error_response = get_vote_value(request)
        if error_response:
            return error_response
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            vote = Vote.objects.filter(user=request.user, comment=comment).first()
            if not vote:
                Vote.objects.create(user=request.user, comment=comment, value=vote_value)
            elif vote.value != vote_value:
                vote.value = vote_value
                vote.save(update_fields=["value"])
            else:
                vote_value = 0
                vote.delete()
        return Response({"message": "Upvoted successfully!", "vote_value": vote_value, "vote_count": comment.get_vote_count()})
