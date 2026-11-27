"""
Module 2 - Gestion des véhicules
Owner: Abdallah Salhi  ·  Branch: Gestion-vehicules
"""
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Document, Vehicle


def private_file_link(doc):
    """Documents live in private storage (no public URL): the default file widget
    would crash, so link to the protected view instead."""
    if not doc or not doc.pk or not doc.file:
        return "-"
    url = reverse("vehicles:document_file", args=[doc.pk])
    return format_html('<a href="{}" target="_blank" rel="noopener">Open (private file)</a>', url)


class DocumentInline(admin.TabularInline):
    model = Document
    extra = 0
    fields = ("document_type", "number", "expiry_date", "file_link", "status")
    readonly_fields = ("file_link", "uploaded_at")

    @admin.display(description="file")
    def file_link(self, obj):
        return private_file_link(obj)


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
        # Go through the model so the same rules apply as in /vehicles/manage/.
        count = 0
        for vehicle in queryset:
            vehicle.refuse("Refused by an administrator.", admin=request.user)
            count += 1
        self.message_user(request, f"{count} vehicle(s) refused.")


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
    exclude = ("file",)
    readonly_fields = ("file_link",)

    @admin.display(description="file")
    def file_link(self, obj):
        return private_file_link(obj)
