from django.core.exceptions import ValidationError
from django.db import transaction
from models import ChallengeSubmission, CHALLENGE_TAG_NAME

@transaction.atomic
def submit_challenge(*, user, challenge, title, content, image):
    """Buat Post dan ChallengeSubmission sekaligus."""
    from posts.models import Post, Tag

    if not challenge.is_open:
        raise ValidationError("Challenge ini sudah tidak menerima submission.")
    if not image:
        raise ValidationError("Foto bukti wajib diunggah.")
    if ChallengeSubmission.objects.filter(challenge=challenge, user=user).exists():
        raise ValidationError("Kamu sudah submit untuk challenge ini.")

    post = Post.objects.create(author=user, title=title, content=content, image=image)
    tag, _ = Tag.objects.get_or_create(
        name=CHALLENGE_TAG_NAME, defaults={"slug": "weekly-challenge"}
    )
    post.tags.add(tag)
    return ChallengeSubmission.objects.create(challenge=challenge, post=post, user=user)


@transaction.atomic
def maybe_award_badge(post):
    """
    Dipanggil setelah vote berubah. Badge hanya diberikan sekali dan tetap ada.
    """
    from users.models import UserBadge

    submission = (
        ChallengeSubmission.objects.select_related("challenge__badge")
        .filter(post=post)
        .first()
    )
    if submission is None:
        return None

    score = post.upvote_count - post.downvote_count
    if score < submission.challenge.upvote_threshold:
        return None

    badge, created = UserBadge.objects.get_or_create(
        user=submission.user, badge=submission.challenge.badge
    )
    return badge if created else None