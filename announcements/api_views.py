import logging

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Announcement, FCMSubscription
from .notifications import send_announcement_notification
from .permissions import AnnouncementPermission
from .serializers import AnnouncementSerializer, NotificationSubscriptionSerializer


logger = logging.getLogger(__name__)
API_AUTHENTICATION_CLASSES = (SessionAuthentication,)
SORT_ORDERS = {
    "newest": ("-created_at", "-id"),
    "oldest": ("created_at", "id"),
}


class AnnouncementPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


def _send_notification_safely(announcement, detail_url):
    try:
        send_announcement_notification(announcement, detail_url)
    except Exception:
        # An external push failure must not turn a saved announcement into a 500.
        logger.exception(
            "Could not send notification for announcement %s.", announcement.pk,
        )


@api_view(["GET", "POST"])
@authentication_classes(API_AUTHENTICATION_CLASSES)
@permission_classes([AnnouncementPermission])
def announcement_list_create(request):
    if request.method == "POST":
        serializer = AnnouncementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            announcement = serializer.save(created_by=request.user)
            detail_url = request.build_absolute_uri(reverse(
                "announcements:detail",
                kwargs={"announcement_id": announcement.pk},
            ))
            transaction.on_commit(
                lambda: _send_notification_safely(announcement, detail_url)
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    queryset = Announcement.objects.select_related("created_by")
    query = request.query_params.get("q", "").strip()
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        )
    sort = request.query_params.get("sort", "newest")
    queryset = queryset.order_by(*SORT_ORDERS.get(sort, SORT_ORDERS["newest"]))
    paginator = AnnouncementPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(
        AnnouncementSerializer(page, many=True).data
    )


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@authentication_classes(API_AUTHENTICATION_CLASSES)
@permission_classes([AnnouncementPermission])
def announcement_detail(request, announcement_id):
    announcement = get_object_or_404(
        Announcement.objects.select_related("created_by"), pk=announcement_id,
    )
    if request.method == "GET":
        return Response(AnnouncementSerializer(announcement).data)
    if request.method == "DELETE":
        announcement.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = AnnouncementSerializer(
        announcement, data=request.data, partial=request.method == "PATCH",
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(["GET"])
@authentication_classes(API_AUTHENTICATION_CLASSES)
@permission_classes([AllowAny])
def announcement_capabilities(request):
    return Response({
        "can_create": request.user.has_perm("announcements.add_announcement"),
        "can_change": request.user.has_perm("announcements.change_announcement"),
        "can_delete": request.user.has_perm("announcements.delete_announcement"),
    })


@api_view(["POST"])
@authentication_classes(API_AUTHENTICATION_CLASSES)
@permission_classes([IsAuthenticated])
def notification_subscribe(request):
    serializer = NotificationSubscriptionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    _, created = FCMSubscription.objects.update_or_create(
        installation_id=serializer.validated_data["installation_id"],
        defaults={"user": request.user},
    )
    return Response(
        {"subscribed": True},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["POST"])
@authentication_classes(API_AUTHENTICATION_CLASSES)
@permission_classes([IsAuthenticated])
def notification_unsubscribe(request):
    serializer = NotificationSubscriptionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    FCMSubscription.objects.filter(
        user=request.user,
        installation_id=serializer.validated_data["installation_id"],
    ).delete()
    return Response({"subscribed": False})
