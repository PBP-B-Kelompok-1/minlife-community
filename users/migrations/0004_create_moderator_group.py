from django.db import migrations


MODERATOR_PERMISSIONS = [
    ("posts", "post", "delete"),
    ("posts", "comment", "delete"),
    ("posts", "tag", "add"),
    ("posts", "tag", "change"),
    ("posts", "tag", "delete"),
    ("announcements", "announcement", "add"),
    ("announcements", "announcement", "change"),
    ("announcements", "announcement", "delete"),
    ("weeklychallenge", "challenge", "add"),
    ("weeklychallenge", "challenge", "change"),
    ("weeklychallenge", "challenge", "delete"),
]


def create_moderator_group(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    group, _ = Group.objects.get_or_create(name="Moderator")

    for app_label, model, action in MODERATOR_PERMISSIONS:
        content_type, _ = ContentType.objects.get_or_create(
            app_label=app_label,
            model=model,
        )
        permission, _ = Permission.objects.get_or_create(
            content_type=content_type,
            codename=f"{action}_{model}",
            defaults={"name": f"Can {action} {model}"},
        )
        group.permissions.add(permission)


class Migration(migrations.Migration):

    dependencies = [
    ("auth", "0001_initial"),
    ("contenttypes", "0002_remove_content_type_name"),
    ("users", "0003_alter_user_bio"),
    ]

    operations = [
        migrations.RunPython(create_moderator_group, migrations.RunPython.noop),
    ]
