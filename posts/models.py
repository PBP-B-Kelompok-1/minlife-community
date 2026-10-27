from django.db import models
from django.db.models import CASCADE, Q, Sum
import uuid

from users.models import User

class Post(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # kalo reddit kan tetep ada yah walau kehapus, tapi keknya ribet
    author = models.ForeignKey(User, on_delete=CASCADE, null=False)
    title = models.CharField(max_length=255, blank=False, null=False)
    content = models.TextField(blank=True, null=False)
    tags = models.ManyToManyField("Tag", blank=True, related_name="tagged_posts")
    challenge_image = models.ImageField(
        upload_to="challenge_images/", blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(blank=True, null=True, auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]

    def get_vote_count(self):
        return self.votes.aggregate(sum=Sum("value"))["sum"] or 0

    def __str__(self):
        return self.title

class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, 
            on_delete=CASCADE, blank=False, null=False,
            related_name="comments", related_query_name="comment"
        )
    user = models.ForeignKey(User, on_delete=CASCADE, null=False)
    content = models.TextField(blank=False, null=False)
    replies_to_comment = models.ForeignKey("self", 
            on_delete=CASCADE, null=True, blank=True,
            related_name="replies", related_query_name="reply"
        )

    def get_vote_count(self):
        return self.votes.aggregate(sum=Sum("value"))["sum"] or 0

    def __str__(self):
        return self.content
    
class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, blank=False, null=False)

    def __str__(self):
        return self.title

class Vote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=CASCADE, null=False, blank=False)
    post = models.ForeignKey(
        Post, on_delete=CASCADE, related_name="votes", null=True, blank=True
    )
    comment = models.ForeignKey(
        Comment, on_delete=CASCADE, related_name="votes", null=True, blank=True
    )
    value = models.SmallIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"],
                condition=Q(post__isnull=False),
                name="one_post_vote_per_user",
            ),
            models.UniqueConstraint(
                fields=["user", "comment"],
                condition=Q(comment__isnull=False),
                name="one_comment_vote_per_user",
            ),
            models.CheckConstraint(
                condition=(Q(post__isnull=True, comment__isnull=False)) 
                | (Q(post__isnull=False, comment__isnull=True)),
                name="vote_either_post_or_comment",
            ),
            models.CheckConstraint(
                condition=Q(value__in=[1,-1]),
                name="vote_value_up_or_down",
            )
        ]

    def __str__(self):
        type = "Upvote" if self.value == 1 else "Downvote"
        return f"{type} on post \"{self.post.title}\"" # do i even need this...
