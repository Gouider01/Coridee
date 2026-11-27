"""Module 4 - Django admin for reservations."""
from django.contrib import admin

from .models import Reservation
from .services import delete_reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("id", "passenger", "trip", "seats", "status", "ticket_code", "reservation_date")
    list_filter = ("status",)
    search_fields = ("passenger__email", "passenger__first_name", "passenger__last_name",
                     "trip__departure_city", "trip__arrival_city")
    # Status, seats and ticket follow the booking rules (seats taken / released on the
    # trip): change them from the app, not by hand here.
    readonly_fields = ("trip", "passenger", "seats", "status", "ticket_code",
                       "reservation_date", "updated_at", "cancelled_at")

    def has_add_permission(self, request):
        return False   # bookings are made by passengers, with the seat checks

    # Delete through the service, like /reservations/manage/: seats still held go back to the trip.
    def delete_model(self, request, obj):
        delete_reservation(obj.pk)

    def delete_queryset(self, request, queryset):
        for pk in list(queryset.values_list("pk", flat=True)):
            delete_reservation(pk)
