from django.db import migrations


def create_weekly_challenge_tag(apps, schema_editor):
    Tag = apps.get_model("posts", "Tag")
    Tag.objects.get_or_create(title="Weekly Challenge")


class Migration(migrations.Migration):

    dependencies = [
        ("posts", "0005_alter_post_tags"),
    ]

    operations = [
        migrations.RunPython(create_weekly_challenge_tag, migrations.RunPython.noop),
    ]
