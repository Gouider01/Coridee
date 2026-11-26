"""
Module 3 - business rules for trips (one function per use case).

Every function raises `TripError` with a message that is safe to show to the
user. Views only call these functions, so the rules are written once.

Rules
  * only a driver with a VALIDATED vehicle publishes a trip, with that vehicle
  * a driver can edit or cancel only their own trip, and only before departure
  * once passengers have booked, route / date / price / vehicle are locked and
    the seats cannot go below the seats already booked
  * cancelling a trip cancels every open booking and closes the chats
  * a trip is completed by its driver after departure; this unlocks the reviews
"""
from django.db import transaction
from django.utils import timezone

from communication import services as chat

from .models import OPEN_BOOKING_STATUSES, Trip, TripStatus


class TripError(Exception):
    """A business rule is broken; str(error) is a user-friendly sentence."""


def _lock(trip_pk):
    try:
        return Trip.objects.select_for_update().get(pk=trip_pk)
    except Trip.DoesNotExist:
        raise TripError("This trip does not exist.")


def _check_owner(trip, user):
    if trip.driver_id != user.pk:
        raise TripError("Only the driver of this trip can do this.")


def sync_status(trip, held=None):
    """Recompute `remaining_seats` and OPEN/FULL from the real bookings."""
    if trip.status not in (TripStatus.OPEN, TripStatus.FULL):
        return trip
    held = trip.held_seats if held is None else held
    trip.remaining_seats = max(trip.seats - held, 0)
    trip.status = TripStatus.FULL if trip.remaining_seats == 0 else TripStatus.OPEN
    return trip


@transaction.atomic
def cancel_trip(trip_pk, user):
    """The driver cancels a trip: open bookings are cancelled, seats and chats released."""
    from reservations.models import Reservation, ReservationStatus

    trip = _lock(trip_pk)
    _check_owner(trip, user)
    if trip.status == TripStatus.CANCELLED:
        raise TripError("This trip is already cancelled.")
    if not trip.can_cancel:
        raise TripError("Only a trip that has not left yet can be cancelled.")

    now = timezone.now()
    affected = list(Reservation.objects.select_for_update().filter(
        trip=trip, status__in=OPEN_BOOKING_STATUSES))
    for reservation in affected:
        reservation.status = ReservationStatus.CANCELLED
        reservation.cancelled_at = now
        reservation.save(update_fields=["status", "cancelled_at", "updated_at"])
        chat.close_conversation(reservation.pk, "CANCELLED")

    trip.status = TripStatus.CANCELLED
    trip.cancelled_at = now
    trip.remaining_seats = 0
    trip.save(update_fields=["status", "cancelled_at", "remaining_seats", "updated_at"])
    return trip, len(affected)


@transaction.atomic
def complete_trip(trip_pk, user):
    """The driver confirms the trip took place. Unlocks the reviews (Module 5)."""
    from reservations.models import Reservation, ReservationStatus

    trip = _lock(trip_pk)
    _check_owner(trip, user)
    if trip.status == TripStatus.COMPLETED:
        raise TripError("This trip is already completed.")
    if trip.status == TripStatus.CANCELLED:
        raise TripError("A cancelled trip cannot be completed.")
    if not trip.has_left:
        raise TripError("You can complete the trip once it has left.")

    Reservation.objects.filter(trip=trip, status=ReservationStatus.PENDING).update(
        status=ReservationStatus.EXPIRED, updated_at=timezone.now())
    Reservation.objects.filter(
        trip=trip, status__in=[ReservationStatus.ACCEPTED, ReservationStatus.BOARDED]
    ).update(status=ReservationStatus.COMPLETED, updated_at=timezone.now())

    trip.status = TripStatus.COMPLETED
    trip.save(update_fields=["status", "updated_at"])
    chat.mark_trip_completed(trip.pk)
    return trip


@transaction.atomic
def delete_trip(trip_pk):
    """Administrator: delete a trip. Its bookings go with it, their chats are closed."""
    from reservations.models import Reservation

    trip = _lock(trip_pk)
    for reservation in Reservation.objects.filter(trip=trip, status__in=OPEN_BOOKING_STATUSES):
        chat.close_conversation(reservation.pk, "CANCELLED")
    trip.delete()
