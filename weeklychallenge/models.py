"""Weekly Challenge: models dan fungsi servis. Kontrak antar modul ada di README.md."""
from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

CHALLENGE_TAG_NAME = "Weekly Challenge"
DEFAULT_UPVOTE_THRESHOLD = 10

class Challenge(models.Model):
    title = models.CharField(max_length=150)
    background = models.TextField(help_text="Latar belakang masalah")
    description = models.TextField(help_text="Deskripsi challenge")
    goal = models.TextField(help_text="Tujuan/ekspektasi setelah challenge")

    upvote_threshold = models.PositiveIntegerField(
        default=DEFAULT_UPVOTE_THRESHOLD, help_text="Skor bersih yang dibutuhkan submission untuk mendapat badge."
    )
    badge = models.ForeignKey(
        "users.Badge", on_delete=models.PROTECT, related_name="challenges"
    )

    week_start = models.DateField()
    week_end = models.DateField()

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_challenges",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-week_start"]
        constraints = [
            models.CheckConstraint(
                condition=Q(week_end__gte=F("week_start")),
                name="challenge_end_not_before_start",
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def is_open(self):
        """Submission hanya boleh di dalam minggu challenge."""
        return self.week_start <= timezone.localdate() <= self.week_end


class ChallengeSubmission(models.Model):
    """Menandai sebuah Post sebagai submission challenge."""

    challenge = models.ForeignKey(
        Challenge, on_delete=models.CASCADE, related_name="submissions"
    )
    post = models.OneToOneField(
        "posts.Post", on_delete=models.CASCADE, related_name="challenge_submission"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="challenge_submissions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["challenge", "user"], name="one_submission_per_user_per_challenge"
            ),
        ]

    def __str__(self):
        return f"{self.user} -> {self.challenge}"


