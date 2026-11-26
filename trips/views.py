"""Module 3 - Gestion des trajets  ·  Owner: Wasim Snoussi  ·  Branch: Gestion-Trajets

Pages
  /trips/                  everyone logged in · search trips by route and date (admins -> manage)
  /trips/<id>/             everyone logged in · trip detail (book button for passengers)
  /trips/mine/             driver             · my published trips
  /trips/new/              driver             · publish a trip (route, stops, date, seats, price)
  /trips/<id>/edit/        driver             · edit my trip
  /trips/<id>/cancel/      driver             · cancel my trip (open bookings are cancelled)
  /trips/<id>/complete/    driver             · confirm the trip took place (unlocks reviews)
  /trips/manage/           admin              · all trips, search, delete
  /trips/manage/<id>/delete/
"""
from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from communication.models import Review
from users.views import admin_required
from vehicles.models import Vehicle

from .cities import TUNISIAN_CITIES
from .forms import TripForm, TripManageFilterForm, TripSearchForm, stop_formset
from .models import Trip, TripStatus
from .services import TripError, cancel_trip, complete_trip, delete_trip


def _driver_required(view):
    """Logged-in drivers only. A passenger is sent to the vehicles page to become one."""

    @login_required
    def wrapper(request, *args, **kwargs):
        user = request.user
        if user.is_administrator:
            raise PermissionDenied
        has_vehicle = Vehicle.objects.filter(
            owner=user, status=Vehicle.VehicleStatus.ACCEPTED).exists()
        if not user.is_driver or not has_vehicle:
            messages.info(request, "To publish trips you need a vehicle validated by our team. "
                                   "Register yours here.")
            return redirect("vehicles:index")
        return view(request, *args, **kwargs)

    wrapper.__name__ = view.__name__
    wrapper.__doc__ = view.__doc__
    return wrapper


def _day_range(day):
    start = timezone.make_aware(datetime.combine(day, time.min))
    return start, start + timedelta(days=1)


@login_required
def index(request):
    """Search the trips that can still be booked, by route and date."""
    if request.user.is_administrator:
        return redirect("trips:manage")

    form = TripSearchForm(request.GET or None)
    searched = bool(request.GET) and any(request.GET.get(k) for k in ("from_city", "to_city", "date", "seats"))
    trips = Trip.objects.bookable().exclude(driver=request.user)

    if form.is_bound and not form.is_valid():
        trips = trips.none()
    elif form.is_bound:
        data = form.cleaned_data
        origin, destination = data["from_city"], data["to_city"]
        if origin:
            trips = trips.filter(Q(departure_city__icontains=origin) | Q(stops__city__icontains=origin))
        if destination:
            trips = trips.filter(Q(arrival_city__icontains=destination) | Q(stops__city__icontains=destination))
        if data["date"]:
            start, end = _day_range(data["date"])
            trips = trips.filter(departure_datetime__gte=start, departure_datetime__lt=end)
        if data["seats"]:
            trips = trips.filter(remaining_seats__gte=data["seats"])

    trips = list(trips.select_related("driver", "vehicle").prefetch_related("stops").distinct())
    if form.is_bound and form.is_valid():
        origin, destination = form.cleaned_data["from_city"], form.cleaned_data["to_city"]
        if origin or destination:   # the origin must come before the destination on the route
            trips = [t for t in trips if t.serves(origin, destination)]

    return render(request, "trips/index.html", {
        "form": form, "trips": trips, "searched": searched, "cities": TUNISIAN_CITIES,
        "is_driver": request.user.is_driver,
    })


@login_required
def detail(request, pk):
    trip = get_object_or_404(
        Trip.objects.select_related("driver", "vehicle").prefetch_related("stops"), pk=pk)
    user = request.user
    is_owner = trip.driver_id == user.pk
    my_booking = None
    if user.is_passenger and not is_owner:
        my_booking = trip.reservations.filter(passenger=user).order_by("-reservation_date").first()
    if trip.is_cancelled and not (is_owner or user.is_administrator or my_booking):
        raise Http404

    pending = trip.reservations.filter(status="PENDING").count() if is_owner else 0

    # Module 5: after a completed trip, the driver and each passenger review each other.
    reviewed, review_passengers = set(), []
    if trip.is_completed:
        reviewed = set(Review.objects.filter(trip_reference=str(trip.pk), reviewer=user)
                       .values_list("target_id", flat=True))
        if is_owner:
            review_passengers = [
                (r.passenger, r.passenger_id in reviewed)
                for r in trip.reservations.select_related("passenger").filter(status="COMPLETED")
            ]
    return render(request, "trips/detail.html", {
        "trip": trip, "stops": list(trip.stops.all()), "is_owner": is_owner,
        "can_book": user.is_passenger and not is_owner and trip.is_bookable,
        "my_booking": my_booking, "pending_count": pending,
        "show_plate": is_owner or user.is_administrator,
        "can_review_driver": bool(my_booking and my_booking.status == "COMPLETED"),
        "reviewed_driver": trip.driver_id in reviewed,
        "review_passengers": review_passengers,
    })


def _validate_together(form, stops):
    """Validate the trip form and its stops; the stops need the validated cities."""
    form_ok = form.is_valid()
    data = getattr(form, "cleaned_data", {})
    stops.route = (data["departure_city"], data["arrival_city"]) \
        if data.get("departure_city") and data.get("arrival_city") else None
    stops_ok = stops.is_valid()
    return form_ok and stops_ok


@_driver_required
def create(request):
    form = TripForm(request.POST or None, driver=request.user)
    stops = stop_formset(data=request.POST or None)
    if request.method == "POST" and _validate_together(form, stops):
        with transaction.atomic():
            trip = form.save()
            stops.instance = trip
            stops.save()
        messages.success(request, "Your trip is published. Passengers can now book it.")
        return redirect("trips:detail", pk=trip.pk)
    return render(request, "trips/form.html", {
        "form": form, "stops": stops, "is_edit": False, "cities": TUNISIAN_CITIES})


@_driver_required
def mine(request):
    """The trips I published."""
    qs = (Trip.objects.filter(driver=request.user)
          .annotate(pending=Count("reservations", filter=Q(reservations__status="PENDING")))
          .select_related("vehicle").order_by("-departure_datetime"))
    status = request.GET.get("status", "")
    trips = qs.filter(status=status) if status in TripStatus.values else qs
    return render(request, "trips/mine.html", {
        "trips": trips, "status": status, "statuses": TripStatus.choices, "total": qs.count(),
        "upcoming_count": Trip.objects.filter(driver=request.user).upcoming().count(),
        "pending_total": sum(t.pending for t in qs),
    })


@_driver_required
def edit(request, pk):
    trip = get_object_or_404(Trip, pk=pk, driver=request.user)
    if not trip.can_edit:
        messages.error(request, "Only a trip that has not left yet can be edited.")
        return redirect("trips:detail", pk=pk)

    if request.method == "POST":
        with transaction.atomic():   # booking and editing cannot cross each other's seats
            locked = Trip.objects.select_for_update().get(pk=pk)
            if not locked.can_edit:
                messages.error(request, "This trip can no longer be edited.")
                return redirect("trips:detail", pk=pk)
            form = TripForm(request.POST, instance=locked, driver=request.user)
            stops = stop_formset(instance=locked, data=request.POST)
            if _validate_together(form, stops):
                form.save()
                stops.save()
                messages.success(request, "Your trip has been updated.")
                return redirect("trips:detail", pk=pk)
        trip = Trip.objects.get(pk=pk)   # the invalid form changed the in-memory copy
    else:
        form = TripForm(instance=trip, driver=request.user)
        stops = stop_formset(instance=trip)
    return render(request, "trips/form.html", {
        "form": form, "stops": stops, "trip": trip, "is_edit": True, "cities": TUNISIAN_CITIES})


@_driver_required
def cancel(request, pk):
    trip = get_object_or_404(Trip, pk=pk, driver=request.user)
    if request.method == "POST":
        try:
            _, count = cancel_trip(pk, request.user)
        except TripError as error:
            messages.error(request, str(error))
            return redirect("trips:detail", pk=pk)
        messages.success(request, "Your trip is cancelled." + (
            f" {count} booking{'s were' if count != 1 else ' was'} cancelled and the passengers "
            "can no longer ride." if count else ""))
        return redirect("trips:mine")
    return render(request, "trips/cancel.html", {
        "trip": trip, "open_bookings": trip.open_booking_count})


@_driver_required
@require_POST
def complete(request, pk):
    get_object_or_404(Trip, pk=pk, driver=request.user)
    try:
        complete_trip(pk, request.user)
    except TripError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Trip completed. Passengers can now leave their review.")
    return redirect("trips:detail", pk=pk)


@admin_required
def manage(request):
    """All trips of the platform."""
    everything = Trip.objects.select_related("driver", "vehicle")
    form = TripManageFilterForm(request.GET or None)
    q = status = ""
    trips = everything
    if form.is_valid():
        q, status = form.cleaned_data["q"].strip(), form.cleaned_data["status"]
    if status:
        trips = trips.filter(status=status)
    if q:
        trips = trips.filter(
            Q(departure_city__icontains=q) | Q(arrival_city__icontains=q)
            | Q(driver__first_name__icontains=q) | Q(driver__last_name__icontains=q)
            | Q(driver__email__icontains=q))
    return render(request, "trips/manage.html", {
        "trips": trips.order_by("-departure_datetime"), "q": q, "status": status,
        "statuses": TripStatus.choices, "total": everything.count(),
        "open_count": everything.filter(status=TripStatus.OPEN).count(),
        "full_count": everything.filter(status=TripStatus.FULL).count(),
        "cancelled_count": everything.filter(status=TripStatus.CANCELLED).count(),
    })


@admin_required
def manage_delete(request, pk):
    trip = get_object_or_404(Trip.objects.select_related("driver"), pk=pk)
    if request.method == "POST":
        try:
            delete_trip(pk)
        except TripError as error:
            messages.error(request, str(error))
            return redirect("trips:manage")
        messages.success(request, "The trip has been deleted.")
        return redirect("trips:manage")
    return render(request, "trips/manage_delete.html", {
        "trip": trip, "booking_count": trip.reservations.count()})
