from datetime import timedelta

from django.db.models import Count, IntegerField, Sum, Value
from django.db.models.functions import Coalesce

from .models import Challenge, ChallengeSubmission, MAX_TASKS_PER_CHALLENGE


def challenge_status(challenge, today):
    if challenge.week_start <= today <= challenge.week_end:
        return "open"
    if challenge.week_start > today:
        return "upcoming"
    return "past"


def annotated_submissions(challenge, sort="score"):
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
    )
    if sort == "newest":
        return submissions.order_by("-created_at")
    return submissions.order_by("-score", "-created_at")


def validate_no_overlap(week_start, exclude_pk=None):
    window = timedelta(days=MAX_TASKS_PER_CHALLENGE - 1)
    overlapping = Challenge.objects.filter(
        week_start__gte=week_start - window,
        week_start__lte=week_start + window,
    )
    if exclude_pk:
        overlapping = overlapping.exclude(pk=exclude_pk)
    return overlapping.exists()


def challenge_queryset():
    return (
        Challenge.objects.select_related("badge", "tag", "created_by")
        .annotate(submission_count=Count("submissions", distinct=True))
        .order_by("-week_start", "-pk")
    )
