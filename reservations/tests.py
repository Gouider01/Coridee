"""Module 4 - tests. Run:  python manage.py test reservations"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from trips.models import Trip

from .models import Reservation, ReservationStatus
from .services import (
    ReservationError,
    accept_request,
    book_seats,
    cancel_booking,
    refuse_request,
    update_seats,
)

User = get_user_model()


def make_user(email, user_type="PASSENGER", **extra):
    return User.objects.create_user(
        email=email, password="Pass12345!", first_name=email.split("@")[0].capitalize(),
        last_name="Test", user_type=user_type, **extra,
    )


class BaseCase(TestCase):
    def setUp(self):
        self.driver = make_user("driver@test.tn", "DRIVER")
        self.sami = make_user("sami@test.tn")
        self.leila = make_user("leila@test.tn")
        self.admin = make_user("admin@test.tn", "ADMINISTRATOR", is_staff=True)
        self.trip = Trip.objects.create(
            driver=self.driver, departure_city="Tunis", arrival_city="Sousse",
            departure_datetime=timezone.now() + timedelta(days=2), seats=3, price_per_seat="12.50",
        )

    def refresh(self):
        self.trip.refresh_from_db()
        return self.trip


class BookingRules(BaseCase):
    def test_success_case_pending_and_seats_drop(self):
        """Acceptance criteria 4.1, case 1."""
        r = book_seats(self.sami, self.trip.pk, 1)
        self.assertEqual(r.status, ReservationStatus.PENDING)
        self.assertEqual(self.refresh().remaining_seats, 2)

    def test_failure_case_trip_full(self):
        """Acceptance criteria 4.1, case 2."""
        book_seats(self.sami, self.trip.pk, 3)
        self.assertEqual(self.refresh().status, "FULL")
        with self.assertRaisesMessage(ReservationError, "No seats available"):
            book_seats(self.leila, self.trip.pk, 1)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_cannot_book_more_than_left(self):
        with self.assertRaises(ReservationError):
            book_seats(self.sami, self.trip.pk, 4)

    def test_cannot_book_zero_seats(self):
        with self.assertRaises(ReservationError):
            book_seats(self.sami, self.trip.pk, 0)

    def test_cannot_book_own_trip(self):
        with self.assertRaisesMessage(ReservationError, "own trip"):
            book_seats(self.driver, self.trip.pk, 1)

    def test_admin_cannot_book(self):
        with self.assertRaises(ReservationError):
            book_seats(self.admin, self.trip.pk, 1)

    def test_cannot_book_past_or_cancelled_trip(self):
        self.trip.departure_datetime = timezone.now() - timedelta(hours=1)
        self.trip.save()
        with self.assertRaisesMessage(ReservationError, "already left"):
            book_seats(self.sami, self.trip.pk, 1)
        self.trip.departure_datetime = timezone.now() + timedelta(days=1)
        self.trip.status = "CANCELLED"
        self.trip.save()
        with self.assertRaisesMessage(ReservationError, "cancelled"):
            book_seats(self.sami, self.trip.pk, 1)

    def test_one_open_booking_per_trip(self):
        book_seats(self.sami, self.trip.pk, 1)
        with self.assertRaisesMessage(ReservationError, "already have a booking"):
            book_seats(self.sami, self.trip.pk, 1)


class LifeCycle(BaseCase):
    def test_update_seats_adjusts_trip(self):
        r = book_seats(self.sami, self.trip.pk, 1)
        update_seats(r.pk, self.sami, 3)
        self.assertEqual(self.refresh().remaining_seats, 0)
        update_seats(r.pk, self.sami, 2)
        self.assertEqual(self.refresh().remaining_seats, 1)
        self.assertEqual(self.refresh().status, "OPEN")

    def test_cannot_update_someone_elses_or_answered_request(self):
        r = book_seats(self.sami, self.trip.pk, 1)
        with self.assertRaises(ReservationError):
            update_seats(r.pk, self.leila, 2)
        accept_request(r.pk, self.driver)
        with self.assertRaises(ReservationError):
            update_seats(r.pk, self.sami, 2)

    def test_accept_creates_ticket_code(self):
        r = book_seats(self.sami, self.trip.pk, 1)
        r = accept_request(r.pk, self.driver)
        self.assertEqual(r.status, ReservationStatus.ACCEPTED)
        self.assertEqual(len(r.ticket_code), 8)

    def test_only_trip_driver_decides(self):
        r = book_seats(self.sami, self.trip.pk, 1)
        other = make_user("other@test.tn", "DRIVER")
        with self.assertRaises(ReservationError):
            accept_request(r.pk, other)
        with self.assertRaises(ReservationError):
            accept_request(r.pk, self.sami)

    def test_refuse_releases_seats_and_reopens_full_trip(self):
        r = book_seats(self.sami, self.trip.pk, 3)
        self.assertEqual(self.refresh().status, "FULL")
        refuse_request(r.pk, self.driver)
        self.assertEqual(self.refresh().remaining_seats, 3)
        self.assertEqual(self.trip.status, "OPEN")
        with self.assertRaises(ReservationError):  # cannot answer twice
            accept_request(r.pk, self.driver)

    def test_cancel_releases_seats(self):
        r = book_seats(self.sami, self.trip.pk, 2)
        cancel_booking(r.pk, self.sami)
        r.refresh_from_db()
        self.assertEqual(r.status, ReservationStatus.CANCELLED)
        self.assertEqual(self.refresh().remaining_seats, 3)

    def test_cancel_refused_less_than_2_hours_before_departure(self):
        self.trip.departure_datetime = timezone.now() + timedelta(hours=1)
        self.trip.save()
        r = book_seats(self.sami, self.trip.pk, 1)
        with self.assertRaisesMessage(ReservationError, "2 hours"):
            cancel_booking(r.pk, self.sami)

    def test_cancel_by_another_passenger_refused(self):
        r = book_seats(self.sami, self.trip.pk, 1)
        with self.assertRaises(ReservationError):
            cancel_booking(r.pk, self.leila)

    def test_can_rebook_after_cancelling(self):
        r = book_seats(self.sami, self.trip.pk, 1)
        cancel_booking(r.pk, self.sami)
        self.assertEqual(book_seats(self.sami, self.trip.pk, 1).status, ReservationStatus.PENDING)

    def test_overdue_pending_expires(self):
        r = book_seats(self.sami, self.trip.pk, 1)
        Trip.objects.filter(pk=self.trip.pk).update(departure_datetime=timezone.now() - timedelta(hours=1))
        Reservation.objects.expire_overdue()
        r.refresh_from_db()
        self.assertEqual(r.status, ReservationStatus.EXPIRED)


class Pages(BaseCase):
    def login(self, user):
        self.client.force_login(user)

    def test_anonymous_redirected_to_login(self):
        for name in ("index", "available", "requests", "manage"):
            resp = self.client.get(reverse(f"reservations:{name}"))
            self.assertEqual(resp.status_code, 302, name)

    def test_book_form_shows_error_and_creates_nothing(self):
        self.login(self.sami)
        resp = self.client.post(reverse("reservations:book", args=[self.trip.pk]), {"seats": 9})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "at most 8")
        resp = self.client.post(reverse("reservations:book", args=[self.trip.pk]), {"seats": 5})
        self.assertContains(resp, "Only 3 seats left")
        self.assertEqual(Reservation.objects.count(), 0)

    def test_full_flow_through_the_pages(self):
        self.login(self.sami)
        resp = self.client.post(reverse("reservations:book", args=[self.trip.pk]), {"seats": 2}, follow=True)
        self.assertContains(resp, "Request sent")
        r = Reservation.objects.get()
        self.assertContains(self.client.get(reverse("reservations:index")), "Tunis")
        self.assertEqual(self.client.get(reverse("reservations:edit", args=[r.pk])).status_code, 200)

        self.login(self.driver)
        self.assertContains(self.client.get(reverse("reservations:requests")), "Accept")
        self.client.post(reverse("reservations:accept", args=[r.pk]))
        r.refresh_from_db()
        self.assertEqual(r.status, ReservationStatus.ACCEPTED)
        self.assertContains(self.client.get(reverse("reservations:detail", args=[r.pk])), r.ticket_code)

        self.login(self.sami)
        self.assertContains(self.client.get(reverse("reservations:cancel", args=[r.pk])), "Cancel booking")
        self.client.post(reverse("reservations:cancel", args=[r.pk]))
        r.refresh_from_db()
        self.assertEqual(r.status, ReservationStatus.CANCELLED)

    def test_permissions(self):
        r = book_seats(self.sami, self.trip.pk, 1)
        self.login(self.leila)                     # stranger
        self.assertEqual(self.client.get(reverse("reservations:detail", args=[r.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("reservations:manage")).status_code, 403)
        self.assertEqual(self.client.get(reverse("reservations:requests")).status_code, 403)  # not a driver
        self.assertEqual(self.client.post(reverse("reservations:cancel", args=[r.pk])).status_code, 404)
        self.login(self.admin)
        # Admins have no personal bookings: "My bookings" redirects to the full list.
        self.assertRedirects(self.client.get(reverse("reservations:index")), reverse("reservations:manage"))
        self.assertEqual(self.client.get(reverse("reservations:manage")).status_code, 200)

    def test_admin_lists_and_deletes(self):
        r = book_seats(self.sami, self.trip.pk, 2)
        self.login(self.admin)
        self.assertContains(self.client.get(reverse("reservations:manage") + "?q=sousse"), "Sami")
        self.assertNotContains(self.client.get(reverse("reservations:manage") + "?q=bizerte"), "Sami Test")
        self.client.post(reverse("reservations:manage_delete", args=[r.pk]))
        self.assertEqual(Reservation.objects.count(), 0)
        self.assertEqual(self.refresh().remaining_seats, 3)

    def test_phone_hidden_until_accepted(self):
        self.driver.phone_number = "22123456"
        self.driver.save()
        r = book_seats(self.sami, self.trip.pk, 1)
        self.login(self.sami)
        self.assertNotContains(self.client.get(reverse("reservations:detail", args=[r.pk])), "22 123 456")
        accept_request(r.pk, self.driver)
        self.assertContains(self.client.get(reverse("reservations:detail", args=[r.pk])), "22 123 456")


class ChatIntegration(TestCase):
    """Module 4 <-> Module 5 hooks: accept opens a chat, refuse/cancel closes it."""

    def setUp(self):
        from datetime import timedelta
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from trips.models import Trip
        U = get_user_model()
        self.driver = U.objects.create_user(email="d@x.tn", password="Pass12345!", first_name="D", last_name="R",
                                            user_type="DRIVER", date_of_birth="1990-01-01")
        self.pax = U.objects.create_user(email="p@x.tn", password="Pass12345!", first_name="P", last_name="A",
                                         user_type="PASSENGER", date_of_birth="1995-01-01")
        self.trip = Trip.objects.create(driver=self.driver, departure_city="Tunis", arrival_city="Sousse",
                                        departure_datetime=timezone.now() + timedelta(days=2),
                                        seats=3, price_per_seat="10.00")

    def test_accept_opens_and_refuse_closes(self):
        from communication.models import Conversation
        r = book_seats(self.pax, self.trip.pk, 1)
        self.assertFalse(Conversation.objects.exists())
        accept_request(r.pk, self.driver)
        conv = Conversation.objects.get(reservation_reference=str(r.pk))
        self.assertEqual(conv.trip_reference, str(self.trip.pk))
        from reservations.services import cancel_booking
        cancel_booking(r.pk, self.pax)
        conv.refresh_from_db()
        self.assertIsNotNone(conv.closed_at)
        self.assertEqual(conv.close_reason, "CANCELLED")
