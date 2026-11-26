"""Module 3 - Django admin for trips (the day-to-day tools are in /trips/manage/)."""
from django.contrib import admin

from .models import Stop, Trip


class StopInline(admin.TabularInline):
    model = Stop
    extra = 0


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ("departure_city", "arrival_city", "departure_datetime", "driver",
                    "remaining_seats", "seats", "price_per_seat", "status")
    list_filter = ("status",)
    search_fields = ("departure_city", "arrival_city", "driver__email", "driver__first_name",
                     "driver__last_name")
    date_hierarchy = "departure_datetime"
    inlines = [StopInline]
