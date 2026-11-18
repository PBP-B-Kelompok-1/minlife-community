from django.contrib.auth import logout
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Follow, User
from .serializers import UpdateProfileSerializer, UserDetailSerializer, UserSummarySerializer


class FollowingContextMixin:
    """Gives serializers the ids the viewer follows (for the is_following flag)."""
    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = self.request.user
        context["following_ids"] = (
            set(user.following.values_list("pk", flat=True)) if user.is_authenticated else set()
        )
        return context


class UserDetailView(FollowingContextMixin, generics.RetrieveAPIView):
    """GET /api/users/<id>/  public profile"""
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "pk"
    lookup_url_kwarg = "user_id"


class MeView(FollowingContextMixin, generics.RetrieveUpdateDestroyAPIView):
    """GET / PATCH / DELETE /api/users/me/"""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]   # multipart is needed for avatar uploads

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        return UserDetailSerializer if self.request.method == "GET" else UpdateProfileSerializer

    def perform_destroy(self, instance):
        logout(self.request)
        instance.delete()


class UserSearchView(FollowingContextMixin, generics.ListAPIView):
    """GET /api/users/search/?q=  (at least 2 characters, max 10 results)"""
    serializer_class = UserSummarySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        q = self.request.query_params.get("q", "").strip()
        if len(q) < 2:
            return User.objects.none()
        return (
            User.objects.filter(is_active=True)
            .filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
            .exclude(pk=self.request.user.pk)
            .order_by("username")[:10]
        )


class FollowView(APIView):
    """POST /api/users/<id>/follow/ follows, DELETE unfollows (both are idempotent)"""
    permission_classes = [permissions.IsAuthenticated]

    def _target(self, request, user_id):
        target = get_object_or_404(User, pk=user_id, is_active=True)
        if target == request.user:
            raise ValidationError("You can't follow yourself.")
        return target

    def _state(self, request, following):
        return {"following": following, "following_count": request.user.following.count()}

    def post(self, request, user_id):
        target = self._target(request, user_id)
        _, created = Follow.objects.get_or_create(follower=request.user, following=target)
        return Response(self._state(request, True), status=201 if created else 200)

    def delete(self, request, user_id):
        target = self._target(request, user_id)
        Follow.objects.filter(follower=request.user, following=target).delete()
        return Response(self._state(request, False))


class FollowingListView(FollowingContextMixin, generics.ListAPIView):
    """GET /api/users/<id>/following/  public"""
    serializer_class = UserSummarySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        profile_user = get_object_or_404(User, pk=self.kwargs["user_id"])
        return profile_user.following.filter(is_active=True).order_by("username")


class FollowersListView(FollowingContextMixin, generics.ListAPIView):
    """GET /api/users/<id>/followers/  owner only"""
    serializer_class = UserSummarySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        profile_user = get_object_or_404(User, pk=self.kwargs["user_id"])
        if profile_user != self.request.user:
            raise PermissionDenied("Only the profile owner can see followers.")
        return profile_user.followers.filter(is_active=True).order_by("username")