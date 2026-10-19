from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from users.models import User
from .models import Post, Vote


class UpvotePostTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="voter", password="test-password", bio=""
        )
        self.post = Post.objects.create(
            author=self.user, title="A post", content="Post content"
        )
        self.url = reverse("api:vote_post", kwargs={"post_id": self.post.pk})

    def test_anonymous_vote_returns_login_location(self):
        response = self.client.post(self.url, HTTP_ACCEPT="application/json")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["login_url"], reverse("login"))
        self.assertEqual(Vote.objects.count(), 0)

    def test_repeated_upvotes_toggle_the_vote_off(self):
        self.client.force_login(self.user)

        first_response = self.client.post(self.url)
        second_response = self.client.post(self.url)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(Vote.objects.filter(user=self.user, post=self.post).count(), 0)
        self.assertEqual(second_response.json()["vote_value"], 0)
        self.assertEqual(second_response.json()["vote_count"], 0)

    def test_database_disallows_two_votes_for_the_same_post(self):
        Vote.objects.create(user=self.user, post=self.post, value=1)

        with self.assertRaises(IntegrityError):
            Vote.objects.create(user=self.user, post=self.post, value=1)
