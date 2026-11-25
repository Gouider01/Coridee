"""
Module 2 - Gestion des véhicules
Owner: Abdallah Salhi  ·  Branch: Gestion-vehicules

Entities implemented:
- Vehicle: Make, model, color, plate number, seats, status
- Document: License, Registration, Insurance (with private file storage and expiry dates)
"""
import os
import re
import uuid
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.utils import timezone
from django.utils.deconstruct import deconstructible

from users.models import get_private_storage


# --------------------------------------------------------------------------- #
# Helpers & Validators
# --------------------------------------------------------------------------- #
DOCUMENT_EXTENSIONS = ["jpg", "jpeg", "png", "webp", "pdf"]
MAX_DOCUMENT_MB = 5


def normalize_plate(value):
    """Normalize Tunisian license plate: remove excess spaces, uppercase."""
    if not value:
        return ""
    cleaned = re.sub(r"\s+", " ", str(value).strip().upper())
    # Format: 123 TU 4567 or 123TU4567
    m_tu = re.match(r"^(\d{1,4})\s*TU\s*(\d{1,4})$", cleaned)
    if m_tu:
        return f"{m_tu.group(1)} TU {m_tu.group(2)}"
    # RS plates: 12345 RS or RS 12345
    m_rs = re.match(r"^(\d{1,6})\s*RS$", cleaned)
    if m_rs:
        return f"{m_rs.group(1)} RS"
    m_rs2 = re.match(r"^RS\s*(\d{1,6})$", cleaned)
    if m_rs2:
        return f"{m_rs2.group(1)} RS"
    return cleaned


def validate_tunisian_plate(value):
    """Check if value is a valid Tunisian license plate."""
    norm = normalize_plate(value)
    is_tu = bool(re.match(r"^\d{1,4}\s*TU\s*\d{1,4}$", norm))
    is_rs = bool(re.match(r"^\d{1,6}\s*RS$", norm))
    if not (is_tu or is_rs):
        raise ValidationError(
            "Enter a valid Tunisian license plate (e.g. '123 TU 4567' or '12345 RS')."
        )


def validate_vehicle_year(year):
    """Ensure manufacturing year is reasonable."""
    current_year = timezone.now().year
    if year < 1980 or year > current_year + 1:
        raise ValidationError(
            f"Enter a valid year of manufacture (between 1980 and {current_year + 1})."
        )


def validate_future_date(d):
    """Ensure document expiry date is in the future."""
    if d and d <= date.today():
        raise ValidationError("The document expiry date must be in the future.")


def validate_document_size(file):
    """Limit document size to 5 MB."""
    if file and file.size > MAX_DOCUMENT_MB * 1024 * 1024:
        raise ValidationError(
            f"The document file is too large: maximum allowed size is {MAX_DOCUMENT_MB} MB."
        )


document_extension_validator = FileExtensionValidator(
    allowed_extensions=DOCUMENT_EXTENSIONS,
    message="Upload a JPG, PNG, WebP image or a PDF document.",
)


@deconstructible
class RandomDocumentName:
    """Randomized file path to prevent direct file name guessing."""

    def __init__(self, folder="vehicles/documents"):
        self.folder = folder

    def __call__(self, instance, filename):
        ext = Path(filename).suffix.lower()
        return f"{self.folder}/{uuid.uuid4().hex}{ext}"


# --------------------------------------------------------------------------- #
# Vehicle Model
# --------------------------------------------------------------------------- #
class Vehicle(models.Model):
    class VehicleStatus(models.TextChoices):
        PENDING = "PENDING", "Pending validation"
        ACCEPTED = "ACCEPTED", "Accepted"
        REFUSED = "REFUSED", "Refused"
        DOCUMENTS_EXPIRED = "DOCUMENTS_EXPIRED", "Documents expired"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vehicles",
        verbose_name="owner",
    )
    brand = models.CharField(
        "brand / make",
        max_length=50,
        help_text="e.g. Peugeot, Volkswagen, Renault",
    )
    model = models.CharField(
        "model",
        max_length=50,
        help_text="e.g. 208, Golf, Clio",
    )
    color = models.CharField(
        "color",
        max_length=30,
        help_text="e.g. White, Grey, Black",
    )
    plate_number = models.CharField(
        "license plate",
        max_length=20,
        unique=True,
        validators=[validate_tunisian_plate],
        help_text="Tunisian format: e.g. 123 TU 4567 or 12345 RS",
    )
    year = models.PositiveIntegerField(
        "year",
        validators=[validate_vehicle_year],
        help_text="Year of manufacture",
    )
    seats = models.PositiveSmallIntegerField(
        "passenger seats",
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(8)],
        help_text="Available seats for passengers (1 to 8).",
    )
    status = models.CharField(
        "status",
        max_length=25,
        choices=VehicleStatus.choices,
        default=VehicleStatus.PENDING,
    )
    rejection_reason = models.TextField("rejection reason", blank=True)
    verified_at = models.DateTimeField("reviewed on", null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_vehicles",
        verbose_name="reviewed by",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "vehicle"
        verbose_name_plural = "vehicles"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.brand} {self.model} ({self.plate_number})"

    def clean(self):
        super().clean()
        if self.plate_number:
            self.plate_number = normalize_plate(self.plate_number)

        # Enforce max 3 vehicles per owner
        if not self.pk and self.owner_id:
            existing_count = Vehicle.objects.filter(owner=self.owner).count()
            if existing_count >= 3:
                raise ValidationError(
                    "You cannot register more than 3 vehicles."
                )

    def save(self, *args, **kwargs):
        if self.plate_number:
            self.plate_number = normalize_plate(self.plate_number)
        super().save(*args, **kwargs)

    # ----- Read helpers ----------------------------------------------------
    @property
    def is_accepted(self):
        return self.status == self.VehicleStatus.ACCEPTED

    @property
    def is_pending(self):
        return self.status == self.VehicleStatus.PENDING

    @property
    def is_refused(self):
        return self.status == self.VehicleStatus.REFUSED

    @property
    def is_expired(self):
        return self.status == self.VehicleStatus.DOCUMENTS_EXPIRED

    @property
    def full_name(self):
        return f"{self.brand} {self.model}"

    def has_all_documents(self):
        """Checks if all 3 mandatory documents have been uploaded."""
        types = set(self.documents.values_list("document_type", flat=True))
        return {
            Document.DocumentType.LICENSE,
            Document.DocumentType.REGISTRATION,
            Document.DocumentType.INSURANCE,
        }.issubset(types)

    # ----- Actions ---------------------------------------------------------
    def accept(self, admin=None):
        """Validate vehicle and promote owner to Driver."""
        self.status = self.VehicleStatus.ACCEPTED
        self.rejection_reason = ""
        self.verified_at = timezone.now()
        self.verified_by = admin
        self.save(update_fields=["status", "rejection_reason", "verified_at", "verified_by", "updated_at"])

        # Update all vehicle documents to VALID
        self.documents.filter(status=Document.DocumentStatus.PENDING).update(
            status=Document.DocumentStatus.VALID,
            updated_at=timezone.now(),
        )

        # Promote user to Driver
        if hasattr(self.owner, "promote_to_driver"):
            self.owner.promote_to_driver()

    def refuse(self, reason, admin=None):
        """Refuse vehicle with a mandatory reason."""
        self.status = self.VehicleStatus.REFUSED
        self.rejection_reason = reason
        self.verified_at = timezone.now()
        self.verified_by = admin
        self.save(update_fields=["status", "rejection_reason", "verified_at", "verified_by", "updated_at"])


# --------------------------------------------------------------------------- #
# Document Model
# --------------------------------------------------------------------------- #
class Document(models.Model):
    class DocumentType(models.TextChoices):
        LICENSE = "LICENSE", "Driving license"
        REGISTRATION = "REGISTRATION", "Registration (Carte grise)"
        INSURANCE = "INSURANCE", "Insurance policy"

    class DocumentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        VALID = "VALID", "Valid"
        EXPIRED = "EXPIRED", "Expired"
        REJECTED = "REJECTED", "Rejected"

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="vehicle",
    )
    document_type = models.CharField(
        "document type",
        max_length=20,
        choices=DocumentType.choices,
    )
    number = models.CharField(
        "document number",
        max_length=50,
        blank=True,
        help_text="Optional reference or document number",
    )
    expiry_date = models.DateField(
        "expiry date",
        null=True,
        blank=True,
        validators=[validate_future_date],
        help_text="Document expiration date",
    )
    file = models.FileField(
        "document file",
        upload_to=RandomDocumentName(),
        storage=get_private_storage,
        validators=[document_extension_validator, validate_document_size],
        help_text="JPG, PNG, WebP or PDF (max 5 MB).",
    )
    status = models.CharField(
        "status",
        max_length=20,
        choices=DocumentStatus.choices,
        default=DocumentStatus.PENDING,
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "document"
        verbose_name_plural = "documents"
        unique_together = ("vehicle", "document_type")
        ordering = ["document_type"]

    def __str__(self):
        return f"{self.get_document_type_display()} for {self.vehicle}"

    def clean(self):
        super().clean()
        if self.expiry_date and self.expiry_date <= date.today():
            raise ValidationError({"expiry_date": "The document expiry date must be in the future."})

    @property
    def is_expired(self):
        return bool(self.expiry_date and self.expiry_date < date.today())

    @property
    def days_until_expiry(self):
        if not self.expiry_date:
            return None
        return (self.expiry_date - date.today()).days

    @property
    def is_expiring_soon(self):
        days = self.days_until_expiry
        return days is not None and 0 <= days <= 30

    @property
    def is_pdf(self):
        return bool(self.file and self.file.name.lower().endswith(".pdf"))
