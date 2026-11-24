"""Module 1 - User management  ·  Owner: Alaaeddine Guouider  ·  Branch: Gestion-Utilisateurs

Forms with full input validation. Every error is attached to its field so the
templates can show it right under the input.
"""
from django import forms
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm, PasswordChangeForm

from .models import (
    User,
    cin_validator,
    normalize_phone,
    passport_validator,
    tunisian_phone_validator,
)

DATE_INPUT = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
IMAGE_INPUT = forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"})


class StyledFormMixin:
    """Adds accessibility attributes: aria-invalid / aria-describedby on errors."""

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                attrs = self.fields[name].widget.attrs
                attrs["aria-invalid"] = "true"
                attrs["aria-describedby"] = f"id_{name}_error"


class PhoneFieldMixin:
    def clean_phone_number(self):
        raw = self.cleaned_data.get("phone_number", "")
        phone = normalize_phone(raw)
        if not phone:
            if self.fields["phone_number"].required:
                raise forms.ValidationError("Enter your phone number.")
            return None
        tunisian_phone_validator(phone)
        qs = User.objects.filter(phone_number=phone)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This phone number is already used by another account.")
        return phone


class EmailFieldMixin:
    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("An account with this e-mail already exists.")
        return email


class IdDocumentMixin:
    """Checks the ID number against the chosen document type."""

    def clean(self):
        cleaned = super().clean()
        doc_type = cleaned.get("id_document_type")
        number = (cleaned.get("id_document_number") or "").strip().upper()
        if "id_document_number" in cleaned:
            cleaned["id_document_number"] = number
        if doc_type and number:
            validator = cin_validator if doc_type == User.IdDocumentType.CIN else passport_validator
            try:
                validator(number)
            except forms.ValidationError as e:
                self.add_error("id_document_number", e)
        return cleaned


# --------------------------------------------------------------------------- #
# Visitor
# --------------------------------------------------------------------------- #
class SignUpForm(StyledFormMixin, PhoneFieldMixin, EmailFieldMixin, IdDocumentMixin, BaseUserCreationForm):
    class Meta:
        model = User
        fields = [
            "first_name", "last_name", "email", "phone_number", "date_of_birth",
            "id_document_type", "id_document_number", "id_document_image", "selfie",
        ]
        widgets = {
            "date_of_birth": DATE_INPUT,
            "id_document_image": IMAGE_INPUT,
            "selfie": IMAGE_INPUT,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.Meta.fields:
            self.fields[name].required = True
        f = self.fields
        f["phone_number"] = forms.CharField(
            label="Phone number", max_length=17, help_text="8 digits, e.g. 22 123 456.",
            widget=forms.TextInput(attrs={"type": "tel", "inputmode": "tel", "autocomplete": "tel-national", "placeholder": "22 123 456"}),
        )
        f["first_name"].widget.attrs.update(autocomplete="given-name")
        f["last_name"].widget.attrs.update(autocomplete="family-name")
        f["email"].widget.attrs.update(autocomplete="email", placeholder="you@example.com")
        f["date_of_birth"].help_text = "You must be 18 or older."
        f["id_document_type"].choices = [("", "Choose a document")] + list(User.IdDocumentType.choices)
        f["id_document_number"].help_text = "National ID: 8 digits. Passport: 6 to 9 letters or digits."
        f["id_document_image"].label = "Photo of your ID document"
        f["id_document_image"].help_text = "The side with your photo and your name, clearly readable."
        f["selfie"].label = "Selfie"
        f["selfie"].help_text = "Your face, well lit, looking at the camera."
        f["password1"].help_text = "At least 8 characters, not only digits, not too common."
        f["password1"].widget.attrs.update(autocomplete="new-password")
        f["password2"].widget.attrs.update(autocomplete="new-password")


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.EmailField(
        label="E-mail address",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email", "placeholder": "you@example.com"}),
    )

    error_messages = {
        "invalid_login": "The e-mail or the password is incorrect.",
        "inactive": "This account is suspended.",
    }

    def clean(self):
        email = (self.cleaned_data.get("username") or "").lower()
        password = self.cleaned_data.get("password")
        if email and password:
            self.cleaned_data["username"] = email
            self.user_cache = authenticate(self.request, username=email, password=password)
            if self.user_cache is None:
                suspended = User.objects.filter(email=email, is_active=False, deleted_at__isnull=True).first()
                if suspended and suspended.check_password(password):
                    reason = f" Reason: {suspended.suspension_reason}" if suspended.suspension_reason else ""
                    raise forms.ValidationError(
                        f"Your account has been suspended by an administrator.{reason}", code="inactive"
                    )
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data


# --------------------------------------------------------------------------- #
# Logged-in user
# --------------------------------------------------------------------------- #
class ProfileForm(StyledFormMixin, PhoneFieldMixin, EmailFieldMixin, IdDocumentMixin, forms.ModelForm):
    IDENTITY_FIELDS = ["id_document_type", "id_document_number", "id_document_image", "selfie"]

    class Meta:
        model = User
        fields = [
            "first_name", "last_name", "email", "phone_number", "date_of_birth", "city",
            "profile_photo", "id_document_type", "id_document_number", "id_document_image", "selfie",
        ]
        widgets = {
            "date_of_birth": DATE_INPUT,
            "profile_photo": IMAGE_INPUT,
            "id_document_image": IMAGE_INPUT,
            "selfie": IMAGE_INPUT,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ["first_name", "last_name", "email", "phone_number", "date_of_birth",
                     "id_document_type", "id_document_number"]:
            self.fields[name].required = True
        self.fields["phone_number"] = forms.CharField(
            label="Phone number", max_length=17, help_text="8 digits, e.g. 22 123 456.",
            initial=self.instance.phone_number,
            widget=forms.TextInput(attrs={"type": "tel", "inputmode": "tel", "autocomplete": "tel-national"}),
        )
        self.fields["id_document_type"].choices = list(User.IdDocumentType.choices)
        self.fields["id_document_image"].label = "Photo of your ID document"
        self.fields["profile_photo"].help_text = "Optional. A clear photo of your face helps drivers recognise you."
        # Plain file inputs: no "clear" checkbox for identity files.
        for name in ["profile_photo", "id_document_image", "selfie"]:
            self.fields[name].widget = forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"})

    @property
    def identity_changed(self):
        return any(name in self.changed_data for name in self.IDENTITY_FIELDS)

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.identity_changed and user.identity_verified:
            user.unverify_identity(save=False)
        if commit:
            user.save()
        return user


class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    pass


class DeleteAccountForm(StyledFormMixin, forms.Form):
    password = forms.CharField(
        label="Your password", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        help_text="Type your password to confirm that you want to delete your account.",
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("The password is incorrect.")
        return password


# --------------------------------------------------------------------------- #
# Administrator
# --------------------------------------------------------------------------- #
class AdminUserForm(StyledFormMixin, PhoneFieldMixin, EmailFieldMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone_number", "date_of_birth", "city", "user_type"]
        widgets = {"date_of_birth": DATE_INPUT}

    def __init__(self, *args, acting_admin=None, **kwargs):
        self.acting_admin = acting_admin
        super().__init__(*args, **kwargs)
        self.fields["phone_number"] = forms.CharField(
            label="Phone number", max_length=17, required=False,
            initial=self.instance.phone_number,
            widget=forms.TextInput(attrs={"type": "tel", "inputmode": "tel"}),
        )
        self.fields["user_type"].help_text = "Administrators can open this management area and Django admin."

    def clean_user_type(self):
        user_type = self.cleaned_data["user_type"]
        if (self.acting_admin and self.instance.pk == self.acting_admin.pk
                and user_type != User.UserType.ADMINISTRATOR):
            raise forms.ValidationError("You cannot remove your own administrator role.")
        return user_type

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_user_type(self.cleaned_data["user_type"])
        if commit:
            user.save()
        return user


class SuspendForm(StyledFormMixin, forms.Form):
    reason = forms.CharField(
        label="Reason", min_length=10, max_length=500,
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "e.g. The selfie does not match the ID card."}),
        help_text="The user sees this reason when they try to log in.",
        error_messages={"min_length": "Explain the reason in at least 10 characters."},
    )


class CreateAdminForm(StyledFormMixin, EmailFieldMixin, BaseUserCreationForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.Meta.fields:
            self.fields[name].required = True
        self.fields["password1"].widget.attrs.update(autocomplete="new-password")
        self.fields["password2"].widget.attrs.update(autocomplete="new-password")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_user_type(User.UserType.ADMINISTRATOR)
        if commit:
            user.save()
        return user


class SearchForm(forms.Form):
    q = forms.CharField(required=False, max_length=100)
