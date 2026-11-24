"""Module 1 - User management  ·  Owner: Alaaeddine Guouider  ·  Branch: Gestion-Utilisateurs"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Django's UserAdmin adapted to login by e-mail (no username)."""

    ordering = ["-date_joined"]
    list_display = ["email", "first_name", "last_name", "user_type", "account_status", "identity_verified", "is_active"]
    list_filter = ["user_type", "account_status", "identity_verified", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name", "phone_number"]

    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Personal information", {"fields": [
            "first_name", "last_name", "phone_number", "date_of_birth", "city", "profile_photo",
        ]}),
        ("CoRide", {"fields": ["user_type", "account_status", "suspension_reason", "deleted_at"]}),
        ("Identity", {"fields": [
            "id_document_type", "id_document_number", "id_document_image", "selfie",
            "identity_verified", "verified_at", "verified_by",
        ]}),
        ("Permissions", {"fields": ["is_active", "is_staff", "is_superuser", "groups", "user_permissions"]}),
        ("Dates", {"fields": ["last_login", "date_joined"]}),
    ]
    readonly_fields = ["verified_at", "verified_by", "deleted_at", "last_login", "date_joined"]
    add_fieldsets = [
        (None, {
            "classes": ["wide"],
            "fields": ["email", "first_name", "last_name", "user_type", "password1", "password2"],
        }),
    ]
