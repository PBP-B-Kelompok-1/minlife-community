import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.test import TestCase
from django.urls import reverse
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

    def test_created_by_allows_null_and_uses_set_null_on_delete(self):
        created_by_field = Announcement._meta.get_field("created_by")
        announcement = self.create_announcement(created_by=None)

        self.assertTrue(created_by_field.null)
        self.assertIs(created_by_field.remote_field.on_delete, models.SET_NULL)
        self.assertIsNone(announcement.created_by)

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


class AnnouncementReadTests(TestCase):
    def setUp(self):
        self.moderator = get_user_model().objects.create_user(
            username="announcement-reader-test-moderator",
            password="test-password",
        )
        self.older = Announcement.objects.create(
            created_by=self.moderator,
            title="Repair cafe registration",
            content="Register with your neighbors before Friday.",
        )
        self.newer = Announcement.objects.create(
            created_by=self.moderator,
            title="Compost drop-off schedule",
            content="Bring reusable containers to the north gate.",
        )
        now = timezone.now()
        Announcement.objects.filter(pk=self.older.pk).update(
            created_at=now - timedelta(days=1)
        )
        Announcement.objects.filter(pk=self.newer.pk).update(created_at=now)

    def test_list_is_public_and_uses_default_newest_order(self):
        response = self.client.get(reverse("announcements:list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "announcements/list.html")
        self.assertQuerySetEqual(
            response.context["announcements"],
            [self.newer, self.older],
        )
        self.assertIsNone(response.context["selected_announcement"])
        self.assertEqual(response.context["query"], "")
        self.assertEqual(response.context["sort"], "newest")

    def test_list_has_an_empty_state(self):
        Announcement.objects.all().delete()

        response = self.client.get(reverse("announcements:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No announcements found")
        self.assertQuerySetEqual(response.context["announcements"], [])

    def test_list_searches_title_and_content_case_insensitively(self):
        title_response = self.client.get(
            reverse("announcements:list"),
            {"q": "  COMPOST  "},
        )
        content_response = self.client.get(
            reverse("announcements:list"),
            {"q": "NEIGHBORS"},
        )

        self.assertQuerySetEqual(
            title_response.context["announcements"],
            [self.newer],
        )
        self.assertEqual(title_response.context["query"], "COMPOST")
        self.assertQuerySetEqual(
            content_response.context["announcements"],
            [self.older],
        )

    def test_list_supports_oldest_sort_and_rejects_unknown_sort_values(self):
        oldest_response = self.client.get(
            reverse("announcements:list"),
            {"sort": "oldest"},
        )
        invalid_response = self.client.get(
            reverse("announcements:list"),
            {"sort": "not-a-valid-sort"},
        )

        self.assertQuerySetEqual(
            oldest_response.context["announcements"],
            [self.older, self.newer],
        )
        self.assertEqual(oldest_response.context["sort"], "oldest")
        self.assertQuerySetEqual(
            invalid_response.context["announcements"],
            [self.newer, self.older],
        )
        self.assertEqual(invalid_response.context["sort"], "newest")

    def test_detail_is_public_and_selects_the_requested_announcement(self):
        response = self.client.get(
            reverse(
                "announcements:detail",
                kwargs={"announcement_id": self.older.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "announcements/list.html")
        self.assertEqual(response.context["selected_announcement"], self.older)
        self.assertContains(response, self.older.title)
        self.assertContains(response, self.older.content)

    def test_detail_returns_not_found_for_unknown_uuid(self):
        response = self.client.get(
            reverse(
                "announcements:detail",
                kwargs={"announcement_id": uuid.UUID(int=0)},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_json_list_returns_expected_fields_in_default_order(self):
        response = self.client.get(reverse("api:get_announcements_json"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            [item["id"] for item in payload["data"]],
            [str(self.newer.pk), str(self.older.pk)],
        )
        self.assertEqual(
            set(payload["data"][0]),
            {
                "id",
                "title",
                "content",
                "created_at",
                "created_at_display",
                "updated_at",
            },
        )
        self.assertEqual(payload["query"], "")
        self.assertEqual(payload["sort"], "newest")

    def test_json_list_applies_database_search_and_sort(self):
        response = self.client.get(
            reverse("api:get_announcements_json"),
            {"q": "reusable", "sort": "oldest"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            [item["id"] for item in payload["data"]],
            [str(self.newer.pk)],
        )
        self.assertEqual(payload["query"], "reusable")
        self.assertEqual(payload["sort"], "oldest")

    def test_json_detail_returns_data_and_missing_item_returns_not_found(self):
        response = self.client.get(
            reverse(
                "api:get_announcement_json",
                kwargs={"announcement_id": self.older.pk},
            )
        )
        missing_response = self.client.get(
            reverse(
                "api:get_announcement_json",
                kwargs={"announcement_id": uuid.UUID(int=0)},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["id"], str(self.older.pk))
        self.assertEqual(response.json()["data"]["title"], self.older.title)
        self.assertEqual(missing_response.status_code, 404)

    def test_read_endpoints_only_accept_get_requests(self):
        html_response = self.client.post(reverse("announcements:list"))
        json_response = self.client.post(reverse("api:get_announcements_json"))

        self.assertEqual(html_response.status_code, 405)
        self.assertEqual(json_response.status_code, 405)
