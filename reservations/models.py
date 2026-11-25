"""
Module 4 - Gestion des réservations  ·  Owner: Selim Aschi  ·  Branch: Gestion-Reservations

Class diagram: Reservation + enumeration ReservationStatus.
A reservation links ONE passenger to ONE trip. Business rules live in
`reservations/services.py`; this file only describes the data.
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

MAX_SEATS_PER_BOOKING = 8


class ReservationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACCEPTED = "ACCEPTED", "Accepted"
    REFUSED = "REFUSED", "Refused"
    EXPIRED = "EXPIRED", "Expired"
    CANCELLED = "CANCELLED", "Cancelled"
    BOARDED = "BOARDED", "Boarded"          # Sprint 2: QR ticket scanned
    COMPLETED = "COMPLETED", "Completed"
    NO_SHOW = "NO_SHOW", "No-show"          # Sprint 2: no-show tracking


# Statuses that still hold seats on the trip.
SEAT_HOLDING = (ReservationStatus.PENDING, ReservationStatus.ACCEPTED, ReservationStatus.BOARDED)
# Statuses that count as "an open booking" (one per passenger per trip).
ACTIVE = (ReservationStatus.PENDING, ReservationStatus.ACCEPTED)

BADGE = {
    ReservationStatus.PENDING: "pending",
    ReservationStatus.ACCEPTED: "active",
    ReservationStatus.BOARDED: "active",
    ReservationStatus.COMPLETED: "neutral",
    ReservationStatus.EXPIRED: "neutral",
    ReservationStatus.REFUSED: "suspended",
    ReservationStatus.CANCELLED: "suspended",
    ReservationStatus.NO_SHOW: "suspended",
}


class ReservationQuerySet(models.QuerySet):
    def expire_overdue(self):
        """A request nobody answered before departure becomes EXPIRED."""
        return self.filter(
            status=ReservationStatus.PENDING, trip__departure_datetime__lte=timezone.now()
        ).update(status=ReservationStatus.EXPIRED, updated_at=timezone.now())


class Reservation(models.Model):
    trip = models.ForeignKey("trips.Trip", on_delete=models.CASCADE, related_name="reservations")
    passenger = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reservations"
    )
    seats = models.PositiveSmallIntegerField(
        "seats", validators=[MinValueValidator(1), MaxValueValidator(MAX_SEATS_PER_BOOKING)]
    )
    status = models.CharField(
        max_length=12, choices=ReservationStatus.choices, default=ReservationStatus.PENDING
    )
    ticket_code = models.CharField("ticket code", max_length=12, blank=True)  # set when accepted
    reservation_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    objects = ReservationQuerySet.as_manager()

    class Meta:
        ordering = ["-reservation_date"]
        constraints = [
            # A passenger cannot have two open bookings on the same trip.
            models.UniqueConstraint(
                fields=["passenger", "trip"],
                condition=Q(status__in=["PENDING", "ACCEPTED"]),
                name="one_open_booking_per_passenger_and_trip",
            ),
            models.CheckConstraint(condition=Q(seats__gte=1), name="reservation_seats_positive"),
        ]

    def __str__(self):
        return f"#{self.pk} · {self.passenger} · {self.trip} · {self.seats} seat(s)"

    # ----- Read helpers ----------------------------------------------------
    @property
    def badge(self):
        return BADGE.get(self.status, "neutral")

    @property
    def total_price(self):
        return self.seats * self.trip.price_per_seat

    @property
    def is_pending(self):
        return self.status == ReservationStatus.PENDING

    @property
    def is_active(self):
        return self.status in ACTIVE

    @property
    def holds_seats(self):
        return self.status in SEAT_HOLDING
