"""
Module 2 - Gestion des véhicules
Owner: Abdallah Salhi  ·  Branch: Gestion-vehicules

Test suite covering:
- Plate format, year, and seat validations
- Maximum 3 vehicles per user constraint
- Document uploads, expiry date checks, and composition cascading delete
- Passenger vehicle CRUD
- Admin inspection, acceptance (promoting owner to Driver), and refusal with reason
- Private document access control
"""
import shutil
import tempfile
from datetime import date, timedelta
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from users.models import User
from .models import (
    Document,
    Vehicle,
    normalize_plate,
    validate_future_date,
    validate_tunisian_plate,
    validate_vehicle_year,
)

TMP_MEDIA = tempfile.mkdtemp(prefix="coride-veh-media-")
TMP_PRIVATE = tempfile.mkdtemp(prefix="coride-veh-private-")
PASSWORD = "Pass-Secret-2026"


def make_dummy_file(name="document.pdf", content_type="application/pdf"):
    if content_type == "application/pdf":
        return SimpleUploadedFile(name, b"%PDF-1.4 dummy content", content_type=content_type)
    buf = BytesIO()
    Image.new("RGB", (60, 60), (29, 63, 143)).save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type=content_type)


def future_date(days=180):
    return date.today() + timedelta(days=days)


def past_date(days=30):
    return date.today() - timedelta(days=days)


@override_settings(MEDIA_ROOT=TMP_MEDIA, PRIVATE_MEDIA_ROOT=TMP_PRIVATE)
class BaseVehicleTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)
        shutil.rmtree(TMP_PRIVATE, ignore_errors=True)

    def setUp(self):
        self.passenger = User.objects.create_user(
            email="passenger@coride.tn",
            password=PASSWORD,
            first_name="Sami",
            last_name="Gharbi",
            phone_number="22111222",
            date_of_birth=date(1995, 5, 12),
        )
        self.admin = User.objects.create_superuser(
            email="admin@coride.tn",
            password=PASSWORD,
            first_name="Amel",
            last_name="Admin",
        )


class VehicleModelValidationTests(BaseVehicleTestCase):
    def test_normalize_and_validate_tunisian_plate(self):
        # Valid plates
        self.assertEqual(normalize_plate("215tu8901"), "215 TU 8901")
        self.assertEqual(normalize_plate("123  TU  4567"), "123 TU 4567")
        self.assertEqual(normalize_plate("12345rs"), "12345 RS")
        self.assertEqual(normalize_plate("RS 12345"), "12345 RS")

        validate_tunisian_plate("215 TU 8901")
        validate_tunisian_plate("12345 RS")

        # Invalid plates
        with self.assertRaises(ValidationError):
            validate_tunisian_plate("INVALID")

        with self.assertRaises(ValidationError):
            validate_tunisian_plate("12345678")

    def test_validate_vehicle_year(self):
        validate_vehicle_year(2020)
        validate_vehicle_year(date.today().year)

        with self.assertRaises(ValidationError):
            validate_vehicle_year(1975)  # too old

        with self.assertRaises(ValidationError):
            validate_vehicle_year(date.today().year + 5)  # too far in the future

    def test_validate_future_date(self):
        validate_future_date(future_date(30))
        with self.assertRaises(ValidationError):
            validate_future_date(past_date(10))

    def test_max_three_vehicles_per_user(self):
        for i in range(3):
            Vehicle.objects.create(
                owner=self.passenger,
                brand="Renault",
                model=f"Clio {i}",
                color="Black",
                plate_number=f"{100 + i} TU 1000",
                year=2018 + i,
                seats=4,
            )

        fourth_vehicle = Vehicle(
            owner=self.passenger,
            brand="Peugeot",
            model="208",
            color="White",
            plate_number="104 TU 1000",
            year=2021,
            seats=4,
        )
        with self.assertRaises(ValidationError):
            fourth_vehicle.clean()

    def test_vehicle_acceptance_promotes_owner_to_driver(self):
        self.assertEqual(self.passenger.user_type, User.UserType.PASSENGER)
        self.assertFalse(self.passenger.is_driver)

        v = Vehicle.objects.create(
            owner=self.passenger,
            brand="Volkswagen",
            model="Golf 7",
            color="Grey",
            plate_number="210 TU 5555",
            year=2019,
            seats=3,
        )
        # Add a pending document
        Document.objects.create(
            vehicle=v,
            document_type=Document.DocumentType.LICENSE,
            number="LIC-12345",
            expiry_date=future_date(365),
            file=make_dummy_file("license.png", "image/png"),
            status=Document.DocumentStatus.PENDING,
        )

        v.accept(admin=self.admin)
        v.refresh_from_db()
        self.passenger.refresh_from_db()

        self.assertEqual(v.status, Vehicle.VehicleStatus.ACCEPTED)
        self.assertEqual(v.verified_by, self.admin)
        self.assertTrue(self.passenger.is_driver)
        # Document should be marked VALID
        self.assertEqual(v.documents.first().status, Document.DocumentStatus.VALID)

    def test_vehicle_refusal_stores_reason(self):
        v = Vehicle.objects.create(
            owner=self.passenger,
            brand="Peugeot",
            model="308",
            color="Blue",
            plate_number="190 TU 3333",
            year=2016,
            seats=4,
        )
        reason_text = "The uploaded insurance policy is expired."
        v.refuse(reason=reason_text, admin=self.admin)
        v.refresh_from_db()

        self.assertEqual(v.status, Vehicle.VehicleStatus.REFUSED)
        self.assertEqual(v.rejection_reason, reason_text)
        self.assertEqual(v.verified_by, self.admin)

    def test_deleting_vehicle_cascades_to_documents(self):
        v = Vehicle.objects.create(
            owner=self.passenger,
            brand="Fiat",
            model="Punto",
            color="Red",
            plate_number="180 TU 7777",
            year=2015,
            seats=4,
        )
        Document.objects.create(
            vehicle=v,
            document_type=Document.DocumentType.REGISTRATION,
            number="REG-111",
            expiry_date=future_date(200),
            file=make_dummy_file("reg.pdf"),
        )
        self.assertEqual(Document.objects.filter(vehicle=v).count(), 1)
        v.delete()
        self.assertEqual(Document.objects.filter(vehicle_id=v.id).count(), 0)


class VehicleFrontOfficeViewsTests(BaseVehicleTestCase):
    def test_vehicle_list_requires_login(self):
        response = self.client.get(reverse("vehicles:index"))
        self.assertEqual(response.status_code, 302)

    def test_vehicle_list_displays_user_cars(self):
        self.client.force_login(self.passenger)
        Vehicle.objects.create(
            owner=self.passenger,
            brand="Kia",
            model="Rio",
            color="White",
            plate_number="220 TU 1234",
            year=2021,
            seats=4,
        )
        response = self.client.get(reverse("vehicles:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kia Rio")
        self.assertContains(response, "220 TU 1234")

    def test_vehicle_add_with_documents(self):
        self.client.force_login(self.passenger)
        data = {
            "brand": "Hyundai",
            "model": "i20",
            "color": "Silver",
            "plate_number": "205 TU 4321",
            "year": 2020,
            "seats": 3,
            "license_number": "LIC-9876",
            "license_expiry_date": future_date(180).isoformat(),
            "license_file": make_dummy_file("license.png", "image/png"),
            "registration_number": "REG-5432",
            "registration_expiry_date": future_date(180).isoformat(),
            "registration_file": make_dummy_file("carte_grise.pdf"),
            "insurance_number": "INS-1234",
            "insurance_expiry_date": future_date(180).isoformat(),
            "insurance_file": make_dummy_file("assurance.pdf"),
        }
        response = self.client.post(reverse("vehicles:add"), data)
        self.assertEqual(response.status_code, 302)

        v = Vehicle.objects.get(plate_number="205 TU 4321")
        self.assertEqual(v.owner, self.passenger)
        self.assertEqual(v.status, Vehicle.VehicleStatus.PENDING)
        self.assertEqual(v.documents.count(), 3)

    def test_cannot_add_more_than_three_vehicles_via_view(self):
        self.client.force_login(self.passenger)
        for i in range(3):
            Vehicle.objects.create(
                owner=self.passenger,
                brand="Brand",
                model=f"Model {i}",
                color="Black",
                plate_number=f"{10 + i} TU 1111",
                year=2019,
                seats=3,
            )

        # GET should redirect back to index
        response = self.client.get(reverse("vehicles:add"))
        self.assertRedirects(response, reverse("vehicles:index"))

    def test_other_user_cannot_access_private_document(self):
        v = Vehicle.objects.create(
            owner=self.passenger,
            brand="Toyota",
            model="Yaris",
            color="Red",
            plate_number="195 TU 9999",
            year=2018,
            seats=4,
        )
        doc = Document.objects.create(
            vehicle=v,
            document_type=Document.DocumentType.INSURANCE,
            number="INS-999",
            file=make_dummy_file("secret_ins.pdf"),
        )

        other_user = User.objects.create_user(
            email="stranger@example.com",
            password=PASSWORD,
            first_name="Ali",
            last_name="Baba",
        )
        self.client.force_login(other_user)
        response = self.client.get(reverse("vehicles:document_file", args=[doc.pk]))
        self.assertEqual(response.status_code, 403)

        # Owner can access
        self.client.force_login(self.passenger)
        response = self.client.get(reverse("vehicles:document_file", args=[doc.pk]))
        self.assertEqual(response.status_code, 200)

        # Admin can access
        self.client.force_login(self.admin)
        response = self.client.get(reverse("vehicles:document_file", args=[doc.pk]))
        self.assertEqual(response.status_code, 200)


class VehicleAdminViewsTests(BaseVehicleTestCase):
    def setUp(self):
        super().setUp()
        self.vehicle = Vehicle.objects.create(
            owner=self.passenger,
            brand="Seat",
            model="Ibiza",
            color="Black",
            plate_number="212 TU 7777",
            year=2021,
            seats=4,
        )

    def test_non_admin_cannot_access_manage_views(self):
        self.client.force_login(self.passenger)
        response = self.client.get(reverse("vehicles:manage"))
        self.assertEqual(response.status_code, 403)

    def test_admin_can_list_and_search_vehicles(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("vehicles:manage"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "212 TU 7777")
        self.assertContains(response, "Seat Ibiza")

        # Filter by search query
        response = self.client.get(f"{reverse('vehicles:manage')}?q=212")
        self.assertContains(response, "212 TU 7777")

        response = self.client.get(f"{reverse('vehicles:manage')}?q=nonexistent")
        self.assertNotContains(response, "212 TU 7777")

    def test_admin_accept_promotes_owner(self):
        self.client.force_login(self.admin)
        url = reverse("vehicles:manage_accept", args=[self.vehicle.pk])
        response = self.client.post(url)
        self.assertRedirects(response, reverse("vehicles:manage_detail", args=[self.vehicle.pk]))

        self.vehicle.refresh_from_db()
        self.passenger.refresh_from_db()
        self.assertEqual(self.vehicle.status, Vehicle.VehicleStatus.ACCEPTED)
        self.assertTrue(self.passenger.is_driver)

    def test_admin_refuse_with_reason(self):
        self.client.force_login(self.admin)
        url = reverse("vehicles:manage_refuse", args=[self.vehicle.pk])
        response = self.client.post(url, {"reason": "The vehicle insurance document is unreadable."})
        self.assertRedirects(response, reverse("vehicles:manage_detail", args=[self.vehicle.pk]))

        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.status, Vehicle.VehicleStatus.REFUSED)
        self.assertEqual(self.vehicle.rejection_reason, "The vehicle insurance document is unreadable.")
