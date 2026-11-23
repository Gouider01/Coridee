"""
Module 1 - Gestion des utilisateurs
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
from datetime import date

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

# --------------------------------------------------------------------------- #
# Validators
# --------------------------------------------------------------------------- #
tunisian_phone_validator = RegexValidator(
    regex=r"^(\+216)?[2-9]\d{7}$",
    message="Numéro tunisien invalide (8 chiffres, ex. 22123456 ou +21622123456).",
)

cin_validator = RegexValidator(
    regex=r"^\d{8}$",
    message="Le numéro de CIN doit contenir exactement 8 chiffres.",
)


def calculate_age(birth_date, today=None):
    today = today or date.today()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


def validate_adult(birth_date):
    """Users must be at least 18 years old."""
    min_age = settings.CORIDE["MIN_AGE"]
    if birth_date and calculate_age(birth_date) < min_age:
        raise ValidationError(f"Vous devez avoir au moins {min_age} ans pour vous inscrire.")


# --------------------------------------------------------------------------- #
# Manager (login with e-mail instead of username)
# --------------------------------------------------------------------------- #
class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("L'adresse e-mail est obligatoire.")
        email = self.normalize_email(email)
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
        extra_fields.setdefault("account_status", User.AccountStatus.ACTIVE)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Un superuser doit avoir is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Un superuser doit avoir is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


# --------------------------------------------------------------------------- #
# User
# --------------------------------------------------------------------------- #
def profile_photo_path(instance, filename):
    return f"users/photos/{filename}"


def identity_path(instance, filename):
    return f"users/identity/{filename}"


class User(AbstractUser):
    class UserType(models.TextChoices):
        PASSENGER = "PASSENGER", "Passager"
        DRIVER = "DRIVER", "Conducteur"
        ADMINISTRATOR = "ADMINISTRATOR", "Administrateur"

    class AccountStatus(models.TextChoices):
        PENDING = "PENDING", "En attente de vérification"
        ACTIVE = "ACTIVE", "Actif"
        SUSPENDED = "SUSPENDED", "Suspendu"

    class IdDocumentType(models.TextChoices):
        CIN = "CIN", "Carte d'identité nationale"
        PASSPORT = "PASSPORT", "Passeport"

    # Login with e-mail: no username.
    username = None
    email = models.EmailField("adresse e-mail", unique=True)

    # Personal information
    phone_number = models.CharField(
        "téléphone", max_length=13, blank=True, validators=[tunisian_phone_validator]
    )
    date_of_birth = models.DateField(
        "date de naissance", null=True, blank=True, validators=[validate_adult]
    )
    city = models.CharField("ville", max_length=100, blank=True)
    profile_photo = models.ImageField(
        "photo de profil", upload_to=profile_photo_path, null=True, blank=True
    )

    # Role and account state
    user_type = models.CharField(
        "type d'utilisateur", max_length=20,
        choices=UserType.choices, default=UserType.PASSENGER,
    )
    account_status = models.CharField(
        "statut du compte", max_length=20,
        choices=AccountStatus.choices, default=AccountStatus.PENDING,
    )

    # Identity documents uploaded at sign-up
    id_document_type = models.CharField(
        "type de pièce d'identité", max_length=10,
        choices=IdDocumentType.choices, blank=True,
    )
    id_document_number = models.CharField("numéro de la pièce", max_length=20, blank=True)
    id_document_image = models.ImageField(
        "photo de la pièce d'identité", upload_to=identity_path, null=True, blank=True
    )
    selfie = models.ImageField("selfie", upload_to=identity_path, null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.get_full_name() or self.email

    def clean(self):
        super().clean()
        if self.id_document_type == self.IdDocumentType.CIN and self.id_document_number:
            cin_validator(self.id_document_number)

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
        verbose_name = "passager"
        verbose_name_plural = "passagers"


class Driver(Passenger):
    objects = DriverManager()

    class Meta:
        proxy = True
        verbose_name = "conducteur"
        verbose_name_plural = "conducteurs"


class Administrator(User):
    objects = AdministratorManager()

    class Meta:
        proxy = True
        verbose_name = "administrateur"
        verbose_name_plural = "administrateurs"
