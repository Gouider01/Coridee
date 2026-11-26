"""Module 3 - forms with input validation (errors appear under the field)."""
from datetime import timedelta

from django import forms
from django.db.models import Q
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from vehicles.models import Vehicle

from .models import MAX_PRICE, MAX_STOPS, Stop, Trip, TripStatus, is_valid_city, normalize_city
from .services import sync_status

MAX_DAYS_AHEAD = 180
CITY_ATTRS = {"list": "tn-cities", "autocomplete": "off", "maxlength": 60}


def _clean_city(value):
    city = normalize_city(value)
    if not is_valid_city(city):
        raise forms.ValidationError("Enter a valid city name (letters only, at least 2).")
    return city


class TripForm(forms.ModelForm):
    """Create or edit a trip. `driver` is the logged-in driver."""

    LOCKED_WHEN_BOOKED = ("vehicle", "departure_city", "arrival_city", "departure_datetime",
                          "price_per_seat")

    class Meta:
        model = Trip
        fields = ["vehicle", "departure_city", "arrival_city", "departure_datetime",
                  "seats", "price_per_seat", "notes"]
        labels = {"departure_city": "From", "arrival_city": "To", "vehicle": "Vehicle",
                  "seats": "Seats offered", "price_per_seat": "Price per seat (TND)"}
        widgets = {
            "departure_city": forms.TextInput(attrs={**CITY_ATTRS, "placeholder": "e.g. Tunis"}),
            "arrival_city": forms.TextInput(attrs={**CITY_ATTRS, "placeholder": "e.g. Sousse"}),
            "departure_datetime": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "seats": forms.NumberInput(attrs={"min": 1, "max": 8, "inputmode": "numeric"}),
            "price_per_seat": forms.NumberInput(
                attrs={"min": "0.5", "max": MAX_PRICE, "step": "0.5", "inputmode": "decimal"}),
            "notes": forms.Textarea(attrs={"rows": 3, "maxlength": 300}),
        }
        error_messages = {
            "departure_city": {"required": "Enter the departure city."},
            "arrival_city": {"required": "Enter the arrival city."},
            "departure_datetime": {"required": "Choose the departure date and time.",
                                   "invalid": "Enter a valid date and time."},
            "seats": {"required": "Enter the number of seats.", "invalid": "Enter a whole number.",
                      "min_value": "Offer at least 1 seat.", "max_value": "At most 8 seats."},
            "price_per_seat": {"required": "Enter the price per seat.", "invalid": "Enter a valid price."},
            "vehicle": {"required": "Choose the vehicle you will drive."},
        }

    def __init__(self, *args, driver, **kwargs):
        super().__init__(*args, **kwargs)
        self.driver = driver
        self.fields["departure_datetime"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"]
        vehicle = self.fields["vehicle"]
        current = Q(pk=self.instance.vehicle_id) if self.instance.vehicle_id else Q(pk__in=[])
        vehicle.queryset = Vehicle.objects.filter(
            Q(owner=driver, status=Vehicle.VehicleStatus.ACCEPTED) | Q(owner=driver) & current
        )
        vehicle.required = True
        vehicle.empty_label = "Choose your vehicle"
        vehicle.label_from_instance = lambda v: f"{v.brand} {v.model} · {v.plate_number} · {v.seats} seats"
        self.fields["notes"].required = False

        self.held = self.instance.held_seats if self.instance.pk else 0
        self.locked = bool(self.instance.pk and self.held and self.instance.has_bookings)
        if self.locked:
            for name in self.LOCKED_WHEN_BOOKED:
                if name == "vehicle" and not self.instance.vehicle_id:
                    continue  # legacy trip without vehicle: the driver must pick one
                self.fields[name].disabled = True
            self.fields["seats"].help_text = (
                f"{self.held} seat{'s' if self.held != 1 else ''} already booked: "
                "you cannot offer fewer. Route, date, price and vehicle are locked.")

    def clean_departure_city(self):
        return _clean_city(self.cleaned_data["departure_city"])

    def clean_arrival_city(self):
        return _clean_city(self.cleaned_data["arrival_city"])

    def clean_departure_datetime(self):
        when = self.cleaned_data["departure_datetime"]
        if self.fields["departure_datetime"].disabled:
            return when
        when = when.replace(second=0, microsecond=0)
        now = timezone.now()
        if when <= now:
            raise forms.ValidationError("The departure must be in the future.")
        if when > now + timedelta(days=MAX_DAYS_AHEAD):
            raise forms.ValidationError(f"You can publish a trip up to {MAX_DAYS_AHEAD} days ahead.")
        return when

    def clean_price_per_seat(self):
        price = self.cleaned_data["price_per_seat"]
        if price <= 0:
            raise forms.ValidationError("The price must be greater than 0.")
        if price > MAX_PRICE:
            raise forms.ValidationError(f"The price cannot exceed {MAX_PRICE} TND per seat.")
        return price

    def clean(self):
        data = super().clean()
        dep, arr = data.get("departure_city"), data.get("arrival_city")
        if dep and arr and dep.casefold() == arr.casefold():
            self.add_error("arrival_city", "Departure and arrival must be different cities.")

        vehicle, seats = data.get("vehicle"), data.get("seats")
        if vehicle is not None:
            if not vehicle.is_accepted and not self.fields["vehicle"].disabled:
                self.add_error("vehicle", "This vehicle is not validated: choose another one.")
            elif seats and seats > vehicle.seats:
                self.add_error("seats", f"Your vehicle has {vehicle.seats} passenger "
                                        f"seat{'s' if vehicle.seats != 1 else ''}: you cannot offer more.")
        if seats and self.held and seats < self.held:
            self.add_error("seats", f"{self.held} seat{'s are' if self.held != 1 else ' is'} "
                                    "already booked: you cannot offer fewer.")

        when = data.get("departure_datetime")
        if when and not self.fields["departure_datetime"].disabled:
            clash = Trip.objects.filter(
                driver=self.driver, departure_datetime=when,
                status__in=[TripStatus.OPEN, TripStatus.FULL],
            ).exclude(pk=self.instance.pk)
            if clash.exists():
                self.add_error("departure_datetime",
                               "You already have a trip leaving at this exact time.")
        return data

    def save(self, commit=True):
        trip = super().save(commit=False)
        trip.driver = self.driver
        if trip.pk:
            sync_status(trip, held=self.held)
        else:
            trip.remaining_seats = trip.seats
            trip.status = TripStatus.OPEN
        if commit:
            trip.save()
        return trip


class StopForm(forms.ModelForm):
    class Meta:
        model = Stop
        fields = ["city"]
        labels = {"city": "Stop"}
        widgets = {"city": forms.TextInput(attrs={**CITY_ATTRS, "placeholder": "Optional stop"})}
        error_messages = {"city": {"required": "Enter the stop city or tick “Remove”."}}

    def clean_city(self):
        return _clean_city(self.cleaned_data["city"])


class BaseStopFormSet(BaseInlineFormSet):
    """Stops must differ from the departure, the arrival and from each other.

    The view sets `route = (departure, arrival)` once the trip form is valid.
    """

    route = None

    def clean(self):
        super().clean()
        dep, arr = ((c.casefold() for c in self.route) if self.route else (None, None))
        seen = set()
        for form in self.forms:
            data = getattr(form, "cleaned_data", None)
            if not data or data.get("DELETE") or not data.get("city"):
                continue
            key = data["city"].casefold()
            if key in (dep, arr):
                form.add_error("city", "A stop must differ from the departure and arrival cities.")
            elif key in seen:
                form.add_error("city", "This stop is already in the list.")
            seen.add(key)

    def save(self, commit=True):
        saved = super().save(commit)
        if commit:  # number the stops in the order the driver wrote them
            position = 0
            for form in self.forms:
                stop = form.instance
                if stop.pk is None or form.cleaned_data.get("DELETE"):
                    continue
                position += 1
                if stop.order != position:
                    Stop.objects.filter(pk=stop.pk).update(order=position)
                    stop.order = position
        return saved


def stop_formset(*, instance=None, data=None):
    """Formset for the stops of `instance`; 3 blank rows on a new trip, 2 when editing."""
    extra = 2 if instance is not None and instance.pk else 3
    factory = inlineformset_factory(
        Trip, Stop, form=StopForm, formset=BaseStopFormSet, extra=extra,
        max_num=MAX_STOPS, validate_max=True, can_delete=True,
    )
    return factory(data, instance=instance, prefix="stops")


class TripSearchForm(forms.Form):
    """Passenger search: route and date."""

    from_city = forms.CharField(
        label="From", required=False, max_length=60,
        widget=forms.TextInput(attrs={**CITY_ATTRS, "placeholder": "Leaving from"}),
    )
    to_city = forms.CharField(
        label="To", required=False, max_length=60,
        widget=forms.TextInput(attrs={**CITY_ATTRS, "placeholder": "Going to"}),
    )
    date = forms.DateField(
        label="Date", required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        error_messages={"invalid": "Enter a valid date."},
    )
    seats = forms.IntegerField(
        label="Seats needed", required=False, min_value=1, max_value=8,
        widget=forms.NumberInput(attrs={"min": 1, "max": 8, "placeholder": "1"}),
        error_messages={"invalid": "Enter a whole number.", "min_value": "At least 1 seat.",
                        "max_value": "At most 8 seats."},
    )

    def clean_from_city(self):
        return normalize_city(self.cleaned_data.get("from_city"))

    def clean_to_city(self):
        return normalize_city(self.cleaned_data.get("to_city"))

    def clean_date(self):
        day = self.cleaned_data.get("date")
        if day and day < timezone.localdate():
            raise forms.ValidationError("Choose today or a later date.")
        return day

    def clean(self):
        data = super().clean()
        a, b = data.get("from_city"), data.get("to_city")
        if a and b and a.casefold() == b.casefold():
            self.add_error("to_city", "Departure and arrival must be different cities.")
        return data


class TripManageFilterForm(forms.Form):
    """Administrator list: search + status filter."""

    q = forms.CharField(required=False, max_length=100)
    status = forms.ChoiceField(
        required=False, choices=[("", "All statuses")] + list(TripStatus.choices)
    )
