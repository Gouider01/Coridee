"""
Module 2 - Gestion des véhicules
Owner: Abdallah Salhi  ·  Branch: Gestion-vehicules

Forms for vehicle management and document uploads with accessible error styling.
"""
from datetime import date

from django import forms
from django.db import transaction

from users.forms import StyledFormMixin
from .models import (
    DOCUMENT_EXTENSIONS,
    MAX_DOCUMENT_MB,
    Document,
    Vehicle,
    document_extension_validator,
    normalize_plate,
    validate_document_size,
    validate_future_date,
    validate_tunisian_plate,
    validate_vehicle_year,
)

DATE_INPUT = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
FILE_INPUT = forms.ClearableFileInput(attrs={"accept": ".jpg,.jpeg,.png,.webp,.pdf"})


# --------------------------------------------------------------------------- #
# Vehicle Creation with Documents
# --------------------------------------------------------------------------- #
class VehicleCreateForm(StyledFormMixin, forms.ModelForm):
    # Driving license
    license_number = forms.CharField(
        label="Driving license number",
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "e.g. 12/345678"}),
    )
    license_expiry_date = forms.DateField(
        label="License expiry date",
        required=True,
        widget=DATE_INPUT,
        help_text="Must be a future date.",
    )
    license_file = forms.FileField(
        label="Driving license scan / photo",
        required=True,
        widget=FILE_INPUT,
        validators=[document_extension_validator, validate_document_size],
        help_text="JPG, PNG, WebP or PDF (max 5 MB).",
    )

    # Registration (Carte grise)
    registration_number = forms.CharField(
        label="Registration (Carte grise) number",
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "e.g. CG-987654"}),
    )
    registration_expiry_date = forms.DateField(
        label="Registration / Inspection expiry date",
        required=False,
        widget=DATE_INPUT,
        help_text="Inspection expiry date (optional).",
    )
    registration_file = forms.FileField(
        label="Registration document scan / photo",
        required=True,
        widget=FILE_INPUT,
        validators=[document_extension_validator, validate_document_size],
        help_text="JPG, PNG, WebP or PDF (max 5 MB).",
    )

    # Insurance
    insurance_number = forms.CharField(
        label="Insurance policy number",
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "e.g. POL-554433"}),
    )
    insurance_expiry_date = forms.DateField(
        label="Insurance expiry date",
        required=True,
        widget=DATE_INPUT,
        help_text="Must be a future date.",
    )
    insurance_file = forms.FileField(
        label="Insurance certificate scan / photo",
        required=True,
        widget=FILE_INPUT,
        validators=[document_extension_validator, validate_document_size],
        help_text="JPG, PNG, WebP or PDF (max 5 MB).",
    )

    class Meta:
        model = Vehicle
        fields = ["brand", "model", "color", "plate_number", "year", "seats"]
        widgets = {
            "brand": forms.TextInput(attrs={"placeholder": "e.g. Volkswagen, Peugeot, Renault"}),
            "model": forms.TextInput(attrs={"placeholder": "e.g. Golf 7, 208, Clio 4"}),
            "color": forms.TextInput(attrs={"placeholder": "e.g. White, Black, Grey"}),
            "plate_number": forms.TextInput(attrs={"placeholder": "e.g. 215 TU 8901 or 12345 RS"}),
            "year": forms.NumberInput(attrs={"placeholder": "2020", "min": "1980", "max": "2030"}),
            "seats": forms.NumberInput(attrs={"min": "1", "max": "8"}),
        }

    def __init__(self, *args, owner=None, **kwargs):
        self.owner = owner
        super().__init__(*args, **kwargs)
        for f in self.fields:
            if f != "registration_expiry_date":
                self.fields[f].required = True

    def clean_plate_number(self):
        raw = self.cleaned_data.get("plate_number", "")
        norm = normalize_plate(raw)
        validate_tunisian_plate(norm)
        qs = Vehicle.objects.filter(plate_number__iexact=norm)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A vehicle with this license plate is already registered.")
        return norm

    def clean_license_expiry_date(self):
        d = self.cleaned_data.get("license_expiry_date")
        validate_future_date(d)
        return d

    def clean_registration_expiry_date(self):
        d = self.cleaned_data.get("registration_expiry_date")
        if d:
            validate_future_date(d)
        return d

    def clean_insurance_expiry_date(self):
        d = self.cleaned_data.get("insurance_expiry_date")
        validate_future_date(d)
        return d

    def clean(self):
        cleaned_data = super().clean()
        if self.owner and not self.instance.pk:
            count = Vehicle.objects.filter(owner=self.owner).count()
            if count >= 3:
                raise forms.ValidationError(
                    "You already have 3 vehicles registered. You cannot add more."
                )
        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        vehicle = super().save(commit=False)
        if self.owner:
            vehicle.owner = self.owner
        vehicle.status = Vehicle.VehicleStatus.PENDING
        if commit:
            vehicle.save()

            # Create the 3 mandatory documents
            Document.objects.create(
                vehicle=vehicle,
                document_type=Document.DocumentType.LICENSE,
                number=self.cleaned_data.get("license_number"),
                expiry_date=self.cleaned_data.get("license_expiry_date"),
                file=self.cleaned_data.get("license_file"),
                status=Document.DocumentStatus.PENDING,
            )
            Document.objects.create(
                vehicle=vehicle,
                document_type=Document.DocumentType.REGISTRATION,
                number=self.cleaned_data.get("registration_number"),
                expiry_date=self.cleaned_data.get("registration_expiry_date"),
                file=self.cleaned_data.get("registration_file"),
                status=Document.DocumentStatus.PENDING,
            )
            Document.objects.create(
                vehicle=vehicle,
                document_type=Document.DocumentType.INSURANCE,
                number=self.cleaned_data.get("insurance_number"),
                expiry_date=self.cleaned_data.get("insurance_expiry_date"),
                file=self.cleaned_data.get("insurance_file"),
                status=Document.DocumentStatus.PENDING,
            )
        return vehicle


# --------------------------------------------------------------------------- #
# Vehicle Edit Form
# --------------------------------------------------------------------------- #
class VehicleEditForm(StyledFormMixin, forms.ModelForm):
    # Optional document updates
    license_number = forms.CharField(label="License number", max_length=50, required=False)
    license_expiry_date = forms.DateField(label="License expiry date", required=False, widget=DATE_INPUT)
    license_file = forms.FileField(
        label="Update license file",
        required=False,
        widget=FILE_INPUT,
        validators=[document_extension_validator, validate_document_size],
    )

    registration_number = forms.CharField(label="Registration number", max_length=50, required=False)
    registration_expiry_date = forms.DateField(label="Registration / Inspection expiry date", required=False, widget=DATE_INPUT)
    registration_file = forms.FileField(
        label="Update registration file",
        required=False,
        widget=FILE_INPUT,
        validators=[document_extension_validator, validate_document_size],
    )

    insurance_number = forms.CharField(label="Insurance number", max_length=50, required=False)
    insurance_expiry_date = forms.DateField(label="Insurance expiry date", required=False, widget=DATE_INPUT)
    insurance_file = forms.FileField(
        label="Update insurance file",
        required=False,
        widget=FILE_INPUT,
        validators=[document_extension_validator, validate_document_size],
    )

    class Meta:
        model = Vehicle
        fields = ["brand", "model", "color", "plate_number", "year", "seats"]
        widgets = {
            "brand": forms.TextInput(attrs={"placeholder": "e.g. Volkswagen"}),
            "model": forms.TextInput(attrs={"placeholder": "e.g. Golf"}),
            "color": forms.TextInput(attrs={"placeholder": "e.g. Grey"}),
            "plate_number": forms.TextInput(attrs={"placeholder": "215 TU 8901"}),
            "year": forms.NumberInput(attrs={"min": "1980", "max": "2030"}),
            "seats": forms.NumberInput(attrs={"min": "1", "max": "8"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Prepopulate document fields if available
            docs = {d.document_type: d for d in self.instance.documents.all()}
            lic = docs.get(Document.DocumentType.LICENSE)
            if lic:
                self.fields["license_number"].initial = lic.number
                self.fields["license_expiry_date"].initial = lic.expiry_date
            reg = docs.get(Document.DocumentType.REGISTRATION)
            if reg:
                self.fields["registration_number"].initial = reg.number
                self.fields["registration_expiry_date"].initial = reg.expiry_date
            ins = docs.get(Document.DocumentType.INSURANCE)
            if ins:
                self.fields["insurance_number"].initial = ins.number
                self.fields["insurance_expiry_date"].initial = ins.expiry_date

    def clean_plate_number(self):
        raw = self.cleaned_data.get("plate_number", "")
        norm = normalize_plate(raw)
        validate_tunisian_plate(norm)
        qs = Vehicle.objects.filter(plate_number__iexact=norm)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A vehicle with this license plate is already registered.")
        return norm

    def clean_license_expiry_date(self):
        d = self.cleaned_data.get("license_expiry_date")
        if d:
            validate_future_date(d)
        return d

    def clean_insurance_expiry_date(self):
        d = self.cleaned_data.get("insurance_expiry_date")
        if d:
            validate_future_date(d)
        return d

    @transaction.atomic
    def save(self, commit=True):
        vehicle = super().save(commit=False)
        needs_revalidation = False

        # If plate changed, requires revalidation
        if "plate_number" in self.changed_data:
            needs_revalidation = True

        if commit:
            # Update documents if files or info changed
            docs = {d.document_type: d for d in vehicle.documents.all()}

            # License
            lic = docs.get(Document.DocumentType.LICENSE)
            new_lic_file = self.cleaned_data.get("license_file")
            new_lic_num = self.cleaned_data.get("license_number")
            new_lic_exp = self.cleaned_data.get("license_expiry_date")
            if lic:
                if new_lic_file:
                    lic.file = new_lic_file
                    lic.status = Document.DocumentStatus.PENDING
                    needs_revalidation = True
                if new_lic_num is not None:
                    lic.number = new_lic_num
                if new_lic_exp:
                    lic.expiry_date = new_lic_exp
                lic.save()
            elif new_lic_file:
                Document.objects.create(
                    vehicle=vehicle,
                    document_type=Document.DocumentType.LICENSE,
                    number=new_lic_num or "",
                    expiry_date=new_lic_exp,
                    file=new_lic_file,
                )
                needs_revalidation = True

            # Registration
            reg = docs.get(Document.DocumentType.REGISTRATION)
            new_reg_file = self.cleaned_data.get("registration_file")
            new_reg_num = self.cleaned_data.get("registration_number")
            new_reg_exp = self.cleaned_data.get("registration_expiry_date")
            if reg:
                if new_reg_file:
                    reg.file = new_reg_file
                    reg.status = Document.DocumentStatus.PENDING
                    needs_revalidation = True
                if new_reg_num is not None:
                    reg.number = new_reg_num
                if new_reg_exp:
                    reg.expiry_date = new_reg_exp
                reg.save()
            elif new_reg_file:
                Document.objects.create(
                    vehicle=vehicle,
                    document_type=Document.DocumentType.REGISTRATION,
                    number=new_reg_num or "",
                    expiry_date=new_reg_exp,
                    file=new_reg_file,
                )
                needs_revalidation = True

            # Insurance
            ins = docs.get(Document.DocumentType.INSURANCE)
            new_ins_file = self.cleaned_data.get("insurance_file")
            new_ins_num = self.cleaned_data.get("insurance_number")
            new_ins_exp = self.cleaned_data.get("insurance_expiry_date")
            if ins:
                if new_ins_file:
                    ins.file = new_ins_file
                    ins.status = Document.DocumentStatus.PENDING
                    needs_revalidation = True
                if new_ins_num is not None:
                    ins.number = new_ins_num
                if new_ins_exp:
                    ins.expiry_date = new_ins_exp
                ins.save()
            elif new_ins_file:
                Document.objects.create(
                    vehicle=vehicle,
                    document_type=Document.DocumentType.INSURANCE,
                    number=new_ins_num or "",
                    expiry_date=new_ins_exp,
                    file=new_ins_file,
                )
                needs_revalidation = True

            if needs_revalidation:
                vehicle.status = Vehicle.VehicleStatus.PENDING
                vehicle.rejection_reason = ""

            vehicle.save()

        return vehicle


# --------------------------------------------------------------------------- #
# Admin Refusal Form
# --------------------------------------------------------------------------- #
class VehicleRefuseForm(StyledFormMixin, forms.Form):
    reason = forms.CharField(
        label="Reason for refusal",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Explain clearly what needs to be corrected (e.g. blurry scan of carte grise, expired insurance certificate)...",
            }
        ),
        required=True,
        help_text="This explanation will be shown directly to the vehicle owner.",
    )


# --------------------------------------------------------------------------- #
# Search and Filter Form
# --------------------------------------------------------------------------- #
class VehicleSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(
            attrs={"placeholder": "Search by plate, make, model or owner...", "autocomplete": "off"}
        ),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[("", "All statuses")] + list(Vehicle.VehicleStatus.choices),
        widget=forms.Select(),
    )
