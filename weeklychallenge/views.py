from datetime import timedelta
from functools import wraps

from django.contrib.auth.decorators import permission_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, IntegerField, Sum, Value
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .forms import ChallengeForm, ChallengeTaskFormSet
from .models import Challenge, ChallengeSubmission, MAX_TASKS_PER_CHALLENGE
from .services import create_challenge

CHALLENGES_PER_PAGE = 6
SUBMISSIONS_PER_PAGE = 8
TASK_FORM_PERMISSIONS = (
    "weeklychallenge.add_challenge",
    "weeklychallenge.change_challenge",
)


def _can_manage_challenges(user):
    return user.is_authenticated and any(
        user.has_perm(permission) for permission in TASK_FORM_PERMISSIONS
    )


def challenge_management_required(view):
    """Require authentication and either add or change challenge permission."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not _can_manage_challenges(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped


def show_weekly_challenge(request):
    """Render the active challenge, its current task, timeline, and scored submissions."""
    today = timezone.localdate()
    can_create_challenge = request.user.is_authenticated and request.user.has_perm(
        "weeklychallenge.add_challenge"
    )
    can_manage = request.user.is_authenticated and request.user.has_perm(
        "weeklychallenge.change_challenge"
    )
    challenge = _challenge_queryset().current().prefetch_related("tasks").first()
    upcoming_challenges = _challenge_queryset().upcoming().order_by("week_start")[:3]
    past_challenges = _challenge_queryset().past()[:3]
    
    if challenge is None:
        return render(
            request,
            "challenges/page.html",
            {
                "challenge": None,
                "can_create_challenge": can_create_challenge,
                "can_manage": can_manage,
                "upcoming_challenges": upcoming_challenges,
                "past_challenges": past_challenges,
            },
        )

    current_day = min((today - challenge.week_start).days + 1, MAX_TASKS_PER_CHALLENGE)
    tasks_by_day = {task.day_number: task for task in challenge.tasks.all()}
    timeline = [
        {
            "day_number": day_number,
            "date": challenge.week_start + timedelta(days=day_number - 1),
            "is_current": day_number == current_day,
        }
        for day_number in range(1, MAX_TASKS_PER_CHALLENGE + 1)
    ]
    submissions = (
        ChallengeSubmission.objects.filter(challenge=challenge)
        .select_related("post", "user")
        .annotate(
            score=Coalesce(
                Sum("post__votes__value"),
                Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("-score", "-created_at")
    )
    has_submitted = request.user.is_authenticated and ChallengeSubmission.objects.filter(
        challenge=challenge, user=request.user
    ).exists()

    return render(
        request,
        "challenges/page.html",
        {
            "challenge": challenge,
            "can_create_challenge": can_create_challenge,
            "current_day": current_day,
            "current_task": tasks_by_day.get(current_day),
            "timeline": timeline,
            "submissions": submissions,
            "has_submitted": has_submitted,
            "can_manage": can_manage,
            "upcoming_challenges": upcoming_challenges,
            "past_challenges": past_challenges,
        },
    )


def challenge_list(request):
    """Render the challenge directory with its HTMX-filterable list partial."""
    return render(
        request,
        "challenges/list.html",
        _challenge_list_context(request),
    )


def challenge_list_partial(request):
    """Return a paginated challenge list filtered by status and title search."""
    return render(
        request,
        "challenges/components/_challenge_list.html",
        _challenge_list_context(request),
    )


def _challenge_list_context(request):
    today = timezone.localdate()
    status = request.GET.get("status", "open")
    search = request.GET.get("q", "").strip()
    challenges = _challenge_queryset()

    if status == "open":
        challenges = challenges.current()
    elif status == "upcoming":
        challenges = challenges.upcoming()
    elif status == "past":
        challenges = challenges.past()

    if search:
        challenges = challenges.filter(title__icontains=search)

    page_obj = Paginator(challenges, CHALLENGES_PER_PAGE).get_page(
        request.GET.get("page")
    )
    query_params = request.GET.copy()
    query_params.pop("page", None)
    return {
        "challenges": page_obj,
        "page_obj": page_obj,
        "status": status,
        "search": search,
        "today": today,
        "can_manage": request.user.is_authenticated
        and request.user.has_perm("weeklychallenge.change_challenge"),
        "can_create_challenge": request.user.is_authenticated
        and request.user.has_perm("weeklychallenge.add_challenge"),
        "page_query": query_params.urlencode(),
        "upcoming_ids": set(
            Challenge.objects.upcoming(today).values_list("pk", flat=True)
        ),
        "past_ids": set(
            Challenge.objects.past(today).values_list("pk", flat=True)
        ),
    }


def _challenge_queryset():
    return (
        Challenge.objects.select_related("badge", "tag")
        .annotate(submission_count=Count("submissions", distinct=True))
        .order_by("-week_start", "-pk")
    )


def _submission_queryset(challenge, sort):
    submissions = ChallengeSubmission.objects.filter(challenge=challenge)
    submissions = submissions.select_related("post", "user").annotate(
        score=Coalesce(
            Sum("post__votes__value"),
            Value(0),
            output_field=IntegerField(),
        )
    )
    if sort == "newest":
        return submissions.order_by("-created_at")
    return submissions.order_by("-score", "-created_at")


def _submission_list_context(request, challenge):
    sort = request.GET.get("sort", "score")
    if sort not in {"score", "newest"}:
        sort = "score"

    page_obj = Paginator(
        _submission_queryset(challenge, sort),
        SUBMISSIONS_PER_PAGE,
    ).get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    return {
        "challenge": challenge,
        "submissions": page_obj,
        "page_obj": page_obj,
        "sort": sort,
        "page_query": query_params.urlencode(),
    }


def challenge_detail(request, pk):
    challenge = get_object_or_404(Challenge, pk=pk)
    can_manage = request.user.has_perm("weeklychallenge.change_challenge")
    is_upcoming = Challenge.objects.upcoming().filter(pk=pk).exists()
    if is_upcoming and not can_manage:
        return render(request, "challenges/detail.html",
                      {"challenge": challenge, "is_teaser": True, "can_manage": can_manage})

    challenge = Challenge.objects.select_related("badge", "tag").get(pk=pk)
    today = timezone.localdate()
    current_day = min(
        max((today - challenge.week_start).days + 1, 1),
        MAX_TASKS_PER_CHALLENGE,
    )
    visible_tasks = challenge.tasks.filter(day_number__lte=current_day)
    has_submitted = request.user.is_authenticated and ChallengeSubmission.objects.filter(
        challenge=challenge, user=request.user
    ).exists()
    context = _submission_list_context(request, challenge)
    context.update({
        "has_submitted": has_submitted,
        "is_current": Challenge.objects.current().filter(pk=pk).exists(),
        "current_day": current_day,
        "visible_tasks": visible_tasks,
        "can_manage": can_manage,
    })
    return render(request, "challenges/detail.html", context)


def submission_list_partial(request, pk):
    """Return a sorted, paginated leaderboard partial for a challenge."""
    challenge = get_object_or_404(Challenge, pk=pk)
    if Challenge.objects.upcoming().filter(pk=pk).exists() and not request.user.has_perm(
        "weeklychallenge.change_challenge"
    ):
        raise Http404
    return render(
        request,
        "challenges/components/_submission_list.html",
        _submission_list_context(request, challenge),
    )


@permission_required("weeklychallenge.add_challenge", raise_exception=True)
def challenge_create(request):
    """Validate and create a challenge with its badge and task formset atomically."""
    if request.method == "POST":
        form = ChallengeForm(request.POST)
        formset = ChallengeTaskFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            challenge = create_challenge(form=form, formset=formset, user=request.user)
            return redirect("weeklychallenge:show_weekly_challenge")
    else:
        form = ChallengeForm()
        formset = ChallengeTaskFormSet()
    return render(
        request,
        "challenges/form.html",
        {
            "form": form,
            "formset": formset,
            "next_form_index": formset.total_form_count(),
            "active_task_count": _active_task_count(formset),
        },
    )


@permission_required("weeklychallenge.change_challenge", raise_exception=True)
def challenge_update(request, pk):
    """Update a challenge and its task formset without replacing its badge or tag."""
    challenge = get_object_or_404(Challenge, pk=pk)
    if request.method == "POST":
        form = ChallengeForm(request.POST, instance=challenge)
        formset = ChallengeTaskFormSet(request.POST, instance=challenge)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            return redirect("weeklychallenge:challenge_detail", pk=challenge.pk)
    else:
        form = ChallengeForm(instance=challenge)
        formset = ChallengeTaskFormSet(instance=challenge)
    return render(
        request,
        "challenges/form.html",
        {
            "challenge": challenge,
            "form": form,
            "formset": formset,
            "next_form_index": formset.total_form_count(),
            "active_task_count": _active_task_count(formset),
        },
    )


@require_http_methods(["GET", "POST"])
@permission_required("weeklychallenge.delete_challenge", raise_exception=True)
def challenge_delete(request, pk):
    """Confirm a moderator's challenge deletion and delete only after a POST."""
    challenge = get_object_or_404(Challenge, pk=pk)
    if request.method == "POST":
        challenge.delete()
        return redirect("weeklychallenge:challenge_list")
    return render(
        request,
        "challenges/confirm_delete.html",
        {"challenge": challenge},
    )


def _active_task_count(formset):
    """Count non-deleted task forms to keep the HTMX add control within the limit."""
    if not formset.is_bound:
        return formset.total_form_count()

    return sum(
        not formset.data.get(f"{formset.prefix}-{index}-DELETE")
        for index in range(formset.total_form_count())
    )


@require_GET
@challenge_management_required
def task_form_row(request):
    """Return one indexed empty task form and updated HTMX controls."""
    try:
        index = int(request.GET["index"])
        active_count = int(request.GET["active"])
    except (KeyError, ValueError):
        raise Http404("Invalid task form index.")

    if index < 0 or active_count < 0 or active_count >= MAX_TASKS_PER_CHALLENGE:
        raise Http404("The maximum number of tasks has been reached.")

    formset = ChallengeTaskFormSet()
    task_form = formset.empty_form
    task_form.prefix = f"{formset.prefix}-{index}"
    return render(
        request,
        "challenges/components/_task_form_added.html",
        {
            "task_form": task_form,
            "formset": formset,
            "next_form_index": index + 1,
            "active_task_count": active_count + 1,
            "total_forms_id": formset.management_form["TOTAL_FORMS"].id_for_label,
        },
    )


@require_POST
@challenge_management_required
def toggle_task_form_delete(request, index):
    """Toggle a task form's DELETE value while preserving submitted form data."""
    formset = ChallengeTaskFormSet(request.POST)
    if index >= formset.total_form_count():
        raise Http404("Task form not found.")

    delete_key = f"{formset.prefix}-{index}-DELETE"
    data = request.POST.copy()
    if data.get(delete_key):
        data.pop(delete_key, None)
    else:
        data[delete_key] = "on"

    formset = ChallengeTaskFormSet(data)
    task_form = formset.forms[index]
    return render(
        request,
        "challenges/components/_task_form_toggled.html",
        {
            "task_form": task_form,
            "task_index": index,
            "formset": formset,
            "next_form_index": formset.total_form_count(),
            "active_task_count": _active_task_count(formset),
        },
    )
