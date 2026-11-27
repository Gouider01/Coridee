"""Module 1 - User management  ·  Owner: Alaaeddine Guouider  ·  Branch: Gestion-Utilisateurs

Django admin for users. The day-to-day tools are in /users/manage/; this admin follows
the same business rules so the two can never disagree:
- suspending needs a reason, blocks the login and cancels the user's upcoming trips/bookings;
- the role decides the staff flag (administrators only);
- verifying records who verified and when;
- "delete" anonymises the account (personal data and files erased, history kept),
  it never removes the row, so trips, bookings and reviews of other people stay intact.
"""
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from trips.services import close_user_activity

from .models import User


class AdminChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("account_status", self.instance.account_status)
        reason = (cleaned.get("suspension_reason") or "").strip()
        if status == User.AccountStatus.SUSPENDED and len(reason) < 10:
            self.add_error("suspension_reason",
                           "Explain the reason in at least 10 characters: the user sees it when they try to log in.")
        return cleaned


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = AdminChangeForm
    ordering = ["-date_joined"]
    list_display = ["email", "first_name", "last_name", "user_type", "account_status",
                    "identity_verified", "is_active", "deleted"]
    list_filter = ["user_type", "account_status", "identity_verified", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name", "phone_number"]
    actions = ["delete_accounts"]

    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Personal information", {"fields": [
            "first_name", "last_name", "phone_number", "date_of_birth", "city", "profile_photo",
        ]}),
        ("CoRide", {"fields": ["user_type", "account_status", "suspension_reason", "deleted_at"]}),
        ("Identity", {"fields": [
            "id_document_type", "id_document_number", "id_document_link", "selfie_link",
            "identity_verified", "verified_at", "verified_by",
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
    # is_active follows the account status, is_staff follows the role.
    readonly_fields = ["id_document_link", "selfie_link", "is_active", "is_staff",
                       "verified_at", "verified_by", "deleted_at", "last_login", "date_joined"]

    # ----- Read-only rules -------------------------------------------------
    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.pk == request.user.pk:
            # An administrator cannot suspend themself or remove their own rights.
            fields += ["user_type", "account_status", "suspension_reason", "is_superuser"]
        return fields

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.is_deleted:
            return False   # a deleted (anonymised) account is kept for history only
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # A hard delete would cascade to trips, bookings, chats and reviews of other
        # people. Use the "Delete selected accounts" action, which anonymises instead.
        return False

    # ----- Private files ---------------------------------------------------
    # The ID photo and the selfie live in private storage (no public URL), so the
    # default file widget would crash. Show a link through the protected view instead.
    def _private_link(self, obj, field, kind):
        if not obj or not getattr(obj, field):
            return "-"
        url = reverse("users:identity_document", args=[obj.pk, kind])
        return format_html('<a href="{}" target="_blank" rel="noopener">Open (private file)</a>', url)

    @admin.display(description="photo of the ID document")
    def id_document_link(self, obj):
        return self._private_link(obj, "id_document_image", "id")

    @admin.display(description="selfie")
    def selfie_link(self, obj):
        return self._private_link(obj, "selfie", "selfie")

    @admin.display(description="deleted", boolean=True)
    def deleted(self, obj):
        return obj.is_deleted

    # ----- Saving with the business rules ----------------------------------
    def save_model(self, request, obj, form, change):
        old = User.objects.get(pk=obj.pk) if change else None

        # Role -> staff flag.
        obj.set_user_type(obj.user_type)
        if obj.is_superuser:
            obj.is_staff = True

        # Account status -> login allowed or not.
        newly_suspended = (obj.account_status == User.AccountStatus.SUSPENDED
                           and (old is None or old.account_status != User.AccountStatus.SUSPENDED))
        if obj.account_status == User.AccountStatus.SUSPENDED:
            obj.is_active = False
        else:
            obj.is_active = True
            obj.suspension_reason = ""

        # Identity verification -> who and when.
        if obj.identity_verified and (old is None or not old.identity_verified):
            obj.verified_at, obj.verified_by = timezone.now(), request.user
        elif not obj.identity_verified:
            obj.verified_at, obj.verified_by = None, None

        super().save_model(request, obj, form, change)

        if newly_suspended:
            trips, bookings = close_user_activity(obj)
            if trips or bookings:
                messages.info(request, f"{obj.get_full_name()} is suspended: {trips} upcoming trip(s) "
                                       f"and {bookings} booking(s) were cancelled.")

    # ----- Delete = anonymise ----------------------------------------------
    @admin.action(description="Delete selected accounts (erase personal data, keep history)")
    def delete_accounts(self, request, queryset):
        done = 0
        for person in queryset.filter(deleted_at__isnull=True):
            if person.pk == request.user.pk:
                messages.error(request, "You cannot delete your own account here.")
                continue
            close_user_activity(person)
            person.anonymize()
            done += 1
        if done:
            messages.success(request, f"{done} account(s) deleted: personal data and documents erased.")
