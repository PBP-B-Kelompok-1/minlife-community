from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_GET, require_http_methods

from .forms import AnnouncementForm
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
        "can_add_announcement": request.user.has_perm(
            "announcements.add_announcement"
        ),
        "can_change_announcement": request.user.has_perm(
            "announcements.change_announcement"
        ),
        "can_delete_announcement": request.user.has_perm(
            "announcements.delete_announcement"
        ),
    }


def _render_announcement_list(request, context):
    template_name = (
        "announcements/_results.html"
        if request.headers.get("HX-Request") == "true"
        else "announcements/list.html"
    )
    return render(request, template_name, context)


@require_GET
def announcement_list(request):
    return _render_announcement_list(request, _list_context(request))


@require_GET
def announcement_detail(request, announcement_id):
    announcement = get_object_or_404(Announcement, pk=announcement_id)
    return _render_announcement_list(
        request,
        _list_context(request, selected_announcement=announcement),
    )


@login_required
@permission_required("announcements.add_announcement", raise_exception=True)
@require_http_methods(["GET", "POST"])
def create_announcement(request):
    form = AnnouncementForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        announcement = form.save(commit=False)
        announcement.created_by = request.user
        announcement.save()
        messages.success(request, "Announcement created successfully.")
        return redirect("announcements:detail", announcement_id=announcement.pk)

    return render(
        request,
        "announcements/form.html",
        {
            "form": form,
            "page_title": "Add Announcement",
            "submit_label": "Create Announcement",
            "cancel_url": reverse("announcements:list"),
        },
    )


@login_required
@permission_required("announcements.change_announcement", raise_exception=True)
@require_http_methods(["GET", "POST"])
def update_announcement(request, announcement_id):
    announcement = get_object_or_404(Announcement, pk=announcement_id)
    form = AnnouncementForm(request.POST or None, instance=announcement)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Announcement updated successfully.")
        return redirect("announcements:detail", announcement_id=announcement.pk)

    return render(
        request,
        "announcements/form.html",
        {
            "form": form,
            "page_title": "Edit Announcement",
            "submit_label": "Save Changes",
            "cancel_url": reverse(
                "announcements:detail",
                kwargs={"announcement_id": announcement.pk},
            ),
        },
    )


@login_required
@permission_required("announcements.delete_announcement", raise_exception=True)
@require_http_methods(["GET", "POST"])
def delete_announcement(request, announcement_id):
    announcement = get_object_or_404(Announcement, pk=announcement_id)
    if request.method == "POST":
        announcement.delete()
        messages.success(request, "Announcement deleted successfully.")
        return redirect("announcements:list")

    return render(
        request,
        "announcements/confirm_delete.html",
        {"announcement": announcement},
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
