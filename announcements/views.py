import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import AnnouncementForm
from .models import Announcement, FCMSubscription
from .notifications import send_announcement_notification


logger = logging.getLogger(__name__)


SORT_ORDERS = {
    "newest": ("-created_at", "-id"),
    "oldest": ("created_at", "id"),
}


def _is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def _get_installation_id(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    installation_id = payload.get("installation_id")
    if not isinstance(installation_id, str):
        return None

    installation_id = installation_id.strip()
    if not installation_id or len(installation_id) > 255:
        return None

    return installation_id


def _get_filter_values(request):
    data = request.POST if request.method == "POST" else request.GET
    query = data.get("q", "").strip()
    sort = data.get("sort", "newest")
    if sort not in SORT_ORDERS:
        sort = "newest"
    return query, sort


def _send_announcement_notification_safely(announcement, detail_url):
    try:
        send_announcement_notification(announcement, detail_url)
    except Exception:
        logger.exception(
            "Could not send notification for announcement %s.",
            announcement.pk,
        )


def _get_filtered_announcements(request):
    query, sort = _get_filter_values(request)

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
    context = {
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
    return context


def _render_announcement_list(request, context):
    template_name = (
        "announcements/_results.html"
        if _is_htmx(request)
        else "announcements/list.html"
    )
    return render(request, template_name, context)


def _render_announcement_form(request, context):
    context["is_htmx"] = _is_htmx(request)
    template_name = (
        "announcements/_form.html"
        if context["is_htmx"]
        else "announcements/form.html"
    )
    return render(request, template_name, context)


def _htmx_mutation_response(request, message, selected_announcement=None):
    response = render(
        request,
        "announcements/_results.html",
        _list_context(request, selected_announcement=selected_announcement),
    )
    response.headers["HX-Retarget"] = "#announcement-results"
    response.headers["HX-Reswap"] = "outerHTML"
    response.headers["HX-Trigger"] = json.dumps(
        {"announcement-changed": {"message": message}}
    )
    return response


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
    query, sort = _get_filter_values(request)
    if request.method == "POST" and form.is_valid():
        announcement = form.save(commit=False)
        announcement.created_by = request.user
        announcement.save()
        detail_url = request.build_absolute_uri(
            reverse(
                "announcements:detail",
                kwargs={"announcement_id": announcement.pk},
            )
        )
        transaction.on_commit(
            lambda: _send_announcement_notification_safely(
                announcement,
                detail_url,
            )
        )
        if _is_htmx(request):
            return _htmx_mutation_response(
                request,
                "Announcement created successfully.",
                selected_announcement=announcement,
            )
        messages.success(request, "Announcement created successfully.")
        return redirect("announcements:detail", announcement_id=announcement.pk)

    return _render_announcement_form(
        request,
        {
            "form": form,
            "page_title": "Add Announcement",
            "submit_label": "Create Announcement",
            "cancel_url": reverse("announcements:list"),
            "form_action": reverse("announcements:create"),
            "query": query,
            "sort": sort,
        },
    )


@login_required
@permission_required("announcements.change_announcement", raise_exception=True)
@require_http_methods(["GET", "POST"])
def update_announcement(request, announcement_id):
    announcement = get_object_or_404(Announcement, pk=announcement_id)
    form = AnnouncementForm(request.POST or None, instance=announcement)
    query, sort = _get_filter_values(request)
    if request.method == "POST" and form.is_valid():
        form.save()
        if _is_htmx(request):
            return _htmx_mutation_response(
                request,
                "Announcement updated successfully.",
                selected_announcement=announcement,
            )
        messages.success(request, "Announcement updated successfully.")
        return redirect("announcements:detail", announcement_id=announcement.pk)

    return _render_announcement_form(
        request,
        {
            "form": form,
            "page_title": "Edit Announcement",
            "submit_label": "Save Changes",
            "cancel_url": reverse(
                "announcements:detail",
                kwargs={"announcement_id": announcement.pk},
            ),
            "form_action": reverse(
                "announcements:update",
                kwargs={"announcement_id": announcement.pk},
            ),
            "query": query,
            "sort": sort,
        },
    )


@login_required
@permission_required("announcements.delete_announcement", raise_exception=True)
@require_http_methods(["GET", "POST"])
def delete_announcement(request, announcement_id):
    announcement = get_object_or_404(Announcement, pk=announcement_id)
    query, sort = _get_filter_values(request)
    if request.method == "POST":
        announcement.delete()
        if _is_htmx(request):
            return _htmx_mutation_response(
                request,
                "Announcement deleted successfully.",
            )
        messages.success(request, "Announcement deleted successfully.")
        return redirect("announcements:list")

    template_name = (
        "announcements/_confirm_delete.html"
        if _is_htmx(request)
        else "announcements/confirm_delete.html"
    )
    return render(
        request,
        template_name,
        {
            "announcement": announcement,
            "is_htmx": _is_htmx(request),
            "form_action": reverse(
                "announcements:delete",
                kwargs={"announcement_id": announcement.pk},
            ),
            "query": query,
            "sort": sort,
        },
    )


@login_required
@require_POST
def subscribe_notifications(request):
    installation_id = _get_installation_id(request)
    if installation_id is None:
        return JsonResponse({"error": "Invalid installation_id."}, status=400)

    _, created = FCMSubscription.objects.update_or_create(
        installation_id=installation_id,
        defaults={"user": request.user},
    )
    return JsonResponse({"subscribed": True}, status=201 if created else 200)


@login_required
@require_POST
def unsubscribe_notifications(request):
    installation_id = _get_installation_id(request)
    if installation_id is None:
        return JsonResponse({"error": "Invalid installation_id."}, status=400)

    FCMSubscription.objects.filter(
        user=request.user,
        installation_id=installation_id,
    ).delete()
    return JsonResponse({"subscribed": False})


@require_GET
def firebase_messaging_service_worker(request):
    return render(
        request,
        "announcements/firebase-messaging-sw.js",
        {
            "firebase_web_config_json": json.dumps(
                settings.FIREBASE_WEB_CONFIG
            ),
            "firebase_web_sdk_version": settings.FIREBASE_WEB_SDK_VERSION,
        },
        content_type="application/javascript",
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
