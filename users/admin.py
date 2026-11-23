"""Module 1 - Gestion des utilisateurs  ·  Owner: Alaaeddine Guouider  ·  Branch: Gestion-Utilisateurs"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Django's UserAdmin adapted to login by e-mail (no username)."""

    ordering = ["-date_joined"]
    list_display = ["email", "first_name", "last_name", "user_type", "account_status", "is_active"]
    list_filter = ["user_type", "account_status", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name", "phone_number"]

    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Informations personnelles", {"fields": [
            "first_name", "last_name", "phone_number", "date_of_birth", "city", "profile_photo",
        ]}),
        ("CoRide", {"fields": ["user_type", "account_status"]}),
        ("Identité", {"fields": [
            "id_document_type", "id_document_number", "id_document_image", "selfie",
        ]}),
        ("Permissions", {"fields": ["is_active", "is_staff", "is_superuser", "groups", "user_permissions"]}),
        ("Dates", {"fields": ["last_login", "date_joined"]}),
    ]
    add_fieldsets = [
        (None, {
            "classes": ["wide"],
            "fields": ["email", "first_name", "last_name", "user_type", "password1", "password2"],
        }),
    ]
