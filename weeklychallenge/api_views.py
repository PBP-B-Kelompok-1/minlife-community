from datetime import timedelta

from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Challenge
from .permissions import ChallengePermission
from .selectors import annotated_submissions, challenge_queryset, challenge_status
from .serializers import (
    ChallengeDetailSerializer, ChallengeListSerializer, ChallengeWriteSerializer,
    SubmissionSerializer,
)
from .services import (
    create_challenge_from_data, get_current_challenge,
    update_challenge_from_data,
)

API_AUTHENTICATION_CLASSES = (SessionAuthentication,)


class ChallengePagination(PageNumberPagination):
    page_size = 6
    page_size_query_param = "page_size"
    max_page_size = 50


def _context(request):
    return {"request": request, "today": timezone.localdate()}


def _paginate(request, queryset, serializer_class, context):
    paginator = ChallengePagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(
        serializer_class(page, many=True, context=context).data
    )


@api_view(["GET", "POST"])
@authentication_classes(API_AUTHENTICATION_CLASSES)
@permission_classes([ChallengePermission])
def challenge_list_create(request):
    if request.method == "POST":
        serializer = ChallengeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tasks = serializer.validated_data.pop("tasks")
        challenge = create_challenge_from_data(
            validated_data=serializer.validated_data,
            tasks_data=tasks,
            user=request.user,
        )
        return Response(
            ChallengeDetailSerializer(challenge, context=_context(request)).data,
            status=status.HTTP_201_CREATED,
        )

    status_filter = request.query_params.get("status", "open")
    if status_filter not in {"open", "upcoming", "past", "all"}:
        status_filter = "open"
    today = timezone.localdate()
    queryset = challenge_queryset()
    if status_filter == "open":
        queryset = queryset.filter(
            week_start__lte=today,
            week_start__gte=today - timedelta(days=6),
        )
    elif status_filter == "upcoming":
        queryset = queryset.filter(week_start__gt=today)
    elif status_filter == "past":
        queryset = queryset.filter(week_start__lt=today - timedelta(days=6))
    search = request.query_params.get("q", "").strip()
    if search:
        queryset = queryset.filter(title__icontains=search)
    return _paginate(request, queryset, ChallengeListSerializer, _context(request))


@api_view(["GET"])
@authentication_classes(API_AUTHENTICATION_CLASSES)
@permission_classes([AllowAny])
def challenge_current(request):
    challenge = get_current_challenge()
    if challenge is None:
        return Response({"detail": "No active challenge."}, status=status.HTTP_404_NOT_FOUND)
    challenge = challenge_queryset().get(pk=challenge.pk)
    return Response(ChallengeDetailSerializer(challenge, context=_context(request)).data)


@api_view(["GET"])
@authentication_classes(API_AUTHENTICATION_CLASSES)
@permission_classes([AllowAny])
def challenge_capabilities(request):
    user = request.user
    return Response({
        "can_create": bool(user.is_authenticated and user.has_perm("weeklychallenge.add_challenge")),
        "can_change": bool(user.is_authenticated and user.has_perm("weeklychallenge.change_challenge")),
        "can_delete": bool(user.is_authenticated and user.has_perm("weeklychallenge.delete_challenge")),
    })


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@authentication_classes(API_AUTHENTICATION_CLASSES)
@permission_classes([ChallengePermission])
def challenge_detail(request, pk):
    challenge = get_object_or_404(challenge_queryset(), pk=pk)
    if request.method == "GET":
        return Response(ChallengeDetailSerializer(challenge, context=_context(request)).data)
    if request.method == "DELETE":
        try:
            challenge.delete()
        except ProtectedError:
            return Response(
                {"detail": "Challenge tidak dapat dihapus karena masih digunakan."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = ChallengeWriteSerializer(
        challenge, data=request.data, partial=request.method == "PATCH"
    )
    serializer.is_valid(raise_exception=True)
    tasks = serializer.validated_data.pop("tasks", None)
    challenge = update_challenge_from_data(
        challenge=challenge,
        validated_data=serializer.validated_data,
        tasks_data=tasks,
    )
    challenge = challenge_queryset().get(pk=challenge.pk)
    return Response(ChallengeDetailSerializer(challenge, context=_context(request)).data)


@api_view(["GET"])
@authentication_classes(API_AUTHENTICATION_CLASSES)
@permission_classes([AllowAny])
def challenge_submissions(request, pk):
    challenge = get_object_or_404(Challenge, pk=pk)
    if (
        challenge_status(challenge, timezone.localdate()) == "upcoming"
        and not request.user.has_perm("weeklychallenge.change_challenge")
    ):
        return Response(status=status.HTTP_404_NOT_FOUND)
    sort = request.query_params.get("sort", "score")
    if sort not in {"score", "newest"}:
        sort = "score"
    return _paginate(
        request,
        annotated_submissions(challenge, sort),
        SubmissionSerializer,
        {"request": request},
    )
