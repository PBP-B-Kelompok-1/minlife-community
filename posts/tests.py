import json

from django.db import IntegrityError, transaction
from django.core.files.uploadedfile import SimpleUploadedFile
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
