"""
Module 2 - Gestion des véhicules
Owner: Abdallah Salhi  ·  Branch: Gestion-vehicules
"""
from django.contrib import admin
from django.utils import timezone

from .models import Document, Vehicle


class DocumentInline(admin.TabularInline):
    model = Document
    extra = 0
    fields = ("document_type", "number", "expiry_date", "file", "status")
    readonly_fields = ("uploaded_at",)


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        "plate_number",
        "brand",
        "model",
        "color",
        "year",
        "seats",
        "owner",
        "status",
        "created_at",
    )
    list_filter = ("status", "brand", "year")
    search_fields = (
        "plate_number",
        "brand",
        "model",
        "owner__email",
        "owner__first_name",
        "owner__last_name",
    )
    inlines = [DocumentInline]
    actions = ["accept_selected_vehicles", "refuse_selected_vehicles"]

    @admin.action(description="Accept selected vehicles and promote owners to drivers")
    def accept_selected_vehicles(self, request, queryset):
        count = 0
        for vehicle in queryset:
            vehicle.accept(admin=request.user)
            count += 1
        self.message_user(request, f"{count} vehicle(s) accepted.")

    @admin.action(description="Refuse selected vehicles")
    def refuse_selected_vehicles(self, request, queryset):
        queryset.update(
            status=Vehicle.VehicleStatus.REFUSED,
            rejection_reason="Refused via admin action.",
            verified_at=timezone.now(),
            verified_by=request.user,
        )
        self.message_user(request, f"{queryset.count()} vehicle(s) refused.")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "vehicle",
        "document_type",
        "number",
        "expiry_date",
        "status",
        "uploaded_at",
    )
    list_filter = ("document_type", "status")
    search_fields = ("vehicle__plate_number", "number", "vehicle__owner__email")
