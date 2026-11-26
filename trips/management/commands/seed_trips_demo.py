"""Demo data for Module 3:  uv run manage.py seed_trips_demo

Builds on `seed_reservations_demo` (same accounts, password Demo12345!). Gives every
driver a VALIDATED vehicle, links the demo trips to it, adds stops and more trips, and
gives the passenger Nour a PENDING vehicle (she cannot publish yet). Safe to run twice.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from trips.models import Stop, Trip
from vehicles.models import Vehicle

VEHICLES = [
    ("leila@coride.tn", "Peugeot", "208", "White", "205 TU 1234", 2021, 4, "ACCEPTED"),
    ("youssef@coride.tn", "Volkswagen", "Golf", "Grey", "188 TU 9087", 2019, 4, "ACCEPTED"),
    ("nour@coride.tn", "Renault", "Clio", "Red", "170 TU 5521", 2018, 3, "PENDING"),
]
TRIPS = [
    ("leila@coride.tn", "Tunis", "Sfax", timedelta(days=4, hours=2), 3, "22.00", ["Hammamet", "Sousse"]),
    ("youssef@coride.tn", "Sousse", "Tunis", timedelta(days=2, hours=6), 2, "11.00", ["Enfidha"]),
    ("leila@coride.tn", "Nabeul", "Tunis", timedelta(days=5, hours=1), 3, "8.50", []),
]
STOPS_FOR_EXISTING = {("Tunis", "Sousse"): ["Hammamet"], ("Sfax", "Tunis"): ["Sousse", "Hammamet"]}


class Command(BaseCommand):
    help = "Create vehicles, stops and extra trips for the Module 3 demo."

    def handle(self, *args, **options):
        call_command("seed_reservations_demo", verbosity=0)
        User = get_user_model()
        users = {u.email: u for u in User.objects.all()}

        vehicles = {}
        for email, brand, model, color, plate, year, seats, status in VEHICLES:
            vehicles[email], _ = Vehicle.objects.get_or_create(
                plate_number=plate,
                defaults=dict(owner=users[email], brand=brand, model=model, color=color,
                              year=year, seats=seats, status=status))

        for trip in Trip.objects.filter(vehicle__isnull=True):
            vehicle = vehicles.get(trip.driver.email)
            if vehicle and vehicle.status == "ACCEPTED":
                trip.vehicle = vehicle
                trip.save(update_fields=["vehicle", "updated_at"])
            for position, city in enumerate(STOPS_FOR_EXISTING.get(
                    (trip.departure_city, trip.arrival_city), []), start=1):
                Stop.objects.get_or_create(trip=trip, city=city, defaults={"order": position})

        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        for email, dep, arr, delta, seats, price, stops in TRIPS:
            trip, created = Trip.objects.get_or_create(
                driver=users[email], departure_city=dep, arrival_city=arr,
                defaults=dict(vehicle=vehicles[email], departure_datetime=now + delta,
                              seats=seats, price_per_seat=price))
            if created:
                for position, city in enumerate(stops, start=1):
                    Stop.objects.create(trip=trip, city=city, order=position)

        self.stdout.write(self.style.SUCCESS(
            f"Trips demo ready: {Trip.objects.count()} trips, {Stop.objects.count()} stops. "
            "Log in as leila@coride.tn or youssef@coride.tn (drivers), sami@coride.tn "
            "(passenger), nour@coride.tn (vehicle pending), admin@coride.tn. Password: Demo12345!"))
