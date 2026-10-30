from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("weeklychallenge", "0004_remove_challenge_challenge_end_not_before_start_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="challenge",
            name="badge",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="challenge",
                to="users.badge",
            ),
        ),
        migrations.AlterField(
            model_name="challenge",
            name="tag",
            field=models.OneToOneField(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="challenge",
                to="posts.tag",
            ),
        ),
    ]
