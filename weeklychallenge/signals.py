from datetime import timedelta

from django.db import IntegrityError
from django.db.models.signals import post_delete, post_save
from django.utils import timezone

from .models import Challenge, ChallengeSubmission, MAX_TASKS_PER_CHALLENGE
from .services import award_badge_if_eligible


def post_saved(sender, instance, **kwargs):
    """Create an active challenge submission after a tagged Post is saved."""
    today = timezone.localdate()
    window = timedelta(days=MAX_TASKS_PER_CHALLENGE - 1)
    challenges = Challenge.objects.filter(
        tag__in=instance.tags.all(),
        week_start__lte=today,
        week_start__gte=today - window,
    )
    for challenge in challenges:
        try:
            ChallengeSubmission.objects.get_or_create(
                challenge=challenge,
                post=instance,
                defaults={"user": instance.author},
            )
        except IntegrityError:
            continue


def _award_badge_for_vote(vote):
    """Re-fetch a voted Post and award its challenge badge when eligible."""
    if not vote.post_id:
        return

    from posts.models import Post

    try:
        post = Post.objects.get(pk=vote.post_id)
    except Post.DoesNotExist:
        return

    award_badge_if_eligible(post)


def vote_saved(sender, instance, **kwargs):
    """Evaluate a challenge submission after a Post vote is saved."""
    _award_badge_for_vote(instance)


def vote_deleted(sender, instance, **kwargs):
    """Re-evaluate an existing challenge submission after a Post vote is deleted."""
    _award_badge_for_vote(instance)


def connect_signals():
    """Connect Weekly Challenge handlers once Django has loaded all app models."""
    from posts.models import Post, Vote

    post_save.connect(
        post_saved,
        sender=Post,
        dispatch_uid="weeklychallenge.post_saved",
    )
    post_save.connect(
        vote_saved,
        sender=Vote,
        dispatch_uid="weeklychallenge.vote_saved",
    )
    post_delete.connect(
        vote_deleted,
        sender=Vote,
        dispatch_uid="weeklychallenge.vote_deleted",
    )
