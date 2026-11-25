"""Create dummy vehicles and documents covering every status, for manual testing.

    python manage.py seed_vehicles           # add demo data
    python manage.py seed_vehicles --reset   # delete previous demo vehicles first

Shares the demo accounts of seed_communication (@demo.coride.tn, password Demo12345!)
and adds an administrator: admin@demo.coride.tn.
"""
import io
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from vehicles.models import Document, Vehicle

DOMAIN = "demo.coride.tn"
PASSWORD = "Demo12345!"
D, V = Document.DocumentType, Vehicle.VehicleStatus

USERS = [
    ("admin", "Nadia", "Admin", "ADMINISTRATOR"),
    ("amine", "Amine", "Ben Salah", "DRIVER"),
    ("sarra", "Sarra", "Trabelsi", "PASSENGER"),
    ("youssef", "Youssef", "Gharbi", "DRIVER"),
    ("ines", "Ines", "Mansour", "PASSENGER"),
    ("karim", "Karim", "Jlassi", "PASSENGER"),
]

PDF = (b"%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
       b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
       b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]>>endobj\n"
       b"trailer<</Root 1 0 R>>\n%%EOF\n")


def png_bytes(label_color):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (320, 200), label_color).save(buf, "PNG")
    return buf.getvalue()


# plate, brand, model, color, year, seats, owner, status, reason, docs
# docs: {type: (days_until_expiry or None, status, "pdf"|"png")}
def vehicle_specs():
    ok = lambda d, s="PENDING", f="png": (d, s, f)
    return [
        # PENDING with all 3 documents: use it to test Accept / Refuse as admin
        ("101 TU 2001", "Peugeot", "208", "White", 2021, 4, "sarra", V.PENDING, "",
         {D.LICENSE: ok(400), D.REGISTRATION: ok(300, f="pdf"), D.INSURANCE: ok(200)}),
        # PENDING, second one, so the admin list has several rows
        ("2345 TU 88", "Renault", "Clio", "Red", 2019, 3, "ines", V.PENDING, "",
         {D.LICENSE: ok(500), D.REGISTRATION: ok(450), D.INSURANCE: ok(90, f="pdf")}),
        # ACCEPTED, insurance expiring in 12 days (expiring-soon warning)
        ("3456 TU 120", "Volkswagen", "Golf", "Grey", 2020, 4, "amine", V.ACCEPTED, "",
         {D.LICENSE: ok(700, "VALID"), D.REGISTRATION: ok(600, "VALID", "pdf"),
          D.INSURANCE: ok(12, "VALID")}),
        # ACCEPTED, second vehicle of the same owner
        ("12345 RS", "Dacia", "Duster", "Black", 2022, 5, "amine", V.ACCEPTED, "",
         {D.LICENSE: ok(700, "VALID"), D.REGISTRATION: ok(650, "VALID"),
          D.INSURANCE: ok(300, "VALID")}),
        # REFUSED with a reason
        ("77 TU 9090", "Fiat", "Punto", "Blue", 2008, 3, "ines", V.REFUSED,
         "Insurance document is unreadable. Please upload a clear scan.",
         {D.LICENSE: ok(100, "REJECTED"), D.REGISTRATION: ok(100, "VALID"),
          D.INSURANCE: ok(100, "REJECTED")}),
        # DOCUMENTS_EXPIRED: documents past their expiry date
        ("500 TU 3003", "Kia", "Picanto", "Yellow", 2018, 3, "youssef", V.DOCUMENTS_EXPIRED, "",
         {D.LICENSE: ok(-40, "EXPIRED"), D.REGISTRATION: ok(200, "VALID"),
          D.INSURANCE: ok(-5, "EXPIRED", "pdf")}),
        # PENDING with only 1 of 3 documents (has_all_documents() is False)
        ("888 TU 4444", "Hyundai", "i10", "Silver", 2023, 4, "youssef", V.PENDING, "",
         {D.LICENSE: ok(365)}),
        # karim owns 3 vehicles: the "Add vehicle" button must be blocked (max 3)
        ("1 TU 1111", "Toyota", "Yaris", "White", 2017, 4, "karim", V.PENDING, "",
         {D.LICENSE: ok(300), D.REGISTRATION: ok(300), D.INSURANCE: ok(300)}),
        ("2 TU 2222", "Seat", "Ibiza", "Orange", 2016, 4, "karim", V.REFUSED,
         "Registration does not match the plate number.", {D.REGISTRATION: ok(300, "REJECTED")}),
        ("3 TU 3333", "Citroen", "C3", "Green", 2015, 4, "karim", V.PENDING, "",
         {D.LICENSE: ok(300), D.REGISTRATION: ok(300, f="pdf"), D.INSURANCE: ok(300)}),
    ]


class Command(BaseCommand):
    help = "Seed demo vehicles and documents for every status."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opts):
        User = get_user_model()
        if opts["reset"]:
            for v in Vehicle.objects.filter(owner__email__endswith="@" + DOMAIN):
                for d in v.documents.all():
                    d.file.delete(save=False)
            Vehicle.objects.filter(owner__email__endswith="@" + DOMAIN).delete()

        users = {}
        for key, first, last, kind in USERS:
            email = f"{key}@{DOMAIN}"
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User.objects.create_user(
                    email=email, password=PASSWORD,
                    first_name=first, last_name=last, user_type=kind,
                )
            users[key] = user
        admin = users["admin"]

        colors = {"png": None}
        for plate, brand, model, color, year, seats, owner, status, reason, docs in vehicle_specs():
            if Vehicle.objects.filter(plate_number=plate).exists():
                continue
            vehicle = Vehicle.objects.create(
                owner=users[owner], brand=brand, model=model, color=color,
                plate_number=plate, year=year, seats=seats, status=status,
                rejection_reason=reason,
            )
            if status in (V.ACCEPTED, V.REFUSED):
                vehicle.verified_at = timezone.now() - timedelta(days=3)
                vehicle.verified_by = admin
                vehicle.save(update_fields=["verified_at", "verified_by"])
            for dtype, (days, dstatus, kind) in docs.items():
                content = PDF if kind == "pdf" else png_bytes((30, 60, 160))
                doc = Document(
                    vehicle=vehicle, document_type=dtype, status=dstatus,
                    number=f"{dtype[:3]}-{vehicle.pk:04d}",
                    expiry_date=date.today() + timedelta(days=days),
                )
                doc.file.save(f"demo.{kind}", ContentFile(content), save=False)
                doc.save()

        self.stdout.write(self.style.SUCCESS("Demo vehicles ready."))
        self.stdout.write(f"Vehicles: {Vehicle.objects.count()}, documents: {Document.objects.count()}")
        self.stdout.write(f"Password for every demo user: {PASSWORD}")
        self.stdout.write(f"Administrator: admin@{DOMAIN}")
