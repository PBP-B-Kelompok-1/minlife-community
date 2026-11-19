from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APITestCase

from posts.models import Post, Vote
from users.models import Badge, UserBadge

from .models import Challenge, ChallengeSubmission, ChallengeTask


class ChallengeAPITestBase(APITestCase):
    def setUp(self):
        self.today = timezone.localdate()
        user_model = get_user_model()
        self.normal_user = user_model.objects.create_user(
            username="normal-api-user",
            password="test-password",
        )
        self.moderator = user_model.objects.create_user(
            username="moderator-api-user",
            password="test-password",
        )
        moderator_group = Group.objects.get(name="Moderator")
        self.moderator.groups.add(moderator_group)

        self.open_challenge = self.create_challenge(
            title="Open challenge",
            week_start=self.today - timedelta(days=2),
        )
        self.upcoming_challenge = self.create_challenge(
            title="Upcoming challenge",
            week_start=self.today + timedelta(days=7),
        )
        self.past_challenge = self.create_challenge(
            title="Past challenge",
            week_start=self.today - timedelta(days=10),
        )

        for challenge in (
            self.open_challenge,
            self.upcoming_challenge,
            self.past_challenge,
        ):
            self.create_tasks(challenge)

        self.first_submission = self.create_submission(
            self.open_challenge,
            username="submission-one",
            title="First submission",
            image_name="first.jpg",
        )
        self.second_submission = self.create_submission(
            self.open_challenge,
            username="submission-two",
            title="Second submission",
        )
        voter = user_model.objects.create_user(
            username="api-voter",
            password="test-password",
        )
        Vote.objects.create(user=voter, post=self.first_submission.post, value=1)
        Vote.objects.create(user=self.normal_user, post=self.first_submission.post, value=1)
        Vote.objects.create(user=voter, post=self.second_submission.post, value=1)

    def create_challenge(self, *, title, week_start):
        return Challenge.objects.create(
            title=title,
            background=f"{title} background",
            description=f"{title} description",
            goal=f"{title} goal",
            upvote_threshold=2,
            week_start=week_start,
            badge=Badge.objects.create(name=f"{title} badge"),
            created_by=self.moderator,
        )

    def create_tasks(self, challenge, count=7):
        ChallengeTask.objects.bulk_create(
            [
                ChallengeTask(
                    challenge=challenge,
                    day_number=day_number,
                    title=f"{challenge.title} task {day_number}",
                    description=f"Task description {day_number}",
                )
                for day_number in range(1, count + 1)
            ]
        )

    def create_submission(
        self,
        challenge,
        *,
        username,
        title,
        image_name=None,
    ):
        user = get_user_model().objects.create_user(
            username=username,
            password="test-password",
        )
        post_values = {
            "author": user,
            "title": title,
            "content": f"{title} content",
        }
        if image_name:
            post_values["challenge_image"] = SimpleUploadedFile(
                image_name,
                b"fake image data",
                content_type="image/jpeg",
            )
        post = Post.objects.create(**post_values)
        return ChallengeSubmission.objects.create(
            challenge=challenge,
            post=post,
            user=user,
        )

    def url(self, name, *args):
        from django.urls import reverse

        return reverse(f"weeklychallenge_api:{name}", args=args)


class ChallengeReadAPITests(ChallengeAPITestBase):
    def test_list_has_paginated_shape_and_default_open_filter(self):
        response = self.client.get(self.url("challenge-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data),
            {"count", "next", "previous", "results"},
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            self.open_challenge.pk,
        )

    def test_list_status_filters_and_invalid_status_falls_back_to_open(self):
        for status_filter, expected in (
            ("open", {self.open_challenge.pk}),
            ("upcoming", {self.upcoming_challenge.pk}),
            ("past", {self.past_challenge.pk}),
            ("all", {
                self.open_challenge.pk,
                self.upcoming_challenge.pk,
                self.past_challenge.pk,
            }),
            ("invalid", {self.open_challenge.pk}),
        ):
            response = self.client.get(
                self.url("challenge-list"),
                {"status": status_filter},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                {item["id"] for item in response.data["results"]},
                expected,
            )

    def test_list_search_and_empty_result(self):
        response = self.client.get(
            self.url("challenge-list"),
            {"status": "all", "q": "Upcoming"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            self.upcoming_challenge.pk,
        )

        response = self.client.get(
            self.url("challenge-list"),
            {"q": "does-not-exist"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_list_page_size_is_capped_at_fifty(self):
        for index in range(51):
            self.create_challenge(
                title=f"Additional challenge {index}",
                week_start=self.today + timedelta(days=14 + index * 7),
            )

        response = self.client.get(
            self.url("challenge-list"),
            {"status": "all", "page_size": 100},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 50)
        self.assertIsNotNone(response.data["next"])

    def test_detail_reveals_cumulative_tasks_for_normal_user(self):
        self.client.force_authenticate(user=self.normal_user)

        response = self.client.get(
            self.url("challenge-detail", self.open_challenge.pk)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["current_day"], 3)
        self.assertEqual(
            [task["day_number"] for task in response.data["tasks"]],
            [1, 2, 3],
        )
        self.assertFalse(response.data["is_teaser"])

    def test_detail_reveals_all_tasks_for_past_challenge(self):
        response = self.client.get(
            self.url("challenge-detail", self.past_challenge.pk)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["current_day"], 7)
        self.assertEqual(len(response.data["tasks"]), 7)

    def test_manager_sees_all_tasks_on_open_challenge(self):
        self.client.force_authenticate(user=self.moderator)

        response = self.client.get(
            self.url("challenge-detail", self.open_challenge.pk)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["tasks"]), 7)

    def test_current_returns_active_challenge_and_current_day(self):
        response = self.client.get(self.url("challenge-current"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.open_challenge.pk)
        self.assertEqual(response.data["current_day"], 3)

    def test_current_returns_404_when_no_challenge_is_active(self):
        self.open_challenge.delete()

        response = self.client.get(self.url("challenge-current"))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"detail": "No active challenge."})

    def test_unknown_challenge_returns_404(self):
        response = self.client.get(self.url("challenge-detail", 999999))

        self.assertEqual(response.status_code, 404)

    def test_upcoming_teaser_has_only_the_teaser_shape(self):
        expected_keys = {"id", "title", "week_start", "status", "is_teaser"}

        list_response = self.client.get(
            self.url("challenge-list"),
            {"status": "upcoming"},
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            set(list_response.data["results"][0]),
            expected_keys,
        )
        self.assertTrue(list_response.data["results"][0]["is_teaser"])

        detail_response = self.client.get(
            self.url("challenge-detail", self.upcoming_challenge.pk)
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(set(detail_response.data), expected_keys)
        self.assertTrue(detail_response.data["is_teaser"])

        submissions_response = self.client.get(
            self.url("challenge-submissions", self.upcoming_challenge.pk)
        )
        self.assertEqual(submissions_response.status_code, 404)

    def test_manager_sees_full_upcoming_challenge_and_submissions(self):
        self.client.force_authenticate(user=self.moderator)

        response = self.client.get(
            self.url("challenge-detail", self.upcoming_challenge.pk)
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("badge", response.data)
        self.assertIn("tasks", response.data)
        self.assertFalse(response.data["is_teaser"])

    def test_capabilities_are_false_for_anonymous_and_true_for_moderator(self):
        response = self.client.get(self.url("challenge-capabilities"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {"can_create": False, "can_change": False, "can_delete": False},
        )

        self.client.force_authenticate(user=self.moderator)
        response = self.client.get(self.url("challenge-capabilities"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {"can_create": True, "can_change": True, "can_delete": True},
        )

    def test_submissions_are_sorted_by_score_then_newest(self):
        response = self.client.get(
            self.url("challenge-submissions", self.open_challenge.pk)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [self.first_submission.pk, self.second_submission.pk],
        )
        self.assertEqual(response.data["results"][0]["score"], 2)
        self.assertEqual(response.data["results"][1]["score"], 1)

    def test_submissions_can_be_sorted_by_newest(self):
        response = self.client.get(
            self.url("challenge-submissions", self.open_challenge.pk),
            {"sort": "newest"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [self.second_submission.pk, self.first_submission.pk],
        )

    def test_submissions_pagination_and_score_and_image_url(self):
        response = self.client.get(
            self.url("challenge-submissions", self.open_challenge.pk),
            {"page_size": 1},
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        first = response.data["results"][0]
        self.assertEqual(first["score"], 2)
        self.assertTrue(first["post"]["image_url"].startswith("http://localhost/"))

        second_page = self.client.get(
            self.url("challenge-submissions", self.open_challenge.pk)
            + "?page=2&page_size=1",
            HTTP_HOST="localhost",
        )
        self.assertEqual(second_page.status_code, 200)
        self.assertIsNone(second_page.data["results"][0]["post"]["image_url"])


class ChallengeCreateAPITests(ChallengeAPITestBase):
    def create_payload(self, **overrides):
        payload = {
            "title": "New API challenge",
            "background": "New background",
            "description": "New description",
            "goal": "New goal",
            "upvote_threshold": 3,
            "week_start": self.today + timedelta(days=100),
            "tasks": [
                {
                    "day_number": 1,
                    "title": "First task",
                    "description": "First task description",
                },
                {
                    "day_number": 2,
                    "title": "Second task",
                    "description": "Second task description",
                },
            ],
        }
        payload.update(overrides)
        return payload

    def test_moderator_can_create_challenge_with_badge_creator_and_tasks(self):
        self.client.force_authenticate(user=self.moderator)
        payload = self.create_payload()

        response = self.client.post(
            self.url("challenge-list"),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        challenge = Challenge.objects.get(pk=response.data["id"])
        self.assertEqual(challenge.created_by, self.moderator)
        self.assertEqual(challenge.badge.name, "New API challenge Badge")
        self.assertEqual(challenge.tasks.count(), 2)
        self.assertEqual(
            list(challenge.tasks.values_list("day_number", flat=True)),
            [1, 2],
        )

    def test_anonymous_and_normal_user_cannot_create_challenge(self):
        payload = self.create_payload()
        challenge_count = Challenge.objects.count()

        response = self.client.post(
            self.url("challenge-list"),
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(user=self.normal_user)
        response = self.client.post(
            self.url("challenge-list"),
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Challenge.objects.count(), challenge_count)

    def assert_invalid_create_does_not_change_database(self, payload):
        counts = {
            "challenges": Challenge.objects.count(),
            "badges": Badge.objects.count(),
            "tasks": ChallengeTask.objects.count(),
        }
        self.client.force_authenticate(user=self.moderator)

        response = self.client.post(
            self.url("challenge-list"),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Challenge.objects.count(), counts["challenges"])
        self.assertEqual(Badge.objects.count(), counts["badges"])
        self.assertEqual(ChallengeTask.objects.count(), counts["tasks"])

    def test_create_rejects_an_overlapping_week(self):
        self.assert_invalid_create_does_not_change_database(
            self.create_payload(week_start=self.open_challenge.week_start)
        )

    def test_create_rejects_eight_tasks(self):
        tasks = [
            {
                "day_number": day_number,
                "title": f"Task {day_number}",
                "description": "",
            }
            for day_number in range(1, 9)
        ]
        self.assert_invalid_create_does_not_change_database(
            self.create_payload(tasks=tasks)
        )

    def test_create_rejects_duplicate_task_days(self):
        tasks = self.create_payload()["tasks"]
        tasks[1]["day_number"] = tasks[0]["day_number"]
        self.assert_invalid_create_does_not_change_database(
            self.create_payload(tasks=tasks)
        )

    def test_create_rejects_task_day_outside_one_to_seven(self):
        for day_number in (0, 8):
            tasks = self.create_payload()["tasks"]
            tasks[0]["day_number"] = day_number
            self.assert_invalid_create_does_not_change_database(
                self.create_payload(tasks=tasks)
            )

    def test_create_rejects_blank_title_after_stripping_html(self):
        self.assert_invalid_create_does_not_change_database(
            self.create_payload(title="<p>   </p>")
        )

    def test_create_rejects_missing_required_fields(self):
        self.assert_invalid_create_does_not_change_database(
            {"title": "Missing fields"}
        )

    def test_create_rejects_threshold_below_minimum(self):
        self.assert_invalid_create_does_not_change_database(
            self.create_payload(upvote_threshold=0)
        )

    def test_read_only_fields_are_ignored_when_creating(self):
        self.client.force_authenticate(user=self.moderator)
        payload = self.create_payload(
            id=999999,
            badge={"id": 999999, "name": "Injected badge"},
            created_by=str(self.normal_user.pk),
        )

        response = self.client.post(
            self.url("challenge-list"),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        challenge = Challenge.objects.get(pk=response.data["id"])
        self.assertNotEqual(challenge.pk, 999999)
        self.assertEqual(challenge.created_by, self.moderator)
        self.assertEqual(challenge.badge.name, "New API challenge Badge")

    def test_delete_on_list_url_returns_method_not_allowed(self):
        self.client.force_authenticate(user=self.moderator)

        response = self.client.delete(self.url("challenge-list"))

        self.assertEqual(response.status_code, 405)

    def test_session_authentication_requires_and_accepts_csrf_token(self):
        from django.urls import reverse
        from rest_framework.test import APIClient

        client = APIClient(enforce_csrf_checks=True)
        self.assertTrue(
            client.login(username="moderator-api-user", password="test-password")
        )
        client.get(reverse("users:login"))
        csrf_token = client.cookies["csrftoken"].value
        payload = self.create_payload(
            title="CSRF challenge",
            week_start=self.today + timedelta(days=200),
        )

        rejected = client.post(
            self.url("challenge-list"),
            payload,
            format="json",
        )
        self.assertEqual(rejected.status_code, 403)
        self.assertFalse(Challenge.objects.filter(title="CSRF challenge").exists())

        accepted = client.post(
            self.url("challenge-list"),
            payload,
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(accepted.status_code, 201)
        self.assertTrue(Challenge.objects.filter(title="CSRF challenge").exists())


class ChallengeUpdateDeleteAPITests(ChallengeAPITestBase):
    def test_patch_title_only_preserves_everything_else(self):
        original = {
            "background": self.open_challenge.background,
            "description": self.open_challenge.description,
            "goal": self.open_challenge.goal,
            "upvote_threshold": self.open_challenge.upvote_threshold,
            "week_start": self.open_challenge.week_start,
            "task_ids": list(self.open_challenge.tasks.values_list("pk", flat=True)),
        }
        self.client.force_authenticate(user=self.moderator)

        response = self.client.patch(
            self.url("challenge-detail", self.open_challenge.pk),
            {"title": "Patched title"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.open_challenge.refresh_from_db()
        self.assertEqual(self.open_challenge.title, "Patched title")
        self.assertEqual(self.open_challenge.background, original["background"])
        self.assertEqual(self.open_challenge.description, original["description"])
        self.assertEqual(self.open_challenge.goal, original["goal"])
        self.assertEqual(
            self.open_challenge.upvote_threshold,
            original["upvote_threshold"],
        )
        self.assertEqual(self.open_challenge.week_start, original["week_start"])
        self.assertEqual(
            list(self.open_challenge.tasks.values_list("pk", flat=True)),
            original["task_ids"],
        )

    def test_patch_with_tasks_replaces_the_task_list(self):
        self.client.force_authenticate(user=self.moderator)

        response = self.client.patch(
            self.url("challenge-detail", self.open_challenge.pk),
            {
                "tasks": [
                    {
                        "day_number": 4,
                        "title": "Replacement task",
                        "description": "Replacement description",
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        tasks = list(
            self.open_challenge.tasks.order_by("day_number").values(
                "day_number", "title", "description"
            )
        )
        self.assertEqual(
            tasks,
            [{
                "day_number": 4,
                "title": "Replacement task",
                "description": "Replacement description",
            }],
        )

    def test_patch_without_tasks_keeps_existing_tasks(self):
        original_tasks = list(
            self.open_challenge.tasks.values_list(
                "day_number", "title", "description"
            )
        )
        self.client.force_authenticate(user=self.moderator)

        response = self.client.patch(
            self.url("challenge-detail", self.open_challenge.pk),
            {"title": "Task-preserving patch"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(
                self.open_challenge.tasks.values_list(
                    "day_number", "title", "description"
                )
            ),
            original_tasks,
        )

    def test_put_missing_required_fields_returns_400(self):
        self.client.force_authenticate(user=self.moderator)

        response = self.client.put(
            self.url("challenge-detail", self.open_challenge.pk),
            {"title": "Incomplete PUT"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.open_challenge.refresh_from_db()
        self.assertEqual(self.open_challenge.title, "Open challenge")

    def test_update_never_changes_badge_or_creator(self):
        original_badge = self.open_challenge.badge
        original_creator = self.open_challenge.created_by
        self.client.force_authenticate(user=self.moderator)

        response = self.client.patch(
            self.url("challenge-detail", self.open_challenge.pk),
            {
                "title": "Badge-preserving update",
                "badge": {"id": 999999, "name": "Injected badge"},
                "created_by": str(self.normal_user.pk),
                "id": 999999,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.open_challenge.refresh_from_db()
        self.assertEqual(self.open_challenge.badge, original_badge)
        self.assertEqual(self.open_challenge.created_by, original_creator)
        self.assertNotEqual(self.open_challenge.pk, 999999)

    def test_update_week_start_excludes_self_but_rejects_other_overlap(self):
        self.client.force_authenticate(user=self.moderator)

        response = self.client.patch(
            self.url("challenge-detail", self.open_challenge.pk),
            {"week_start": self.open_challenge.week_start.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        overlapping_challenge = self.create_challenge(
            title="Overlapping challenge",
            week_start=self.open_challenge.week_start - timedelta(days=6),
        )
        response = self.client.patch(
            self.url("challenge-detail", self.open_challenge.pk),
            {"week_start": overlapping_challenge.week_start.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.open_challenge.refresh_from_db()
        self.assertNotEqual(
            self.open_challenge.week_start,
            overlapping_challenge.week_start,
        )

    def test_delete_returns_204_empty_and_preserves_badge_history(self):
        challenge_badge = self.open_challenge.badge
        submission_user = self.first_submission.user
        earned, _ = UserBadge.objects.get_or_create(
            user=submission_user,
            badge=challenge_badge,
        )
        challenge_pk = self.open_challenge.pk
        badge_pk = challenge_badge.pk
        earned_pk = earned.pk
        self.client.force_authenticate(user=self.moderator)

        response = self.client.delete(
            self.url("challenge-detail", challenge_pk)
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertFalse(Challenge.objects.filter(pk=challenge_pk).exists())
        self.assertFalse(
            ChallengeSubmission.objects.filter(challenge_id=challenge_pk).exists()
        )
        self.assertTrue(Badge.objects.filter(pk=badge_pk).exists())
        self.assertTrue(UserBadge.objects.filter(pk=earned_pk).exists())

    @patch("weeklychallenge.api_views.Challenge.delete")
    def test_delete_protected_error_returns_409(self, delete):
        from django.db.models.deletion import ProtectedError

        delete.side_effect = ProtectedError(
            "protected",
            {self.open_challenge},
        )
        self.client.force_authenticate(user=self.moderator)

        response = self.client.delete(
            self.url("challenge-detail", self.open_challenge.pk)
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.data,
            {"detail": "Challenge tidak dapat dihapus karena masih digunakan."},
        )

    def test_normal_user_cannot_patch_or_delete(self):
        self.client.force_authenticate(user=self.normal_user)

        patch_response = self.client.patch(
            self.url("challenge-detail", self.open_challenge.pk),
            {"title": "Forbidden patch"},
            format="json",
        )
        delete_response = self.client.delete(
            self.url("challenge-detail", self.open_challenge.pk)
        )

        self.assertEqual(patch_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.open_challenge.refresh_from_db()
        self.assertEqual(self.open_challenge.title, "Open challenge")

    def test_list_and_submissions_query_counts_do_not_grow_per_item(self):
        with CaptureQueriesContext(connection) as list_queries:
            list_response = self.client.get(
                self.url("challenge-list"),
                {"status": "all", "page_size": 50},
            )
        self.assertEqual(list_response.status_code, 200)
        self.assertLessEqual(len(list_queries), 12)

        with CaptureQueriesContext(connection) as submission_queries:
            submission_response = self.client.get(
                self.url("challenge-submissions", self.open_challenge.pk),
                {"page_size": 50},
            )
        self.assertEqual(submission_response.status_code, 200)
        self.assertLessEqual(len(submission_queries), 12)
