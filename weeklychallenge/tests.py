from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from posts.models import Comment, Post, Tag, Vote
from users.models import Badge, UserBadge
from .forms import ChallengeForm, ChallengeTaskFormSet
from .models import Challenge, ChallengeSubmission
from .services import (
    award_badge_if_eligible,
    create_challenge,
    get_current_challenge,
    user_has_submitted,
)


class ChallengeTaskRowHTMXTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="moderator",
            password="test-password",
        )
        permission = Permission.objects.get(
            content_type__app_label="weeklychallenge",
            codename="add_challenge",
        )
        self.user.user_permissions.add(permission)
        moderator_group, _ = Group.objects.get_or_create(name="Moderator")
        self.user.groups.add(moderator_group)
        self.client.force_login(self.user)

    def test_create_button_is_shown_to_moderator_group(self):
        response = self.client.get(reverse("weeklychallenge:show_weekly_challenge"))

        self.assertContains(response, reverse("weeklychallenge:challenge_create"))
        self.assertContains(response, "Buat challenge")

    def test_create_button_is_hidden_from_users_outside_moderator_group(self):
        normal_user = get_user_model().objects.create_user(
            username="regular-user",
            password="test-password",
        )
        self.client.force_login(normal_user)

        response = self.client.get(reverse("weeklychallenge:show_weekly_challenge"))

        self.assertNotContains(response, reverse("weeklychallenge:challenge_create"))
        self.assertNotContains(response, "Buat challenge")

    def test_create_button_is_shown_to_superuser(self):
        superuser = get_user_model().objects.create_superuser(
            username="superuser",
            password="test-password",
        )
        self.client.force_login(superuser)

        response = self.client.get(reverse("weeklychallenge:show_weekly_challenge"))

        self.assertContains(response, reverse("weeklychallenge:challenge_create"))
        self.assertContains(response, "Buat challenge")

    def test_add_task_row_updates_formset_management_count(self):
        response = self.client.get(
            reverse("weeklychallenge:task_form_row"),
            {"index": 1, "active": 1},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_tasks-1-day_number"')
        self.assertContains(response, 'name="tasks-TOTAL_FORMS"')
        self.assertContains(response, 'value="2"')

    def test_delete_task_toggle_preserves_form_data_and_updates_add_control(self):
        form_data = {
            "tasks-TOTAL_FORMS": "2",
            "tasks-INITIAL_FORMS": "0",
            "tasks-MIN_NUM_FORMS": "0",
            "tasks-MAX_NUM_FORMS": "7",
            "tasks-0-day_number": "1",
            "tasks-0-title": "Declutter a drawer",
            "tasks-0-description": "Keep only useful items.",
            "tasks-1-day_number": "2",
            "tasks-1-title": "Organize a shelf",
            "tasks-1-description": "",
        }
        response = self.client.post(
            reverse("weeklychallenge:toggle_task_form_delete", args=[0]),
            form_data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tugas ini akan dihapus")
        self.assertContains(response, "Declutter a drawer")
        self.assertContains(
            response,
            'name="tasks-0-DELETE" id="id_tasks-0-DELETE" checked',
        )
        self.assertContains(response, "active=1")

        form_data["tasks-0-DELETE"] = "on"
        response = self.client.post(
            reverse("weeklychallenge:toggle_task_form_delete", args=[0]),
            form_data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Tugas ini akan dihapus")
        self.assertContains(response, "Hapus tugas")


class ChallengeServiceAndFormTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="challenge-user",
            password="test-password",
        )

    def make_challenge(self, *, week_start, week_end, threshold=2):
        badge = Badge.objects.create(name="Test Badge")
        return Challenge.objects.create(
            title="Test challenge",
            background="Background",
            description="Description",
            goal="Goal",
            upvote_threshold=threshold,
            badge=badge,
            week_start=week_start,
            week_end=week_end,
            created_by=self.user,
        )

    def challenge_form_data(self, *, start="2026-11-01", end="2026-11-07"):
        return {
            "title": "Digital minimalism",
            "background": "Too many distractions.",
            "description": "Reduce screen clutter.",
            "goal": "Build focus.",
            "upvote_threshold": "2",
            "week_start": start,
            "week_end": end,
        }

    def task_formset_data(self, count=1):
        data = {
            "tasks-TOTAL_FORMS": str(count),
            "tasks-INITIAL_FORMS": "0",
            "tasks-MIN_NUM_FORMS": "0",
            "tasks-MAX_NUM_FORMS": "7",
        }
        for index in range(count):
            data.update(
                {
                    f"tasks-{index}-day_number": str(index + 1),
                    f"tasks-{index}-title": f"Task {index + 1}",
                    f"tasks-{index}-description": "",
                }
            )
        return data

    def test_create_challenge_creates_badge_tag_and_tasks(self):
        form = ChallengeForm(data=self.challenge_form_data())
        formset = ChallengeTaskFormSet(data=self.task_formset_data())

        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(formset.is_valid(), formset.errors)

        challenge = create_challenge(form=form, formset=formset, user=self.user)

        self.assertEqual(challenge.badge.name, "Digital minimalism Badge")
        self.assertEqual(challenge.tag.title, f"weeklychallenge{challenge.pk}")
        self.assertEqual(challenge.created_by, self.user)
        self.assertEqual(list(challenge.tasks.values_list("title", flat=True)), ["Task 1"])

    def test_form_rejects_overlapping_challenge_ranges(self):
        self.make_challenge(
            week_start=date(2026, 10, 25),
            week_end=date(2026, 11, 1),
        )
        form = ChallengeForm(data=self.challenge_form_data())

        self.assertFalse(form.is_valid())
        self.assertIn(
            "Rentang tanggal challenge tidak boleh tumpang tindih dengan challenge lain.",
            form.non_field_errors(),
        )

    def test_form_allows_edit_without_overlapping_itself(self):
        challenge = self.make_challenge(
            week_start=date(2026, 11, 1),
            week_end=date(2026, 11, 7),
        )
        form = ChallengeForm(
            data=self.challenge_form_data(),
            instance=challenge,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejects_end_before_start(self):
        form = ChallengeForm(
            data=self.challenge_form_data(start="2026-11-08", end="2026-11-01")
        )

        self.assertFalse(form.is_valid())
        self.assertIn("week_end", form.errors)

    def test_formset_rejects_more_than_seven_tasks(self):
        formset = ChallengeTaskFormSet(data=self.task_formset_data(count=8))

        self.assertFalse(formset.is_valid())
        self.assertTrue(formset.non_form_errors())

    def test_date_fields_use_native_date_picker_widgets(self):
        form = ChallengeForm()

        self.assertEqual(form.fields["week_start"].widget.input_type, "date")
        self.assertEqual(form.fields["week_end"].widget.input_type, "date")

    @patch("weeklychallenge.models.timezone.localdate")
    def test_challenge_is_open_on_both_boundary_dates_only(self, localdate):
        challenge = self.make_challenge(
            week_start=date(2026, 11, 1),
            week_end=date(2026, 11, 7),
        )

        localdate.return_value = date(2026, 10, 31)
        self.assertFalse(challenge.is_open)
        localdate.return_value = date(2026, 11, 1)
        self.assertTrue(challenge.is_open)
        localdate.return_value = date(2026, 11, 7)
        self.assertTrue(challenge.is_open)
        localdate.return_value = date(2026, 11, 8)
        self.assertFalse(challenge.is_open)

    def test_submission_is_unique_per_user_and_challenge(self):
        challenge = self.make_challenge(
            week_start=date(2026, 11, 1),
            week_end=date(2026, 11, 7),
        )
        post = Post.objects.create(author=self.user, title="Progress", content="Done")
        ChallengeSubmission.objects.create(
            challenge=challenge,
            post=post,
            user=self.user,
        )
        second_post = Post.objects.create(
            author=self.user,
            title="Another progress",
            content="Still done",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ChallengeSubmission.objects.create(
                    challenge=challenge,
                    post=second_post,
                    user=self.user,
                )

    def test_get_current_challenge_includes_start_and_end_dates(self):
        challenge = self.make_challenge(
            week_start=date(2026, 11, 1),
            week_end=date(2026, 11, 7),
        )

        self.assertEqual(get_current_challenge(date(2026, 11, 1)), challenge)
        self.assertEqual(get_current_challenge(date(2026, 11, 7)), challenge)
        self.assertIsNone(get_current_challenge(date(2026, 11, 8)))

    def test_user_has_submitted_returns_false_for_anonymous_users(self):
        challenge = self.make_challenge(
            week_start=date(2026, 11, 1),
            week_end=date(2026, 11, 7),
        )

        self.assertFalse(user_has_submitted(AnonymousUser(), challenge))

    def test_user_has_submitted_checks_challenge_submission(self):
        challenge = self.make_challenge(
            week_start=date(2026, 11, 1),
            week_end=date(2026, 11, 7),
        )
        post = Post.objects.create(author=self.user, title="Progress", content="Done")
        ChallengeSubmission.objects.create(
            challenge=challenge,
            post=post,
            user=self.user,
        )

        self.assertTrue(user_has_submitted(self.user, challenge))

    def test_badge_is_awarded_only_when_net_score_meets_threshold(self):
        challenge = self.make_challenge(
            week_start=date(2026, 11, 1),
            week_end=date(2026, 11, 7),
            threshold=2,
        )
        post = Post.objects.create(author=self.user, title="Progress", content="Done")
        ChallengeSubmission.objects.create(
            challenge=challenge,
            post=post,
            user=self.user,
        )
        voter = get_user_model().objects.create_user(username="voter")

        self.assertFalse(award_badge_if_eligible(post))
        Vote.objects.create(user=voter, post=post, value=1)
        self.assertFalse(award_badge_if_eligible(post))
        Vote.objects.create(user=self.user, post=post, value=1)
        self.assertFalse(award_badge_if_eligible(post))
        self.assertFalse(award_badge_if_eligible(post))
        self.assertTrue(
            UserBadge.objects.filter(user=self.user, badge=challenge.badge).exists()
        )

    def test_awarded_badge_is_not_revoked_after_score_drops(self):
        challenge = self.make_challenge(
            week_start=date(2026, 11, 1),
            week_end=date(2026, 11, 7),
            threshold=1,
        )
        post = Post.objects.create(author=self.user, title="Progress", content="Done")
        ChallengeSubmission.objects.create(
            challenge=challenge,
            post=post,
            user=self.user,
        )
        voter = get_user_model().objects.create_user(username="downvoter")
        upvote = Vote.objects.create(user=voter, post=post, value=1)

        self.assertFalse(award_badge_if_eligible(post))
        upvote.delete()
        Vote.objects.create(user=voter, post=post, value=-1)

        self.assertEqual(post.get_vote_count(), -1)
        self.assertTrue(
            UserBadge.objects.filter(user=self.user, badge=challenge.badge).exists()
        )


class ChallengeSignalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="signal-user")
        self.voter = get_user_model().objects.create_user(username="signal-voter")

    def make_challenge(self, *, start, end, threshold=1):
        badge = Badge.objects.create(name="Signal Badge")
        challenge = Challenge.objects.create(
            title="Signal challenge",
            background="Background",
            description="Description",
            goal="Goal",
            upvote_threshold=threshold,
            badge=badge,
            week_start=start,
            week_end=end,
            created_by=self.user,
        )
        challenge.tag = Tag.objects.create(title=f"weeklychallenge{challenge.pk}")
        challenge.save(update_fields=["tag"])
        return challenge

    def test_saving_tagged_active_post_creates_submission(self):
        today = timezone.localdate()
        challenge = self.make_challenge(
            start=today,
            end=today + timedelta(days=6),
        )
        post = Post.objects.create(
            author=self.user,
            title="Challenge progress",
            content="Done",
        )
        post.tags.add(challenge.tag)
        post.save()

        submission = ChallengeSubmission.objects.get(challenge=challenge)
        self.assertEqual(submission.post, post)
        self.assertEqual(submission.user, self.user)

    def test_saving_tagged_inactive_post_does_not_create_submission(self):
        today = timezone.localdate()
        challenge = self.make_challenge(
            start=today - timedelta(days=8),
            end=today - timedelta(days=1),
        )
        post = Post.objects.create(
            author=self.user,
            title="Late progress",
            content="Done",
        )
        post.tags.add(challenge.tag)
        post.save()

        self.assertFalse(
            ChallengeSubmission.objects.filter(challenge=challenge).exists()
        )

    def test_duplicate_user_submission_does_not_break_post_save(self):
        today = timezone.localdate()
        challenge = self.make_challenge(
            start=today,
            end=today + timedelta(days=6),
        )
        first_post = Post.objects.create(
            author=self.user,
            title="First progress",
            content="Done",
        )
        first_post.tags.add(challenge.tag)
        first_post.save()
        second_post = Post.objects.create(
            author=self.user,
            title="Second progress",
            content="Done again",
        )
        second_post.tags.add(challenge.tag)
        second_post.save()

        self.assertEqual(
            ChallengeSubmission.objects.filter(challenge=challenge).count(),
            1,
        )
        self.assertFalse(
            ChallengeSubmission.objects.filter(post=second_post).exists()
        )

    def test_vote_save_awards_badge_at_threshold(self):
        today = timezone.localdate()
        challenge = self.make_challenge(
            start=today,
            end=today + timedelta(days=6),
        )
        post = Post.objects.create(
            author=self.user,
            title="Voted progress",
            content="Done",
        )
        post.tags.add(challenge.tag)
        post.save()

        Vote.objects.create(user=self.voter, post=post, value=1)

        self.assertTrue(
            UserBadge.objects.filter(user=self.user, badge=challenge.badge).exists()
        )

    def test_vote_save_does_not_award_before_threshold(self):
        today = timezone.localdate()
        challenge = self.make_challenge(
            start=today,
            end=today + timedelta(days=6),
            threshold=2,
        )
        post = Post.objects.create(
            author=self.user,
            title="Not enough votes",
            content="Done",
        )
        post.tags.add(challenge.tag)
        post.save()

        Vote.objects.create(user=self.voter, post=post, value=1)

        self.assertFalse(
            UserBadge.objects.filter(user=self.user, badge=challenge.badge).exists()
        )

    def test_vote_delete_does_not_revoke_awarded_badge(self):
        today = timezone.localdate()
        challenge = self.make_challenge(
            start=today,
            end=today + timedelta(days=6),
        )
        post = Post.objects.create(
            author=self.user,
            title="Persistent badge",
            content="Done",
        )
        post.tags.add(challenge.tag)
        post.save()
        vote = Vote.objects.create(user=self.voter, post=post, value=1)

        vote.delete()

        self.assertTrue(
            UserBadge.objects.filter(user=self.user, badge=challenge.badge).exists()
        )

    def test_comment_vote_does_not_award_challenge_badge(self):
        today = timezone.localdate()
        challenge = self.make_challenge(
            start=today,
            end=today + timedelta(days=6),
        )
        post = Post.objects.create(
            author=self.user,
            title="Comment target",
            content="Done",
        )
        post.tags.add(challenge.tag)
        post.save()
        comment = Comment.objects.create(
            post=post,
            user=self.user,
            content="Comment",
        )

        Vote.objects.create(user=self.voter, comment=comment, value=1)

        self.assertFalse(
            UserBadge.objects.filter(user=self.user, badge=challenge.badge).exists()
        )

    def test_deleting_post_with_votes_does_not_raise_from_vote_signal(self):
        today = timezone.localdate()
        challenge = self.make_challenge(
            start=today,
            end=today + timedelta(days=6),
        )
        post = Post.objects.create(
            author=self.user,
            title="Deleted progress",
            content="Done",
        )
        post.tags.add(challenge.tag)
        post.save()
        Vote.objects.create(user=self.voter, post=post, value=1)

        post.delete()

        self.assertFalse(ChallengeSubmission.objects.filter(challenge=challenge).exists())


class ChallengeViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="challenge-moderator",
            password="test-password",
        )
        permissions = Permission.objects.filter(
            content_type__app_label="weeklychallenge",
            codename__in=["add_challenge", "change_challenge", "delete_challenge"],
        )
        self.user.user_permissions.add(*permissions)
        self.client.force_login(self.user)

    def make_challenge(self, title, *, start, end):
        return Challenge.objects.create(
            title=title,
            background="Background",
            description=f"Description for {title}",
            goal="Goal",
            badge=Badge.objects.create(name=f"{title} Badge"),
            week_start=start,
            week_end=end,
            created_by=self.user,
        )

    def test_challenge_directory_filters_by_status_and_search(self):
        today = timezone.localdate()
        self.make_challenge(
            "Current digital reset",
            start=today,
            end=today + timedelta(days=2),
        )
        self.make_challenge(
            "Upcoming closet reset",
            start=today + timedelta(days=4),
            end=today + timedelta(days=10),
        )
        self.make_challenge(
            "Past mindful shopping",
            start=today - timedelta(days=10),
            end=today - timedelta(days=4),
        )

        response = self.client.get(
            reverse("weeklychallenge:challenge_list_partial"),
            {"status": "upcoming", "q": "closet"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upcoming closet reset")
        self.assertNotContains(response, "Current digital reset")
        self.assertNotContains(response, "Past mindful shopping")

    def test_challenge_directory_status_all_includes_open_upcoming_and_past(self):
        today = timezone.localdate()
        self.make_challenge("Open challenge", start=today, end=today)
        self.make_challenge(
            "Upcoming challenge",
            start=today + timedelta(days=2),
            end=today + timedelta(days=3),
        )
        self.make_challenge(
            "Past challenge",
            start=today - timedelta(days=3),
            end=today - timedelta(days=2),
        )

        response = self.client.get(
            reverse("weeklychallenge:challenge_list_partial"),
            {"status": "all"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open challenge")
        self.assertContains(response, "Upcoming challenge")
        self.assertContains(response, "Past challenge")

    def test_landing_page_renders_empty_state_when_no_challenge_is_active(self):
        today = timezone.localdate()
        self.make_challenge(
            "Future challenge",
            start=today + timedelta(days=2),
            end=today + timedelta(days=8),
        )

        response = self.client.get(reverse("weeklychallenge:show_weekly_challenge"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Future challenge")
        self.assertIsNone(response.context["challenge"])

    def test_management_routes_require_permissions(self):
        self.client.logout()
        create_url = reverse("weeklychallenge:challenge_create")
        response = self.client.get(create_url)
        self.assertEqual(response.status_code, 403)

        normal_user = get_user_model().objects.create_user(username="not-a-moderator")
        self.client.force_login(normal_user)
        response = self.client.get(create_url)
        self.assertEqual(response.status_code, 403)

    def test_detail_returns_not_found_for_unknown_challenge(self):
        response = self.client.get(
            reverse("weeklychallenge:challenge_detail", args=[999999])
        )

        self.assertEqual(response.status_code, 404)

    def test_challenge_detail_renders_tasks_badge_and_submission_list(self):
        challenge = self.make_challenge(
            "Focused mornings",
            start=timezone.localdate(),
            end=timezone.localdate() + timedelta(days=6),
        )
        challenge.tasks.create(day_number=1, title="Clear the desk", description="One step.")

        response = self.client.get(
            reverse("weeklychallenge:challenge_detail", args=[challenge.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Focused mornings")
        self.assertContains(response, "Clear the desk")
        self.assertContains(response, "Focused mornings Badge")
        self.assertContains(response, "Belum ada submission")

    def test_update_changes_challenge_and_tasks_without_replacing_badge_or_tag(self):
        challenge = self.make_challenge(
            "Old title",
            start=timezone.localdate() + timedelta(days=10),
            end=timezone.localdate() + timedelta(days=16),
        )
        original_badge = challenge.badge
        from posts.models import Tag

        challenge.tag = Tag.objects.create(title=f"weeklychallenge{challenge.pk}")
        challenge.save(update_fields=["tag"])
        original_tag = challenge.tag
        data = {
            "title": "Updated title",
            "background": "New background",
            "description": "New description",
            "goal": "New goal",
            "upvote_threshold": "12",
            "week_start": (timezone.localdate() + timedelta(days=10)).isoformat(),
            "week_end": (timezone.localdate() + timedelta(days=16)).isoformat(),
            "tasks-TOTAL_FORMS": "1",
            "tasks-INITIAL_FORMS": "0",
            "tasks-MIN_NUM_FORMS": "0",
            "tasks-MAX_NUM_FORMS": "7",
            "tasks-0-day_number": "1",
            "tasks-0-title": "New task",
            "tasks-0-description": "Task details",
        }

        response = self.client.post(
            reverse("weeklychallenge:challenge_update", args=[challenge.pk]),
            data,
        )

        self.assertRedirects(
            response,
            reverse("weeklychallenge:challenge_detail", args=[challenge.pk]),
        )
        challenge.refresh_from_db()
        self.assertEqual(challenge.title, "Updated title")
        self.assertEqual(challenge.badge, original_badge)
        self.assertEqual(challenge.tag, original_tag)
        self.assertEqual(challenge.tasks.get().title, "New task")

    def test_delete_requires_confirmation_then_deletes_on_post(self):
        challenge = self.make_challenge(
            "Remove me",
            start=timezone.localdate() + timedelta(days=20),
            end=timezone.localdate() + timedelta(days=26),
        )
        url = reverse("weeklychallenge:challenge_delete", args=[challenge.pk])

        confirm_response = self.client.get(url)
        self.assertEqual(confirm_response.status_code, 200)
        self.assertTrue(Challenge.objects.filter(pk=challenge.pk).exists())

        delete_response = self.client.post(url)
        self.assertRedirects(delete_response, reverse("weeklychallenge:challenge_list"))
        self.assertFalse(Challenge.objects.filter(pk=challenge.pk).exists())
