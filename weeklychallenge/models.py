"""Weekly Challenge: models dan fungsi servis. Kontrak antar modul ada di README.md."""
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

CHALLENGE_TAG_NAME = "Weekly Challenge"
DEFAULT_UPVOTE_THRESHOLD = 10


# Should be the number of days, do not change!!
MAX_TASKS_PER_CHALLENGE = 7

class ChallengeQuerySet(models.QuerySet):
    def _cutoff(self, today):
        return (today or timezone.localdate()) - timedelta(days=MAX_TASKS_PER_CHALLENGE - 1)

    def current(self, today=None):
        today = today or timezone.localdate()
        return self.filter(week_start__lte=today, week_start__gte=self._cutoff(today))

    def upcoming(self, today=None):
        return self.filter(week_start__gt=today or timezone.localdate())

    def past(self, today=None):
        return self.filter(week_start__lt=self._cutoff(today))

class ChallengeTask(models.Model):
    """One daily task (sub-challenge) inside a weekly Challenge. Max 7 per challenge."""

    challenge = models.ForeignKey(
        "Challenge",
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    day_number = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(MAX_TASKS_PER_CHALLENGE),
        ],
        help_text="Day of the challenge week (1-7).",
    )
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["day_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["challenge", "day_number"],
                name="unique_task_day_per_challenge",
            ),
            models.CheckConstraint(
                condition=models.Q(day_number__gte=1, day_number__lte=MAX_TASKS_PER_CHALLENGE),
                name="task_day_between_1_and_7",
            ),
        ]

    def __str__(self):
        return f"{self.challenge} - Day {self.day_number}: {self.title}"

class Challenge(models.Model):
    title = models.CharField(max_length=150)
    background = models.TextField(help_text="Latar belakang masalah")
    description = models.TextField(help_text="Deskripsi challenge")
    goal = models.TextField(help_text="Tujuan/ekspektasi setelah challenge")
    tag = models.OneToOneField(
        "posts.Tag",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        editable=False,
        related_name="challenge",
    )
    
    upvote_threshold = models.PositiveIntegerField(
        default=DEFAULT_UPVOTE_THRESHOLD, help_text="Skor bersih yang dibutuhkan submission untuk mendapat badge."
    )
    badge = models.OneToOneField(
        "users.Badge", on_delete=models.PROTECT, related_name="challenge"
    )

    week_start = models.DateField()

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_challenges",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-week_start"]

    def __str__(self):
        return self.title

    @property
    def week_end(self):
        return self.week_start + timedelta(days=MAX_TASKS_PER_CHALLENGE - 1)

    @property
    def is_open(self):
        """Submission hanya boleh di dalam minggu challenge."""
        return self.week_start <= timezone.localdate() <= self.week_end
    
    objects = ChallengeQuerySet.as_manager()



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
