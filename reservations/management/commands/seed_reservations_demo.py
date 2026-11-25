"""Demo data for the Sprint 1 validation:  python manage.py seed_reservations_demo

Creates 1 administrator, 2 drivers, 2 passengers and 3 trips (all passwords: Demo12345!).
Safe to run twice. Uses the Trip fields listed in trips/models.py.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from trips.models import Trip

PASSWORD = "Demo12345!"
PEOPLE = [
    ("admin@coride.tn", "Admin", "CoRide", "ADMINISTRATOR", None),
    ("leila@coride.tn", "Leila", "Khemiri", "DRIVER", "22111222"),
    ("youssef@coride.tn", "Youssef", "Haddad", "DRIVER", "23222333"),
    ("sami@coride.tn", "Sami", "Ben Salah", "PASSENGER", "24333444"),
    ("nour@coride.tn", "Nour", "Bouzid", "PASSENGER", "25444555"),
]


class Command(BaseCommand):
    help = "Create demo users and trips for the reservations demo."

    def handle(self, *args, **options):
        User = get_user_model()
        users = {}
        for email, first, last, kind, phone in PEOPLE:
            user, created = User.objects.get_or_create(
                email=email,
                defaults=dict(first_name=first, last_name=last, user_type=kind, phone_number=phone,
                              identity_verified=True, is_staff=(kind == "ADMINISTRATOR")),
            )
            if created:
                user.set_password(PASSWORD)
                user.save()
            users[first] = user

        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        trips = [
            ("Leila", "Tunis", "Sousse", timedelta(days=2, hours=3), 3, "12.50"),
            ("Youssef", "Sfax", "Tunis", timedelta(days=3, hours=1), 4, "18.00"),
            ("Leila", "Bizerte", "Tunis", timedelta(days=1, hours=5), 1, "7.00"),
        ]
        for driver, dep, arr, delta, seats, price in trips:
            Trip.objects.get_or_create(
                driver=users[driver], departure_city=dep, arrival_city=arr,
                defaults=dict(departure_datetime=now + delta, seats=seats, price_per_seat=price),
            )
        self.stdout.write(self.style.SUCCESS(
            f"Demo ready. Password for every account: {PASSWORD}\n"
            "  admin@coride.tn (admin) · leila@coride.tn, youssef@coride.tn (drivers) · "
            "sami@coride.tn, nour@coride.tn (passengers)"))
