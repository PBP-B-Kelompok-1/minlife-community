from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0008_alter_comment_user_alter_post_author"),
    ]

    operations = [
        migrations.AddField(
            model_name="comment",
            name="is_deleted",
            field=models.BooleanField(default=False),
        ),
    ]
