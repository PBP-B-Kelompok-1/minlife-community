import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .models import Announcement, FCMSubscription


class AnnouncementAPITestBase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.moderator = user_model.objects.create_user(username="api-moderator")
        cls.moderator.groups.add(Group.objects.get(name="Moderator"))
        cls.reader = user_model.objects.create_user(username="api-reader")
        cls.other = user_model.objects.create_user(username="api-other")
        cls.older = Announcement.objects.create(
            created_by=cls.moderator, title="Repair cafe", content="Bring your tools.",
        )
        cls.newer = Announcement.objects.create(
            created_by=cls.moderator, title="Community update", content="Garden repair day.",
        )
        Announcement.objects.filter(pk=cls.older.pk).update(
            created_at=timezone.now() - timedelta(days=1),
        )

    def url(self, name="announcement-list", *args):
        return reverse(f"announcements_api:{name}", args=args)

    def payload(self):
        return {"title": "New announcement", "content": "Join the community event."}


class AnnouncementReadAPITests(AnnouncementAPITestBase):
    def test_public_list_is_paginated_and_newest_first(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {"count", "next", "previous", "results"})
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [str(self.newer.pk), str(self.older.pk)],
        )
        item = response.data["results"][0]
        self.assertEqual(item["created_by"], {
            "id": str(self.moderator.pk), "username": self.moderator.username,
        })
        self.assertIn("created_at_display", item)
        self.assertIn("updated_at", item)

    def test_search_title_content_and_empty_result(self):
        for query, expected in (
            (" CAFE ", [str(self.older.pk)]),
            ("garden", [str(self.newer.pk)]),
            ("not-found", []),
        ):
            with self.subTest(query=query):
                response = self.client.get(self.url(), {"q": query})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    [item["id"] for item in response.data["results"]], expected,
                )

    def test_sort_oldest_and_invalid_sort_falls_back_to_newest(self):
        for sort, first in (("oldest", self.older), ("invalid", self.newer)):
            response = self.client.get(self.url(), {"sort": sort})
            self.assertEqual(response.data["results"][0]["id"], str(first.pk))

    def test_pagination_links_can_be_followed_and_missing_page_is_json_404(self):
        response = self.client.get(self.url(), {"page_size": 1})
        self.assertEqual(len(response.data["results"]), 1)
        next_page = self.client.get(response.data["next"])
        self.assertEqual(next_page.data["results"][0]["id"], str(self.older.pk))
        response = self.client.get(self.url(), {"page": 99})
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.data)

    def test_page_size_is_capped_and_creator_does_not_cause_n_plus_one(self):
        Announcement.objects.bulk_create([
            Announcement(created_by=self.moderator, title=f"Extra {i}", content="Text")
            for i in range(51)
        ])
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.url(), {"page_size": 100})
        self.assertEqual(response.data["count"], 53)
        self.assertEqual(len(response.data["results"]), 50)
        self.assertLessEqual(len(queries), 3)

    def test_public_detail_and_deleted_creator(self):
        url = self.url("announcement-detail", self.older.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["content"], self.older.content)
        Announcement.objects.filter(pk=self.older.pk).update(created_by=None)
        self.assertIsNone(self.client.get(url).data["created_by"])

    def test_missing_detail_is_json_404(self):
        response = self.client.get(self.url("announcement-detail", uuid.uuid4()))
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.data)

    def test_capabilities_for_guest_reader_and_moderator(self):
        for user, allowed in ((None, False), (self.reader, False), (self.moderator, True)):
            self.client.logout()
            if user:
                self.client.force_login(user)
            response = self.client.get(self.url("announcement-capabilities"))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, {
                "can_create": allowed, "can_change": allowed, "can_delete": allowed,
            })

    def test_unsupported_method_returns_json_405(self):
        self.client.force_login(self.moderator)
        response = self.client.delete(self.url())
        self.assertEqual(response.status_code, 405)
        self.assertIn("detail", response.data)


class AnnouncementWriteAPITests(AnnouncementAPITestBase):
    def test_guest_and_reader_cannot_create_update_or_delete(self):
        for user in (None, self.reader):
            self.client.logout()
            if user:
                self.client.force_login(user)
            detail_url = self.url("announcement-detail", self.older.pk)
            for method, url in (
                ("post", self.url()), ("put", detail_url),
                ("patch", detail_url), ("delete", detail_url),
            ):
                with self.subTest(user=user, method=method):
                    response = getattr(self.client, method)(url, self.payload(), format="json")
                    self.assertEqual(response.status_code, 403)
                    self.assertIn("detail", response.data)
        self.assertEqual(Announcement.objects.count(), 2)
        self.older.refresh_from_db()
        self.assertEqual(self.older.title, "Repair cafe")

    @patch("announcements.api_views.send_announcement_notification")
    def test_create_uses_session_creator_and_sends_once_after_commit(self, send):
        self.client.force_login(self.moderator)
        payload = {
            **self.payload(), "title": "  New announcement  ",
            "created_by": {"id": str(self.other.pk)},
            "id": str(uuid.uuid4()), "created_at": "2000-01-01T00:00:00Z",
        }
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(self.url(), payload, format="json")
            send.assert_not_called()
        self.assertEqual(response.status_code, 201)
        announcement = Announcement.objects.get(pk=response.data["id"])
        self.assertEqual(announcement.created_by, self.moderator)
        self.assertEqual(announcement.title, "New announcement")
        self.assertNotEqual(str(announcement.pk), payload["id"])
        self.assertNotEqual(announcement.created_at.year, 2000)
        self.assertEqual(len(callbacks), 1)
        send.assert_called_once_with(announcement, "http://testserver" + reverse(
            "announcements:detail", kwargs={"announcement_id": announcement.pk},
        ))
        # Both clients read the same database, with their respective contracts.
        legacy = self.client.get(reverse("api:get_announcement_json", args=[announcement.pk]))
        self.assertEqual(legacy.json()["data"]["title"], announcement.title)

    @patch("announcements.api_views.send_announcement_notification")
    def test_invalid_create_is_400_and_never_sends(self, send):
        self.client.force_login(self.moderator)
        for payload in (
            {}, {"title": "Title"}, {"content": "Content"},
            {"title": " ", "content": "Valid"},
            {"title": "Valid", "content": "\n "},
            {"title": "x" * 256, "content": "Valid"},
            {"title": None, "content": "Valid"},
        ):
            with self.subTest(payload=payload), self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.url(), payload, format="json")
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Announcement.objects.count(), 2)
        send.assert_not_called()

    def test_malformed_json_returns_400(self):
        self.client.force_login(self.moderator)
        response = self.client.post(self.url(), '{"title":', content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)

    @patch("announcements.api_views.send_announcement_notification")
    def test_push_failure_keeps_saved_announcement_and_201(self, send):
        send.side_effect = RuntimeError("Firebase unavailable")
        self.client.force_login(self.moderator)
        with self.assertLogs("announcements.api_views", level="ERROR"):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.url(), self.payload(), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Announcement.objects.filter(pk=response.data["id"]).exists())

    @patch("announcements.api_views.send_announcement_notification")
    def test_rolled_back_create_does_not_send(self, send):
        self.client.force_login(self.moderator)
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError), transaction.atomic():
                response = self.client.post(self.url(), self.payload(), format="json")
                self.assertEqual(response.status_code, 201)
                raise RuntimeError("Roll back outer transaction")
        self.assertEqual(Announcement.objects.count(), 2)
        send.assert_not_called()

    @patch("announcements.api_views.send_announcement_notification")
    def test_patch_preserves_content_creator_and_creation_time_without_push(self, send):
        self.client.force_login(self.moderator)
        self.older.refresh_from_db()
        created_at = self.older.created_at
        previous_updated_at = self.older.updated_at
        response = self.client.patch(self.url("announcement-detail", self.older.pk), {
            "title": "Edited", "created_by": {"id": str(self.other.pk)},
            "created_at": "2000-01-01T00:00:00Z",
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.older.refresh_from_db()
        self.assertEqual(self.older.title, "Edited")
        self.assertEqual(self.older.content, "Bring your tools.")
        self.assertEqual(self.older.created_by, self.moderator)
        self.assertEqual(self.older.created_at, created_at)
        self.assertGreater(self.older.updated_at, previous_updated_at)
        send.assert_not_called()

    def test_put_requires_both_fields_and_valid_put_replaces_them(self):
        self.client.force_login(self.moderator)
        url = self.url("announcement-detail", self.older.pk)
        response = self.client.put(url, {"title": "Only title"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.older.refresh_from_db()
        self.assertEqual(self.older.title, "Repair cafe")
        response = self.client.put(url, self.payload(), format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["content"], self.payload()["content"])

    def test_delete_returns_empty_204_and_detail_becomes_404(self):
        self.client.force_login(self.moderator)
        url = self.url("announcement-detail", self.older.pk)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertFalse(Announcement.objects.filter(pk=self.older.pk).exists())
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_each_write_checks_its_own_model_permission(self):
        self.reader.user_permissions.add(Permission.objects.get(
            content_type__app_label="announcements", codename="add_announcement",
        ))
        self.client.force_login(self.reader)
        response = self.client.post(self.url(), self.payload(), format="json")
        self.assertEqual(response.status_code, 201)
        url = self.url("announcement-detail", response.data["id"])
        self.assertEqual(self.client.patch(url, {"title": "Denied"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)


class NotificationSubscriptionAPITests(AnnouncementAPITestBase):
    def test_guest_gets_json_403_instead_of_login_redirect(self):
        for name in ("notification-subscribe", "notification-unsubscribe"):
            response = self.client.post(self.url(name), {"installation_id": "device-fid"}, format="json")
            self.assertEqual(response.status_code, 403)
            self.assertIn("detail", response.data)

    def test_subscribe_is_idempotent_and_can_transfer_device_to_current_user(self):
        url = self.url("notification-subscribe")
        payload = {"installation_id": " device-fid ", "user": str(self.moderator.pk)}
        self.client.force_login(self.reader)
        first = self.client.post(url, payload, format="json")
        second = self.client.post(url, payload, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data, {"subscribed": True})
        self.assertEqual(FCMSubscription.objects.get().user, self.reader)
        self.assertEqual(FCMSubscription.objects.get().installation_id, "device-fid")
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 200)
        self.assertEqual(FCMSubscription.objects.count(), 1)
        self.assertEqual(FCMSubscription.objects.get().user, self.other)

    def test_invalid_identifier_is_400_without_writes(self):
        self.client.force_login(self.reader)
        for payload in ({}, [], {"installation_id": None}, {"installation_id": 123},
                        {"installation_id": True}, {"installation_id": []},
                        {"installation_id": " "}, {"installation_id": "x" * 256}):
            for name in ("notification-subscribe", "notification-unsubscribe"):
                with self.subTest(payload=payload, name=name):
                    response = self.client.post(self.url(name), payload, format="json")
                    self.assertEqual(response.status_code, 400)
        self.assertFalse(FCMSubscription.objects.exists())

    def test_unsubscribe_only_deletes_current_users_device_and_is_idempotent(self):
        subscription = FCMSubscription.objects.create(user=self.other, installation_id="other-fid")
        self.client.force_login(self.reader)
        url = self.url("notification-unsubscribe")
        payload = {"installation_id": "other-fid"}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(FCMSubscription.objects.filter(pk=subscription.pk).exists())
        self.client.force_login(self.other)
        for _ in range(2):
            response = self.client.post(url, payload, format="json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, {"subscribed": False})
        self.assertFalse(FCMSubscription.objects.exists())

    def test_subscription_endpoints_only_accept_post(self):
        self.client.force_login(self.reader)
        for name in ("notification-subscribe", "notification-unsubscribe"):
            self.assertEqual(self.client.get(self.url(name)).status_code, 405)


class AnnouncementSessionCSRFApiTests(AnnouncementAPITestBase):
    def test_session_writes_require_csrf_for_crud_and_subscription(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.moderator)
        detail_url = self.url("announcement-detail", self.older.pk)
        for method, url, payload in (
            ("post", self.url(), self.payload()),
            ("put", detail_url, self.payload()),
            ("patch", detail_url, {"title": "Denied"}),
            ("delete", detail_url, {}),
            ("post", self.url("notification-subscribe"), {"installation_id": "fid"}),
            ("post", self.url("notification-unsubscribe"), {"installation_id": "fid"}),
        ):
            with self.subTest(method=method, url=url):
                response = getattr(client, method)(url, payload, format="json")
                self.assertEqual(response.status_code, 403)
                self.assertIn("CSRF", str(response.data))
        self.assertEqual(Announcement.objects.count(), 2)
        self.assertFalse(FCMSubscription.objects.exists())

    def test_real_session_with_csrf_cookie_and_header_can_create_and_subscribe(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.moderator)
        client.get(reverse("login"))
        csrf_token = client.cookies["csrftoken"].value
        response = client.post(self.url(), self.payload(), format="json", HTTP_X_CSRFTOKEN=csrf_token)
        self.assertEqual(response.status_code, 201)
        response = client.post(self.url("notification-subscribe"), {
            "installation_id": "session-device-fid",
        }, format="json", HTTP_X_CSRFTOKEN=csrf_token)
        self.assertEqual(response.status_code, 201)
