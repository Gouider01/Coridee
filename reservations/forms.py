"""Module 4 - forms with input validation (errors appear under the field)."""
from django import forms

from .models import MAX_SEATS_PER_BOOKING, ReservationStatus
from .services import ReservationError, check_can_book


class SeatsForm(forms.Form):
    """Book seats on a trip, or change the seats of a pending request."""

    seats = forms.IntegerField(
        label="Number of seats",
        min_value=1,
        max_value=MAX_SEATS_PER_BOOKING,
        initial=1,
        error_messages={
            "required": "Enter the number of seats.",
            "invalid": "Enter a whole number.",
            "min_value": "Choose at least 1 seat.",
            "max_value": f"You can book at most {MAX_SEATS_PER_BOOKING} seats at once.",
        },
        widget=forms.NumberInput(attrs={"inputmode": "numeric", "min": 1, "max": MAX_SEATS_PER_BOOKING}),
    )

    def __init__(self, *args, trip, user, reservation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.trip, self.user, self.reservation = trip, user, reservation
        if reservation is not None and not self.is_bound:
            self.initial["seats"] = reservation.seats

    def clean_seats(self):
        seats = self.cleaned_data["seats"]
        try:
            check_can_book(self.user, self.trip, seats, ignore=self.reservation)
        except ReservationError as error:
            raise forms.ValidationError(str(error))
        return seats

    def full_clean(self):
        super().full_clean()
        if "seats" in self.errors:
            self.fields["seats"].widget.attrs.update(
                {"aria-invalid": "true", "aria-describedby": "id_seats_error"}
            )


class ReservationFilterForm(forms.Form):
    """Search + status filter for the lists."""

    q = forms.CharField(required=False, max_length=100)
    status = forms.ChoiceField(
        required=False,
        choices=[("", "All statuses")] + list(ReservationStatus.choices),
    )
