from django.db import transaction
from django.utils import timezone

from .models import Challenge, ChallengeSubmission


def get_current_challenge(today=None):
    """Return the challenge whose date range includes today, if one exists."""
    if today is None:
        today = timezone.localdate()

    return Challenge.objects.filter(
        week_start__lte=today,
        week_end__gte=today,
    ).first()


def user_has_submitted(user, challenge):
    """Return whether an authenticated user already submitted to this challenge."""
    if not getattr(user, "is_authenticated", False):
        return False

    return ChallengeSubmission.objects.filter(
        user=user,
        challenge=challenge,
    ).exists()


@transaction.atomic
def create_challenge(*, form, formset, user):
    """Create a challenge, its badge and tag, and its validated task formset atomically."""
    from posts.models import Tag
    from users.models import Badge

    challenge = form.save(commit=False)
    challenge.badge = Badge.objects.create(
        name=f"{challenge.title} Badge",
        description=f"Selesaikan challenge: {challenge.title}",
    )
    challenge.created_by = user
    challenge.save()

    challenge.tag = Tag.objects.create(title=f"weeklychallenge{challenge.pk}")
    challenge.save(update_fields=["tag"])

    formset.instance = challenge
    formset.save()
    return challenge


@transaction.atomic
def award_badge_if_eligible(post):
    """Award the submission's challenge badge once its net vote score meets the threshold."""
    from users.models import UserBadge

    try:
        submission = post.challenge_submission
    except ChallengeSubmission.DoesNotExist:
        return False

    if post.get_vote_count() < submission.challenge.upvote_threshold:
        return False

    _, created = UserBadge.objects.get_or_create(
        user=submission.user,
        badge=submission.challenge.badge,
    )
    return created
