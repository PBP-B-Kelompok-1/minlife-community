from django.db import IntegrityError, transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.utils import timezone

from .models import CHALLENGE_TAG_NAME, Challenge, ChallengeSubmission
from .services import award_badge_if_eligible


def _create_submission_for_tagged_post(instance):
    """Create the current challenge submission for a tagged Post, if eligible."""
    today = timezone.localdate()
    if not instance.tags.filter(title=CHALLENGE_TAG_NAME).exists():
        return

    challenge = Challenge.objects.current(today).first()
    if challenge is None:
        return

    try:
        # A nested atomic block keeps an expected uniqueness race from marking
        # an outer ModelForm.save_m2m() transaction as broken.
        with transaction.atomic():
            ChallengeSubmission.objects.get_or_create(
                challenge=challenge,
                post=instance,
                defaults={"user": instance.author},
            )
    except IntegrityError:
        return


def post_saved(sender, instance, **kwargs):
    """Keep tagged Posts synchronized when they are saved again."""
    _create_submission_for_tagged_post(instance)


def post_tags_changed(sender, instance, action, reverse, **kwargs):
    """Create a submission after ModelForm.save_m2m() adds the challenge tag."""
    if reverse or action != "post_add":
        return

    _create_submission_for_tagged_post(instance)


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
    m2m_changed.connect(
        post_tags_changed,
        sender=Post.tags.through,
        dispatch_uid="weeklychallenge.post_tags_changed",
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
