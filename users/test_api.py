"""
Tests for the users REST API (/api/users/...).

Run:  python manage.py test users.test_api
      python manage.py test users            (runs these together with users/tests.py)

These tests expect:
  * the users API is included in minlife/urls_api.py under the "api" namespace
  * REST_FRAMEWORK uses users.authentication.CsrfExemptSessionAuthentication
  * the "Moderator" group exists (created by migration 0004)
"""
import atexit
import io
import os
import shutil
import tempfile
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient, APITestCase

from .models import Badge, Follow, SocialLink, UserBadge

User = get_user_model()
PASSWORD = "S3cure-pass!"

# uploaded test avatars go here, never into your real media/ folder
TEMP_MEDIA = tempfile.mkdtemp(prefix="minlife-test-media-")
atexit.register(shutil.rmtree, TEMP_MEDIA, ignore_errors=True)

# anonymous requests get 403 with SessionAuthentication (401 with token auth)
DENIED = (401, 403)


def image_bytes(fmt="PNG", size=(4, 4)):
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, fmt)
    return buffer.getvalue()


def png_upload(name="avatar.png"):
    return SimpleUploadedFile(name, image_bytes(), content_type="image/png")


class ApiTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user("alice", "alice@example.com", PASSWORD)
        cls.bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        cls.carol = User.objects.create_user("carol", "carol@example.com", PASSWORD)

    def login(self, user):
        self.client.force_login(user)

    # url helpers
    def url(self, name, **kwargs):
        return reverse(f"users_api:{name}", kwargs=kwargs or None)

    def detail_url(self, user):
        return self.url("user_detail", user_id=user.id)

    def follow_url(self, user):
        return self.url("user_follow", user_id=user.id)

    def search(self, q):
        return self.client.get(self.url("user_search"), {"q": q})

    def usernames(self, response):
        return [u["username"] for u in response.json()]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
class LoginApiTests(ApiTestCase):
    def test_login_with_json(self):
        response = self.client.post(
            self.url("auth_login"), {"username": "alice", "password": PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIs(body["status"], True)
        self.assertEqual(body["username"], "alice")
        self.assertEqual(body["id"], str(self.alice.id))
        self.assertIs(body["is_moderator"], False)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_with_form_data(self):
        # pbp_django_auth's request.login() sends form-encoded data
        response = self.client.post(
            self.url("auth_login"),
            {"username": "alice", "password": PASSWORD},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json()["status"], True)

    def test_wrong_password_returns_401(self):
        response = self.client.post(
            self.url("auth_login"), {"username": "alice", "password": "nope"}, format="json"
        )
        self.assertEqual(response.status_code, 401)
        self.assertIs(response.json()["status"], False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unknown_user_and_empty_body_return_401(self):
        url = self.url("auth_login")
        self.assertEqual(
            self.client.post(url, {"username": "ghost", "password": PASSWORD}, format="json").status_code,
            401,
        )
        self.assertEqual(self.client.post(url, {}, format="json").status_code, 401)

    def test_inactive_user_cannot_log_in(self):
        self.bob.is_active = False
        self.bob.save()
        response = self.client.post(
            self.url("auth_login"), {"username": "bob", "password": PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_login_reports_moderators(self):
        self.alice.groups.add(Group.objects.get(name="Moderator"))
        response = self.client.post(
            self.url("auth_login"), {"username": "alice", "password": PASSWORD}, format="json"
        )
        self.assertIs(response.json()["is_moderator"], True)

    def test_login_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url("auth_login")).status_code, 405)


class RegisterApiTests(ApiTestCase):
    def data(self, **overrides):
        data = {"username": "dave", "password1": PASSWORD, "password2": PASSWORD}
        data.update(overrides)
        return data

    def test_register_with_json(self):
        response = self.client.post(self.url("auth_register"), self.data(), format="json")
        self.assertEqual(response.status_code, 201)
        self.assertIs(response.json()["status"], True)
        self.assertEqual(response.json()["username"], "dave")
        self.assertTrue(User.objects.filter(username="dave").exists())

    def test_register_with_optional_fields(self):
        response = self.client.post(
            self.url("auth_register"),
            self.data(email="dave@example.com", first_name="Dave", bio="Less is more."),
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        dave = User.objects.get(username="dave")
        self.assertEqual(dave.first_name, "Dave")
        self.assertEqual(dave.bio, "Less is more.")

    def test_register_does_not_log_in_and_password_is_hashed(self):
        self.client.post(self.url("auth_register"), self.data(), format="json")
        self.assertNotIn("_auth_user_id", self.client.session)
        dave = User.objects.get(username="dave")
        self.assertNotEqual(dave.password, PASSWORD)
        self.assertTrue(dave.check_password(PASSWORD))

    def test_password_mismatch(self):
        response = self.client.post(
            self.url("auth_register"), self.data(password2="Different-pass1!"), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIs(response.json()["status"], False)
        self.assertIn("password2", response.json()["errors"])
        self.assertFalse(User.objects.filter(username="dave").exists())

    def test_weak_password_is_rejected(self):
        response = self.client.post(
            self.url("auth_register"), self.data(password1="12345678", password2="12345678"), format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_duplicate_username(self):
        response = self.client.post(self.url("auth_register"), self.data(username="alice"), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json()["errors"])
        self.assertEqual(User.objects.filter(username="alice").count(), 1)

    def test_missing_fields(self):
        response = self.client.post(self.url("auth_register"), {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json()["errors"])

    def test_register_with_form_data(self):
        response = self.client.post(self.url("auth_register"), self.data(), format="multipart")
        self.assertEqual(response.status_code, 201)


class LogoutApiTests(ApiTestCase):
    def test_logout_ends_the_session(self):
        self.client.post(
            self.url("auth_login"), {"username": "alice", "password": PASSWORD}, format="json"
        )
        self.assertEqual(self.client.get(self.url("user_me")).status_code, 200)

        response = self.client.post(self.url("auth_logout"))
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json()["status"], True)
        self.assertIn(self.client.get(self.url("user_me")).status_code, DENIED)

    def test_logout_without_a_session_still_succeeds(self):
        self.assertEqual(self.client.post(self.url("auth_logout")).status_code, 200)

    def test_logout_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url("auth_logout")).status_code, 405)


class CsrfApiTests(ApiTestCase):
    """Flutter's CookieRequest sends no CSRF token, so the API must not ask for one."""

    def test_session_login_then_post_works_without_csrf_token(self):
        client = APIClient(enforce_csrf_checks=True)

        login = client.post(
            self.url("auth_login"), {"username": "alice", "password": PASSWORD}, format="json"
        )
        self.assertEqual(login.status_code, 200)

        follow = client.post(self.follow_url(self.bob), format="json")
        self.assertEqual(follow.status_code, 201)   # 403 here would mean CSRF is still enforced

        patch = client.patch(self.url("user_me"), {"bio": "hi"}, format="json")
        self.assertEqual(patch.status_code, 200)

        unfollow = client.delete(self.follow_url(self.bob))
        self.assertEqual(unfollow.status_code, 200)


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------
class ProfileApiTests(ApiTestCase):
    def test_public_profile_is_visible_to_anonymous_users(self):
        response = self.client.get(self.detail_url(self.bob))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], str(self.bob.id))
        self.assertEqual(data["username"], "bob")
        for key in ("bio", "full_name", "avatar_url", "is_following", "is_moderator",
                    "following_count", "social_links", "badges", "date_joined"):
            self.assertIn(key, data)

    def test_private_fields_are_not_exposed(self):
        data = self.client.get(self.detail_url(self.bob)).json()
        for key in ("email", "password", "is_staff", "groups"):
            self.assertNotIn(key, data)

    def test_followers_count_is_hidden_from_others(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        self.login(self.alice)
        self.assertNotIn("followers_count", self.client.get(self.detail_url(self.bob)).json())

    def test_followers_count_is_visible_to_the_owner(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        self.login(self.bob)
        data = self.client.get(self.url("user_me")).json()
        self.assertEqual(data["followers_count"], 1)

    def test_following_count(self):
        Follow.objects.create(follower=self.bob, following=self.alice)
        Follow.objects.create(follower=self.bob, following=self.carol)
        self.assertEqual(self.client.get(self.detail_url(self.bob)).json()["following_count"], 2)

    def test_is_following_flag(self):
        self.login(self.alice)
        self.assertFalse(self.client.get(self.detail_url(self.bob)).json()["is_following"])
        Follow.objects.create(follower=self.alice, following=self.bob)
        self.assertTrue(self.client.get(self.detail_url(self.bob)).json()["is_following"])

    def test_unknown_and_inactive_users_are_404(self):
        self.assertEqual(
            self.client.get(self.url("user_detail", user_id=uuid.uuid4())).status_code, 404
        )
        self.carol.is_active = False
        self.carol.save()
        self.assertEqual(self.client.get(self.detail_url(self.carol)).status_code, 404)

    def test_badges_are_nested(self):
        badge = Badge.objects.create(name="Tidy Desk", description="Cleared the desk")
        UserBadge.objects.create(user=self.bob, badge=badge)
        badges = self.client.get(self.detail_url(self.bob)).json()["badges"]
        self.assertEqual(len(badges), 1)
        self.assertEqual(badges[0]["badge"]["name"], "Tidy Desk")
        self.assertIn("earned_at", badges[0])

    def test_social_links_are_nested(self):
        SocialLink.objects.create(user=self.bob, platform="instagram", url="https://instagram.com/bob")
        links = self.client.get(self.detail_url(self.bob)).json()["social_links"]
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["platform"], "instagram")
        self.assertEqual(links[0]["platform_display"], "Instagram")

    def test_is_moderator(self):
        self.bob.groups.add(Group.objects.get(name="Moderator"))
        self.assertTrue(self.client.get(self.detail_url(self.bob)).json()["is_moderator"])
        self.assertFalse(self.client.get(self.detail_url(self.carol)).json()["is_moderator"])

    def test_avatar_url_is_empty_without_a_photo(self):
        self.assertEqual(self.client.get(self.detail_url(self.bob)).json()["avatar_url"], "")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class AvatarApiTests(ApiTestCase):
    def test_avatar_url_is_absolute(self):
        self.bob.avatar.save("bob.png", SimpleUploadedFile("bob.png", image_bytes()))
        url = self.client.get(self.detail_url(self.bob)).json()["avatar_url"]
        self.assertTrue(url.startswith("http://testserver/"), url)

    def test_upload_avatar(self):
        self.login(self.alice)
        response = self.client.patch(self.url("user_me"), {"avatar": png_upload()}, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["avatar"].startswith("http"))
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.avatar)
        self.assertTrue(os.path.exists(self.alice.avatar.path))

    def test_replacing_avatar_deletes_the_old_file(self):
        self.login(self.alice)
        self.client.patch(self.url("user_me"), {"avatar": png_upload("one.png")}, format="multipart")
        self.alice.refresh_from_db()
        old_path = self.alice.avatar.path

        self.client.patch(self.url("user_me"), {"avatar": png_upload("two.png")}, format="multipart")
        self.alice.refresh_from_db()
        self.assertNotEqual(self.alice.avatar.path, old_path)
        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(self.alice.avatar.path))

    def test_null_clears_avatar_and_deletes_the_file(self):
        self.login(self.alice)
        self.client.patch(self.url("user_me"), {"avatar": png_upload()}, format="multipart")
        self.alice.refresh_from_db()
        path = self.alice.avatar.path

        response = self.client.patch(self.url("user_me"), {"avatar": None}, format="json")
        self.assertEqual(response.status_code, 200)
        self.alice.refresh_from_db()
        self.assertFalse(self.alice.avatar)
        self.assertFalse(os.path.exists(path))

    def test_editing_other_fields_keeps_the_avatar(self):
        self.login(self.alice)
        self.client.patch(self.url("user_me"), {"avatar": png_upload()}, format="multipart")
        self.client.patch(self.url("user_me"), {"bio": "still here"}, format="json")
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.avatar)

    def test_oversized_avatar_is_rejected(self):
        self.login(self.alice)
        big = SimpleUploadedFile("big.bmp", image_bytes("BMP", (1200, 1200)), content_type="image/bmp")
        response = self.client.patch(self.url("user_me"), {"avatar": big}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("avatar", response.json())

    def test_non_image_is_rejected(self):
        self.login(self.alice)
        fake = SimpleUploadedFile("avatar.png", b"this is not an image", content_type="image/png")
        response = self.client.patch(self.url("user_me"), {"avatar": fake}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("avatar", response.json())


class MeApiTests(ApiTestCase):
    def test_requires_login(self):
        url = self.url("user_me")
        self.assertIn(self.client.get(url).status_code, DENIED)
        self.assertIn(self.client.patch(url, {"bio": "x"}, format="json").status_code, DENIED)
        self.assertIn(self.client.delete(url).status_code, DENIED)

    def test_get_returns_own_profile(self):
        self.login(self.alice)
        data = self.client.get(self.url("user_me")).json()
        self.assertEqual(data["username"], "alice")
        self.assertIn("followers_count", data)

    def test_patch_updates_profile(self):
        self.login(self.alice)
        response = self.client.patch(
            self.url("user_me"),
            {"first_name": "Alice", "last_name": "Anderson", "bio": "Less stuff, more life."},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.first_name, "Alice")
        self.assertEqual(self.alice.last_name, "Anderson")
        self.assertEqual(self.alice.bio, "Less stuff, more life.")

    def test_bio_over_160_characters_is_rejected(self):
        self.login(self.alice)
        response = self.client.patch(self.url("user_me"), {"bio": "x" * 161}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("bio", response.json())
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.bio, "")

    def test_cannot_change_protected_fields(self):
        self.login(self.alice)
        self.client.patch(
            self.url("user_me"),
            {"username": "hacker", "is_staff": True, "is_superuser": True, "email": "x@x.com"},
            format="json",
        )
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.username, "alice")
        self.assertFalse(self.alice.is_staff)
        self.assertFalse(self.alice.is_superuser)
        self.assertEqual(self.alice.email, "alice@example.com")

    def test_patch_only_touches_the_logged_in_user(self):
        self.login(self.alice)
        self.client.patch(self.url("user_me"), {"first_name": "Changed"}, format="json")
        self.bob.refresh_from_db()
        self.assertNotEqual(self.bob.first_name, "Changed")

    def test_delete_removes_the_account_and_ends_the_session(self):
        self.client.post(
            self.url("auth_login"), {"username": "alice", "password": PASSWORD}, format="json"
        )
        response = self.client.delete(self.url("user_me"))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(User.objects.filter(pk=self.alice.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.bob.pk).exists())
        self.assertIn(self.client.get(self.url("user_me")).status_code, DENIED)

    def test_delete_removes_the_users_follows(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        Follow.objects.create(follower=self.carol, following=self.alice)
        self.login(self.alice)
        self.client.delete(self.url("user_me"))
        self.assertEqual(Follow.objects.count(), 0)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
class SearchApiTests(ApiTestCase):
    def test_requires_login(self):
        self.assertIn(self.search("bo").status_code, DENIED)

    def test_post_is_not_allowed(self):
        self.login(self.alice)
        self.assertEqual(self.client.post(self.url("user_search"), {"q": "bo"}).status_code, 405)

    def test_short_query_returns_nothing(self):
        self.login(self.alice)
        self.assertEqual(self.search("b").json(), [])
        self.assertEqual(self.search("").json(), [])
        self.assertEqual(self.client.get(self.url("user_search")).json(), [])

    def test_finds_by_partial_username_case_insensitively(self):
        self.login(self.alice)
        self.assertEqual(self.usernames(self.search("BO")), ["bob"])

    def test_finds_by_first_or_last_name(self):
        self.carol.first_name = "Caroline"
        self.carol.last_name = "Whitfield"
        self.carol.save()
        self.login(self.alice)
        self.assertEqual(self.usernames(self.search("carolin")), ["carol"])
        self.assertEqual(self.usernames(self.search("whitf")), ["carol"])

    def test_excludes_yourself_and_inactive_users(self):
        self.bob.is_active = False
        self.bob.save()
        self.login(self.alice)
        self.assertEqual(self.search("alice").json(), [])
        self.assertEqual(self.search("bob").json(), [])

    def test_result_shape(self):
        self.login(self.alice)
        result = self.search("bob").json()[0]
        self.assertEqual(
            set(result), {"id", "username", "full_name", "avatar_url", "is_following"}
        )
        self.assertEqual(result["id"], str(self.bob.id))

    def test_is_following_flag(self):
        self.login(self.alice)
        self.assertFalse(self.search("bob").json()[0]["is_following"])
        Follow.objects.create(follower=self.alice, following=self.bob)
        self.assertTrue(self.search("bob").json()[0]["is_following"])

    def test_other_peoples_follows_do_not_affect_the_flag(self):
        Follow.objects.create(follower=self.carol, following=self.bob)
        self.login(self.alice)
        self.assertFalse(self.search("bob").json()[0]["is_following"])

    def test_limited_to_ten_and_sorted(self):
        for i in range(12):
            User.objects.create_user(f"searchuser{i:02d}", password=PASSWORD)
        self.login(self.alice)
        names = self.usernames(self.search("searchuser"))
        self.assertEqual(len(names), 10)
        self.assertEqual(names, sorted(names))


# ---------------------------------------------------------------------------
# Following
# ---------------------------------------------------------------------------
class FollowApiTests(ApiTestCase):
    def test_requires_login(self):
        self.assertIn(self.client.post(self.follow_url(self.bob)).status_code, DENIED)
        self.assertIn(self.client.delete(self.follow_url(self.bob)).status_code, DENIED)
        self.assertEqual(Follow.objects.count(), 0)

    def test_follow(self):
        self.login(self.alice)
        response = self.client.post(self.follow_url(self.bob))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"following": True, "following_count": 1})
        self.assertTrue(Follow.objects.filter(follower=self.alice, following=self.bob).exists())

    def test_following_twice_is_idempotent(self):
        self.login(self.alice)
        self.client.post(self.follow_url(self.bob))
        response = self.client.post(self.follow_url(self.bob))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"following": True, "following_count": 1})
        self.assertEqual(Follow.objects.count(), 1)

    def test_unfollow(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        self.login(self.alice)
        response = self.client.delete(self.follow_url(self.bob))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"following": False, "following_count": 0})
        self.assertEqual(Follow.objects.count(), 0)

    def test_unfollowing_twice_is_harmless(self):
        self.login(self.alice)
        self.assertEqual(self.client.delete(self.follow_url(self.bob)).status_code, 200)
        self.assertEqual(self.client.delete(self.follow_url(self.bob)).status_code, 200)

    def test_following_count_counts_everyone_followed(self):
        self.login(self.alice)
        self.client.post(self.follow_url(self.bob))
        response = self.client.post(self.follow_url(self.carol))
        self.assertEqual(response.json()["following_count"], 2)

    def test_cannot_follow_or_unfollow_yourself(self):
        self.login(self.alice)
        self.assertEqual(self.client.post(self.follow_url(self.alice)).status_code, 400)
        self.assertEqual(self.client.delete(self.follow_url(self.alice)).status_code, 400)
        self.assertEqual(Follow.objects.count(), 0)

    def test_unknown_and_inactive_users_are_404(self):
        self.login(self.alice)
        unknown = self.url("user_follow", user_id=uuid.uuid4())
        self.assertEqual(self.client.post(unknown).status_code, 404)
        self.carol.is_active = False
        self.carol.save()
        self.assertEqual(self.client.post(self.follow_url(self.carol)).status_code, 404)

    def test_get_is_not_allowed(self):
        self.login(self.alice)
        self.assertEqual(self.client.get(self.follow_url(self.bob)).status_code, 405)


class FollowListApiTests(ApiTestCase):
    def setUp(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        Follow.objects.create(follower=self.alice, following=self.carol)
        Follow.objects.create(follower=self.carol, following=self.bob)

    def following_url(self, user):
        return self.url("user_following", user_id=user.id)

    def followers_url(self, user):
        return self.url("user_followers", user_id=user.id)

    def test_following_list_is_public(self):
        response = self.client.get(self.following_url(self.alice))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.usernames(response), ["bob", "carol"])

    def test_following_list_marks_who_the_viewer_follows(self):
        self.login(self.carol)
        flags = {u["username"]: u["is_following"] for u in
                 self.client.get(self.following_url(self.alice)).json()}
        self.assertEqual(flags, {"bob": True, "carol": False})

    def test_following_list_hides_inactive_users(self):
        self.carol.is_active = False
        self.carol.save()
        self.assertEqual(self.usernames(self.client.get(self.following_url(self.alice))), ["bob"])

    def test_owner_sees_their_followers(self):
        self.login(self.bob)
        response = self.client.get(self.followers_url(self.bob))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.usernames(response), ["alice", "carol"])

    def test_other_users_cannot_see_followers(self):
        self.login(self.alice)
        self.assertEqual(self.client.get(self.followers_url(self.bob)).status_code, 403)

    def test_followers_require_login(self):
        self.assertIn(self.client.get(self.followers_url(self.bob)).status_code, DENIED)

    def test_empty_lists(self):
        self.login(self.alice)
        self.assertEqual(self.client.get(self.followers_url(self.alice)).json(), [])
        self.assertEqual(self.client.get(self.following_url(self.bob)).json(), [])

    def test_unknown_user_is_404(self):
        unknown = self.url("user_following", user_id=uuid.uuid4())
        self.assertEqual(self.client.get(unknown).status_code, 404)


# ---------------------------------------------------------------------------
# Social links
# ---------------------------------------------------------------------------
class SocialLinkApiTests(ApiTestCase):
    list_name = "user_social_links"
    detail_name = "user_social_link"

    def link_url(self, link):
        return self.url(self.detail_name, pk=link.pk)

    def make_link(self, user=None, platform="instagram", url="https://instagram.com/alice"):
        return SocialLink.objects.create(user=user or self.alice, platform=platform, url=url)

    def test_requires_login(self):
        link = self.make_link()
        self.assertIn(self.client.get(self.url(self.list_name)).status_code, DENIED)
        self.assertIn(
            self.client.post(self.url(self.list_name), {"platform": "website", "url": "https://a.com"},
                             format="json").status_code, DENIED)
        self.assertIn(self.client.delete(self.link_url(link)).status_code, DENIED)

    def test_list_shows_only_own_links(self):
        self.make_link()
        self.make_link(user=self.bob, url="https://instagram.com/bob")
        self.login(self.alice)
        data = self.client.get(self.url(self.list_name)).json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["url"], "https://instagram.com/alice")

    def test_create(self):
        self.login(self.alice)
        response = self.client.post(
            self.url(self.list_name),
            {"platform": "youtube", "url": "https://youtube.com/@alice"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["platform"], "youtube")
        self.assertEqual(body["platform_display"], "YouTube")
        link = SocialLink.objects.get(pk=body["id"])
        self.assertEqual(link.user, self.alice)

    def test_cannot_assign_a_link_to_someone_else(self):
        self.login(self.alice)
        self.client.post(
            self.url(self.list_name),
            {"platform": "youtube", "url": "https://youtube.com/@alice", "user": str(self.bob.id)},
            format="json",
        )
        self.assertEqual(SocialLink.objects.filter(user=self.bob).count(), 0)
        self.assertEqual(SocialLink.objects.filter(user=self.alice).count(), 1)

    def test_duplicate_platform_is_rejected(self):
        self.make_link()
        self.login(self.alice)
        response = self.client.post(
            self.url(self.list_name),
            {"platform": "instagram", "url": "https://instagram.com/other"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("platform", response.json())
        self.assertEqual(SocialLink.objects.filter(user=self.alice).count(), 1)

    def test_same_platform_for_different_users_is_fine(self):
        self.make_link(user=self.bob, url="https://instagram.com/bob")
        self.login(self.alice)
        response = self.client.post(
            self.url(self.list_name),
            {"platform": "instagram", "url": "https://instagram.com/alice"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_invalid_url_and_platform_are_rejected(self):
        self.login(self.alice)
        bad_url = self.client.post(
            self.url(self.list_name), {"platform": "website", "url": "not-a-url"}, format="json"
        )
        self.assertEqual(bad_url.status_code, 400)
        self.assertIn("url", bad_url.json())

        bad_platform = self.client.post(
            self.url(self.list_name), {"platform": "myspace", "url": "https://a.com"}, format="json"
        )
        self.assertEqual(bad_platform.status_code, 400)
        self.assertIn("platform", bad_platform.json())

    def test_missing_fields_are_rejected(self):
        self.login(self.alice)
        response = self.client.post(self.url(self.list_name), {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_retrieve(self):
        link = self.make_link()
        self.login(self.alice)
        response = self.client.get(self.link_url(link))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["url"], "https://instagram.com/alice")

    def test_patch_url(self):
        link = self.make_link()
        self.login(self.alice)
        response = self.client.patch(
            self.link_url(link), {"url": "https://instagram.com/new"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        link.refresh_from_db()
        self.assertEqual(link.url, "https://instagram.com/new")

    def test_patch_keeping_the_same_platform_is_not_a_duplicate(self):
        link = self.make_link()
        self.login(self.alice)
        response = self.client.patch(
            self.link_url(link),
            {"platform": "instagram", "url": "https://instagram.com/new"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_patch_to_a_platform_already_used_is_rejected(self):
        link = self.make_link()
        self.make_link(platform="website", url="https://alice.example.com")
        self.login(self.alice)
        response = self.client.patch(self.link_url(link), {"platform": "website"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("platform", response.json())
        link.refresh_from_db()
        self.assertEqual(link.platform, "instagram")

    def test_delete(self):
        link = self.make_link()
        self.login(self.alice)
        self.assertEqual(self.client.delete(self.link_url(link)).status_code, 204)
        self.assertFalse(SocialLink.objects.filter(pk=link.pk).exists())

    def test_other_users_links_are_404(self):
        link = self.make_link(user=self.bob, url="https://instagram.com/bob")
        self.login(self.alice)
        self.assertEqual(self.client.get(self.link_url(link)).status_code, 404)
        self.assertEqual(
            self.client.patch(self.link_url(link), {"url": "https://evil.example.com"}, format="json").status_code,
            404,
        )
        self.assertEqual(self.client.delete(self.link_url(link)).status_code, 404)
        link.refresh_from_db()
        self.assertEqual(link.url, "https://instagram.com/bob")

    def test_links_show_up_in_the_public_profile(self):
        self.make_link()
        self.login(self.bob)
        links = self.client.get(self.detail_url(self.alice)).json()["social_links"]
        self.assertEqual([l["platform"] for l in links], ["instagram"])
