"""Module 3 - Django admin for trips (the day-to-day tools are in /trips/manage/)."""
from django.contrib import admin

from .models import Stop, Trip
from .services import delete_trip


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
    # Status and free seats are kept in line by the trip services (book, cancel,
    # complete); editing them by hand would break the seat count.
    readonly_fields = ("driver", "vehicle", "seats", "status", "remaining_seats", "cancelled_at", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False   # trips are published by drivers, with the publish checks

    # Delete through the service, like /trips/manage/: the chats of its bookings are closed.
    def delete_model(self, request, obj):
        delete_trip(obj.pk)

    def delete_queryset(self, request, queryset):
        for pk in list(queryset.values_list("pk", flat=True)):
            delete_trip(pk)
