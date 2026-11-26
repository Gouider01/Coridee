"""Module 3 - tests.  Run:  uv run manage.py test trips"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from communication.models import Conversation
from reservations.models import Reservation, ReservationStatus
from reservations.services import accept_request, book_seats
from vehicles.models import Vehicle

from .forms import TripForm, stop_formset
from .models import Stop, Trip, TripStatus, is_valid_city, normalize_city
from .services import TripError, cancel_trip, complete_trip, delete_trip

User = get_user_model()


def make_user(email, user_type="PASSENGER", **extra):
    return User.objects.create_user(
        email=email, password="Pass12345!", first_name=email.split("@")[0].capitalize(),
        last_name="Test", user_type=user_type, **extra)


def make_vehicle(owner, plate="123 TU 4567", seats=4, status=Vehicle.VehicleStatus.ACCEPTED):
    return Vehicle.objects.create(owner=owner, brand="Peugeot", model="208", color="White",
                                  plate_number=plate, year=2020, seats=seats, status=status)


def local(dt):
    return timezone.localtime(dt).strftime("%Y-%m-%dT%H:%M")


def future(days=2, hours=0):
    return (timezone.now() + timedelta(days=days, hours=hours)).replace(second=0, microsecond=0)


def make_trip(driver, vehicle=None, **kw):
    data = dict(departure_city="Tunis", arrival_city="Sousse", departure_datetime=future(),
                seats=3, price_per_seat="12.50")
    data.update(kw)
    return Trip.objects.create(driver=driver, vehicle=vehicle, **data)


class Base(TestCase):
    def setUp(self):
        self.driver = make_user("driver@test.tn", "DRIVER")
        self.vehicle = make_vehicle(self.driver)
        self.other_driver = make_user("other@test.tn", "DRIVER")
        self.other_vehicle = make_vehicle(self.other_driver, plate="456 TU 7890")
        self.sami = make_user("sami@test.tn")
        self.nour = make_user("nour@test.tn")
        self.admin = make_user("admin@test.tn", "ADMINISTRATOR", is_staff=True)

    def login(self, user):
        self.client.force_login(user)

    def payload(self, **over):
        data = {
            "vehicle": self.vehicle.pk, "departure_city": "tunis", "arrival_city": "sfax",
            "departure_datetime": local(future(3)), "seats": 3, "price_per_seat": "15.00",
            "notes": "Meeting at the station",
            "stops-TOTAL_FORMS": 3, "stops-INITIAL_FORMS": 0,
            "stops-MIN_NUM_FORMS": 0, "stops-MAX_NUM_FORMS": 5,
            "stops-0-city": "", "stops-1-city": "", "stops-2-city": "",
        }
        data.update(over)
        return data


class CityTests(TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_city("  sidi   bou said "), "Sidi Bou Said")
        self.assertEqual(normalize_city("HAMMAM-LIF"), "Hammam-Lif")
        self.assertEqual(normalize_city("béja"), "Béja")

    def test_validity(self):
        for good in ("Tunis", "Le Kef", "Hammam-Lif", "M'saken", "Béja"):
            self.assertTrue(is_valid_city(normalize_city(good)), good)
        for bad in ("", "A", "Tunis 2", "12345", "Tunis_", "<script>"):
            self.assertFalse(is_valid_city(bad), bad)


class ModelTests(Base):
    def test_remaining_seats_default_to_seats(self):
        self.assertEqual(make_trip(self.driver, seats=3).remaining_seats, 3)

    def test_route_cities_and_serves(self):
        trip = make_trip(self.driver)
        Stop.objects.create(trip=trip, city="Hammamet", order=1)
        Stop.objects.create(trip=trip, city="Enfidha", order=2)
        self.assertEqual(trip.route_cities(), ["Tunis", "Hammamet", "Enfidha", "Sousse"])
        self.assertTrue(trip.serves("tunis", "sousse"))
        self.assertTrue(trip.serves("hammamet", "sousse"))
        self.assertTrue(trip.serves("tunis", "enfidha"))
        self.assertFalse(trip.serves("sousse", "tunis"))
        self.assertFalse(trip.serves("enfidha", "hammamet"))
        self.assertFalse(trip.serves("sousse"))
        self.assertTrue(trip.serves("", "sousse"))
        self.assertFalse(trip.serves("Sfax"))

    def test_bookable_queryset(self):
        ok = make_trip(self.driver)
        make_trip(self.driver, departure_datetime=future(3), status=TripStatus.CANCELLED)
        make_trip(self.driver, departure_datetime=future(4), status=TripStatus.FULL, remaining_seats=0)
        make_trip(self.driver, departure_datetime=timezone.now() - timedelta(hours=1))
        self.assertEqual(list(Trip.objects.bookable()), [ok])


class AccessTests(Base):
    def test_anonymous_redirected_to_login(self):
        for name in ("trips:index", "trips:create", "trips:mine"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn("/users/login", response["Location"])

    def test_passenger_cannot_publish(self):
        self.login(self.sami)
        for name in ("trips:create", "trips:mine"):
            response = self.client.get(reverse(name))
            self.assertRedirects(response, reverse("vehicles:index"), fetch_redirect_response=False)

    def test_driver_without_validated_vehicle_cannot_publish(self):
        lonely = make_user("lonely@test.tn", "DRIVER")
        make_vehicle(lonely, plate="999 TU 1111", status=Vehicle.VehicleStatus.PENDING)
        self.login(lonely)
        response = self.client.get(reverse("trips:create"))
        self.assertRedirects(response, reverse("vehicles:index"), fetch_redirect_response=False)

    def test_admin_cannot_publish_and_is_sent_to_manage(self):
        self.login(self.admin)
        self.assertEqual(self.client.get(reverse("trips:create")).status_code, 403)
        self.assertRedirects(self.client.get(reverse("trips:index")), reverse("trips:manage"),
                             fetch_redirect_response=False)

    def test_manage_is_admin_only(self):
        trip = make_trip(self.driver)
        for user in (self.sami, self.driver):
            self.login(user)
            self.assertEqual(self.client.get(reverse("trips:manage")).status_code, 403)
            self.assertEqual(self.client.post(reverse("trips:manage_delete", args=[trip.pk])).status_code, 403)
        self.assertTrue(Trip.objects.filter(pk=trip.pk).exists())


class CreateTests(Base):
    def setUp(self):
        super().setUp()
        self.login(self.driver)
        self.url = reverse("trips:create")

    def test_form_renders(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Publish a trip")
        self.assertContains(response, 'id="tn-cities"')

    def test_create_with_stops(self):
        data = self.payload(**{"stops-0-city": "hammamet", "stops-2-city": "  el   jem "})
        response = self.client.post(self.url, data)
        trip = Trip.objects.get(departure_city="Tunis")
        self.assertRedirects(response, reverse("trips:detail", args=[trip.pk]))
        self.assertEqual((trip.arrival_city, trip.driver, trip.vehicle), ("Sfax", self.driver, self.vehicle))
        self.assertEqual((trip.status, trip.seats, trip.remaining_seats), ("OPEN", 3, 3))
        self.assertEqual([(s.city, s.order) for s in trip.stops.all()], [("Hammamet", 1), ("El Jem", 2)])

    def assertRejected(self, field, **over):
        count = Trip.objects.count()
        response = self.client.post(self.url, self.payload(**over))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Trip.objects.count(), count)
        self.assertTrue(response.context["form"].errors.get(field), response.context["form"].errors)
        return response

    def test_departure_must_be_in_future(self):
        self.assertRejected("departure_datetime", departure_datetime=local(timezone.now() - timedelta(hours=1)))

    def test_departure_not_too_far(self):
        self.assertRejected("departure_datetime", departure_datetime=local(future(400)))

    def test_departure_required_and_valid(self):
        self.assertRejected("departure_datetime", departure_datetime="")
        self.assertRejected("departure_datetime", departure_datetime="not a date")

    def test_seats_cannot_exceed_vehicle(self):
        small = make_vehicle(self.driver, plate="321 TU 1234", seats=2)
        response = self.assertRejected("seats", vehicle=small.pk, seats=3)
        self.assertIn("2 passenger seats", response.context["form"].errors["seats"][0])

    def test_seats_bounds(self):
        self.assertRejected("seats", seats=0)
        self.assertRejected("seats", seats=9)
        self.assertRejected("seats", seats="abc")

    def test_cities_must_differ(self):
        response = self.assertRejected("arrival_city", departure_city="Tunis", arrival_city=" TUNIS ")
        self.assertIn("different cities", response.context["form"].errors["arrival_city"][0])

    def test_city_must_be_valid(self):
        self.assertRejected("departure_city", departure_city="Tunis 2")
        self.assertRejected("arrival_city", arrival_city="")

    def test_price_must_be_positive(self):
        for bad in ("0", "-5", "0.00"):
            self.assertRejected("price_per_seat", price_per_seat=bad)
        self.assertRejected("price_per_seat", price_per_seat="501")
        self.assertRejected("price_per_seat", price_per_seat="abc")
        self.assertRejected("price_per_seat", price_per_seat="")

    def test_vehicle_must_be_mine_and_validated(self):
        self.assertRejected("vehicle", vehicle=self.other_vehicle.pk)
        pending = make_vehicle(self.driver, plate="777 TU 1000", status=Vehicle.VehicleStatus.PENDING)
        self.assertRejected("vehicle", vehicle=pending.pk)
        self.assertRejected("vehicle", vehicle="")

    def test_same_departure_time_refused(self):
        make_trip(self.driver, self.vehicle, departure_datetime=future(3))
        self.assertRejected("departure_datetime", departure_datetime=local(future(3)))

    def test_notes_limited(self):
        self.assertRejected("notes", notes="x" * 301)

    def test_stop_validation(self):
        def post(**over):
            response = self.client.post(self.url, self.payload(**over))
            self.assertEqual(response.status_code, 200)
            return response.context["stops"]

        stops = post(**{"stops-0-city": "Tunis"})
        self.assertIn("differ", stops.forms[0].errors["city"][0])
        stops = post(**{"stops-0-city": "SFAX"})
        self.assertIn("differ", stops.forms[0].errors["city"][0])
        stops = post(**{"stops-0-city": "Sousse", "stops-1-city": "sousse"})
        self.assertIn("already", stops.forms[1].errors["city"][0])
        stops = post(**{"stops-0-city": "S0usse 99"})
        self.assertTrue(stops.forms[0].errors["city"])
        self.assertFalse(Trip.objects.exists())

    def test_at_most_five_stops(self):
        data = self.payload(**{"stops-TOTAL_FORMS": 6})
        for i, city in enumerate(["Nabeul", "Hammamet", "Enfidha", "Sousse", "Monastir", "Mahdia"]):
            data[f"stops-{i}-city"] = city
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Trip.objects.exists())
        self.assertTrue(response.context["stops"].non_form_errors())

    def test_errors_are_shown_under_the_field(self):
        response = self.client.post(self.url, self.payload(price_per_seat="0"))
        self.assertContains(response, "The price must be greater than 0.")


class DetailTests(Base):
    def test_detail_for_passenger_has_book_button(self):
        trip = make_trip(self.driver, self.vehicle)
        self.login(self.sami)
        response = self.client.get(reverse("trips:detail", args=[trip.pk]))
        self.assertContains(response, reverse("reservations:book", args=[trip.pk]))
        self.assertNotContains(response, "Edit trip")
        self.assertNotContains(response, "123 TU 4567")

    def test_detail_for_driver_shows_edit_and_plate(self):
        trip = make_trip(self.driver, self.vehicle)
        self.login(self.driver)
        response = self.client.get(reverse("trips:detail", args=[trip.pk]))
        self.assertContains(response, "Edit trip")
        self.assertContains(response, "123 TU 4567")
        self.assertNotContains(response, "Book a seat")

    def test_no_book_button_when_full_or_own(self):
        trip = make_trip(self.driver, self.vehicle, status=TripStatus.FULL, remaining_seats=0)
        self.login(self.sami)
        response = self.client.get(reverse("trips:detail", args=[trip.pk]))
        self.assertNotContains(response, "Book a seat")
        self.assertContains(response, "No seats are left")

    def test_cancelled_trip_hidden_from_strangers(self):
        trip = make_trip(self.driver, self.vehicle, status=TripStatus.CANCELLED)
        self.login(self.nour)
        self.assertEqual(self.client.get(reverse("trips:detail", args=[trip.pk])).status_code, 404)
        for user in (self.driver, self.admin):
            self.login(user)
            self.assertEqual(self.client.get(reverse("trips:detail", args=[trip.pk])).status_code, 200)

    def test_missing_trip_is_404(self):
        self.login(self.sami)
        self.assertEqual(self.client.get(reverse("trips:detail", args=[9999])).status_code, 404)

    def test_mine_lists_only_my_trips_and_filters(self):
        mine = make_trip(self.driver, self.vehicle)
        cancelled = make_trip(self.driver, self.vehicle, departure_datetime=future(4), status=TripStatus.CANCELLED)
        theirs = make_trip(self.other_driver, self.other_vehicle)
        self.login(self.driver)
        trips = list(self.client.get(reverse("trips:mine")).context["trips"])
        self.assertEqual(set(trips), {mine, cancelled})
        self.assertNotIn(theirs, trips)
        only = self.client.get(reverse("trips:mine"), {"status": "CANCELLED"}).context["trips"]
        self.assertEqual(list(only), [cancelled])

    def test_mine_counts_pending_requests(self):
        trip = make_trip(self.driver, self.vehicle)
        book_seats(self.sami, trip.pk, 1)
        self.login(self.driver)
        response = self.client.get(reverse("trips:mine"))
        self.assertEqual(response.context["pending_total"], 1)
        self.assertContains(response, "1 request waiting")


class SearchTests(Base):
    def setUp(self):
        super().setUp()
        self.t_sousse = make_trip(self.driver, self.vehicle, departure_city="Tunis", arrival_city="Sousse",
                                  departure_datetime=future(2, 1))
        Stop.objects.create(trip=self.t_sousse, city="Hammamet", order=1)
        self.t_sfax = make_trip(self.driver, self.vehicle, departure_city="Tunis", arrival_city="Sfax",
                                departure_datetime=future(3, 2))
        self.t_back = make_trip(self.other_driver, self.other_vehicle, departure_city="Sousse",
                                arrival_city="Tunis", departure_datetime=future(6))
        self.login(self.sami)

    def found(self, **params):
        response = self.client.get(reverse("trips:index"), params)
        self.assertEqual(response.status_code, 200)
        return set(response.context["trips"])

    def test_lists_everything_bookable(self):
        self.assertEqual(self.found(), {self.t_sousse, self.t_sfax, self.t_back})

    def test_search_by_route(self):
        self.assertEqual(self.found(from_city="tunis", to_city="sousse"), {self.t_sousse})
        self.assertEqual(self.found(from_city="Sousse", to_city="Tunis"), {self.t_back})
        self.assertEqual(self.found(to_city="sfax"), {self.t_sfax})
        self.assertEqual(self.found(from_city="Sousse"), {self.t_back})

    def test_search_matches_stops_in_the_right_direction(self):
        self.assertEqual(self.found(from_city="Hammamet", to_city="Sousse"), {self.t_sousse})
        self.assertEqual(self.found(from_city="Tunis", to_city="Hammamet"), {self.t_sousse})
        self.assertEqual(self.found(from_city="Sousse", to_city="Hammamet"), set())

    def test_search_by_date(self):
        self.assertEqual(self.found(date=timezone.localtime(self.t_sfax.departure_datetime).date()), {self.t_sfax})
        self.assertEqual(self.found(date=timezone.localdate() + timedelta(days=30)), set())

    def test_search_by_seats(self):
        self.t_sfax.remaining_seats = 1
        self.t_sfax.save()
        self.assertNotIn(self.t_sfax, self.found(seats=2))
        self.assertIn(self.t_sfax, self.found(seats=1))

    def test_excludes_unbookable_and_own_trips(self):
        make_trip(self.driver, self.vehicle, departure_datetime=future(5), status=TripStatus.CANCELLED)
        make_trip(self.driver, self.vehicle, departure_datetime=future(6), status=TripStatus.FULL, remaining_seats=0)
        make_trip(self.driver, self.vehicle, departure_datetime=timezone.now() - timedelta(hours=2))
        self.assertEqual(self.found(), {self.t_sousse, self.t_sfax, self.t_back})
        self.login(self.driver)
        self.assertEqual(set(self.client.get(reverse("trips:index")).context["trips"]), {self.t_back})

    def test_invalid_search(self):
        response = self.client.get(reverse("trips:index"), {"from_city": "Tunis", "to_city": "tunis"})
        self.assertEqual(list(response.context["trips"]), [])
        self.assertContains(response, "different cities")
        response = self.client.get(reverse("trips:index"), {"date": "2020-01-01"})
        self.assertContains(response, "Choose today or a later date.")
        response = self.client.get(reverse("trips:index"), {"seats": "0"})
        self.assertContains(response, "At least 1 seat.")

    def test_empty_state(self):
        response = self.client.get(reverse("trips:index"), {"to_city": "Tozeur"})
        self.assertContains(response, "No trip found")

    def test_detail_link_present(self):
        response = self.client.get(reverse("trips:index"))
        self.assertContains(response, reverse("trips:detail", args=[self.t_sousse.pk]))


class EditTests(Base):
    def setUp(self):
        super().setUp()
        self.trip = make_trip(self.driver, self.vehicle, seats=3, price_per_seat="12.50",
                              departure_datetime=future(3))
        self.url = reverse("trips:edit", args=[self.trip.pk])
        self.login(self.driver)

    def edit_payload(self, trip=None, **over):
        trip = trip or Trip.objects.get(pk=self.trip.pk)
        stops = list(trip.stops.all())
        data = {
            "vehicle": trip.vehicle_id, "departure_city": trip.departure_city,
            "arrival_city": trip.arrival_city, "departure_datetime": local(trip.departure_datetime),
            "seats": trip.seats, "price_per_seat": str(trip.price_per_seat), "notes": trip.notes,
            "stops-TOTAL_FORMS": len(stops) + 2, "stops-INITIAL_FORMS": len(stops),
            "stops-MIN_NUM_FORMS": 0, "stops-MAX_NUM_FORMS": 5,
        }
        for i, stop in enumerate(stops):
            data[f"stops-{i}-id"] = stop.pk
            data[f"stops-{i}-trip"] = trip.pk
            data[f"stops-{i}-city"] = stop.city
        for j in range(len(stops), len(stops) + 2):
            data[f"stops-{j}-city"] = ""
        data.update(over)
        return data

    def test_form_prefilled(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'value="12.50"')
        self.assertContains(response, local(self.trip.departure_datetime))

    def test_edit_price_and_notes(self):
        response = self.client.post(self.url, self.edit_payload(price_per_seat="20", notes="Back seat free"))
        self.assertRedirects(response, reverse("trips:detail", args=[self.trip.pk]))
        self.trip.refresh_from_db()
        self.assertEqual((str(self.trip.price_per_seat), self.trip.notes), ("20.00", "Back seat free"))

    def test_edit_validation_runs_again(self):
        response = self.client.post(self.url, self.edit_payload(price_per_seat="0"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "greater than 0")
        self.trip.refresh_from_db()
        self.assertEqual(str(self.trip.price_per_seat), "12.50")
        response = self.client.post(self.url, self.edit_payload(departure_datetime=local(timezone.now() - timedelta(days=1))))
        self.assertContains(response, "must be in the future")
        response = self.client.post(self.url, self.edit_payload(arrival_city="tunis"))
        self.assertContains(response, "different cities")

    def test_failed_edit_keeps_header_of_saved_trip(self):
        response = self.client.post(self.url, self.edit_payload(arrival_city="Gabes!"))
        self.assertEqual(response.context["trip"].arrival_city, "Sousse")

    def test_add_edit_remove_and_renumber_stops(self):
        resp = self.client.post(self.url, self.edit_payload(**{"stops-0-city": "enfidha", "stops-1-city": "hammamet"}))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual([(s.city, s.order) for s in self.trip.stops.all()], [("Enfidha", 1), ("Hammamet", 2)])
        data = self.edit_payload(**{"stops-0-DELETE": "on", "stops-2-city": "Msaken"})
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.assertEqual([(s.city, s.order) for s in self.trip.stops.all()], [("Hammamet", 1), ("Msaken", 2)])

    def test_edit_stop_cannot_equal_route(self):
        response = self.client.post(self.url, self.edit_payload(**{"stops-0-city": "Sousse"}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.trip.stops.exists())

    def test_other_driver_gets_404(self):
        self.login(self.other_driver)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, self.edit_payload(price_per_seat="1")).status_code, 404)

    def test_passenger_cannot_edit(self):
        self.login(self.sami)
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_cancelled_or_left_trip_cannot_be_edited(self):
        self.trip.status = TripStatus.CANCELLED
        self.trip.save()
        self.assertRedirects(self.client.get(self.url), reverse("trips:detail", args=[self.trip.pk]),
                             fetch_redirect_response=False)
        past = make_trip(self.driver, self.vehicle, departure_datetime=timezone.now() - timedelta(hours=1))
        self.assertEqual(self.client.get(reverse("trips:edit", args=[past.pk])).status_code, 302)

    def test_seats_cannot_exceed_vehicle(self):
        response = self.client.post(self.url, self.edit_payload(seats=5))
        self.assertContains(response, "4 passenger seats")

    def book(self, user, seats):
        return book_seats(user, self.trip.pk, seats)

    def test_booked_trip_locks_route_date_price_vehicle(self):
        self.book(self.sami, 1)
        original = Trip.objects.get(pk=self.trip.pk)
        response = self.client.post(self.url, self.edit_payload(
            original, departure_city="Nabeul", price_per_seat="99", arrival_city="Gabes",
            departure_datetime=local(future(5)), vehicle=self.other_vehicle.pk, notes="New note"))
        self.assertEqual(response.status_code, 302)
        after = Trip.objects.get(pk=self.trip.pk)
        self.assertEqual((after.departure_city, after.arrival_city, after.vehicle_id, after.price_per_seat),
                         (original.departure_city, original.arrival_city, original.vehicle_id, original.price_per_seat))
        self.assertEqual(after.departure_datetime, original.departure_datetime)
        self.assertEqual(after.notes, "New note")

    def test_locked_form_says_so(self):
        self.book(self.sami, 2)
        response = self.client.get(self.url)
        self.assertContains(response, "2 seats already booked")
        self.assertTrue(response.context["form"].fields["price_per_seat"].disabled)

    def test_seats_cannot_go_below_booked(self):
        self.book(self.sami, 2)
        response = self.client.post(self.url, self.edit_payload(seats=1))
        self.assertContains(response, "already booked: you cannot offer fewer")
        self.assertEqual(Trip.objects.get(pk=self.trip.pk).seats, 3)

    def test_reducing_seats_keeps_remaining_in_sync(self):
        self.book(self.sami, 1)
        self.assertEqual(self.client.post(self.url, self.edit_payload(seats=2)).status_code, 302)
        trip = Trip.objects.get(pk=self.trip.pk)
        self.assertEqual((trip.seats, trip.remaining_seats, trip.status), (2, 1, "OPEN"))
        self.assertEqual(self.client.post(self.url, self.edit_payload(seats=1)).status_code, 302)
        trip.refresh_from_db()
        self.assertEqual((trip.seats, trip.remaining_seats, trip.status), (1, 0, "FULL"))

    def test_adding_seats_reopens_a_full_trip(self):
        self.book(self.sami, 3)
        self.assertEqual(Trip.objects.get(pk=self.trip.pk).status, "FULL")
        self.assertEqual(self.client.post(self.url, self.edit_payload(seats=4)).status_code, 302)
        trip = Trip.objects.get(pk=self.trip.pk)
        self.assertEqual((trip.seats, trip.remaining_seats, trip.status), (4, 1, "OPEN"))

    def test_refused_seats_are_not_counted_as_held(self):
        from reservations.services import refuse_request
        reservation = self.book(self.sami, 2)
        refuse_request(reservation.pk, self.driver)
        self.assertEqual(self.client.post(self.url, self.edit_payload(seats=1)).status_code, 302)
        trip = Trip.objects.get(pk=self.trip.pk)
        self.assertEqual((trip.seats, trip.remaining_seats), (1, 1))


class CancelTests(Base):
    def setUp(self):
        super().setUp()
        self.trip = make_trip(self.driver, self.vehicle, seats=3)
        self.url = reverse("trips:cancel", args=[self.trip.pk])

    def test_confirm_page_and_cancel(self):
        self.login(self.driver)
        self.assertContains(self.client.get(self.url), "Nobody has booked")
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse("trips:mine"))
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.status, "CANCELLED")
        self.assertIsNotNone(self.trip.cancelled_at)
        self.assertNotIn(self.trip, Trip.objects.bookable())

    def test_cancel_cancels_open_bookings_and_closes_chats(self):
        pending = book_seats(self.sami, self.trip.pk, 1)
        accepted = book_seats(self.nour, self.trip.pk, 2)
        accept_request(accepted.pk, self.driver)
        self.assertTrue(Conversation.objects.filter(reservation_reference=str(accepted.pk), closed_at=None).exists())
        self.login(self.driver)
        self.assertContains(self.client.get(self.url), "2</strong> bookings")
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, "2 bookings were cancelled")
        for r in (pending, accepted):
            r.refresh_from_db()
            self.assertEqual(r.status, ReservationStatus.CANCELLED)
            self.assertIsNotNone(r.cancelled_at)
        self.assertFalse(Conversation.objects.filter(reservation_reference=str(accepted.pk), closed_at=None).exists())
        self.trip.refresh_from_db()
        self.assertEqual((self.trip.status, self.trip.remaining_seats), ("CANCELLED", 0))

    def test_cannot_book_a_cancelled_trip(self):
        cancel_trip(self.trip.pk, self.driver)
        from reservations.services import ReservationError
        with self.assertRaises(ReservationError):
            book_seats(self.sami, self.trip.pk, 1)

    def test_only_owner_can_cancel(self):
        self.login(self.other_driver)
        self.assertEqual(self.client.post(self.url).status_code, 404)
        with self.assertRaises(TripError):
            cancel_trip(self.trip.pk, self.other_driver)
        self.login(self.sami)
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.status, "OPEN")

    def test_cannot_cancel_twice_or_after_departure(self):
        cancel_trip(self.trip.pk, self.driver)
        with self.assertRaises(TripError):
            cancel_trip(self.trip.pk, self.driver)
        past = make_trip(self.driver, self.vehicle, departure_datetime=timezone.now() - timedelta(hours=1))
        with self.assertRaises(TripError):
            cancel_trip(past.pk, self.driver)


class CompleteTests(Base):
    def setUp(self):
        super().setUp()
        self.trip = make_trip(self.driver, self.vehicle, seats=3)

    def depart(self):
        Trip.objects.filter(pk=self.trip.pk).update(departure_datetime=timezone.now() - timedelta(hours=3))

    def test_cannot_complete_before_departure(self):
        with self.assertRaises(TripError):
            complete_trip(self.trip.pk, self.driver)

    def test_complete_updates_trip_bookings_and_unlocks_reviews(self):
        accepted = book_seats(self.sami, self.trip.pk, 1)
        accept_request(accepted.pk, self.driver)
        pending = book_seats(self.nour, self.trip.pk, 1)
        conversation = Conversation.objects.get(reservation_reference=str(accepted.pk))
        self.assertIsNone(conversation.trip_completed_at)
        self.depart()
        complete_trip(self.trip.pk, self.driver)
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.status, "COMPLETED")
        accepted.refresh_from_db(); pending.refresh_from_db(); conversation.refresh_from_db()
        self.assertEqual(accepted.status, ReservationStatus.COMPLETED)
        self.assertEqual(pending.status, ReservationStatus.EXPIRED)
        self.assertIsNotNone(conversation.trip_completed_at)

    def test_complete_view_post_only_and_owner_only(self):
        self.depart()
        url = reverse("trips:complete", args=[self.trip.pk])
        self.login(self.driver)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.login(self.other_driver)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.login(self.driver)
        self.assertRedirects(self.client.post(url), reverse("trips:detail", args=[self.trip.pk]))
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.status, "COMPLETED")
        with self.assertRaises(TripError):
            complete_trip(self.trip.pk, self.driver)

    def test_detail_offers_completion_after_departure(self):
        self.login(self.driver)
        self.assertNotContains(self.client.get(reverse("trips:detail", args=[self.trip.pk])), "Mark as completed")
        self.depart()
        self.assertContains(self.client.get(reverse("trips:detail", args=[self.trip.pk])), "Mark as completed")

    def test_cancelled_trip_cannot_be_completed(self):
        cancel_trip(self.trip.pk, self.driver)
        self.depart()
        with self.assertRaises(TripError):
            complete_trip(self.trip.pk, self.driver)


class AdminTests(Base):
    def setUp(self):
        super().setUp()
        self.t1 = make_trip(self.driver, self.vehicle, departure_city="Tunis", arrival_city="Sousse")
        self.t2 = make_trip(self.other_driver, self.other_vehicle, departure_city="Sfax", arrival_city="Gabès",
                            departure_datetime=future(4), status=TripStatus.CANCELLED)
        self.login(self.admin)

    def test_list_search_and_filter(self):
        response = self.client.get(reverse("trips:manage"))
        self.assertEqual(set(response.context["trips"]), {self.t1, self.t2})
        self.assertEqual(response.context["cancelled_count"], 1)
        self.assertEqual(set(self.client.get(reverse("trips:manage"), {"q": "sfax"}).context["trips"]), {self.t2})
        self.assertEqual(set(self.client.get(reverse("trips:manage"), {"q": "driver@test"}).context["trips"]), {self.t1})
        self.assertEqual(set(self.client.get(reverse("trips:manage"), {"status": "OPEN"}).context["trips"]), {self.t1})

    def test_delete_confirm_and_delete(self):
        url = reverse("trips:manage_delete", args=[self.t1.pk])
        self.assertContains(self.client.get(url), "Delete this trip?")
        self.assertTrue(Trip.objects.filter(pk=self.t1.pk).exists())
        self.assertRedirects(self.client.post(url), reverse("trips:manage"))
        self.assertFalse(Trip.objects.filter(pk=self.t1.pk).exists())

    def test_delete_removes_bookings_and_closes_chats(self):
        reservation = book_seats(self.sami, self.t1.pk, 1)
        accept_request(reservation.pk, self.driver)
        delete_trip(self.t1.pk)
        self.assertFalse(Reservation.objects.filter(pk=reservation.pk).exists())
        self.assertFalse(Conversation.objects.filter(reservation_reference=str(reservation.pk), closed_at=None).exists())

    def test_delete_missing_trip(self):
        self.assertEqual(self.client.post(reverse("trips:manage_delete", args=[9999])).status_code, 404)
        with self.assertRaises(TripError):
            delete_trip(9999)

    def test_detail_for_admin_has_delete_only(self):
        response = self.client.get(reverse("trips:detail", args=[self.t1.pk]))
        self.assertContains(response, reverse("trips:manage_delete", args=[self.t1.pk]))
        self.assertNotContains(response, "Book a seat")


class IntegrationTests(Base):
    def test_publish_then_book_then_full(self):
        self.login(self.driver)
        self.client.post(reverse("trips:create"), self.payload(seats=2))
        trip = Trip.objects.get()
        self.login(self.sami)
        self.assertContains(self.client.get(reverse("trips:index")), "Tunis → Sfax")
        self.assertContains(self.client.get(reverse("reservations:book", args=[trip.pk])), "Send my request")
        book_seats(self.sami, trip.pk, 1)
        book_seats(self.nour, trip.pk, 1)
        trip.refresh_from_db()
        self.assertEqual((trip.remaining_seats, trip.status), (0, "FULL"))
        self.assertNotIn(trip, Trip.objects.bookable())

    def test_navbar_shows_find_a_trip(self):
        self.login(self.sami)
        self.assertContains(self.client.get(reverse("home")), "Find a trip")

    def test_form_helpers_are_importable(self):
        form = TripForm(driver=self.driver)
        self.assertEqual(list(form.fields["vehicle"].queryset), [self.vehicle])
        self.assertEqual(len(stop_formset().forms), 3)
        self.assertEqual(len(stop_formset(instance=make_trip(self.driver)).forms), 2)
