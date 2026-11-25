"""Module 5 integration tests: chat and reviews use real Module 1 users."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CommunicationParticipant, Conversation, Message
from .services import mark_trip_completed, open_conversation

User = get_user_model()


def make_user(email, first, last, **kw):
    return User.objects.create_user(email=email, password="pw-12345-xyz", first_name=first, last_name=last, **kw)


class IntegrationTests(TestCase):
    def setUp(self):
        self.passenger = make_user("p@example.com", "Sara", "Ben Ali")
        self.driver = make_user("d@example.com", "Leila", "Khemiri", user_type=User.UserType.DRIVER)
        self.outsider = make_user("o@example.com", "Omar", "Trabelsi")
        self.conv = open_conversation(
            reservation_reference="R1", trip_reference="1",
            passenger=self.passenger, driver=self.driver,
            departure_at=timezone.now() + timedelta(days=1),
        )

    def test_visitors_are_sent_to_login(self):
        for name in ("communication:index", "communication:conversation_list"):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302)
            self.assertIn(reverse("users:login"), r["Location"])

    def test_participants_are_real_users_and_names_come_from_profile(self):
        p = CommunicationParticipant.objects.get(user=self.passenger)
        self.assertEqual(p.display_label, "Sara Ben Ali")
        self.passenger.anonymize()
        p.refresh_from_db()
        self.assertEqual(p.display_label, "Deleted user")
        self.assertNotIn("example.com", p.display_label)

    def test_chat_flow(self):
        self.client.force_login(self.passenger)
        self.assertContains(self.client.get(reverse("communication:conversation_list")), "Leila Khemiri")
        url = reverse("communication:conversation_detail", args=[self.conv.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        r = self.client.post(reverse("communication:send_message", args=[self.conv.pk]), {"content": "Hello"})
        self.assertIn(r.status_code, (200, 201, 302))
        self.assertEqual(Message.objects.get().sender, self.passenger)
        self.client.force_login(self.driver)
        self.assertContains(self.client.get(url), "Hello")

    def test_outsider_is_refused(self):
        self.client.force_login(self.outsider)
        r = self.client.get(reverse("communication:conversation_detail", args=[self.conv.pk]))
        self.assertEqual(r.status_code, 403)

    def test_invite_join_needs_login_and_group_works(self):
        group_owner = self.client
        group_owner.force_login(self.passenger)
        group_owner.post(reverse("communication:create_conversation"), {"chat_type": "GROUP"})
        group = Conversation.objects.get(chat_type="GROUP")
        join = reverse("communication:join_conversation", args=[group.invite_code])
        from django.test import Client
        anon = Client()
        self.assertEqual(anon.get(join).status_code, 302)
        other = Client(); other.force_login(self.outsider)
        self.assertEqual(other.post(join).status_code, 302)
        self.assertTrue(group.includes(CommunicationParticipant.objects.get(user=self.outsider)))

    def test_reviews_after_completed_trip(self):
        self.client.force_login(self.passenger)
        url = reverse("communication:review_create", args=["1", self.driver.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        mark_trip_completed("1")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {"rating": 5, "comment": "Great"})
        page = self.client.get(reverse("communication:user_reviews", args=[self.driver.pk]))
        self.assertContains(page, "Sara Ben Ali")
        self.assertNotContains(page, "d@example.com")

    def test_admin_pages_staff_only(self):
        self.client.force_login(self.passenger)
        self.assertEqual(self.client.get(reverse("communication:admin_review_list")).status_code, 403)
        admin = User.objects.create_superuser(email="a@example.com", password="pw-12345-xyz", first_name="Ad", last_name="Min")
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("communication:admin_review_list")).status_code, 200)
