"""
Module 1 - User management
Owner: Alaaeddine Guouider  ·  Branch: Gestion-Utilisateurs

Class diagram mapping
---------------------
User (abstract in UML)  -> `User`, the Django auth model (AUTH_USER_MODEL)
Passenger               -> proxy of User (user_type = PASSENGER or DRIVER)
Driver                  -> proxy of User (user_type = DRIVER)
Administrator           -> proxy of User (user_type = ADMINISTRATOR)
AccountStatus           -> enumeration `User.AccountStatus`

Django allows one auth model only, so the UML inheritance is implemented as
one table + a `user_type` field + proxy models.
Other modules must point to users with `settings.AUTH_USER_MODEL`.
"""
import os
import uuid
from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.deconstruct import deconstructible

# --------------------------------------------------------------------------- #
# Validators
# --------------------------------------------------------------------------- #
IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
MAX_IMAGE_MB = 5

name_validator = RegexValidator(
    regex=r"^[^\W\d_]+(?:[ '\-][^\W\d_]+)*$",
    message="Use letters only (spaces, hyphens and apostrophes are allowed).",
)

tunisian_phone_validator = RegexValidator(
    regex=r"^[2-9]\d{7}$",
    message="Enter a Tunisian number: 8 digits starting with 2 to 9 (e.g. 22 123 456).",
)

cin_validator = RegexValidator(
    regex=r"^\d{8}$",
    message="A national ID card number has exactly 8 digits.",
)

passport_validator = RegexValidator(
    regex=r"^[A-Za-z0-9]{6,9}$",
    message="A passport number has 6 to 9 letters or digits.",
)

image_extension_validator = FileExtensionValidator(
    allowed_extensions=IMAGE_EXTENSIONS,
    message="Upload a JPG, PNG or WebP image.",
)


def validate_image_size(file):
    if file and file.size > MAX_IMAGE_MB * 1024 * 1024:
        raise ValidationError(f"The image is too large: the maximum is {MAX_IMAGE_MB} MB.")


def calculate_age(birth_date, today=None):
    today = today or date.today()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


def validate_adult(birth_date):
    """Users must be at least 18 years old."""
    if not birth_date:
        return
    if birth_date > date.today():
        raise ValidationError("The date of birth cannot be in the future.")
    min_age = settings.CORIDE["MIN_AGE"]
    if calculate_age(birth_date) < min_age:
        raise ValidationError(f"You must be at least {min_age} years old to use CoRide.")


def normalize_phone(value):
    """'+216 22 123 456' -> '22123456'. Returns '' for empty input."""
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if digits.startswith("216") and len(digits) == 11:
        digits = digits[3:]
    return digits


# --------------------------------------------------------------------------- #
# File storage: identity documents are private (never under /media/)
# --------------------------------------------------------------------------- #
class PrivateStorage(FileSystemStorage):
    """Stores files in settings.PRIVATE_MEDIA_ROOT, which has no public URL."""

    @property
    def base_location(self):
        return str(settings.PRIVATE_MEDIA_ROOT)

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None


private_storage = PrivateStorage()


def get_private_storage():
    return private_storage


@deconstructible
class RandomName:
    """Upload path with a random file name, so files cannot be guessed."""

    def __init__(self, folder):
        self.folder = folder

    def __call__(self, instance, filename):
        ext = Path(filename).suffix.lower()
        return f"{self.folder}/{uuid.uuid4().hex}{ext}"


# Kept only because migration 0001 refers to them.
def profile_photo_path(instance, filename):
    return f"users/photos/{filename}"


def identity_path(instance, filename):
    return f"users/identity/{filename}"


# --------------------------------------------------------------------------- #
# Manager (login with e-mail instead of username)
# --------------------------------------------------------------------------- #
class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The e-mail address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("user_type", User.UserType.ADMINISTRATOR)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


# --------------------------------------------------------------------------- #
# User
# --------------------------------------------------------------------------- #
class User(AbstractUser):
    class UserType(models.TextChoices):
        PASSENGER = "PASSENGER", "Passenger"
        DRIVER = "DRIVER", "Driver"
        ADMINISTRATOR = "ADMINISTRATOR", "Administrator"

    class AccountStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"

    class IdDocumentType(models.TextChoices):
        CIN = "CIN", "National ID card (CIN)"
        PASSPORT = "PASSPORT", "Passport"

    # Login with e-mail: no username.
    username = None
    email = models.EmailField("e-mail address", unique=True)
    first_name = models.CharField("first name", max_length=50, validators=[name_validator])
    last_name = models.CharField("last name", max_length=50, validators=[name_validator])

    # Personal information
    phone_number = models.CharField(
        "phone number", max_length=8, unique=True, null=True, blank=True,
        validators=[tunisian_phone_validator],
        help_text="8 digits, e.g. 22 123 456.",
    )
    date_of_birth = models.DateField(
        "date of birth", null=True, blank=True, validators=[validate_adult]
    )
    city = models.CharField("city", max_length=100, blank=True)
    profile_photo = models.ImageField(
        "profile photo", upload_to=RandomName("users/photos"), null=True, blank=True,
        validators=[image_extension_validator, validate_image_size],
    )

    # Role and account state
    user_type = models.CharField(
        "account type", max_length=20,
        choices=UserType.choices, default=UserType.PASSENGER,
    )
    account_status = models.CharField(
        "account status", max_length=20,
        choices=AccountStatus.choices, default=AccountStatus.ACTIVE,
    )
    suspension_reason = models.TextField("suspension reason", blank=True)

    # Identity documents (private files) and their verification
    id_document_type = models.CharField(
        "ID document type", max_length=10, choices=IdDocumentType.choices, blank=True,
    )
    id_document_number = models.CharField("ID document number", max_length=20, blank=True)
    id_document_image = models.ImageField(
        "photo of the ID document", upload_to=RandomName("identity"), storage=get_private_storage,
        null=True, blank=True, validators=[image_extension_validator, validate_image_size],
    )
    selfie = models.ImageField(
        "selfie", upload_to=RandomName("identity"), storage=get_private_storage,
        null=True, blank=True, validators=[image_extension_validator, validate_image_size],
    )
    identity_verified = models.BooleanField("identity verified", default=False)
    verified_at = models.DateTimeField("verified on", null=True, blank=True)
    verified_by = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="verified_users", verbose_name="verified by",
    )

    deleted_at = models.DateTimeField("deleted on", null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.get_full_name() or self.email

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.lower()
        if self.phone_number == "":
            self.phone_number = None
        if self.id_document_number:
            if self.id_document_type == self.IdDocumentType.CIN:
                try:
                    cin_validator(self.id_document_number)
                except ValidationError as e:
                    raise ValidationError({"id_document_number": e.messages})
            elif self.id_document_type == self.IdDocumentType.PASSPORT:
                try:
                    passport_validator(self.id_document_number)
                except ValidationError as e:
                    raise ValidationError({"id_document_number": e.messages})

    # ----- Read helpers ----------------------------------------------------
    @property
    def age(self):
        return calculate_age(self.date_of_birth) if self.date_of_birth else None

    @property
    def is_passenger(self):
        """A driver is a passenger too."""
        return self.user_type in (self.UserType.PASSENGER, self.UserType.DRIVER)

    @property
    def is_driver(self):
        return self.user_type == self.UserType.DRIVER

    @property
    def is_administrator(self):
        return self.user_type == self.UserType.ADMINISTRATOR

    @property
    def is_suspended(self):
        return self.account_status == self.AccountStatus.SUSPENDED

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @property
    def masked_id_number(self):
        n = self.id_document_number
        return f"••••{n[-4:]}" if len(n) > 4 else n

    @property
    def formatted_phone(self):
        p = self.phone_number or ""
        return f"+216 {p[:2]} {p[2:5]} {p[5:]}" if len(p) == 8 else p

    # ----- Actions ---------------------------------------------------------
    def promote_to_driver(self):
        """Called by Module 2 when one of the user's vehicles is validated."""
        if self.user_type == self.UserType.PASSENGER:
            self.user_type = self.UserType.DRIVER
            self.save(update_fields=["user_type", "updated_at"])

    def set_user_type(self, user_type):
        """Change the role and keep Django's staff flag in line with it."""
        self.user_type = user_type
        if user_type == self.UserType.ADMINISTRATOR:
            self.is_staff = True
        elif not self.is_superuser:
            self.is_staff = False

    def verify_identity(self, admin):
        self.identity_verified = True
        self.verified_at = timezone.now()
        self.verified_by = admin
        self.save(update_fields=["identity_verified", "verified_at", "verified_by", "updated_at"])

    def unverify_identity(self, save=True):
        self.identity_verified = False
        self.verified_at = None
        self.verified_by = None
        if save:
            self.save(update_fields=["identity_verified", "verified_at", "verified_by", "updated_at"])

    def suspend(self, reason):
        self.account_status = self.AccountStatus.SUSPENDED
        self.suspension_reason = reason
        self.is_active = False
        self.save(update_fields=["account_status", "suspension_reason", "is_active", "updated_at"])

    def reactivate(self):
        self.account_status = self.AccountStatus.ACTIVE
        self.suspension_reason = ""
        self.is_active = True
        self.save(update_fields=["account_status", "suspension_reason", "is_active", "updated_at"])

    def anonymize(self):
        """Delete the account: erase personal data and files, keep the row
        so other modules' history (trips, bookings, reviews) stays intact."""
        for field in ("profile_photo", "id_document_image", "selfie"):
            f = getattr(self, field)
            if f:
                f.delete(save=False)
        self.first_name = "Deleted"
        self.last_name = "user"
        self.email = f"deleted-{self.pk}@deleted.coride.invalid"
        self.phone_number = None
        self.date_of_birth = None
        self.city = ""
        self.id_document_type = ""
        self.id_document_number = ""
        self.suspension_reason = ""
        self.unverify_identity(save=False)
        self.set_unusable_password()
        self.is_active = False
        self.is_staff = False
        self.is_superuser = False
        self.deleted_at = timezone.now()
        self.save()

    # ----- AI hooks (Sprint 3) --------------------------------------------
    # verify_identity_ai(): compare selfie with ID photo.
    # check_photo(): moderate the profile photo.


# --------------------------------------------------------------------------- #
# Proxy models (UML subclasses)
# --------------------------------------------------------------------------- #
class PassengerManager(UserManager):
    def get_queryset(self):
        return super().get_queryset().filter(
            user_type__in=[User.UserType.PASSENGER, User.UserType.DRIVER]
        )


class DriverManager(UserManager):
    def get_queryset(self):
        return super().get_queryset().filter(user_type=User.UserType.DRIVER)


class AdministratorManager(UserManager):
    def get_queryset(self):
        return super().get_queryset().filter(user_type=User.UserType.ADMINISTRATOR)


class Passenger(User):
    objects = PassengerManager()

    class Meta:
        proxy = True
        verbose_name = "passenger"
        verbose_name_plural = "passengers"


class Driver(Passenger):
    objects = DriverManager()

    class Meta:
        proxy = True
        verbose_name = "driver"
        verbose_name_plural = "drivers"


class Administrator(User):
    objects = AdministratorManager()

    class Meta:
        proxy = True
        verbose_name = "administrator"
        verbose_name_plural = "administrators"
