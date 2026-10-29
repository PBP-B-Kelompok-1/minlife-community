import json
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
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


class AnnouncementCreateTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.regular_user = user_model.objects.create_user(
            username="announcement-regular-user",
            password="test-password",
        )
        self.moderator = user_model.objects.create_user(
            username="announcement-create-moderator",
            password="test-password",
        )
        self.moderator.groups.add(Group.objects.get(name="Moderator"))
        self.superuser = user_model.objects.create_superuser(
            username="announcement-superuser",
            password="test-password",
        )

    def valid_form_data(self, **overrides):
        data = {
            "title": "Community garden clean-up",
            "content": "Join the clean-up this Saturday.",
        }
        data.update(overrides)
        return data

    def test_announcement_form_exposes_only_editable_content_fields(self):
        from .forms import AnnouncementForm

        form = AnnouncementForm(data=self.valid_form_data())

        self.assertEqual(list(form.fields), ["title", "content"])
        self.assertTrue(form.is_valid(), form.errors)

    def test_announcement_form_requires_title_and_content(self):
        from .forms import AnnouncementForm

        form = AnnouncementForm(data={"title": "", "content": ""})

        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)
        self.assertIn("content", form.errors)

    def test_guest_is_redirected_to_login_before_opening_create_page(self):
        create_url = reverse("announcements:create")

        response = self.client.get(create_url)

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={create_url}",
            fetch_redirect_response=False,
        )

    def test_regular_user_receives_forbidden_and_cannot_create(self):
        self.client.force_login(self.regular_user)
        create_url = reverse("announcements:create")

        get_response = self.client.get(create_url)
        post_response = self.client.post(create_url, self.valid_form_data())

        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)
        self.assertEqual(Announcement.objects.count(), 0)

    def test_moderator_can_open_create_form(self):
        from .forms import AnnouncementForm

        self.client.force_login(self.moderator)

        response = self.client.get(reverse("announcements:create"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "announcements/form.html")
        self.assertIsInstance(response.context["form"], AnnouncementForm)

    def test_moderator_can_create_announcement_and_becomes_its_creator(self):
        self.client.force_login(self.moderator)

        response = self.client.post(
            reverse("announcements:create"),
            self.valid_form_data(created_by=self.regular_user.pk),
        )

        announcement = Announcement.objects.get()
        self.assertEqual(announcement.created_by, self.moderator)
        self.assertEqual(announcement.title, "Community garden clean-up")
        self.assertRedirects(
            response,
            reverse(
                "announcements:detail",
                kwargs={"announcement_id": announcement.pk},
            ),
        )

    def test_invalid_submission_is_redisplayed_without_creating_announcement(self):
        self.client.force_login(self.moderator)

        response = self.client.post(
            reverse("announcements:create"),
            {"title": "", "content": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "announcements/form.html")
        self.assertFormError(response.context["form"], "title", "This field is required.")
        self.assertFormError(response.context["form"], "content", "This field is required.")
        self.assertEqual(Announcement.objects.count(), 0)

    def test_superuser_can_create_announcement(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("announcements:create"),
            self.valid_form_data(title="Platform update"),
        )

        announcement = Announcement.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(announcement.created_by, self.superuser)

    def test_add_button_is_only_rendered_for_authorized_users(self):
        list_url = reverse("announcements:list")
        create_url = reverse("announcements:create")

        anonymous_response = self.client.get(list_url)
        self.client.force_login(self.regular_user)
        regular_response = self.client.get(list_url)
        self.client.force_login(self.moderator)
        moderator_response = self.client.get(list_url)

        self.assertNotContains(anonymous_response, create_url)
        self.assertNotContains(regular_response, create_url)
        self.assertContains(moderator_response, create_url)

    def test_create_endpoint_rejects_unsupported_methods(self):
        self.client.force_login(self.moderator)

        response = self.client.put(
            reverse("announcements:create"),
            data=self.valid_form_data(),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 405)


class AnnouncementUpdateDeleteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        moderator_group = Group.objects.get(name="Moderator")

        cls.regular_user = user_model.objects.create_user(
            username="announcement-update-regular-user",
            password="test-password",
        )
        cls.creator = user_model.objects.create_user(
            username="announcement-original-creator",
            password="test-password",
        )
        cls.creator.groups.add(moderator_group)
        cls.moderator = user_model.objects.create_user(
            username="announcement-update-moderator",
            password="test-password",
        )
        cls.moderator.groups.add(moderator_group)
        cls.superuser = user_model.objects.create_superuser(
            username="announcement-update-superuser",
            password="test-password",
        )
        cls.announcement = Announcement.objects.create(
            created_by=cls.creator,
            title="Original announcement",
            content="Original announcement content.",
        )

    def update_url(self, announcement=None):
        announcement = announcement or self.announcement
        return reverse(
            "announcements:update",
            kwargs={"announcement_id": announcement.pk},
        )

    def delete_url(self, announcement=None):
        announcement = announcement or self.announcement
        return reverse(
            "announcements:delete",
            kwargs={"announcement_id": announcement.pk},
        )

    def valid_update_data(self, **overrides):
        data = {
            "title": "Updated announcement",
            "content": "Updated announcement content.",
        }
        data.update(overrides)
        return data

    def test_guest_is_redirected_to_login_for_update_and_delete(self):
        update_url = self.update_url()
        delete_url = self.delete_url()

        update_response = self.client.get(update_url)
        delete_response = self.client.get(delete_url)

        self.assertRedirects(
            update_response,
            f"{reverse('login')}?next={update_url}",
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            delete_response,
            f"{reverse('login')}?next={delete_url}",
            fetch_redirect_response=False,
        )

    def test_regular_user_receives_forbidden_and_cannot_update_or_delete(self):
        self.client.force_login(self.regular_user)

        responses = [
            self.client.get(self.update_url()),
            self.client.post(self.update_url(), self.valid_update_data()),
            self.client.get(self.delete_url()),
            self.client.post(self.delete_url()),
        ]

        for response in responses:
            self.assertEqual(response.status_code, 403)
        self.announcement.refresh_from_db()
        self.assertEqual(self.announcement.title, "Original announcement")
        self.assertTrue(
            Announcement.objects.filter(pk=self.announcement.pk).exists()
        )

    def test_moderator_can_open_update_form_for_the_requested_announcement(self):
        from .forms import AnnouncementForm

        self.client.force_login(self.moderator)

        response = self.client.get(self.update_url())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "announcements/form.html")
        self.assertIsInstance(response.context["form"], AnnouncementForm)
        self.assertEqual(response.context["form"].instance, self.announcement)

    def test_moderator_can_update_content_without_changing_creator_or_created_at(self):
        original_creator = self.announcement.created_by
        original_created_at = self.announcement.created_at
        old_updated_at = timezone.now() - timedelta(days=1)
        Announcement.objects.filter(pk=self.announcement.pk).update(
            updated_at=old_updated_at
        )
        self.client.force_login(self.moderator)

        response = self.client.post(
            self.update_url(),
            self.valid_update_data(created_by=self.moderator.pk),
        )

        self.announcement.refresh_from_db()
        self.assertRedirects(
            response,
            reverse(
                "announcements:detail",
                kwargs={"announcement_id": self.announcement.pk},
            ),
        )
        self.assertEqual(self.announcement.title, "Updated announcement")
        self.assertEqual(self.announcement.content, "Updated announcement content.")
        self.assertEqual(self.announcement.created_by, original_creator)
        self.assertEqual(self.announcement.created_at, original_created_at)
        self.assertGreater(self.announcement.updated_at, old_updated_at)

    def test_invalid_update_is_redisplayed_without_changing_announcement(self):
        self.client.force_login(self.moderator)

        response = self.client.post(
            self.update_url(),
            {"title": "", "content": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "announcements/form.html")
        self.assertFormError(response.context["form"], "title", "This field is required.")
        self.assertFormError(response.context["form"], "content", "This field is required.")
        self.announcement.refresh_from_db()
        self.assertEqual(self.announcement.title, "Original announcement")

    def test_delete_get_only_displays_confirmation(self):
        self.client.force_login(self.moderator)

        response = self.client.get(self.delete_url())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "announcements/confirm_delete.html")
        self.assertEqual(response.context["announcement"], self.announcement)
        self.assertTrue(
            Announcement.objects.filter(pk=self.announcement.pk).exists()
        )

    def test_moderator_can_delete_announcement_with_post(self):
        self.client.force_login(self.moderator)

        response = self.client.post(self.delete_url())

        self.assertRedirects(response, reverse("announcements:list"))
        self.assertFalse(
            Announcement.objects.filter(pk=self.announcement.pk).exists()
        )

    def test_superuser_can_update_and_delete_announcement(self):
        self.client.force_login(self.superuser)

        update_response = self.client.post(
            self.update_url(),
            self.valid_update_data(title="Superuser update"),
        )
        delete_response = self.client.post(self.delete_url())

        self.assertEqual(update_response.status_code, 302)
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(
            Announcement.objects.filter(pk=self.announcement.pk).exists()
        )

    def test_edit_and_delete_controls_are_only_rendered_for_authorized_users(self):
        list_url = reverse("announcements:list")
        update_url = self.update_url()
        delete_url = self.delete_url()

        anonymous_response = self.client.get(list_url)
        self.client.force_login(self.regular_user)
        regular_response = self.client.get(list_url)
        self.client.force_login(self.moderator)
        moderator_response = self.client.get(list_url)

        for response in (anonymous_response, regular_response):
            self.assertNotContains(response, update_url)
            self.assertNotContains(response, delete_url)
        self.assertContains(moderator_response, update_url)
        self.assertContains(moderator_response, delete_url)

    def test_missing_announcement_returns_not_found_for_authorized_user(self):
        self.client.force_login(self.moderator)
        missing_id = uuid.UUID(int=0)

        update_response = self.client.get(
            reverse(
                "announcements:update",
                kwargs={"announcement_id": missing_id},
            )
        )
        delete_response = self.client.get(
            reverse(
                "announcements:delete",
                kwargs={"announcement_id": missing_id},
            )
        )

        self.assertEqual(update_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)

    def test_update_and_delete_reject_unsupported_methods(self):
        self.client.force_login(self.moderator)

        update_response = self.client.put(
            self.update_url(),
            data=self.valid_update_data(),
            content_type="application/json",
        )
        delete_response = self.client.put(self.delete_url())

        self.assertEqual(update_response.status_code, 405)
        self.assertEqual(delete_response.status_code, 405)


class AnnouncementHtmxReadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.moderator = user_model.objects.create_user(
            username="announcement-async-moderator",
            password="test-password",
        )
        cls.moderator.groups.add(Group.objects.get(name="Moderator"))
        cls.announcement = Announcement.objects.create(
            created_by=cls.moderator,
            title="Async announcement",
            content="Rendered safely without a full page reload.",
        )

    def test_list_loads_htmx_and_exposes_dynamic_filter_controls(self):
        response = self.client.get(reverse("announcements:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="announcements-app"')
        self.assertContains(
            response,
            'src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js"',
        )
        self.assertContains(
            response,
            f'hx-get="{reverse("announcements:list")}"',
        )
        self.assertContains(response, 'hx-target="#announcement-results"')
        self.assertContains(response, 'hx-push-url="true"')
        self.assertContains(
            response,
            'hx-trigger="input changed delay:300ms"',
        )

    def test_htmx_list_request_returns_only_the_results_fragment(self):
        response = self.client.get(
            reverse("announcements:list"),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "announcements/_results.html")
        self.assertTemplateNotUsed(response, "announcements/list.html")
        self.assertContains(response, 'id="announcement-results"')
        self.assertNotContains(response, "<title>")

    def test_detail_link_uses_htmx_with_a_normal_navigation_fallback(self):
        detail_url = reverse(
            "announcements:detail",
            kwargs={"announcement_id": self.announcement.pk},
        )
        list_response = self.client.get(reverse("announcements:list"))

        self.assertContains(list_response, f'href="{detail_url}?q=&amp;sort=newest"')
        self.assertContains(list_response, f'hx-get="{detail_url}?q=&amp;sort=newest"')
        self.assertContains(list_response, 'hx-target="#announcement-results"')
        self.assertContains(list_response, 'hx-push-url="true"')

        response = self.client.get(
            detail_url,
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "announcements/_results.html")
        self.assertContains(response, self.announcement.content)


class AnnouncementHtmxMutationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.moderator = user_model.objects.create_user(
            username="announcement-htmx-mutation-moderator",
            password="test-password",
        )
        cls.moderator.groups.add(Group.objects.get(name="Moderator"))
        cls.announcement = Announcement.objects.create(
            created_by=cls.moderator,
            title="HTMX mutation announcement",
            content="Original content for HTMX mutation tests.",
        )

    def create_url(self):
        return reverse("announcements:create")

    def update_url(self):
        return reverse(
            "announcements:update",
            kwargs={"announcement_id": self.announcement.pk},
        )

    def delete_url(self):
        return reverse(
            "announcements:delete",
            kwargs={"announcement_id": self.announcement.pk},
        )

    def assert_htmx_success_response(self, response, expected_message):
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "announcements/_results.html")
        self.assertEqual(response.headers["HX-Retarget"], "#announcement-results")
        self.assertEqual(response.headers["HX-Reswap"], "outerHTML")
        self.assertEqual(
            json.loads(response.headers["HX-Trigger"]),
            {"announcement-changed": {"message": expected_message}},
        )

    def test_moderator_controls_target_the_htmx_dialog(self):
        self.client.force_login(self.moderator)

        response = self.client.get(reverse("announcements:list"))

        self.assertContains(response, 'id="announcement-dialog"')
        self.assertContains(response, 'id="announcement-dialog-content"')
        for url in (self.create_url(), self.update_url(), self.delete_url()):
            self.assertContains(response, f'hx-get="{url}"')
        self.assertContains(response, 'hx-target="#announcement-dialog-content"')

    def test_htmx_create_get_returns_only_the_form_fragment(self):
        self.client.force_login(self.moderator)

        response = self.client.get(
            self.create_url(),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "announcements/_form.html")
        self.assertTemplateNotUsed(response, "announcements/form.html")
        self.assertContains(response, f'hx-post="{self.create_url()}"')

    def test_invalid_htmx_create_redisplays_errors_inside_the_dialog(self):
        self.client.force_login(self.moderator)
        original_count = Announcement.objects.count()

        response = self.client.post(
            self.create_url(),
            {"title": "", "content": ""},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "announcements/_form.html")
        self.assertContains(response, "This field is required.", count=2)
        self.assertEqual(Announcement.objects.count(), original_count)
        self.assertNotIn("HX-Retarget", response.headers)

    def test_valid_htmx_create_updates_results_and_signals_success(self):
        self.client.force_login(self.moderator)

        response = self.client.post(
            self.create_url(),
            {
                "title": "Created through HTMX",
                "content": "The list should update without a full page reload.",
            },
            HTTP_HX_REQUEST="true",
        )

        announcement = Announcement.objects.get(title="Created through HTMX")
        self.assertEqual(announcement.created_by, self.moderator)
        self.assertContains(response, "Created through HTMX")
        self.assert_htmx_success_response(
            response,
            "Announcement created successfully.",
        )

    def test_htmx_update_get_returns_only_the_form_fragment(self):
        self.client.force_login(self.moderator)

        response = self.client.get(
            self.update_url(),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "announcements/_form.html")
        self.assertTemplateNotUsed(response, "announcements/form.html")
        self.assertContains(response, self.announcement.title)

    def test_valid_htmx_update_preserves_creator_and_updates_results(self):
        original_creator = self.announcement.created_by
        original_created_at = self.announcement.created_at
        self.client.force_login(self.moderator)

        response = self.client.post(
            self.update_url(),
            {
                "title": "Updated through HTMX",
                "content": "Updated content through the modal.",
            },
            HTTP_HX_REQUEST="true",
        )

        self.announcement.refresh_from_db()
        self.assertEqual(self.announcement.created_by, original_creator)
        self.assertEqual(self.announcement.created_at, original_created_at)
        self.assertContains(response, "Updated through HTMX")
        self.assert_htmx_success_response(
            response,
            "Announcement updated successfully.",
        )

    def test_htmx_delete_confirmation_and_successful_post_use_fragments(self):
        self.client.force_login(self.moderator)

        get_response = self.client.get(
            self.delete_url(),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(get_response.status_code, 200)
        self.assertTemplateUsed(
            get_response,
            "announcements/_confirm_delete.html",
        )
        self.assertTemplateNotUsed(
            get_response,
            "announcements/confirm_delete.html",
        )
        self.assertContains(get_response, self.announcement.title)

        post_response = self.client.post(
            self.delete_url(),
            HTTP_HX_REQUEST="true",
        )

        self.assertFalse(
            Announcement.objects.filter(pk=self.announcement.pk).exists()
        )
        self.assertNotContains(post_response, self.announcement.title)
        self.assert_htmx_success_response(
            post_response,
            "Announcement deleted successfully.",
        )


class FCMSubscriptionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(
            username="notification-subscriber",
            password="test-password",
        )
        cls.other_user = user_model.objects.create_user(
            username="other-notification-subscriber",
            password="test-password",
        )

    def subscription_model(self):
        from .models import FCMSubscription

        return FCMSubscription

    def subscribe_url(self):
        return reverse("announcements:notification_subscribe")

    def unsubscribe_url(self):
        return reverse("announcements:notification_unsubscribe")

    def post_json(self, url, payload):
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_subscription_uses_expected_field_configuration(self):
        subscription_model = self.subscription_model()
        subscription = subscription_model.objects.create(
            user=self.user,
            installation_id="firebase-installation-id",
        )

        self.assertIsInstance(subscription.pk, uuid.UUID)
        self.assertFalse(subscription_model._meta.get_field("id").editable)
        self.assertEqual(
            subscription_model._meta.get_field("installation_id").max_length,
            255,
        )
        self.assertTrue(
            subscription_model._meta.get_field("installation_id").unique
        )
        self.assertEqual(
            subscription_model._meta.get_field("user").remote_field.related_name,
            "fcm_subscriptions",
        )
        self.assertEqual(
            subscription_model._meta.ordering,
            ["-updated_at", "-id"],
        )

    def test_guest_is_redirected_to_login_for_subscription_endpoints(self):
        for url in (self.subscribe_url(), self.unsubscribe_url()):
            response = self.post_json(
                url,
                {"installation_id": "firebase-installation-id"},
            )

            self.assertRedirects(
                response,
                f"{reverse('login')}?next={url}",
                fetch_redirect_response=False,
            )

    def test_authenticated_user_can_subscribe_an_installation(self):
        self.client.force_login(self.user)

        response = self.post_json(
            self.subscribe_url(),
            {"installation_id": "firebase-installation-id"},
        )

        subscription = self.subscription_model().objects.get()
        self.assertEqual(response.status_code, 201)
        self.assertJSONEqual(response.content, {"subscribed": True})
        self.assertEqual(subscription.user, self.user)
        self.assertEqual(subscription.installation_id, "firebase-installation-id")

    def test_subscribing_an_existing_installation_reassigns_it_to_current_user(self):
        subscription_model = self.subscription_model()
        subscription = subscription_model.objects.create(
            user=self.other_user,
            installation_id="shared-browser-installation-id",
        )
        self.client.force_login(self.user)

        response = self.post_json(
            self.subscribe_url(),
            {"installation_id": subscription.installation_id},
        )

        subscription.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(subscription_model.objects.count(), 1)
        self.assertEqual(subscription.user, self.user)

    def test_subscribe_rejects_invalid_json_and_installation_ids(self):
        self.client.force_login(self.user)
        invalid_requests = [
            ("not-json", "application/json"),
            (json.dumps({}), "application/json"),
            (json.dumps({"installation_id": ""}), "application/json"),
            (json.dumps({"installation_id": 123}), "application/json"),
            (json.dumps({"installation_id": "x" * 256}), "application/json"),
        ]

        for body, content_type in invalid_requests:
            with self.subTest(body=body):
                response = self.client.post(
                    self.subscribe_url(),
                    data=body,
                    content_type=content_type,
                )
                self.assertEqual(response.status_code, 400)

        self.assertEqual(self.subscription_model().objects.count(), 0)

    def test_user_can_unsubscribe_their_own_installation_idempotently(self):
        subscription_model = self.subscription_model()
        subscription_model.objects.create(
            user=self.user,
            installation_id="firebase-installation-id",
        )
        self.client.force_login(self.user)

        first_response = self.post_json(
            self.unsubscribe_url(),
            {"installation_id": "firebase-installation-id"},
        )
        second_response = self.post_json(
            self.unsubscribe_url(),
            {"installation_id": "firebase-installation-id"},
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertJSONEqual(first_response.content, {"subscribed": False})
        self.assertJSONEqual(second_response.content, {"subscribed": False})
        self.assertFalse(subscription_model.objects.exists())

    def test_user_cannot_unsubscribe_another_users_installation(self):
        subscription_model = self.subscription_model()
        subscription = subscription_model.objects.create(
            user=self.other_user,
            installation_id="other-users-installation-id",
        )
        self.client.force_login(self.user)

        response = self.post_json(
            self.unsubscribe_url(),
            {"installation_id": subscription.installation_id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(subscription_model.objects.filter(pk=subscription.pk).exists())

    def test_subscription_endpoints_only_accept_post(self):
        self.client.force_login(self.user)

        for url in (self.subscribe_url(), self.unsubscribe_url()):
            self.assertEqual(self.client.get(url).status_code, 405)
