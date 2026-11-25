"""
Module 3 - Gestion des trajets  ·  Owner: Wasim Snoussi  ·  Branch: Gestion-Trajets

!!! TEMPORARY MINIMAL VERSION !!!
Written by Module 4 (Reservations) only so that bookings can be developed and
demonstrated before Module 3 is merged. Wasim: replace this file with the real
Trip / Stop models. Keep these names, because `reservations` relies on them:

    Trip.driver, Trip.departure_city, Trip.arrival_city, Trip.departure_datetime,
    Trip.seats, Trip.remaining_seats, Trip.price_per_seat, Trip.status
    Trip.status values: "OPEN", "FULL", "CANCELLED", "COMPLETED"
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Trip(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        FULL = "FULL", "Full"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trips",
        limit_choices_to={"user_type": "DRIVER"},
    )
    departure_city = models.CharField("departure", max_length=100)
    arrival_city = models.CharField("arrival", max_length=100)
    departure_datetime = models.DateTimeField("departure date and time")
    seats = models.PositiveSmallIntegerField(
        "seats offered", validators=[MinValueValidator(1), MaxValueValidator(8)]
    )
    remaining_seats = models.PositiveSmallIntegerField("seats left", default=0, blank=True)
    price_per_seat = models.DecimalField("price per seat (TND)", max_digits=6, decimal_places=2)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["departure_datetime"]

    def __str__(self):
        return f"{self.departure_city} → {self.arrival_city} · {self.departure_datetime:%d/%m/%Y %H:%M}"

    def save(self, *args, **kwargs):
        if self._state.adding and not self.remaining_seats:
            self.remaining_seats = self.seats
        super().save(*args, **kwargs)
