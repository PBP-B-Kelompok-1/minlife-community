from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

from django.conf import settings

class User(AbstractUser):
    """
    Role dan permissions User didefinisikan dalam Group di mana User tersebut terdaftar.

    Note: Email didaftarkan di User (bukan Profile atau SocialLink), opsional untuk ditampilkan.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    avatar_url = models.URLField(
            blank=True,
            default="",
            max_length=500,
            help_text="User avatar URL."
        )

    avatar = models.ImageField(
        upload_to="avatars/",
        blank=True,
        help_text="Profile picture."
    )

    bio = models.TextField(
        blank=True,
        default = "",
        max_length=160, 
        help_text="Short description of the User."
    )
    
    following = models.ManyToManyField(
        "self",
        through="Follow",
        through_fields=("follower", "following"),
        symmetrical=False,          # A following B does NOT mean B follows A
        related_name="followers",
        blank=True,
    )
    
    @property
    def avatar_src(self):
        """URL of the uploaded profile picture, or an empty string if none."""
        return self.avatar.url if self.avatar else ""

class Follow(models.Model):
    follower = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="following_links"
    )
    following = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="follower_links"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["follower", "following"],
                name="unique_follow",
            ),
            models.CheckConstraint(
                condition=~models.Q(follower=models.F("following")),
                name="no_self_follow",
            ),
        ]

    def __str__(self):
        return f"{self.follower.username} → {self.following.username}"
    
# TODO: badges dari weekly challenge. Ini buat models baru karena relasi-nya n-to-m sama users
    
class SocialPlatform(models.TextChoices):
    """
    Example usage:
    ```
    request.user.social_links.get(platform=SocialPlatform.INSTAGRAM)
    ```
    """
    INSTAGRAM = "instagram", "Instagram"
    TWITTER = "twitter", "Twitter (X)"
    YOUTUBE = "youtube", "YouTube"
    LINKEDIN = "linkedin", "LinkedIn"
    WEBSITE = "website", "Website"

class SocialLink(models.Model):
    """
    Example usage:
    ```
    request.user.social_links.all()
    ```
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="social_links",
    )

    platform = models.CharField(
        max_length=20,
        choices=SocialPlatform,
    )

    url = models.URLField(
        max_length=500,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "platform"],
                name="unique_social_platform_per_user",
            ),
        ]
        ordering = ["platform"]

    def __str__(self):
        return f"{self.user.username} - {self.get_platform_display()}"
    
class Badge(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon_url = models.URLField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    

class UserBadge(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_badges")
    badge = models.ForeignKey(Badge, on_delete=models.PROTECT, related_name="awards")
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "badge"], name="unique_badge_per_user")]
