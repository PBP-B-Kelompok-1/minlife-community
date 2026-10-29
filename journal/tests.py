import json
from datetime import date

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import JournalEntry

User = get_user_model()


def entry_url(iso):
    return reverse("journal:entry", args=[iso])


class JournalTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pass12345")
        self.bob = User.objects.create_user("bob", password="pass12345")
        self.client.login(username="alice", password="pass12345")

    def save(self, iso, content="<p>Halo hari ini</p>", visibility="private"):
        return self.client.post(
            entry_url(iso),
            data=json.dumps({"content": content, "visibility": visibility}),
            content_type="application/json",
        )

    def test_one_entry_per_user_per_date(self):
        JournalEntry.objects.create(user=self.alice, date=date(2026, 10, 22), content="a")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                JournalEntry.objects.create(user=self.alice, date=date(2026, 10, 22), content="b")

    def test_same_date_for_different_users_is_fine(self):
        JournalEntry.objects.create(user=self.alice, date=date(2026, 10, 22), content="a")
        JournalEntry.objects.create(user=self.bob, date=date(2026, 10, 22), content="b")
        self.assertEqual(JournalEntry.objects.count(), 2)

    def test_calendar_needs_login(self):
        self.client.logout()
        response = self.client.get(reverse("journal:show_journal"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response["Location"])

    def test_calendar_only_shows_own_entries(self):
        JournalEntry.objects.create(user=self.alice, date=date(2026, 10, 22), content="<p>punya alice</p>")
        JournalEntry.objects.create(user=self.bob, date=date(2026, 10, 23), content="<p>punya bob</p>")
        response = self.client.get(reverse("journal:show_journal"), {"year": 2026, "month": 10})
        self.assertEqual(response.status_code, 200)

        cells = {c["iso"]: c for week in response.context["weeks"] for c in week}
        self.assertTrue(cells["2026-10-22"]["has_entry"])
        self.assertFalse(cells["2026-10-23"]["has_entry"])
        self.assertEqual(list(response.context["entries"]), ["2026-10-22"])
        self.assertEqual(response.context["entries"]["2026-10-22"]["snippet"], "punya alice")

    def test_calendar_grid_for_october_2026(self):
        response = self.client.get(reverse("journal:show_journal"), {"year": 2026, "month": 10})
        weeks = response.context["weeks"]
        self.assertEqual(len(weeks), 5)
        self.assertEqual(weeks[0][0]["iso"], "2026-09-28")
        self.assertEqual(weeks[-1][-1]["iso"], "2026-11-01")

    def test_calendar_only_loads_visible_range(self):
        JournalEntry.objects.create(user=self.alice, date=date(2026, 10, 22), content="a")
        JournalEntry.objects.create(user=self.alice, date=date(2026, 3, 1), content="b")
        response = self.client.get(reverse("journal:show_journal"), {"year": 2026, "month": 10})
        self.assertEqual(list(response.context["entries"]), ["2026-10-22"])

    def test_calendar_bad_params_fall_back_to_today(self):
        response = self.client.get(reverse("journal:show_journal"), {"year": "abc", "month": "99"})
        self.assertEqual(response.status_code, 200)

    def test_create_read_update_delete(self):
        iso = "2026-10-22"

        self.assertEqual(self.save(iso, "<p>Pertama</p>").status_code, 201)
        data = self.client.get(entry_url(iso)).json()
        self.assertTrue(data["exists"])
        self.assertEqual(data["content"], "<p>Pertama</p>")

        self.assertEqual(self.save(iso, "<p>Diubah</p>", "public").status_code, 200)
        self.assertEqual(JournalEntry.objects.filter(user=self.alice).count(), 1)
        entry = JournalEntry.objects.get(user=self.alice)
        self.assertEqual(entry.visibility, "public")
        self.assertEqual(entry.content, "<p>Diubah</p>")

        self.assertEqual(self.client.delete(entry_url(iso)).status_code, 200)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(self.client.delete(entry_url(iso)).status_code, 404)

    def test_read_empty_date(self):
        data = self.client.get(entry_url("2026-10-25")).json()
        self.assertFalse(data["exists"])
        self.assertEqual(data["content"], "")

    def test_future_dates_are_allowed(self):
        self.assertEqual(self.save("2030-01-01").status_code, 201)

    def test_bad_input_is_rejected(self):
        self.assertEqual(self.save("2026-10-22", "<p><br></p>").status_code, 400)
        self.assertEqual(self.save("2026-10-22", visibility="friends").status_code, 400)
        bad_json = self.client.post(entry_url("2026-10-22"), data="bukan json", content_type="application/json")
        self.assertEqual(bad_json.status_code, 400)
        self.assertEqual(JournalEntry.objects.count(), 0)

    def test_bad_date_is_404(self):
        self.assertEqual(self.client.get(entry_url("2026-13-40")).status_code, 404)
        self.assertEqual(self.client.get(entry_url("kemarin")).status_code, 404)

    def test_content_is_sanitized(self):
        self.save("2026-10-22", '<p onclick="x()">Halo</p><script>alert(1)</script><img src=x onerror=alert(1)>')
        stored = JournalEntry.objects.get(user=self.alice).content
        for bad in ("<script", "onclick", "<img", "onerror"):
            self.assertNotIn(bad, stored)
        self.assertIn("Halo", stored)

    def test_cannot_touch_other_users_entry(self):
        JournalEntry.objects.create(user=self.bob, date=date(2026, 10, 22), content="<p>rahasia bob</p>")

        data = self.client.get(entry_url("2026-10-22")).json()
        self.assertFalse(data["exists"])
        self.assertNotIn("rahasia", json.dumps(data))

        self.save("2026-10-22", "<p>punya alice</p>")
        self.assertEqual(JournalEntry.objects.get(user=self.bob).content, "<p>rahasia bob</p>")
        self.assertEqual(self.client.delete(entry_url("2026-10-22")).status_code, 200)
        self.assertTrue(JournalEntry.objects.filter(user=self.bob).exists())

    def test_entry_endpoint_needs_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(entry_url("2026-10-22")).status_code, 401)
        self.assertEqual(self.save("2026-10-22").status_code, 401)
