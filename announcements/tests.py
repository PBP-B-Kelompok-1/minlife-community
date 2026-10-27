import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import Announcement


class AnnouncementModelTests(TestCase):
    def setUp(self):
        self.moderator = get_user_model().objects.create_user(
            username="announcement-moderator",
            password="test-password",
        )

    def create_announcement(self, **overrides):
        values = {
            "created_by": self.moderator,
            "title": "Community garden clean-up",
            "content": "Join the community garden clean-up this weekend.",
        }
        values.update(overrides)
        return Announcement.objects.create(**values)

    def test_announcement_uses_the_expected_field_configuration(self):
        announcement = self.create_announcement()

        self.assertIsInstance(announcement.pk, uuid.UUID)
        self.assertFalse(Announcement._meta.get_field("id").editable)
        self.assertEqual(Announcement._meta.get_field("title").max_length, 255)
        self.assertTrue(Announcement._meta.get_field("created_at").db_index)
        self.assertEqual(Announcement._meta.ordering, ["-created_at", "-id"])

    def test_announcement_string_representation_is_its_title(self):
        announcement = self.create_announcement(title="Repair cafe registration")

        self.assertEqual(str(announcement), "Repair cafe registration")

    def test_title_and_content_are_required(self):
        announcement = Announcement(
            created_by=self.moderator,
            title="",
            content="",
        )

        with self.assertRaises(ValidationError) as context:
            announcement.full_clean()

        self.assertIn("title", context.exception.message_dict)
        self.assertIn("content", context.exception.message_dict)

    def test_created_by_relation_exposes_the_users_created_announcements(self):
        announcement = self.create_announcement()

        self.assertQuerySetEqual(
            self.moderator.created_announcements.all(),
            [announcement],
        )

    def test_deleting_creator_preserves_announcement_and_sets_creator_to_null(self):
        announcement = self.create_announcement()

        self.moderator.delete()
        announcement.refresh_from_db()

        self.assertIsNone(announcement.created_by)
        self.assertTrue(Announcement.objects.filter(pk=announcement.pk).exists())

    def test_created_at_is_immutable_and_updated_at_changes_when_saved(self):
        announcement = self.create_announcement()
        original_created_at = announcement.created_at
        deliberately_old_updated_at = timezone.now() - timedelta(days=1)
        Announcement.objects.filter(pk=announcement.pk).update(
            updated_at=deliberately_old_updated_at
        )

        announcement.refresh_from_db()
        announcement.title = "Updated community garden clean-up"
        announcement.save()
        announcement.refresh_from_db()

        self.assertEqual(announcement.created_at, original_created_at)
        self.assertGreater(announcement.updated_at, deliberately_old_updated_at)

    def test_announcements_are_returned_newest_first(self):
        older = self.create_announcement(title="Older announcement")
        newer = self.create_announcement(title="Newer announcement")
        now = timezone.now()
        Announcement.objects.filter(pk=older.pk).update(
            created_at=now - timedelta(days=1)
        )
        Announcement.objects.filter(pk=newer.pk).update(created_at=now)

        self.assertQuerySetEqual(
            Announcement.objects.all(),
            [newer, older],
        )
