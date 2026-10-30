from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("posts", "0003_alter_post_content"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="vote",
            name="one_vote_per_user",
        ),
        migrations.AddConstraint(
            model_name="vote",
            constraint=models.UniqueConstraint(
                fields=("user", "post"),
                condition=Q(("post__isnull", False)),
                name="one_post_vote_per_user",
            ),
        ),
        migrations.AddConstraint(
            model_name="vote",
            constraint=models.UniqueConstraint(
                fields=("user", "comment"),
                condition=Q(("comment__isnull", False)),
                name="one_comment_vote_per_user",
            ),
        ),
    ]
