"""Module 4 - Django admin for reservations."""
from django.contrib import admin

from .models import Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("id", "passenger", "trip", "seats", "status", "ticket_code", "reservation_date")
    list_filter = ("status",)
    search_fields = ("passenger__email", "passenger__first_name", "passenger__last_name",
                     "trip__departure_city", "trip__arrival_city")
    readonly_fields = ("reservation_date", "updated_at", "cancelled_at")
