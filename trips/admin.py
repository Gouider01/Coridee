"""Module 3 - temporary admin so trips can be created for the Reservations demo."""
from django.contrib import admin

from .models import Trip


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ("departure_city", "arrival_city", "departure_datetime", "driver",
                    "remaining_seats", "seats", "price_per_seat", "status")
    list_filter = ("status",)
