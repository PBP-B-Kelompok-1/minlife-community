"""
Tests for the users app.

Run all of them:        python manage.py test users
Run one class:          python manage.py test users.tests.ToggleFollowTests
Run one test, verbose:  python manage.py test users.tests.ToggleFollowTests.test_follow_creates_row -v 2

The test runner builds a throwaway database, so your db.sqlite3 is never touched.
"""
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from posts.models import Post

from .models import Badge, Follow, SocialLink, SocialPlatform, UserBadge

User = get_user_model()
PASSWORD = "S3cure-pass!"
AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def social_formset_data(rows=()):
    """Management-form data for the social links formset, plus new rows.

    rows: iterable of (platform, url) tuples, all treated as NEW rows.
    """
    data = {
        "social_links-TOTAL_FORMS": str(len(rows)),
        "social_links-INITIAL_FORMS": "0",
        "social_links-MIN_NUM_FORMS": "0",
        "social_links-MAX_NUM_FORMS": "5",
    }
    for i, (platform, url) in enumerate(rows):
        data[f"social_links-{i}-platform"] = platform
        data[f"social_links-{i}-url"] = url
    return data


def profile_post_data(rows=(), **overrides):
    data = {
        "first_name": "Alice",
        "last_name": "Anderson",
        "bio": "Less stuff, more life.",
    }
    data.update(overrides)
    data.update(social_formset_data(rows))
    return data


class UsersTestCase(TestCase):
    """Shared fixtures: three users and a couple of helpers."""

    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user("alice", "alice@example.com", PASSWORD)
        cls.bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        cls.carol = User.objects.create_user("carol", "carol@example.com", PASSWORD)

    def login(self, user):
        self.client.force_login(user)

    def assertRequiresLogin(self, response):
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def follow_url(self, user):
        return reverse("users:toggle_follow", kwargs={"user_id": user.id})

    def profile_url(self, user):
        return reverse("users:show_profile", kwargs={"user_id": user.id})


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class UserModelTests(UsersTestCase):
    def test_id_is_uuid(self):
        self.assertIsInstance(self.alice.id, uuid.UUID)

    def test_defaults(self):
        self.assertEqual(self.alice.bio, "")
        self.assertEqual(self.alice.get_zen_points(), 0)

    def test_username_is_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user("alice", "other@example.com", PASSWORD)


class FollowModelTests(UsersTestCase):
    def test_follow_is_one_directional(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        self.assertIn(self.bob, self.alice.following.all())
        self.assertIn(self.alice, self.bob.followers.all())
        self.assertNotIn(self.alice, self.bob.following.all())

    def test_cannot_follow_twice(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Follow.objects.create(follower=self.alice, following=self.bob)

    def test_cannot_follow_self(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Follow.objects.create(follower=self.alice, following=self.alice)

    def test_str(self):
        follow = Follow.objects.create(follower=self.alice, following=self.bob)
        self.assertEqual(str(follow), "alice → bob")

    def test_deleting_user_deletes_their_follows(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        Follow.objects.create(follower=self.carol, following=self.alice)
        self.alice.delete()
        self.assertEqual(Follow.objects.count(), 0)


class SocialLinkModelTests(UsersTestCase):
    def test_one_link_per_platform_per_user(self):
        SocialLink.objects.create(
            user=self.alice, platform=SocialPlatform.INSTAGRAM, url="https://instagram.com/a"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SocialLink.objects.create(
                    user=self.alice, platform=SocialPlatform.INSTAGRAM, url="https://instagram.com/b"
                )

    def test_same_platform_for_different_users_is_fine(self):
        SocialLink.objects.create(
            user=self.alice, platform=SocialPlatform.INSTAGRAM, url="https://instagram.com/a"
        )
        SocialLink.objects.create(
            user=self.bob, platform=SocialPlatform.INSTAGRAM, url="https://instagram.com/b"
        )
        self.assertEqual(SocialLink.objects.count(), 2)

    def test_related_name_and_str(self):
        link = SocialLink.objects.create(
            user=self.alice, platform=SocialPlatform.YOUTUBE, url="https://youtube.com/a"
        )
        self.assertEqual(self.alice.social_links.count(), 1)
        self.assertEqual(str(link), "alice - YouTube")


class BadgeModelTests(UsersTestCase):
    def test_user_cannot_earn_same_badge_twice(self):
        badge = Badge.objects.create(name="Tidy Desk")
        UserBadge.objects.create(user=self.alice, badge=badge)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserBadge.objects.create(user=self.alice, badge=badge)

    def test_related_names(self):
        badge = Badge.objects.create(name="Tidy Desk")
        UserBadge.objects.create(user=self.alice, badge=badge)
        self.assertEqual(self.alice.user_badges.count(), 1)
        self.assertEqual(badge.awards.count(), 1)


class ModeratorGroupTests(TestCase):
    def test_moderator_group_is_created_by_migration(self):
        self.assertTrue(Group.objects.filter(name="Moderator").exists())


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
class RegisterViewTests(UsersTestCase):
    def valid_data(self, **overrides):
        data = {
            "username": "dave",
            "email": "dave@example.com",
            "first_name": "Dave",
            "last_name": "Dawson",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
        data.update(overrides)
        return data

    def test_get_renders_form(self):
        response = self.client.get(reverse("users:register"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/register.html")

    def test_valid_registration_creates_user_and_redirects_to_login(self):
        response = self.client.post(reverse("users:register"), self.valid_data())
        self.assertRedirects(response, reverse("users:login"), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(username="dave").exists())

    def test_registered_user_can_log_in_with_hashed_password(self):
        self.client.post(reverse("users:register"), self.valid_data())
        dave = User.objects.get(username="dave")
        self.assertNotEqual(dave.password, PASSWORD)
        self.assertTrue(self.client.login(username="dave", password=PASSWORD))

    def test_success_message_is_queued(self):
        response = self.client.post(reverse("users:register"), self.valid_data())
        levels = [m.level_tag for m in get_messages(response.wsgi_request)]
        self.assertIn("success", levels)

    def test_mismatched_passwords_are_rejected(self):
        response = self.client.post(
            reverse("users:register"), self.valid_data(password2="Different-pass1!")
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="dave").exists())

    def test_duplicate_username_is_rejected(self):
        response = self.client.post(reverse("users:register"), self.valid_data(username="alice"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username="alice").count(), 1)


class LoginLogoutTests(UsersTestCase):
    def test_get_renders_form(self):
        response = self.client.get(reverse("users:login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/login.html")

    def test_valid_login_redirects_to_frontpage(self):
        response = self.client.post(
            reverse("users:login"), {"username": "alice", "password": PASSWORD}
        )
        self.assertRedirects(response, reverse("frontpage"), fetch_redirect_response=False)
        self.assertIn("_auth_user_id", self.client.session)

    def test_wrong_password_does_not_log_in(self):
        response = self.client.post(
            reverse("users:login"), {"username": "alice", "password": "nope"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_post_logs_out(self):
        self.login(self.alice)
        response = self.client.post(reverse("users:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_get_is_not_allowed(self):
        self.login(self.alice)
        response = self.client.get(reverse("users:logout"))
        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)


# ---------------------------------------------------------------------------
# Profile pages
# ---------------------------------------------------------------------------
class ProfileViewTests(UsersTestCase):
    def test_my_profile_requires_login(self):
        self.assertRequiresLogin(self.client.get(reverse("users:show_my_profile")))

    def test_my_profile_shows_own_profile(self):
        self.login(self.alice)
        response = self.client.get(reverse("users:show_my_profile"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/profile.html")
        self.assertEqual(response.context["profile_user"], self.alice)

    def test_other_profiles_are_public(self):
        response = self.client.get(self.profile_url(self.bob))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["profile_user"], self.bob)
        self.assertContains(response, "bob")

    def test_unknown_profile_is_404(self):
        url = reverse("users:show_profile", kwargs={"user_id": uuid.uuid4()})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_is_following_flag(self):
        self.login(self.alice)
        self.assertFalse(self.client.get(self.profile_url(self.bob)).context["is_following"])
        Follow.objects.create(follower=self.alice, following=self.bob)
        self.assertTrue(self.client.get(self.profile_url(self.bob)).context["is_following"])

    def test_followers_link_only_visible_to_owner(self):
        followers_url = lambda u: reverse("users:followers_list", kwargs={"user_id": u.id})
        self.login(self.alice)
        own = self.client.get(reverse("users:show_my_profile"))
        self.assertContains(own, followers_url(self.alice))
        other = self.client.get(self.profile_url(self.bob))
        self.assertNotContains(other, followers_url(self.bob))

    def test_badges_are_shown(self):
        badge = Badge.objects.create(name="Tidy Desk")
        UserBadge.objects.create(user=self.alice, badge=badge)
        self.login(self.alice)
        response = self.client.get(reverse("users:show_my_profile"))
        self.assertEqual(len(response.context["user_badges"]), 1)
        self.assertContains(response, "Tidy Desk")

    def test_no_badges_message(self):
        self.login(self.alice)
        response = self.client.get(reverse("users:show_my_profile"))
        self.assertContains(response, "No badges yet.")

    def test_social_links_are_shown(self):
        SocialLink.objects.create(
            user=self.alice, platform=SocialPlatform.INSTAGRAM, url="https://instagram.com/alice"
        )
        self.login(self.alice)
        response = self.client.get(reverse("users:show_my_profile"))
        self.assertContains(response, "https://instagram.com/alice")
        self.assertContains(response, "Instagram")


class PostsOnProfileTests(UsersTestCase):
    """If these fail after a posts-app change, the Post model probably gained a required field."""

    def test_own_posts_are_listed_and_others_are_not(self):
        Post.objects.create(author=self.alice, title="Alice post", content="hello")
        Post.objects.create(author=self.bob, title="Bob post", content="hi")
        self.login(self.alice)
        response = self.client.get(reverse("users:show_my_profile"))
        titles = [p.title for p in response.context["user_posts"]]
        self.assertEqual(titles, ["Alice post"])
        self.assertContains(response, "Alice post")
        self.assertNotContains(response, "Bob post")

    def test_empty_state(self):
        self.login(self.alice)
        response = self.client.get(reverse("users:show_my_profile"))
        self.assertContains(response, "No posts yet.")

    def test_only_latest_ten_are_shown(self):
        for i in range(12):
            Post.objects.create(author=self.alice, title=f"Post {i}", content="x")
        self.login(self.alice)
        response = self.client.get(reverse("users:show_my_profile"))
        self.assertEqual(len(response.context["user_posts"]), 10)


# ---------------------------------------------------------------------------
# Edit profile / social links
# ---------------------------------------------------------------------------
class UpdateProfileTests(UsersTestCase):
    url_name = "users:update_profile"

    def test_requires_login(self):
        self.assertRequiresLogin(self.client.get(reverse(self.url_name)))

    def test_get_renders_form_and_formset(self):
        self.login(self.alice)
        response = self.client.get(reverse(self.url_name))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/update_profile.html")
        self.assertIn("form", response.context)
        self.assertIn("formset", response.context)

    def test_updates_profile_fields(self):
        self.login(self.alice)
        response = self.client.post(reverse(self.url_name), profile_post_data())
        self.assertRedirects(
            response, reverse("users:show_my_profile"), fetch_redirect_response=False
        )
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.first_name, "Alice")
        self.assertEqual(self.alice.last_name, "Anderson")
        self.assertEqual(self.alice.bio, "Less stuff, more life.")

    def test_bio_over_160_characters_is_rejected(self):
        self.login(self.alice)
        response = self.client.post(reverse(self.url_name), profile_post_data(bio="x" * 161))
        self.assertEqual(response.status_code, 200)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.bio, "")

    def test_cannot_edit_someone_elses_profile(self):
        # The view always edits request.user, whatever the form says.
        self.login(self.alice)
        self.client.post(reverse(self.url_name), profile_post_data(first_name="Hacked"))
        self.bob.refresh_from_db()
        self.assertNotEqual(self.bob.first_name, "Hacked")

    def test_adds_new_social_link(self):
        self.login(self.alice)
        rows = [("instagram", "https://instagram.com/alice")]
        response = self.client.post(reverse(self.url_name), profile_post_data(rows))
        self.assertEqual(response.status_code, 302)
        link = SocialLink.objects.get(user=self.alice, platform="instagram")
        self.assertEqual(link.url, "https://instagram.com/alice")

    def test_invalid_url_is_rejected(self):
        self.login(self.alice)
        rows = [("website", "not-a-url")]
        response = self.client.post(reverse(self.url_name), profile_post_data(rows))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SocialLink.objects.count(), 0)

    def test_new_row_for_platform_user_already_has_is_rejected(self):
        SocialLink.objects.create(
            user=self.alice, platform="instagram", url="https://instagram.com/old"
        )
        self.login(self.alice)
        rows = [("instagram", "https://instagram.com/new")]
        response = self.client.post(reverse(self.url_name), profile_post_data(rows))
        self.assertEqual(response.status_code, 200)
        link = SocialLink.objects.get(user=self.alice, platform="instagram")
        self.assertEqual(link.url, "https://instagram.com/old")

    def test_same_platform_twice_in_one_submission_is_rejected(self):
        # If this test ERRORS with an IntegrityError instead of failing cleanly,
        # the formset needs a clean() that checks for duplicate platforms
        # (see the notes next to this file).
        self.login(self.alice)
        rows = [
            ("instagram", "https://instagram.com/one"),
            ("instagram", "https://instagram.com/two"),
        ]
        response = self.client.post(reverse(self.url_name), profile_post_data(rows))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SocialLink.objects.count(), 0)

    def _existing_link_data(self, link, **overrides):
        data = profile_post_data()
        data.update({
            "social_links-TOTAL_FORMS": "1",
            "social_links-INITIAL_FORMS": "1",
            "social_links-0-id": str(link.pk),
            "social_links-0-user": str(self.alice.pk),
            "social_links-0-platform": link.platform,
            "social_links-0-url": link.url,
        })
        data.update(overrides)
        return data

    def test_updates_existing_link_url(self):
        link = SocialLink.objects.create(
            user=self.alice, platform="instagram", url="https://instagram.com/old"
        )
        self.login(self.alice)
        data = self._existing_link_data(link, **{"social_links-0-url": "https://instagram.com/new"})
        self.client.post(reverse(self.url_name), data)
        link.refresh_from_db()
        self.assertEqual(link.url, "https://instagram.com/new")

    def test_deletes_existing_link(self):
        link = SocialLink.objects.create(
            user=self.alice, platform="instagram", url="https://instagram.com/old"
        )
        self.login(self.alice)
        data = self._existing_link_data(link, **{"social_links-0-DELETE": "on"})
        self.client.post(reverse(self.url_name), data)
        self.assertFalse(SocialLink.objects.filter(pk=link.pk).exists())


# ---------------------------------------------------------------------------
# Delete account
# ---------------------------------------------------------------------------
class DeleteAccountTests(UsersTestCase):
    url_name = "users:delete_account"

    def test_requires_login(self):
        self.assertRequiresLogin(self.client.get(reverse(self.url_name)))
        self.assertRequiresLogin(self.client.post(reverse(self.url_name)))
        self.assertTrue(User.objects.filter(pk=self.alice.pk).exists())

    def test_get_shows_confirmation_page_without_deleting(self):
        self.login(self.alice)
        response = self.client.get(reverse(self.url_name))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/delete_account.html")
        self.assertTrue(User.objects.filter(pk=self.alice.pk).exists())

    def test_post_deletes_account_and_logs_out(self):
        self.login(self.alice)
        response = self.client.post(reverse(self.url_name))
        self.assertRedirects(response, reverse("frontpage"), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(pk=self.alice.pk).exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_only_deletes_the_logged_in_user(self):
        self.login(self.alice)
        self.client.post(reverse(self.url_name))
        self.assertTrue(User.objects.filter(pk=self.bob.pk).exists())

    def test_deleting_account_deletes_their_posts(self):
        Post.objects.create(author=self.alice, title="Alice post", content="x")
        self.login(self.alice)
        self.client.post(reverse(self.url_name))
        self.assertEqual(Post.objects.count(), 0)


# ---------------------------------------------------------------------------
# Following
# ---------------------------------------------------------------------------
class ToggleFollowTests(UsersTestCase):
    def test_requires_login(self):
        response = self.client.post(self.follow_url(self.bob))
        self.assertRequiresLogin(response)
        self.assertEqual(Follow.objects.count(), 0)

    def test_get_is_not_allowed(self):
        self.login(self.alice)
        self.assertEqual(self.client.get(self.follow_url(self.bob)).status_code, 405)

    def test_follow_creates_row(self):
        self.login(self.alice)
        response = self.client.post(self.follow_url(self.bob))
        self.assertRedirects(response, self.profile_url(self.bob), fetch_redirect_response=False)
        self.assertTrue(Follow.objects.filter(follower=self.alice, following=self.bob).exists())

    def test_second_post_unfollows(self):
        self.login(self.alice)
        self.client.post(self.follow_url(self.bob))
        self.client.post(self.follow_url(self.bob))
        self.assertFalse(Follow.objects.filter(follower=self.alice, following=self.bob).exists())

    def test_cannot_follow_yourself(self):
        self.login(self.alice)
        response = self.client.post(self.follow_url(self.alice))
        # older version answers 400, the toast version redirects back with an error
        self.assertIn(response.status_code, (302, 400))
        self.assertEqual(Follow.objects.count(), 0)

    def test_following_unknown_user_is_404(self):
        self.login(self.alice)
        url = reverse("users:toggle_follow", kwargs={"user_id": uuid.uuid4()})
        self.assertEqual(self.client.post(url).status_code, 404)

    def test_follow_queues_a_message(self):
        self.login(self.alice)
        response = self.client.post(self.follow_url(self.bob))
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("bob" in m for m in messages))


class AjaxToggleFollowTests(UsersTestCase):
    def test_follow_and_unfollow_return_json(self):
        self.login(self.alice)

        data = self.client.post(self.follow_url(self.bob), **AJAX).json()
        self.assertTrue(data["following"])
        self.assertEqual(data["following_count"], 1)

        data = self.client.post(self.follow_url(self.bob), **AJAX).json()
        self.assertFalse(data["following"])
        self.assertEqual(data["following_count"], 0)

    def test_ajax_does_not_queue_messages(self):
        # otherwise a stale toast would appear on the next page load
        self.login(self.alice)
        response = self.client.post(self.follow_url(self.bob), **AJAX)
        self.assertEqual(list(get_messages(response.wsgi_request)), [])

    def test_ajax_self_follow_is_rejected(self):
        self.login(self.alice)
        response = self.client.post(self.follow_url(self.alice), **AJAX)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Follow.objects.count(), 0)


class FollowListTests(UsersTestCase):
    def following_url(self, user):
        return reverse("users:following_list", kwargs={"user_id": user.id})

    def followers_url(self, user):
        return reverse("users:followers_list", kwargs={"user_id": user.id})

    def setUp(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        Follow.objects.create(follower=self.carol, following=self.bob)

    def test_following_list_shows_who_a_user_follows(self):
        self.login(self.alice)
        response = self.client.get(self.following_url(self.alice))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/follow_list.html")
        self.assertEqual([p.pk for p in response.context["people"]], [self.bob.pk])
        self.assertEqual(response.context["list_type"], "following")

    def test_following_list_of_another_user_is_visible(self):
        self.login(self.bob)
        response = self.client.get(self.following_url(self.alice))
        self.assertEqual(response.status_code, 200)

    def test_owner_sees_their_followers(self):
        self.login(self.bob)
        response = self.client.get(self.followers_url(self.bob))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {p.pk for p in response.context["people"]}, {self.alice.pk, self.carol.pk}
        )
        self.assertEqual(response.context["list_type"], "followers")

    def test_other_users_cannot_see_followers(self):
        self.login(self.alice)
        self.assertEqual(self.client.get(self.followers_url(self.bob)).status_code, 403)

    def test_followers_list_requires_login(self):
        self.assertRequiresLogin(self.client.get(self.followers_url(self.bob)))

    def test_empty_list(self):
        self.login(self.carol)
        response = self.client.get(self.followers_url(self.carol))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nobody here yet.")


# ---------------------------------------------------------------------------
# People search (AJAX)
# ---------------------------------------------------------------------------
class SearchUsersTests(UsersTestCase):
    url_name = "users:search_users"

    def search(self, q):
        return self.client.get(reverse(self.url_name), {"q": q})

    def test_anonymous_gets_401_json(self):
        response = self.search("bo")
        self.assertEqual(response.status_code, 401)
        self.assertIn("message", response.json())

    def test_post_is_not_allowed(self):
        self.login(self.alice)
        self.assertEqual(self.client.post(reverse(self.url_name), {"q": "bo"}).status_code, 405)

    def test_short_query_returns_nothing(self):
        self.login(self.alice)
        self.assertEqual(self.search("b").json()["data"], [])
        self.assertEqual(self.search("").json()["data"], [])

    def test_finds_user_by_partial_username_case_insensitively(self):
        self.login(self.alice)
        data = self.search("BO").json()["data"]
        self.assertEqual([u["username"] for u in data], ["bob"])

    def test_finds_user_by_first_or_last_name(self):
        self.carol.first_name = "Caroline"
        self.carol.last_name = "Whitfield"
        self.carol.save()
        self.login(self.alice)
        self.assertEqual(self.search("carolin").json()["data"][0]["username"], "carol")
        self.assertEqual(self.search("whitf").json()["data"][0]["username"], "carol")

    def test_excludes_yourself(self):
        self.login(self.alice)
        self.assertEqual(self.search("alice").json()["data"], [])

    def test_excludes_inactive_users(self):
        self.bob.is_active = False
        self.bob.save()
        self.login(self.alice)
        self.assertEqual(self.search("bob").json()["data"], [])

    def test_result_shape(self):
        self.login(self.alice)
        result = self.search("bob").json()["data"][0]
        self.assertEqual(result["id"], str(self.bob.id))
        for key in ("username", "full_name", "avatar_url", "is_following"):
            self.assertIn(key, result)

    def test_is_following_flag(self):
        self.login(self.alice)
        self.assertFalse(self.search("bob").json()["data"][0]["is_following"])
        Follow.objects.create(follower=self.alice, following=self.bob)
        self.assertTrue(self.search("bob").json()["data"][0]["is_following"])

    def test_following_someone_else_does_not_affect_flag(self):
        Follow.objects.create(follower=self.carol, following=self.bob)
        self.login(self.alice)
        self.assertFalse(self.search("bob").json()["data"][0]["is_following"])

    def test_results_are_limited_to_ten(self):
        for i in range(12):
            User.objects.create_user(f"searchuser{i:02d}", password=PASSWORD)
        self.login(self.alice)
        self.assertEqual(len(self.search("searchuser").json()["data"]), 10)

    def test_results_are_sorted_by_username(self):
        for name in ("zed_match", "abe_match", "mid_match"):
            User.objects.create_user(name, password=PASSWORD)
        self.login(self.alice)
        names = [u["username"] for u in self.search("_match").json()["data"]]
        self.assertEqual(names, sorted(names))
