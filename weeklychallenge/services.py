from django.db import transaction

from .models import Challenge, ChallengeSubmission


def _create_badge(title):
    from users.models import Badge

    return Badge.objects.create(
        name=f"{title} Badge",
        description=f"Selesaikan challenge: {title}",
    )


def get_current_challenge(today=None):
    """Return the challenge whose date range includes today, if one exists."""
    return Challenge.objects.current(today).first()


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
    """Create a challenge, its badge, and validated task formset atomically."""
    challenge = form.save(commit=False)
    challenge.badge = _create_badge(challenge.title)
    challenge.created_by = user
    challenge.save()

    formset.instance = challenge
    formset.save()
    return challenge


@transaction.atomic
def create_challenge_from_data(*, validated_data, tasks_data, user):
    challenge = Challenge(
        **validated_data,
        badge=_create_badge(validated_data["title"]),
        created_by=user,
    )
    challenge.save()
    from .models import ChallengeTask

    ChallengeTask.objects.bulk_create(
        [ChallengeTask(challenge=challenge, **task) for task in tasks_data]
    )
    return challenge


@transaction.atomic
def update_challenge_from_data(*, challenge, validated_data, tasks_data=None):
    for field, value in validated_data.items():
        setattr(challenge, field, value)
    challenge.save()

    if tasks_data is not None:
        from .models import ChallengeTask

        challenge.tasks.all().delete()
        ChallengeTask.objects.bulk_create(
            [ChallengeTask(challenge=challenge, **task) for task in tasks_data]
        )
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
