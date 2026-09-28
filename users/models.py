from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

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

    bio = models.TextField(
        max_length=160, 
        help_text="Short description of the User."
    )

    zen_points = models.IntegerField(
        default=0,
        editable=False,
        help_text="Upvote accumulation."
    )
    # TODO: badges dari weekly challenge

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
