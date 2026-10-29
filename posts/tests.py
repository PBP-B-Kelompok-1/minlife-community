import json

from django.db import IntegrityError, transaction
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from users.models import User

from .forms import PostForm
from .models import Comment, Post, Tag, Vote


class PostsTestCase(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author", password="test-password", bio=""
        )
        self.other_user = User.objects.create_user(
            username="reader", password="test-password", bio=""
        )

    def create_post(self, **overrides):
        values = {"author": self.author, "title": "A post", "content": "Post content"}
        values.update(overrides)
        return Post.objects.create(**values)


class PostModelAndFormTests(PostsTestCase):
    def test_post_is_stringified_by_title_and_tags_can_be_assigned(self):
        post = self.create_post(title="Declutter desk")
        tag = Tag.objects.create(title="article")
        post.tags.add(tag)

        self.assertEqual(str(post), "Declutter desk")
        self.assertQuerySetEqual(tag.tagged_posts.all(), [post])

    def test_post_form_accepts_content_and_selected_tags(self):
        tag = Tag.objects.create(title="question")
        form = PostForm(data={"title": "Need advice", "content": "Where do I start?", "tags": [tag.pk]})

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["tags"].get(), tag)

    def test_post_form_requires_a_title(self):
        form = PostForm(data={"title": "", "content": "Body"})

        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)

    def test_post_form_removes_executable_html_but_keeps_editor_markup(self):
        form = PostForm(
            data={
                "title": "Safe HTML",
                "content": (
                    '<p>Hello <strong>there</strong></p>'
                    '<img src="https://example.com/photo.png" onerror="alert(1)">'
                    '<a href="javascript:alert(1)">bad link</a>'
                    '<script>alert(1)</script>'
                ),
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["content"],
            '<p>Hello <strong>there</strong></p>'
            '<img src="https://example.com/photo.png">'
            '<a>bad link</a>',
        )

    def test_weekly_challenge_post_requires_a_challenge_image(self):
        weekly_challenge = Tag.objects.create(title="Weekly Challenge")
        form = PostForm(
            data={
                "title": "My submission",
                "content": "I completed the challenge.",
                "tags": [weekly_challenge.pk],
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("challenge_image", form.errors)

    def test_weekly_challenge_post_accepts_a_challenge_image(self):
        weekly_challenge = Tag.objects.create(title="Weekly Challenge")
        image = SimpleUploadedFile(
            "proof.gif", b"GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;", content_type="image/gif"
        )
        form = PostForm(
            data={
                "title": "My submission",
                "content": "I completed the challenge.",
                "tags": [weekly_challenge.pk],
            },
            files={"challenge_image": image},
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_weekly_challenge_post_rejects_an_oversized_image(self):
        weekly_challenge = Tag.objects.create(title="Weekly Challenge")
        image = SimpleUploadedFile(
            "proof.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
            + (b"x" * (5 * 1024 * 1024)),
            content_type="image/gif",
        )
        form = PostForm(
            data={
                "title": "My submission",
                "content": "I completed the challenge.",
                "tags": [weekly_challenge.pk],
            },
            files={"challenge_image": image},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("challenge_image", form.errors)

    def test_vote_constraints_allow_only_one_valid_target_and_value(self):
        post = self.create_post()
        comment = Comment.objects.create(post=post, user=self.other_user, content="Reply")

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Vote.objects.create(user=self.author, value=1)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Vote.objects.create(user=self.author, post=post, comment=comment, value=1)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Vote.objects.create(user=self.author, post=post, value=0)

    def test_database_disallows_duplicate_votes_for_the_same_post(self):
        post = self.create_post()
        Vote.objects.create(user=self.author, post=post, value=1)

        with self.assertRaises(IntegrityError):
            Vote.objects.create(user=self.author, post=post, value=-1)


class FrontpageAndCreatePostTests(PostsTestCase):
    def test_frontpage_renders_post_list_and_api_configuration(self):
        response = self.client.get(reverse("frontpage"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/frontpage.html")
        self.assertContains(response, 'id="posts"')
        self.assertContains(response, reverse("api:get_posts_json"))
        self.assertContains(response, reverse("posts:create_post"))

    def test_create_post_requires_authentication(self):
        response = self.client.get(reverse("posts:create_post"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('posts:create_post')}",
            fetch_redirect_response=False,
        )

    def test_authenticated_user_can_view_create_form(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse("posts:create_post"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/create_form.html")
        self.assertIsInstance(response.context["form"], PostForm)

    def test_authenticated_user_can_create_a_tagged_post(self):
        tag = Tag.objects.create(title="giveaway")
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("posts:create_post"),
            {"title": "Free jars", "content": "Pick them up", "tags": [tag.pk]},
        )

        self.assertRedirects(response, reverse("frontpage"))
        post = Post.objects.get(title="Free jars")
        self.assertEqual(post.author, self.author)
        self.assertEqual(post.content, "Pick them up")
        self.assertQuerySetEqual(post.tags.all(), [tag])

    def test_invalid_post_submission_is_redisplayed_without_creating_post(self):
        self.client.force_login(self.author)
        response = self.client.post(reverse("posts:create_post"), {"title": "", "content": "Body"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/create_form.html")
        self.assertFormError(response.context["form"], "title", "This field is required.")
        self.assertEqual(Post.objects.count(), 0)


class UpdateAndDeletePostTests(PostsTestCase):
    def setUp(self):
        super().setUp()
        self.post = self.create_post(title="Original", content="Original content")
        self.update_url = reverse("posts:update_post", kwargs={"post_id": self.post.pk})
        self.delete_url = reverse("api:delete_post", kwargs={"post_id": self.post.pk})

    def test_author_can_update_a_post(self):
        self.client.force_login(self.author)

        response = self.client.post(self.update_url, {"title": "Updated", "content": "New content"})

        self.assertRedirects(response, reverse("posts:show_post", kwargs={"post_id": self.post.pk}))
        self.post.refresh_from_db()
        self.assertEqual((self.post.title, self.post.content, self.post.author), ("Updated", "New content", self.author))

    def test_other_user_cannot_update_a_post_without_permission(self):
        self.client.force_login(self.other_user)

        response = self.client.get(self.update_url)

        self.assertEqual(response.status_code, 403)

    def test_anonymous_delete_returns_login_details(self):
        response = self.client.post(self.delete_url)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["login_url"], reverse("login"))
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())

    def test_author_can_delete_a_post_via_api(self):
        self.client.force_login(self.author)

        response = self.client.post(self.delete_url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())

    def test_other_user_cannot_delete_a_post_without_permission(self):
        self.client.force_login(self.other_user)

        response = self.client.post(self.delete_url)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())

    def test_user_with_delete_post_permission_can_delete_another_users_post(self):
        permission = Permission.objects.get(codename="delete_post")
        self.other_user.user_permissions.add(permission)
        self.client.force_login(self.other_user)

        response = self.client.post(self.delete_url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())


class GetPostsJsonTests(PostsTestCase):
    def test_get_posts_json_includes_related_data_and_current_users_vote(self):
        older_post = self.create_post(title="Older")
        post = self.create_post(title="Newer")
        tag = Tag.objects.create(title="article")
        post.tags.add(tag)
        Comment.objects.create(post=post, user=self.other_user, content="One")
        Comment.objects.create(post=post, user=self.author, content="Two")
        Vote.objects.create(user=self.author, post=post, value=1)
        Vote.objects.create(user=self.other_user, post=post, value=-1)
        self.client.force_login(self.author)

        response = self.client.get(reverse("api:get_posts_json"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual([item["id"] for item in payload], [str(post.pk), str(older_post.pk)])
        item = payload[0]
        self.assertEqual(item["title"], "Newer")
        self.assertEqual(item["content"], "Post content")
        self.assertEqual(item["tags"], [{"id": str(tag.pk), "title": "article"}])
        self.assertEqual(item["vote_count"], 0)
        self.assertEqual(item["user_vote_value"], 1)
        self.assertEqual(item["comment_count"], 2)
        self.assertIsNotNone(item["created_at"])
        self.assertIsNotNone(item["updated_at"])

    def test_anonymous_get_posts_json_does_not_expose_a_user_vote(self):
        post = self.create_post()
        Vote.objects.create(user=self.author, post=post, value=1)

        response = self.client.get(reverse("api:get_posts_json"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["user_vote_value"], 0)

    def test_get_posts_json_only_allows_get_requests(self):
        response = self.client.post(reverse("api:get_posts_json"))

        self.assertEqual(response.status_code, 405)


class ShowPostAndGetPostJsonTests(PostsTestCase):
    def setUp(self):
        super().setUp()
        self.post = self.create_post(title="Repair cafe")

    def test_show_post_renders_comment_forms_for_the_requested_post(self):
        response = self.client.get(reverse("posts:show_post", kwargs={"post_id": self.post.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/show_post.html")
        self.assertEqual(response.context["post_id"], self.post.pk)
        self.assertIn("comment_form", response.context)
        self.assertIn("reply_comment_form", response.context)

    def test_get_post_json_includes_post_data_and_viewers_vote(self):
        Vote.objects.create(user=self.other_user, post=self.post, value=-1)
        self.client.force_login(self.other_user)

        response = self.client.get(
            reverse("api:get_post_json", kwargs={"post_id": self.post.pk})
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["id"], str(self.post.pk))
        self.assertEqual(data["username"], self.author.username)
        self.assertEqual(data["title"], "Repair cafe")
        self.assertEqual(data["user_vote_value"], -1)

    def test_get_post_json_returns_not_found_for_an_unknown_post(self):
        response = self.client.get(
            reverse("api:get_post_json", kwargs={"post_id": "00000000-0000-0000-0000-000000000001"})
        )

        self.assertEqual(response.status_code, 404)


class GetCommentsJsonTests(PostsTestCase):
    def setUp(self):
        super().setUp()
        self.post = self.create_post()
        self.url = reverse("api:get_comments_json", kwargs={"post_id": self.post.pk})

    def test_returns_nested_comments_with_recursive_reply_counts_and_votes(self):
        root = Comment.objects.create(post=self.post, user=self.author, content="Root")
        reply = Comment.objects.create(
            post=self.post, user=self.other_user, content="Reply", replies_to_comment=root
        )
        Comment.objects.create(
            post=self.post, user=self.author, content="Nested reply", replies_to_comment=reply
        )
        Vote.objects.create(user=self.other_user, comment=root, value=1)
        self.client.force_login(self.other_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        comments = response.json()["data"]
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["content"], "Root")
        self.assertEqual(comments[0]["vote_count"], 1)
        self.assertEqual(comments[0]["user_vote_value"], 1)
        self.assertEqual(comments[0]["reply_count"], 2)
        self.assertEqual(comments[0]["replies"][0]["content"], "Reply")
        self.assertEqual(comments[0]["replies"][0]["reply_count"], 1)

    def test_get_comments_only_allows_get_requests(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 405)


class VotePostTests(PostsTestCase):
    def setUp(self):
        super().setUp()
        self.post = self.create_post()
        self.url = reverse("api:vote_post", kwargs={"post_id": self.post.pk})

    def vote(self, value):
        return self.client.post(
            self.url,
            data=json.dumps({"vote_value": value}),
            content_type="application/json",
        )

    def test_anonymous_vote_returns_login_location(self):
        response = self.client.post(self.url, HTTP_ACCEPT="application/json")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["login_url"], reverse("login"))
        self.assertEqual(Vote.objects.count(), 0)

    def test_vote_requires_post_request(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)

    def test_vote_rejects_malformed_missing_or_invalid_values(self):
        self.client.force_login(self.other_user)
        malformed = self.client.post(self.url, data="{", content_type="application/json")
        missing = self.client.post(self.url, data="{}", content_type="application/json")
        invalid = self.vote(0)

        for response in (malformed, missing):
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["error"], "value is required")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["error"], "value must be 1 or -1")
        self.assertEqual(Vote.objects.count(), 0)

    def test_first_vote_creates_vote_and_returns_total(self):
        self.client.force_login(self.other_user)
        response = self.vote(1)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["vote_value"], 1)
        self.assertEqual(response.json()["vote_count"], 1)
        self.assertTrue(Vote.objects.filter(user=self.other_user, post=self.post, value=1).exists())

    def test_changing_vote_updates_existing_vote_and_total(self):
        Vote.objects.create(user=self.other_user, post=self.post, value=1)
        self.client.force_login(self.other_user)
        response = self.vote(-1)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["vote_value"], -1)
        self.assertEqual(response.json()["vote_count"], -1)
        self.assertEqual(Vote.objects.get(user=self.other_user, post=self.post).value, -1)

    def test_repeating_same_vote_toggles_vote_off(self):
        self.client.force_login(self.other_user)
        self.vote(1)
        response = self.vote(1)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["vote_value"], 0)
        self.assertEqual(response.json()["vote_count"], 0)
        self.assertFalse(Vote.objects.filter(user=self.other_user, post=self.post).exists())

    def test_authenticated_vote_for_missing_post_returns_not_found(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse("api:vote_post", kwargs={"post_id": "00000000-0000-0000-0000-000000000001"}),
            data=json.dumps({"vote_value": 1}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)


class CreateCommentTests(PostsTestCase):
    def setUp(self):
        super().setUp()
        self.post = self.create_post()
        self.url = reverse("api:create_comment", kwargs={"post_id": self.post.pk})

    def test_creating_a_reply_sets_its_parent_comment(self):
        parent = Comment.objects.create(post=self.post, user=self.author, content="Parent")
        self.client.force_login(self.other_user)

        response = self.client.post(self.url, {
            "content": "This is a reply",
            "replies_to_comment": parent.pk,
        })

        self.assertEqual(response.status_code, 201)
        reply = Comment.objects.get(content="This is a reply")
        self.assertEqual(reply.replies_to_comment, parent)

    def test_anonymous_user_cannot_create_a_comment(self):
        response = self.client.post(self.url, {"content": "Please let me in"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["login_url"], reverse("login"))
        self.assertEqual(Comment.objects.count(), 0)

    def test_invalid_comment_submission_returns_form_errors(self):
        self.client.force_login(self.other_user)
        response = self.client.post(self.url, {"content": ""})

        self.assertEqual(response.status_code, 400)
        self.assertIn("content", response.json()["errors"])
        self.assertEqual(Comment.objects.count(), 0)

    def test_create_comment_only_allows_post_requests(self):
        self.client.force_login(self.other_user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)

    def test_cannot_reply_to_a_comment_from_another_post(self):
        other_post = self.create_post(title="Other")
        parent = Comment.objects.create(post=other_post, user=self.author, content="Elsewhere")
        self.client.force_login(self.other_user)

        response = self.client.post(self.url, {
            "content": "This should not be created",
            "replies_to_comment": parent.pk,
        })

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Comment.objects.filter(content="This should not be created").exists())


class DeleteCommentTests(PostsTestCase):
    def setUp(self):
        super().setUp()
        self.post = self.create_post()
        self.comment = Comment.objects.create(post=self.post, user=self.author, content="Remove me")
        self.url = reverse("api:delete_comment", kwargs={"comment_id": self.comment.pk})

    def test_author_can_delete_a_comment_via_api(self):
        self.client.force_login(self.author)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_deleted)
        self.assertEqual(self.comment.content, "✖ This comment has been deleted")

    def test_other_user_cannot_delete_a_comment_without_permission(self):
        self.client.force_login(self.other_user)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_user_with_delete_comment_permission_can_delete_another_users_comment(self):
        permission = Permission.objects.get(codename="delete_comment")
        self.other_user.user_permissions.add(permission)
        self.client.force_login(self.other_user)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_deleted)

    def test_soft_deleting_a_comment_preserves_its_replies_and_masks_its_author(self):
        reply = Comment.objects.create(
            post=self.post, user=self.other_user, content="Still here", replies_to_comment=self.comment
        )
        self.client.force_login(self.author)

        self.client.post(self.url)
        response = self.client.get(
            reverse("api:get_comments_json", kwargs={"post_id": self.post.pk})
        )

        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_deleted)
        self.assertTrue(Comment.objects.filter(pk=reply.pk).exists())
        deleted_comment = response.json()["data"][0]
        self.assertEqual(deleted_comment["username"], "[deleted comment]")
        self.assertEqual(deleted_comment["avatar_url"], "")
        self.assertIsNone(deleted_comment["user_id"])
        self.assertFalse(deleted_comment["can_delete"])
        self.assertEqual(deleted_comment["replies"][0]["id"], str(reply.pk))


class VoteCommentTests(PostsTestCase):
    def setUp(self):
        super().setUp()
        self.post = self.create_post()
        self.comment = Comment.objects.create(post=self.post, user=self.author, content="Helpful")
        self.url = reverse("api:vote_comment", kwargs={"comment_id": self.comment.pk})

    def vote(self, value):
        return self.client.post(
            self.url, data=json.dumps({"vote_value": value}), content_type="application/json"
        )

    def test_anonymous_user_cannot_vote_on_a_comment(self):
        response = self.vote(1)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["login_url"], reverse("login"))

    def test_comment_vote_creates_changes_and_toggles_a_vote(self):
        self.client.force_login(self.other_user)

        created = self.vote(1)
        changed = self.vote(-1)
        toggled_off = self.vote(-1)

        self.assertEqual((created.json()["vote_value"], created.json()["vote_count"]), (1, 1))
        self.assertEqual((changed.json()["vote_value"], changed.json()["vote_count"]), (-1, -1))
        self.assertEqual((toggled_off.json()["vote_value"], toggled_off.json()["vote_count"]), (0, 0))
        self.assertFalse(Vote.objects.filter(user=self.other_user, comment=self.comment).exists())

    def test_comment_vote_rejects_invalid_input_and_non_post_requests(self):
        self.client.force_login(self.other_user)
        invalid = self.vote(0)
        wrong_method = self.client.get(self.url)

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["error"], "value must be 1 or -1")
        self.assertEqual(wrong_method.status_code, 405)
