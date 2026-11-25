"""Module 4 - Gestion des rÃ©servations  Â·  Owner: Selim Aschi  Â·  Branch: Gestion-Reservations

Pages
  /reservations/                 passenger  Â· my bookings (filter by status)
  /reservations/trips/           passenger  Â· trips open for booking
  /reservations/book/<trip>/     passenger  Â· book seats
  /reservations/<id>/            passenger, driver of the trip, admin Â· detail
  /reservations/<id>/edit/       passenger  Â· change seats of a pending request
  /reservations/<id>/cancel/     passenger  Â· cancel (2 h rule)
  /reservations/requests/        driver     Â· requests received, accept or refuse
  /reservations/manage/          admin      Â· all reservations, search, delete
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from trips.models import Trip
from users.views import admin_required

from .forms import ReservationFilterForm, SeatsForm
from .models import Reservation, ReservationStatus
from .services import (
    ReservationError,
    accept_request,
    book_seats,
    can_cancel,
    cancel_booking,
    delete_reservation,
    refuse_request,
    update_seats,
)


def _passenger_required(view):
    """Logged-in passengers (drivers are passengers too). Admins get a 403."""

    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_passenger:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    wrapper.__name__ = view.__name__
    wrapper.__doc__ = view.__doc__
    return wrapper


def _driver_required(view):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_driver:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    wrapper.__name__ = view.__name__
    wrapper.__doc__ = view.__doc__
    return wrapper


def _filtered(request, queryset):
    """Apply the q / status filter of the list pages."""
    form = ReservationFilterForm(request.GET or None)
    q = status = ""
    if form.is_valid():
        q = form.cleaned_data["q"].strip()
        status = form.cleaned_data["status"]
    if status:
        queryset = queryset.filter(status=status)
    if q:
        queryset = queryset.filter(
            Q(trip__departure_city__icontains=q)
            | Q(trip__arrival_city__icontains=q)
            | Q(passenger__first_name__icontains=q)
            | Q(passenger__last_name__icontains=q)
            | Q(passenger__email__icontains=q)
            | Q(ticket_code__iexact=q)
        )
    return queryset, q, status


# --------------------------------------------------------------------------- #
# Passenger
# --------------------------------------------------------------------------- #
@login_required
def index(request):
    """My bookings. Administrators go to the full list."""
    if request.user.is_administrator:
        return redirect("reservations:manage")
    Reservation.objects.expire_overdue()
    mine = Reservation.objects.filter(passenger=request.user).select_related("trip", "trip__driver")
    reservations, q, status = _filtered(request, mine)
    for r in reservations:
        r.cancel_allowed, r.cancel_reason = can_cancel(r)
    return render(request, "reservations/index.html", {
        "reservations": reservations, "q": q, "status": status,
        "statuses": ReservationStatus.choices, "total": mine.count(),
        "pending_count": mine.filter(status=ReservationStatus.PENDING).count(),
        "accepted_count": mine.filter(status=ReservationStatus.ACCEPTED).count(),
    })


@_passenger_required
def available_trips(request):
    """Trips that can still be booked (until the trips module offers its own search)."""
    trips = (Trip.objects.filter(status="OPEN", remaining_seats__gt=0,
                                 departure_datetime__gt=timezone.now())
             .exclude(driver=request.user).select_related("driver"))
    q = request.GET.get("q", "").strip()
    if q:
        trips = trips.filter(Q(departure_city__icontains=q) | Q(arrival_city__icontains=q))
    return render(request, "reservations/available.html", {"trips": trips, "q": q})


@_passenger_required
def book(request, trip_id):
    trip = get_object_or_404(Trip.objects.select_related("driver"), pk=trip_id)
    form = SeatsForm(request.POST or None, trip=trip, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            reservation = book_seats(request.user, trip.pk, form.cleaned_data["seats"])
        except ReservationError as error:   # someone else took the seats a moment ago
            form.add_error("seats", str(error))
        else:
            messages.success(request, "Request sent. The driver will accept or refuse it soon.")
            return redirect("reservations:detail", pk=reservation.pk)
    return render(request, "reservations/book.html", {"form": form, "trip": trip})


@login_required
def detail(request, pk):
    reservation = get_object_or_404(
        Reservation.objects.select_related("trip", "trip__driver", "passenger"), pk=pk
    )
    user = request.user
    is_owner = reservation.passenger_id == user.pk
    is_driver = reservation.trip.driver_id == user.pk
    if not (is_owner or is_driver or user.is_administrator):
        raise PermissionDenied
    cancel_allowed, cancel_reason = can_cancel(reservation)
    return render(request, "reservations/detail.html", {
        "r": reservation, "is_owner": is_owner, "is_driver": is_driver,
        "cancel_allowed": cancel_allowed and is_owner, "cancel_reason": cancel_reason,
        # The phone number is shown only once the driver accepted (privacy rule).
        "show_phones": reservation.status in (ReservationStatus.ACCEPTED, ReservationStatus.BOARDED,
                                              ReservationStatus.COMPLETED) or user.is_administrator,
    })


@_passenger_required
def edit(request, pk):
    reservation = get_object_or_404(Reservation.objects.select_related("trip"), pk=pk,
                                    passenger=request.user)
    if not reservation.is_pending:
        messages.error(request, "Only a pending request can be changed.")
        return redirect("reservations:detail", pk=pk)
    form = SeatsForm(request.POST or None, trip=reservation.trip, user=request.user,
                     reservation=reservation)
    if request.method == "POST" and form.is_valid():
        try:
            update_seats(pk, request.user, form.cleaned_data["seats"])
        except ReservationError as error:
            form.add_error("seats", str(error))
        else:
            messages.success(request, "Your request has been updated.")
            return redirect("reservations:detail", pk=pk)
    return render(request, "reservations/edit.html", {"form": form, "r": reservation, "trip": reservation.trip})


@_passenger_required
def cancel(request, pk):
    reservation = get_object_or_404(Reservation.objects.select_related("trip", "trip__driver"),
                                    pk=pk, passenger=request.user)
    allowed, reason = can_cancel(reservation)
    if request.method == "POST":
        try:
            cancel_booking(pk, request.user)
        except ReservationError as error:
            messages.error(request, str(error))
            return redirect("reservations:detail", pk=pk)
        messages.success(request, "Your booking is cancelled and the seats are free again.")
        return redirect("reservations:index")
    return render(request, "reservations/cancel.html", {"r": reservation, "allowed": allowed, "reason": reason})


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
@_driver_required
def driver_requests(request):
    """Requests received on my trips."""
    Reservation.objects.expire_overdue()
    received = Reservation.objects.filter(trip__driver=request.user).select_related("trip", "passenger")
    reservations, q, status = _filtered(request, received)
    return render(request, "reservations/requests.html", {
        "reservations": reservations, "q": q, "status": status,
        "statuses": ReservationStatus.choices, "total": received.count(),
        "pending_count": received.filter(status=ReservationStatus.PENDING).count(),
    })


def _decide(request, pk, action, success):
    try:
        action(pk, request.user)
    except Reservation.DoesNotExist:
        raise PermissionDenied
    except ReservationError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, success)
    return redirect("reservations:requests")


@_driver_required
@require_POST
def accept(request, pk):
    return _decide(request, pk, accept_request, "Request accepted. The passenger can now see the ticket code.")


@_driver_required
@require_POST
def refuse(request, pk):
    return _decide(request, pk, refuse_request, "Request refused. The seats are free again.")


# --------------------------------------------------------------------------- #
# Administrator
# --------------------------------------------------------------------------- #
@admin_required
def manage(request):
    """All reservations on the platform."""
    Reservation.objects.expire_overdue()
    everything = Reservation.objects.select_related("trip", "trip__driver", "passenger")
    reservations, q, status = _filtered(request, everything)
    return render(request, "reservations/manage.html", {
        "reservations": reservations, "q": q, "status": status,
        "statuses": ReservationStatus.choices, "total": everything.count(),
        "pending_count": everything.filter(status=ReservationStatus.PENDING).count(),
        "accepted_count": everything.filter(status=ReservationStatus.ACCEPTED).count(),
        "closed_count": everything.filter(status__in=[
            ReservationStatus.CANCELLED, ReservationStatus.REFUSED, ReservationStatus.EXPIRED]).count(),
    })


@admin_required
def manage_delete(request, pk):
    reservation = get_object_or_404(Reservation.objects.select_related("trip", "passenger"), pk=pk)
    if request.method == "POST":
        delete_reservation(pk)
        messages.success(request, "The reservation has been deleted.")
        return redirect("reservations:manage")
    return render(request, "reservations/manage_delete.html", {"r": reservation})

