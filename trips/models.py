"""
Module 3 - Gestion des trajets  ·  Owner: Wasim Snoussi  ·  Branch: Gestion-Trajets

Entities
  Trip - one journey offered by a driver with one of their validated vehicles.
  Stop - an optional intermediate city on the way (0 to MAX_STOPS per trip).

The field names `driver`, `departure_city`, `arrival_city`, `departure_datetime`,
`seats`, `remaining_seats`, `price_per_seat` and `status` are used by the
reservations module: do not rename them. Business rules live in
`trips/services.py`; this file only describes the data.
"""
import re

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

MAX_STOPS = 5
MAX_PRICE = 500  # TND per seat - a sanity limit

# Plain strings so this module never imports `reservations` (which imports `trips`).
SEAT_HOLDING_STATUSES = ("PENDING", "ACCEPTED", "BOARDED")
OPEN_BOOKING_STATUSES = ("PENDING", "ACCEPTED")


class TripStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    FULL = "FULL", "Full"
    CANCELLED = "CANCELLED", "Cancelled"
    COMPLETED = "COMPLETED", "Completed"


BADGE = {
    TripStatus.OPEN: "active",
    TripStatus.FULL: "pending",
    TripStatus.CANCELLED: "suspended",
    TripStatus.COMPLETED: "neutral",
}


class TripQuerySet(models.QuerySet):
    def bookable(self):
        return self.filter(
            status=TripStatus.OPEN, remaining_seats__gt=0, departure_datetime__gt=timezone.now(),
            driver__is_active=True,   # suspended / deleted drivers (Module 1) are hidden
        )

    def upcoming(self):
        return self.filter(
            status__in=[TripStatus.OPEN, TripStatus.FULL], departure_datetime__gt=timezone.now()
        )


class Trip(models.Model):
    Status = TripStatus  # keeps `Trip.Status.OPEN` working for the other modules

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trips",
        limit_choices_to={"user_type": "DRIVER"},
    )
    # Null only for rows created before the vehicle link existed (demo data, tests).
    vehicle = models.ForeignKey(
        "vehicles.Vehicle", on_delete=models.PROTECT, related_name="trips",
        null=True, blank=True,
    )
    departure_city = models.CharField("departure", max_length=100)
    arrival_city = models.CharField("arrival", max_length=100)
    departure_datetime = models.DateTimeField("departure date and time")
    seats = models.PositiveSmallIntegerField(
        "seats offered", validators=[MinValueValidator(1), MaxValueValidator(8)]
    )
    remaining_seats = models.PositiveSmallIntegerField("seats left", default=0, blank=True)
    price_per_seat = models.DecimalField("price per seat (TND)", max_digits=6, decimal_places=2)
    notes = models.CharField(
        "notes for passengers", max_length=300, blank=True,
        help_text="Meeting point, luggage, music, smoking… (optional, 300 characters).",
    )
    status = models.CharField(max_length=12, choices=TripStatus.choices, default=TripStatus.OPEN)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TripQuerySet.as_manager()

    class Meta:
        ordering = ["departure_datetime"]
        indexes = [
            models.Index(fields=["status", "departure_datetime"], name="trip_status_departure_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(price_per_seat__gt=0), name="trip_price_positive"),
            models.CheckConstraint(condition=Q(seats__gte=1), name="trip_seats_positive"),
            models.CheckConstraint(
                condition=Q(remaining_seats__lte=F("seats")), name="trip_remaining_lte_seats"
            ),
        ]

    def __str__(self):
        return f"{self.departure_city} → {self.arrival_city} · {self.departure_datetime:%d/%m/%Y %H:%M}"

    def save(self, *args, **kwargs):
        if self._state.adding and not self.remaining_seats:
            self.remaining_seats = self.seats
        super().save(*args, **kwargs)

    # ----- Read helpers ----------------------------------------------------
    @property
    def badge(self):
        return BADGE.get(self.status, "neutral")

    @property
    def route_label(self):
        return f"{self.departure_city} → {self.arrival_city}"

    @property
    def has_left(self):
        return self.departure_datetime <= timezone.now()

    @property
    def is_cancelled(self):
        return self.status == TripStatus.CANCELLED

    @property
    def is_completed(self):
        return self.status == TripStatus.COMPLETED

    @property
    def is_bookable(self):
        return (self.status == TripStatus.OPEN and self.remaining_seats > 0 and not self.has_left
                and self.driver.is_active)

    @property
    def seats_taken(self):
        return self.seats - self.remaining_seats

    @property
    def held_seats(self):
        """Seats really held by bookings (source of truth, used when editing)."""
        total = self.reservations.filter(status__in=SEAT_HOLDING_STATUSES).aggregate(
            n=models.Sum("seats")
        )["n"]
        return total or 0

    @property
    def open_booking_count(self):
        return self.reservations.filter(status__in=OPEN_BOOKING_STATUSES).count()

    @property
    def has_bookings(self):
        return self.reservations.filter(status__in=SEAT_HOLDING_STATUSES).exists()

    @property
    def can_edit(self):
        return self.status in (TripStatus.OPEN, TripStatus.FULL) and not self.has_left

    @property
    def can_cancel(self):
        return self.can_edit

    @property
    def can_complete(self):
        return self.status in (TripStatus.OPEN, TripStatus.FULL) and self.has_left

    def route_cities(self):
        """Departure, every stop in order, then arrival."""
        return [self.departure_city, *[s.city for s in self.stops.all()], self.arrival_city]

    def serves(self, origin="", destination=""):
        """True if a passenger can ride from `origin` to `destination` on this trip.

        Both are optional, case-insensitive fragments. When both are given the
        origin must come before the destination along the route (a stop counts).
        """
        cities = [c.casefold() for c in self.route_cities()]
        origin, destination = origin.strip().casefold(), destination.strip().casefold()

        def positions(fragment):
            return [i for i, c in enumerate(cities) if fragment in c]

        if origin and destination:
            return any(i < j for i in positions(origin) for j in positions(destination))
        if origin:
            return any(i < len(cities) - 1 for i in positions(origin))
        if destination:
            return any(j > 0 for j in positions(destination))
        return True


class Stop(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="stops")
    city = models.CharField("stop", max_length=100)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return f"{self.order}. {self.city} ({self.trip_id})"


_CITY_RE = re.compile(r"^[^\W\d_]+(?:[ '’\-][^\W\d_]+)*$")


def normalize_city(value):
    """'  sidi   bou said ' -> 'Sidi Bou Said' (stored form, also used to compare cities)."""
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    return re.sub(r"(^|[ \-])([^\W\d_])", lambda m: m.group(1) + m.group(2).upper(), cleaned)


def is_valid_city(value):
    return 2 <= len(value) <= 60 and bool(_CITY_RE.match(value))
