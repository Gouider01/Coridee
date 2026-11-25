"""
Module 4 - business rules for bookings (one function per use case).

Every function raises `ReservationError` with a message that is safe to show
to the user. Views and forms only call these functions, so the rules are
written once and are easy to test.

Rules (from the project presentation):
  * seats available, cannot book your own trip, one open booking per trip
  * a pending request holds its seats; refusing or cancelling releases them
  * cancellation is allowed up to 2 hours before departure
  * only the driver of the trip accepts or refuses a request
"""
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from communication import services as chat
from trips.models import Trip

from .models import ACTIVE, MAX_SEATS_PER_BOOKING, Reservation, ReservationStatus

CANCEL_LIMIT_HOURS = 2
BOOKABLE_TRIP_STATUSES = ("OPEN",)


class ReservationError(Exception):
    """A business rule is broken; str(error) is a user-friendly sentence."""


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #
def check_can_book(user, trip, seats, ignore=None):
    """Raise ReservationError if `user` cannot hold `seats` seats on `trip`.

    `ignore` is a reservation being edited: its own seats do not count twice.
    """
    if not user.is_authenticated or not user.is_passenger:
        raise ReservationError("Only passengers can book a seat.")
    if trip.driver_id == user.pk:
        raise ReservationError("You cannot book your own trip.")
    if trip.status == "CANCELLED":
        raise ReservationError("This trip has been cancelled.")
    if trip.departure_datetime <= timezone.now() or trip.status == "COMPLETED":
        raise ReservationError("This trip has already left.")

    already_held = ignore.seats if ignore is not None and ignore.holds_seats else 0
    free = trip.remaining_seats + already_held
    if trip.status == "FULL" and not already_held or free <= 0:
        raise ReservationError("No seats available on this trip.")
    if not isinstance(seats, int) or seats < 1:
        raise ReservationError("Choose at least 1 seat.")
    if seats > MAX_SEATS_PER_BOOKING:
        raise ReservationError(f"You can book at most {MAX_SEATS_PER_BOOKING} seats at once.")
    if seats > free:
        raise ReservationError(f"Only {free} seat{'s' if free != 1 else ''} left on this trip.")

    duplicates = Reservation.objects.filter(
        trip=trip, passenger=user, status__in=ACTIVE
    )
    if ignore is not None:
        duplicates = duplicates.exclude(pk=ignore.pk)
    if duplicates.exists():
        raise ReservationError("You already have a booking on this trip: edit it from “My bookings”.")


def hours_before_departure(trip):
    return (trip.departure_datetime - timezone.now()) / timedelta(hours=1)


def can_cancel(reservation):
    """(allowed, reason) for the passenger's cancel button."""
    if not reservation.is_active:
        return False, "This booking is already closed."
    if hours_before_departure(reservation.trip) < CANCEL_LIMIT_HOURS:
        return False, f"Cancellation is only possible up to {CANCEL_LIMIT_HOURS} hours before departure."
    return True, ""


# --------------------------------------------------------------------------- #
# Seat bookkeeping on the trip (always called inside a transaction)
# --------------------------------------------------------------------------- #
def _take_seats(trip, count):
    trip.remaining_seats -= count
    if trip.remaining_seats <= 0 and trip.status == "OPEN":
        trip.status = "FULL"
    trip.save(update_fields=["remaining_seats", "status"])


def _release_seats(trip, count):
    trip.remaining_seats = min(trip.seats, trip.remaining_seats + count)
    if trip.status == "FULL" and trip.remaining_seats > 0:
        trip.status = "OPEN"
    trip.save(update_fields=["remaining_seats", "status"])


def _lock(reservation_pk):
    """Re-read a reservation and its trip with a row lock (safe against double clicks)."""
    reservation = Reservation.objects.select_for_update().get(pk=reservation_pk)
    trip = Trip.objects.select_for_update().get(pk=reservation.trip_id)
    reservation.trip = trip
    return reservation, trip


def _close_chat(reservation, reason):
    """Module 5 hook: close the booking's conversation (no-op if none was opened)."""
    chat.close_conversation(reservation.pk, reason)


# --------------------------------------------------------------------------- #
# Use cases
# --------------------------------------------------------------------------- #
@transaction.atomic
def book_seats(user, trip_id, seats):
    """Book a seat: creates a PENDING reservation and holds the seats."""
    try:
        trip = Trip.objects.select_for_update().get(pk=trip_id)
    except Trip.DoesNotExist:
        raise ReservationError("This trip does not exist.")
    check_can_book(user, trip, seats)
    reservation = Reservation.objects.create(
        trip=trip, passenger=user, seats=seats, status=ReservationStatus.PENDING
    )
    _take_seats(trip, seats)
    return reservation


@transaction.atomic
def update_seats(reservation_pk, user, new_seats):
    """Change the number of seats of a request that is still pending."""
    reservation, trip = _lock(reservation_pk)
    if reservation.passenger_id != user.pk:
        raise ReservationError("This is not your booking.")
    if not reservation.is_pending:
        raise ReservationError("Only a pending request can be changed.")
    check_can_book(user, trip, new_seats, ignore=reservation)
    delta = new_seats - reservation.seats
    if delta > 0:
        _take_seats(trip, delta)
    elif delta < 0:
        _release_seats(trip, -delta)
    reservation.seats = new_seats
    reservation.save(update_fields=["seats", "updated_at"])
    return reservation


@transaction.atomic
def cancel_booking(reservation_pk, user):
    """The passenger cancels a pending or accepted booking (2 h rule)."""
    reservation, trip = _lock(reservation_pk)
    if reservation.passenger_id != user.pk:
        raise ReservationError("This is not your booking.")
    allowed, reason = can_cancel(reservation)
    if not allowed:
        raise ReservationError(reason)
    _release_seats(trip, reservation.seats)
    reservation.status = ReservationStatus.CANCELLED
    reservation.cancelled_at = timezone.now()
    reservation.save(update_fields=["status", "cancelled_at", "updated_at"])
    _close_chat(reservation, "CANCELLED")
    return reservation


def _check_driver_decision(reservation, user):
    if reservation.trip.driver_id != user.pk:
        raise ReservationError("Only the driver of this trip can answer this request.")
    if not reservation.is_pending:
        raise ReservationError("This request has already been answered.")
    if reservation.trip.departure_datetime <= timezone.now():
        raise ReservationError("This trip has already left: the request expired.")


@transaction.atomic
def accept_request(reservation_pk, user):
    """The driver accepts a request; the ticket code is created now (QR code in Sprint 2)."""
    reservation, trip = _lock(reservation_pk)
    _check_driver_decision(reservation, user)
    reservation.status = ReservationStatus.ACCEPTED
    reservation.ticket_code = secrets.token_hex(4).upper()
    reservation.save(update_fields=["status", "ticket_code", "updated_at"])
    chat.open_conversation(
        reservation_reference=reservation.pk,
        trip_reference=trip.pk,
        passenger=reservation.passenger,
        driver=trip.driver,
        departure_at=trip.departure_datetime,
    )
    return reservation


@transaction.atomic
def refuse_request(reservation_pk, user):
    """The driver refuses a request; the seats go back to the trip."""
    reservation, trip = _lock(reservation_pk)
    _check_driver_decision(reservation, user)
    _release_seats(trip, reservation.seats)
    reservation.status = ReservationStatus.REFUSED
    reservation.save(update_fields=["status", "updated_at"])
    _close_chat(reservation, "REFUSED")
    return reservation


@transaction.atomic
def delete_reservation(reservation_pk):
    """Administrator: delete a reservation; seats still held are released."""
    reservation, trip = _lock(reservation_pk)
    if reservation.holds_seats and trip.departure_datetime > timezone.now():
        _release_seats(trip, reservation.seats)
    reservation.delete()
