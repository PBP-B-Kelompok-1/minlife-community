from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_GET

from .models import Announcement


SORT_ORDERS = {
    "newest": ("-created_at", "-id"),
    "oldest": ("created_at", "id"),
}


def _get_filtered_announcements(request):
    query = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "newest")
    if sort not in SORT_ORDERS:
        sort = "newest"

    announcements = Announcement.objects.all()
    if query:
        announcements = announcements.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        )

    return announcements.order_by(*SORT_ORDERS[sort]), query, sort


def _serialize_announcement(announcement):
    created_at = timezone.localtime(announcement.created_at)
    updated_at = timezone.localtime(announcement.updated_at)
    return {
        "id": str(announcement.pk),
        "title": announcement.title,
        "content": announcement.content,
        "created_at": created_at.isoformat(),
        "created_at_display": date_format(created_at, "j M Y"),
        "updated_at": updated_at.isoformat(),
    }


def _list_context(request, selected_announcement=None):
    announcements, query, sort = _get_filtered_announcements(request)
    return {
        "announcements": announcements,
        "selected_announcement": selected_announcement,
        "query": query,
        "sort": sort,
    }


@require_GET
def announcement_list(request):
    return render(
        request,
        "announcements/list.html",
        _list_context(request),
    )


@require_GET
def announcement_detail(request, announcement_id):
    announcement = get_object_or_404(Announcement, pk=announcement_id)
    return render(
        request,
        "announcements/list.html",
        _list_context(request, selected_announcement=announcement),
    )


@require_GET
def get_announcements_json(request):
    announcements, query, sort = _get_filtered_announcements(request)
    return JsonResponse(
        {
            "data": [
                _serialize_announcement(announcement)
                for announcement in announcements
            ],
            "query": query,
            "sort": sort,
        }
    )


@require_GET
def get_announcement_json(request, announcement_id):
    announcement = get_object_or_404(Announcement, pk=announcement_id)
    return JsonResponse({"data": _serialize_announcement(announcement)})
