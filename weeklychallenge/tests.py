from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from posts.models import Comment, Post, Tag, Vote
from users.models import Badge, UserBadge
from .forms import ChallengeForm, ChallengeTaskFormSet
from .models import Challenge, ChallengeSubmission, MAX_TASKS_PER_CHALLENGE
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

    def make_challenge(self, *, week_start, threshold=2):
        badge = Badge.objects.create(name="Test Badge")
        return Challenge.objects.create(
            title="Test challenge",
            background="Background",
            description="Description",
            goal="Goal",
            upvote_threshold=threshold,
            badge=badge,
            week_start=week_start,
            created_by=self.user,
        )

    def challenge_form_data(self, *, start="2026-11-01"):
        return {
            "title": "Digital minimalism",
            "background": "Too many distractions.",
            "description": "Reduce screen clutter.",
            "goal": "Build focus.",
            "upvote_threshold": "2",
            "week_start": start,
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

    def test_create_challenge_creates_badge_and_tasks_without_per_challenge_tag(self):
        form = ChallengeForm(data=self.challenge_form_data())
        formset = ChallengeTaskFormSet(data=self.task_formset_data())

        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(formset.is_valid(), formset.errors)

        challenge = create_challenge(form=form, formset=formset, user=self.user)

        self.assertEqual(challenge.badge.name, "Digital minimalism Badge")
        self.assertIsNone(challenge.tag)
        self.assertEqual(challenge.created_by, self.user)
        self.assertEqual(list(challenge.tasks.values_list("title", flat=True)), ["Task 1"])

    def test_form_rejects_overlapping_challenge_ranges(self):
        # Oct 26 to Nov 1 (inclusive) overlaps a challenge starting Nov 1
        self.make_challenge(week_start=date(2026, 10, 26))
        form = ChallengeForm(data=self.challenge_form_data())

        self.assertFalse(form.is_valid())
        self.assertIn(
            "Rentang tanggal challenge tidak boleh tumpang tindih dengan challenge lain.",
            form.errors["week_start"],
        )
    
    def test_form_allows_back_to_back_challenges(self):
        self.make_challenge(week_start=date(2026, 10, 25))  # ends Oct 31
        form = ChallengeForm(data=self.challenge_form_data(start="2026-11-01"))

        self.assertTrue(form.is_valid(), form.errors)

    def test_form_allows_edit_without_overlapping_itself(self):
        challenge = self.make_challenge(week_start=date(2026, 11, 1))
        form = ChallengeForm(
            data=self.challenge_form_data(),
            instance=challenge,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejects_overlapping_window_on_week_start(self):
        self.make_challenge(week_start=date(2026, 11, 1))
        form = ChallengeForm(data=self.challenge_form_data(start="2026-11-05"))

        self.assertFalse(form.is_valid())
        self.assertIn("week_start", form.errors)

    def test_formset_rejects_more_than_seven_tasks(self):
        formset = ChallengeTaskFormSet(data=self.task_formset_data(count=8))

        self.assertFalse(formset.is_valid())
        self.assertTrue(formset.non_form_errors())

    def test_date_fields_use_native_date_picker_widgets(self):
        form = ChallengeForm()

        self.assertEqual(form.fields["week_start"].widget.input_type, "date")

    @patch("weeklychallenge.models.timezone.localdate")
    def test_challenge_is_open_on_both_boundary_dates_only(self, localdate):
        challenge = self.make_challenge(week_start=date(2026, 11, 1))

        localdate.return_value = date(2026, 10, 31)
        self.assertFalse(challenge.is_open)
        localdate.return_value = date(2026, 11, 1)
        self.assertTrue(challenge.is_open)
        localdate.return_value = date(2026, 11, 7)
        self.assertTrue(challenge.is_open)
        localdate.return_value = date(2026, 11, 8)
        self.assertFalse(challenge.is_open)

    def test_challenge_status_querysets_cover_all_boundaries(self):
        start = date(2026, 11, 1)
        challenge = self.make_challenge(week_start=start)
        before = start - timedelta(days=1)
        last_day = start + timedelta(days=MAX_TASKS_PER_CHALLENGE - 1)
        after = last_day + timedelta(days=1)

        self.assertNotIn(challenge, Challenge.objects.current(before))
        self.assertIn(challenge, Challenge.objects.upcoming(before))
        self.assertIn(challenge, Challenge.objects.current(start))
        self.assertNotIn(challenge, Challenge.objects.past(start))
        self.assertIn(challenge, Challenge.objects.current(last_day))
        self.assertNotIn(challenge, Challenge.objects.past(last_day))
        self.assertIn(challenge, Challenge.objects.past(after))
        self.assertNotIn(challenge, Challenge.objects.current(after))

    def test_submission_is_unique_per_user_and_challenge(self):
        challenge = self.make_challenge(week_start=date(2026, 11, 1))
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
        challenge = self.make_challenge(week_start=date(2026, 11, 1))

        self.assertEqual(get_current_challenge(date(2026, 11, 1)), challenge)
        self.assertEqual(get_current_challenge(date(2026, 11, 7)), challenge)
        self.assertIsNone(get_current_challenge(date(2026, 11, 8)))

    def test_user_has_submitted_returns_false_for_anonymous_users(self):
        challenge = self.make_challenge(week_start=date(2026, 11, 1))

        self.assertFalse(user_has_submitted(AnonymousUser(), challenge))

    def test_user_has_submitted_checks_challenge_submission(self):
        challenge = self.make_challenge(week_start=date(2026, 11, 1))
        post = Post.objects.create(author=self.user, title="Progress", content="Done")
        ChallengeSubmission.objects.create(
            challenge=challenge,
            post=post,
            user=self.user,
        )

        self.assertTrue(user_has_submitted(self.user, challenge))

    def test_badge_is_awarded_only_when_net_score_meets_threshold(self):
        challenge = self.make_challenge(week_start=date(2026, 11, 1), threshold=2)
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
        challenge = self.make_challenge(week_start=date(2026, 11, 1), threshold=1)
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

    def test_awarded_badge_survives_submission_deletion(self):
        challenge = self.make_challenge(week_start=date(2026, 11, 1), threshold=1)
        post = Post.objects.create(author=self.user, title="Progress", content="Done")
        submission = ChallengeSubmission.objects.create(
            challenge=challenge,
            post=post,
            user=self.user,
        )
        UserBadge.objects.create(user=self.user, badge=challenge.badge)

        submission.delete()

        self.assertTrue(
            UserBadge.objects.filter(user=self.user, badge=challenge.badge).exists()
        )

    def test_challenge_has_one_badge_and_deletion_preserves_earned_badge(self):
        challenge = self.make_challenge(week_start=date(2026, 11, 1))
        UserBadge.objects.create(user=self.user, badge=challenge.badge)

        challenge.delete()

        self.assertTrue(Badge.objects.filter(pk=challenge.badge_id).exists())
        self.assertTrue(
            UserBadge.objects.filter(user=self.user, badge_id=challenge.badge_id).exists()
        )


class ChallengeSignalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="signal-user")
        self.voter = get_user_model().objects.create_user(username="signal-voter")

    def make_challenge(self, *, start, threshold=1):
        badge = Badge.objects.create(name="Signal Badge")
        challenge = Challenge.objects.create(
            title="Signal challenge",
            background="Background",
            description="Description",
            goal="Goal",
            upvote_threshold=threshold,
            badge=badge,
            week_start=start,
            created_by=self.user,
        )
        return challenge

    def weekly_challenge_tag(self):
        return Tag.objects.get_or_create(title="Weekly Challenge")[0]

    def test_saving_tagged_active_post_creates_submission(self):
        today = timezone.localdate()
        challenge = self.make_challenge(start=today)
        post = Post.objects.create(
            author=self.user,
            title="Challenge progress",
            content="Done",
        )
        post.tags.add(self.weekly_challenge_tag())
        post.save()

        submission = ChallengeSubmission.objects.get(challenge=challenge)
        self.assertEqual(submission.post, post)
        self.assertEqual(submission.user, self.user)

    def test_adding_weekly_challenge_tag_creates_submission_without_resaving_post(self):
        today = timezone.localdate()
        challenge = self.make_challenge(start=today)
        post = Post.objects.create(
            author=self.user,
            title="Progress created through the post form",
            content="Done",
        )

        # ModelForm.save_m2m() adds tags after Post.save(), so the submission
        # must be created from the many-to-many change itself.
        post.tags.add(self.weekly_challenge_tag())

        submission = ChallengeSubmission.objects.get(challenge=challenge)
        self.assertEqual(submission.post, post)
        self.assertEqual(submission.user, self.user)

    def test_saving_tagged_inactive_post_does_not_create_submission(self):
        today = timezone.localdate()
        challenge = self.make_challenge(start=today - timedelta(days=8))
        post = Post.objects.create(
            author=self.user,
            title="Late progress",
            content="Done",
        )
        post.tags.add(self.weekly_challenge_tag())
        post.save()

        self.assertFalse(
            ChallengeSubmission.objects.filter(challenge=challenge).exists()
        )

    def test_duplicate_user_submission_does_not_break_post_save(self):
        today = timezone.localdate()
        challenge = self.make_challenge(start=today)
        first_post = Post.objects.create(
            author=self.user,
            title="First progress",
            content="Done",
        )
        first_post.tags.add(self.weekly_challenge_tag())
        first_post.save()
        second_post = Post.objects.create(
            author=self.user,
            title="Second progress",
            content="Done again",
        )
        second_post.tags.add(self.weekly_challenge_tag())
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
        challenge = self.make_challenge(start=today)
        post = Post.objects.create(
            author=self.user,
            title="Voted progress",
            content="Done",
        )
        post.tags.add(self.weekly_challenge_tag())
        post.save()

        Vote.objects.create(user=self.voter, post=post, value=1)

        self.assertTrue(
            UserBadge.objects.filter(user=self.user, badge=challenge.badge).exists()
        )

    def test_vote_save_does_not_award_before_threshold(self):
        today = timezone.localdate()
        challenge = self.make_challenge(start=today, threshold=2)
        post = Post.objects.create(
            author=self.user,
            title="Not enough votes",
            content="Done",
        )
        post.tags.add(self.weekly_challenge_tag())
        post.save()

        Vote.objects.create(user=self.voter, post=post, value=1)

        self.assertFalse(
            UserBadge.objects.filter(user=self.user, badge=challenge.badge).exists()
        )

    def test_vote_delete_does_not_revoke_awarded_badge(self):
        today = timezone.localdate()
        challenge = self.make_challenge(start=today)
        post = Post.objects.create(
            author=self.user,
            title="Persistent badge",
            content="Done",
        )
        post.tags.add(self.weekly_challenge_tag())
        post.save()
        vote = Vote.objects.create(user=self.voter, post=post, value=1)

        vote.delete()

        self.assertTrue(
            UserBadge.objects.filter(user=self.user, badge=challenge.badge).exists()
        )

    def test_comment_vote_does_not_award_challenge_badge(self):
        today = timezone.localdate()
        challenge = self.make_challenge(start=today)
        post = Post.objects.create(
            author=self.user,
            title="Comment target",
            content="Done",
        )
        post.tags.add(self.weekly_challenge_tag())
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
        challenge = self.make_challenge(start=today)
        post = Post.objects.create(
            author=self.user,
            title="Deleted progress",
            content="Done",
        )
        post.tags.add(self.weekly_challenge_tag())
        post.save()
        Vote.objects.create(user=self.voter, post=post, value=1)

        post.delete()

        self.assertFalse(ChallengeSubmission.objects.filter(challenge=challenge).exists())


class ChallengeProgressPostFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="progress-user",
            password="test-password",
        )
        self.challenge = Challenge.objects.create(
            title="Active challenge",
            background="Background",
            description="Description",
            goal="Goal",
            badge=Badge.objects.create(name="Progress Badge"),
            week_start=timezone.localdate(),
            created_by=self.user,
        )
        self.client.force_login(self.user)

    def progress_post_url(self):
        return f"{reverse('posts:create_post')}?challenge={self.challenge.pk}"

    def challenge_image(self):
        return SimpleUploadedFile(
            "proof.gif",
            (
                b"GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
                b"\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00"
                b"\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
            ),
            content_type="image/gif",
        )

    def test_progress_links_identify_the_active_challenge(self):
        page_response = self.client.get(
            reverse("weeklychallenge:show_weekly_challenge")
        )
        detail_response = self.client.get(
            reverse("weeklychallenge:challenge_detail", args=[self.challenge.pk])
        )

        self.assertContains(page_response, self.progress_post_url())
        self.assertContains(detail_response, self.progress_post_url())

    def test_progress_post_forces_official_tag_and_creates_submission(self):
        wrong_tag = Tag.objects.create(title="weeklychallenge1")

        response = self.client.post(
            self.progress_post_url(),
            {
                "title": "My weekly progress",
                "content": "Done",
                "tags": [wrong_tag.pk],
                "challenge_image": self.challenge_image(),
            },
        )

        self.assertRedirects(
            response,
            reverse("weeklychallenge:show_weekly_challenge"),
        )
        post = Post.objects.get(title="My weekly progress")
        self.assertTrue(post.tags.filter(title="Weekly Challenge").exists())
        self.assertTrue(
            ChallengeSubmission.objects.filter(
                challenge=self.challenge,
                post=post,
                user=self.user,
            ).exists()
        )


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

    def make_challenge(self, title, *, start):
        return Challenge.objects.create(
            title=title,
            background="Background",
            description=f"Description for {title}",
            goal="Goal",
            badge=Badge.objects.create(name=f"{title} Badge"),
            week_start=start,
            created_by=self.user,
        )

    def challenge_post_data(self, *, title="Created challenge", start=None):
        start = start or (timezone.localdate() + timedelta(days=10))
        return {
            "title": title,
            "background": "Background",
            "description": "Description",
            "goal": "Goal",
            "upvote_threshold": "2",
            "week_start": start.isoformat(),
            "tasks-TOTAL_FORMS": "1",
            "tasks-INITIAL_FORMS": "0",
            "tasks-MIN_NUM_FORMS": "0",
            "tasks-MAX_NUM_FORMS": "7",
            "tasks-0-day_number": "1",
            "tasks-0-title": "Task 1",
            "tasks-0-description": "Task details",
        }

    def test_create_route_accepts_valid_and_rejects_invalid_posts(self):
        url = reverse("weeklychallenge:challenge_create")
        response = self.client.post(url, self.challenge_post_data())

        challenge = Challenge.objects.get(title="Created challenge")
        self.assertRedirects(
            response,
            reverse("weeklychallenge:challenge_detail", args=[challenge.pk]),
        )
        self.assertTrue(challenge.tasks.filter(title="Task 1").exists())
        self.assertIsNotNone(challenge.badge)

        invalid_response = self.client.post(
            url,
            self.challenge_post_data(title=""),
        )
        self.assertEqual(invalid_response.status_code, 200)
        self.assertContains(invalid_response, "This field is required")

    def test_create_route_returns_htmx_redirect_and_htmx_errors(self):
        url = reverse("weeklychallenge:challenge_create")
        response = self.client.post(
            url,
            self.challenge_post_data(),
            HTTP_HX_REQUEST="true",
        )

        challenge = Challenge.objects.get(title="Created challenge")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["HX-Redirect"],
            reverse("weeklychallenge:challenge_detail", args=[challenge.pk]),
        )

        invalid_response = self.client.post(
            url,
            self.challenge_post_data(title=""),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(invalid_response.status_code, 200)
        self.assertContains(invalid_response, "This field is required")

    def test_challenge_directory_filters_by_status_and_search(self):
        today = timezone.localdate()
        self.make_challenge("Current digital reset", start=today)
        self.make_challenge("Upcoming closet reset", start=today + timedelta(days=4))
        self.make_challenge("Past mindful shopping", start=today - timedelta(days=10))

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
        self.make_challenge("Open challenge", start=today)
        self.make_challenge("Upcoming challenge", start=today + timedelta(days=2))
        self.make_challenge("Past challenge", start=today - timedelta(days=10))

        response = self.client.get(
            reverse("weeklychallenge:challenge_list_partial"),
            {"status": "all"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open challenge")
        self.assertContains(response, "Upcoming challenge")
        self.assertContains(response, "Past challenge")

    def test_challenge_directory_filters_open_and_past_statuses(self):
        today = timezone.localdate()
        self.make_challenge("Open challenge", start=today)
        self.make_challenge("Past challenge", start=today - timedelta(days=10))

        open_response = self.client.get(
            reverse("weeklychallenge:challenge_list_partial"),
            {"status": "open"},
        )
        past_response = self.client.get(
            reverse("weeklychallenge:challenge_list_partial"),
            {"status": "past"},
        )

        self.assertContains(open_response, "Open challenge")
        self.assertNotContains(open_response, "Past challenge")
        self.assertContains(past_response, "Past challenge")
        self.assertNotContains(past_response, "Open challenge")

    def test_challenge_directory_paginates_at_page_boundary(self):
        today = timezone.localdate()
        for index in range(7):
            self.make_challenge(f"Open challenge {index}", start=today)

        first_page = self.client.get(
            reverse("weeklychallenge:challenge_list_partial"),
            {"status": "open", "page": 1},
        )
        second_page = self.client.get(
            reverse("weeklychallenge:challenge_list_partial"),
            {"status": "open", "page": 2},
        )

        self.assertEqual(first_page.context["page_obj"].number, 1)
        self.assertEqual(first_page.context["page_obj"].paginator.num_pages, 2)
        self.assertContains(first_page, "Open challenge 6")
        self.assertNotContains(first_page, "Open challenge 0")
        self.assertEqual(second_page.context["page_obj"].number, 2)
        self.assertContains(second_page, "Open challenge 0")

    def test_landing_page_renders_empty_state_when_no_challenge_is_active(self):
        today = timezone.localdate()
        self.make_challenge("Future challenge", start=today + timedelta(days=2))

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

    def test_update_and_delete_routes_require_permissions(self):
        challenge = self.make_challenge(
            "Protected challenge",
            start=timezone.localdate() + timedelta(days=10),
        )
        normal_user = get_user_model().objects.create_user(
            username="cannot-manage-challenge"
        )
        self.client.force_login(normal_user)

        update_response = self.client.get(
            reverse("weeklychallenge:challenge_update", args=[challenge.pk])
        )
        delete_response = self.client.get(
            reverse("weeklychallenge:challenge_delete", args=[challenge.pk])
        )

        self.assertEqual(update_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.assertTrue(Challenge.objects.filter(pk=challenge.pk).exists())

    def test_detail_returns_not_found_for_unknown_challenge(self):
        response = self.client.get(
            reverse("weeklychallenge:challenge_detail", args=[999999])
        )

        self.assertEqual(response.status_code, 404)

    def test_challenge_detail_renders_tasks_badge_and_submission_list(self):
        challenge = self.make_challenge(
            "Focused mornings",
            start=timezone.localdate(),
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

    def test_challenge_detail_renders_without_tasks(self):
        challenge = self.make_challenge(
            "No tasks",
            start=timezone.localdate(),
        )

        response = self.client.get(
            reverse("weeklychallenge:challenge_detail", args=[challenge.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No tasks")
        self.assertNotContains(response, "Clear the desk")

    def test_submission_list_sorts_by_score_and_newest(self):
        challenge = self.make_challenge(
            "Leaderboard challenge",
            start=timezone.localdate(),
        )
        older_post = Post.objects.create(
            author=self.user,
            title="Older high score",
            content="Done",
        )
        newer_post = Post.objects.create(
            author=get_user_model().objects.create_user(username="newer-author"),
            title="Newer low score",
            content="Done",
        )
        older_submission = ChallengeSubmission.objects.create(
            challenge=challenge,
            post=older_post,
            user=self.user,
        )
        newer_submission = ChallengeSubmission.objects.create(
            challenge=challenge,
            post=newer_post,
            user=newer_post.author,
        )
        ChallengeSubmission.objects.filter(pk=older_submission.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        Vote.objects.create(user=get_user_model().objects.create_user(
            username="score-voter"
        ), post=older_post, value=1)

        url = reverse(
            "weeklychallenge:submission_list_partial",
            args=[challenge.pk],
        )
        score_response = self.client.get(url, {"sort": "score"})
        newest_response = self.client.get(url, {"sort": "newest"})
        fallback_response = self.client.get(url, {"sort": "unknown"})

        self.assertLess(
            score_response.content.find(b"Older high score"),
            score_response.content.find(b"Newer low score"),
        )
        self.assertLess(
            newest_response.content.find(b"Newer low score"),
            newest_response.content.find(b"Older high score"),
        )
        self.assertEqual(fallback_response.context["sort"], "score")

    @patch("weeklychallenge.views.timezone.localdate")
    def test_challenge_detail_reveals_tasks_cumulatively_without_spoilers(
        self, localdate
    ):
        start = date(2026, 11, 1)
        challenge = self.make_challenge("Cumulative tasks", start=start)
        for day_number in range(1, 8):
            challenge.tasks.create(
                day_number=day_number,
                title=f"Task {day_number}",
                description=f"Details {day_number}",
            )

        normal_user = get_user_model().objects.create_user(username="challenge-reader")
        detail_url = reverse("weeklychallenge:challenge_detail", args=[challenge.pk])

        self.client.logout()
        localdate.return_value = start - timedelta(days=1)
        anonymous_response = self.client.get(detail_url)
        self.assertTrue(anonymous_response.context["is_teaser"])
        for day_number in range(1, 8):
            self.assertNotContains(anonymous_response, f"Task {day_number}")

        self.client.force_login(normal_user)
        teaser_response = self.client.get(detail_url)
        self.assertTrue(teaser_response.context["is_teaser"])
        for day_number in range(1, 8):
            self.assertNotContains(teaser_response, f"Task {day_number}")

        for current_day in (1, 3, 7):
            localdate.return_value = start + timedelta(days=current_day - 1)
            response = self.client.get(detail_url)
            self.assertFalse(response.context.get("is_teaser", False))
            for day_number in range(1, 8):
                if day_number <= current_day:
                    self.assertContains(response, f"Task {day_number}")
                else:
                    self.assertNotContains(response, f"Task {day_number}")

        localdate.return_value = start + timedelta(days=7)
        completed_response = self.client.get(detail_url)
        for day_number in range(1, 8):
            self.assertContains(completed_response, f"Task {day_number}")

    def test_update_changes_challenge_and_tasks_without_replacing_badge_or_tag(self):
        challenge = self.make_challenge(
            "Old title",
            start=timezone.localdate() + timedelta(days=10),
        )
        original_badge = challenge.badge
        from posts.models import Tag

        challenge.tag = Tag.objects.create(title="Weekly Challenge")
        challenge.save(update_fields=["tag"])
        original_tag = challenge.tag
        data = {
            "title": "Updated title",
            "background": "New background",
            "description": "New description",
            "goal": "New goal",
            "upvote_threshold": "12",
            "week_start": (timezone.localdate() + timedelta(days=10)).isoformat(),
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

    def test_update_route_returns_htmx_redirect_and_validation_errors(self):
        challenge = self.make_challenge(
            "Editable challenge",
            start=timezone.localdate() + timedelta(days=10),
        )
        url = reverse("weeklychallenge:challenge_update", args=[challenge.pk])

        response = self.client.post(
            url,
            self.challenge_post_data(
                title="Updated challenge",
                start=timezone.localdate() + timedelta(days=10),
            ),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["HX-Redirect"],
            reverse("weeklychallenge:challenge_detail", args=[challenge.pk]),
        )

        invalid_response = self.client.post(
            url,
            self.challenge_post_data(
                title="",
                start=timezone.localdate() + timedelta(days=10),
            ),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(invalid_response.status_code, 200)
        self.assertContains(invalid_response, "This field is required")

    def test_delete_requires_confirmation_then_deletes_on_post(self):
        challenge = self.make_challenge(
            "Remove me",
            start=timezone.localdate() + timedelta(days=20),
        )
        url = reverse("weeklychallenge:challenge_delete", args=[challenge.pk])

        confirm_response = self.client.get(url)
        self.assertEqual(confirm_response.status_code, 200)
        self.assertTrue(Challenge.objects.filter(pk=challenge.pk).exists())

        delete_response = self.client.post(url)
        self.assertRedirects(delete_response, reverse("weeklychallenge:challenge_list"))
        self.assertFalse(Challenge.objects.filter(pk=challenge.pk).exists())

    def test_delete_route_supports_htmx_confirmation_and_success(self):
        challenge = self.make_challenge(
            "HTMX removal",
            start=timezone.localdate() + timedelta(days=20),
        )
        url = reverse("weeklychallenge:challenge_delete", args=[challenge.pk])

        confirm_response = self.client.get(url, HTTP_HX_REQUEST="true")
        self.assertEqual(confirm_response.status_code, 200)
        self.assertContains(confirm_response, "<dialog")

        delete_response = self.client.post(
            url,
            {"origin": "list"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.headers["HX-Trigger"], "challengeChanged")
        self.assertFalse(Challenge.objects.filter(pk=challenge.pk).exists())

    @patch("weeklychallenge.views.Challenge.delete")
    def test_delete_route_reports_protected_error(self, delete):
        challenge = self.make_challenge(
            "Protected removal",
            start=timezone.localdate() + timedelta(days=20),
        )
        delete.side_effect = ProtectedError("protected", {challenge})

        response = self.client.post(
            reverse("weeklychallenge:challenge_delete", args=[challenge.pk])
        )

        self.assertEqual(response.status_code, 409)
        self.assertContains(
            response,
            "Challenge tidak dapat dihapus karena masih digunakan.",
            status_code=409,
        )
