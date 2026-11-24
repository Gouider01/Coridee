"""Module 1 - User management  ·  Owner: Alaaeddine Guouider  ·  Branch: Gestion-Utilisateurs

Run with:  python manage.py test users
"""
import shutil
import tempfile
from datetime import date
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import User, normalize_phone

TMP_MEDIA = tempfile.mkdtemp(prefix="coride-media-")
TMP_PRIVATE = tempfile.mkdtemp(prefix="coride-private-")
PASSWORD = "Tr4vel-Safe-2026"


def image(name="photo.png", fmt="PNG"):
    buf = BytesIO()
    Image.new("RGB", (40, 40), (29, 63, 143)).save(buf, fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")


def adult_birthday():
    today = date.today()
    return date(today.year - 25, 1, 15)


def make_user(email="sami@example.com", phone="22123456", **extra):
    defaults = dict(first_name="Sami", last_name="Ben Ali", phone_number=phone, date_of_birth=adult_birthday())
    defaults.update(extra)
    return User.objects.create_user(email, PASSWORD, **defaults)


def make_admin(email="admin@coride.tn"):
    return User.objects.create_superuser(email, PASSWORD, first_name="Amel", last_name="Admin")


def signup_data(**overrides):
    data = {
        "first_name": "Leila", "last_name": "Karoui", "email": "leila@example.com",
        "phone_number": "+216 55 123 456", "date_of_birth": adult_birthday().isoformat(),
        "password1": PASSWORD, "password2": PASSWORD,
        "id_document_type": "CIN", "id_document_number": "12345678",
        "id_document_image": image("id.png"), "selfie": image("selfie.jpg", "JPEG"),
    }
    data.update(overrides)
    return data


@override_settings(MEDIA_ROOT=TMP_MEDIA, PRIVATE_MEDIA_ROOT=TMP_PRIVATE)
class BaseTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)
        shutil.rmtree(TMP_PRIVATE, ignore_errors=True)


class ModelTests(BaseTest):
    def test_normalize_phone(self):
        self.assertEqual(normalize_phone("+216 22 123 456"), "22123456")
        self.assertEqual(normalize_phone("22-123-456"), "22123456")
        self.assertEqual(normalize_phone(""), "")

    def test_superuser_is_administrator(self):
        admin = make_admin()
        self.assertTrue(admin.is_administrator)
        self.assertEqual(admin.account_status, User.AccountStatus.ACTIVE)

    def test_new_user_is_active_passenger_not_verified(self):
        user = make_user()
        self.assertTrue(user.is_passenger)
        self.assertEqual(user.account_status, User.AccountStatus.ACTIVE)
        self.assertFalse(user.identity_verified)

    def test_promote_to_driver(self):
        user = make_user()
        user.promote_to_driver()
        self.assertTrue(user.is_driver)
        self.assertTrue(user.is_passenger)

    def test_anonymize_erases_personal_data(self):
        user = make_user(id_document_type="CIN", id_document_number="12345678")
        user.anonymize()
        user.refresh_from_db()
        self.assertTrue(user.is_deleted)
        self.assertFalse(user.is_active)
        self.assertIsNone(user.phone_number)
        self.assertEqual(user.id_document_number, "")
        self.assertFalse(user.has_usable_password())


class SignUpTests(BaseTest):
    url = reverse("users:signup")

    def test_page_loads(self):
        self.assertContains(self.client.get(self.url), "Create your account")

    def test_valid_signup_creates_active_account_and_logs_in(self):
        response = self.client.post(self.url, signup_data())
        self.assertRedirects(response, reverse("users:profile"))
        user = User.objects.get(email="leila@example.com")
        self.assertEqual(user.phone_number, "55123456")
        self.assertEqual(user.account_status, User.AccountStatus.ACTIVE)
        self.assertFalse(user.identity_verified)
        self.assertTrue(user.id_document_image.name.startswith("identity/"))
        self.assertNotIn("id.png", user.id_document_image.name)  # random file name
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def assertFieldError(self, data, field):
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertIn(field, response.context["form"].errors, response.context["form"].errors)
        self.assertFalse(User.objects.filter(email=data["email"]).exists())

    def test_under_18_rejected(self):
        today = date.today()
        self.assertFieldError(signup_data(date_of_birth=date(today.year - 16, 1, 1).isoformat()), "date_of_birth")

    def test_future_birth_date_rejected(self):
        self.assertFieldError(signup_data(date_of_birth=date(date.today().year + 1, 1, 1).isoformat()), "date_of_birth")

    def test_bad_phone_rejected(self):
        self.assertFieldError(signup_data(phone_number="12345"), "phone_number")
        self.assertFieldError(signup_data(phone_number="11123456"), "phone_number")

    def test_duplicate_phone_rejected(self):
        make_user(email="other@example.com", phone="55123456")
        self.assertFieldError(signup_data(), "phone_number")

    def test_duplicate_email_rejected_case_insensitive(self):
        make_user(email="leila@example.com", phone="98111222")
        response = self.client.post(self.url, signup_data(email="LEILA@example.com"))
        self.assertIn("email", response.context["form"].errors)

    def test_bad_name_rejected(self):
        self.assertFieldError(signup_data(first_name="L3ila"), "first_name")

    def test_cin_must_have_8_digits(self):
        self.assertFieldError(signup_data(id_document_number="1234"), "id_document_number")

    def test_passport_format(self):
        self.assertFieldError(signup_data(id_document_type="PASSPORT", id_document_number="A1"), "id_document_number")
        response = self.client.post(self.url, signup_data(id_document_type="PASSPORT", id_document_number="ab12345"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.get(email="leila@example.com").id_document_number, "AB12345")

    def test_documents_required(self):
        data = signup_data()
        del data["selfie"]
        self.assertFieldError(data, "selfie")

    def test_non_image_rejected(self):
        fake = SimpleUploadedFile("id.pdf", b"%PDF-1.4 not an image", content_type="application/pdf")
        self.assertFieldError(signup_data(id_document_image=fake), "id_document_image")

    def test_password_mismatch(self):
        self.assertFieldError(signup_data(password2="Different-2026"), "password2")

    def test_weak_password(self):
        self.assertFieldError(signup_data(password1="12345678", password2="12345678"), "password2")

    def test_logged_in_user_redirected(self):
        self.client.force_login(make_user())
        self.assertRedirects(self.client.get(self.url), reverse("users:profile"))


class LoginLogoutTests(BaseTest):
    def test_login_with_email_any_case(self):
        make_user()
        response = self.client.post(reverse("users:login"), {"username": "SAMI@example.com", "password": PASSWORD})
        self.assertRedirects(response, reverse("users:profile"))

    def test_wrong_password(self):
        make_user()
        response = self.client.post(reverse("users:login"), {"username": "sami@example.com", "password": "nope"})
        self.assertContains(response, "incorrect")

    def test_suspended_user_cannot_log_in_and_sees_reason(self):
        make_user().suspend("The selfie does not match the ID card.")
        response = self.client.post(reverse("users:login"), {"username": "sami@example.com", "password": PASSWORD})
        self.assertContains(response, "suspended")
        self.assertContains(response, "does not match")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_post(self):
        self.client.force_login(make_user())
        self.assertEqual(self.client.get(reverse("users:logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("users:logout")), reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class ProfileTests(BaseTest):
    def setUp(self):
        self.user = make_user(id_document_type="CIN", id_document_number="12345678")
        self.client.force_login(self.user)

    def test_profile_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("users:profile"))
        self.assertRedirects(response, f"{reverse('users:login')}?next={reverse('users:profile')}")

    def test_profile_shows_pending_seal(self):
        self.assertContains(self.client.get(reverse("users:profile")), "Verification pending")

    def edit_data(self, **overrides):
        data = {
            "first_name": "Sami", "last_name": "Ben Ali", "email": "sami@example.com",
            "phone_number": "22123456", "date_of_birth": adult_birthday().isoformat(), "city": "Sousse",
            "id_document_type": "CIN", "id_document_number": "12345678",
        }
        data.update(overrides)
        return data

    def test_edit_profile(self):
        response = self.client.post(reverse("users:profile_edit"), self.edit_data())
        self.assertRedirects(response, reverse("users:profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.city, "Sousse")

    def test_edit_validation(self):
        response = self.client.post(reverse("users:profile_edit"), self.edit_data(phone_number="abc"))
        self.assertIn("phone_number", response.context["form"].errors)

    def test_changing_id_removes_verification(self):
        self.user.verify_identity(make_admin())
        self.client.post(reverse("users:profile_edit"), self.edit_data(id_document_number="87654321"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.identity_verified)

    def test_editing_city_keeps_verification(self):
        self.user.verify_identity(make_admin())
        self.client.post(reverse("users:profile_edit"), self.edit_data(city="Nabeul"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.identity_verified)

    def test_change_password(self):
        response = self.client.post(reverse("users:password_change"), {
            "old_password": PASSWORD, "new_password1": "New-Road-2027!", "new_password2": "New-Road-2027!",
        })
        self.assertRedirects(response, reverse("users:profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("New-Road-2027!"))

    def test_delete_with_wrong_password_fails(self):
        response = self.client.post(reverse("users:account_delete"), {"password": "wrong"})
        self.assertIn("password", response.context["form"].errors)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_deleted)

    def test_delete_with_password_anonymizes_and_logs_out(self):
        response = self.client.post(reverse("users:account_delete"), {"password": PASSWORD})
        self.assertRedirects(response, reverse("home"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_deleted)
        self.assertNotIn("_auth_user_id", self.client.session)


class DocumentAccessTests(BaseTest):
    def setUp(self):
        self.owner = make_user(id_document_image=image("id.png"), selfie=image("s.png"))
        self.url = reverse("users:identity_document", args=[self.owner.pk, "id"])

    def test_owner_can_see_document(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_admin_can_see_document(self):
        self.client.force_login(make_admin())
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_other_user_cannot_see_document(self):
        self.client.force_login(make_user(email="x@example.com", phone="98765432"))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_document_not_public(self):
        self.assertFalse(self.owner.id_document_image.name.startswith("users/"))
        self.assertEqual(self.client.get(self.url).status_code, 302)  # login required


class AdminAccessTests(BaseTest):
    def setUp(self):
        self.admin = make_admin()
        self.user = make_user(id_document_image=image("id.png"), selfie=image("s.png"))

    def test_non_admin_gets_403(self):
        self.client.force_login(self.user)
        for name, args in [("users:manage", []), ("users:manage_detail", [self.user.pk]),
                           ("users:manage_new_admin", [])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 403)

    def test_list_and_search(self):
        self.client.force_login(self.admin)
        make_user(email="leila@example.com", phone="55111222", first_name="Leila", last_name="Karoui")
        response = self.client.get(reverse("users:manage"), {"q": "karoui"})
        self.assertContains(response, "leila@example.com")
        self.assertNotContains(response, "sami@example.com")
        response = self.client.get(reverse("users:manage"), {"q": "22 123"})
        self.assertContains(response, "sami@example.com")

    def test_verify_and_unverify(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("users:manage_verify", args=[self.user.pk]))
        self.user.refresh_from_db()
        self.assertTrue(self.user.identity_verified)
        self.assertEqual(self.user.verified_by, self.admin)
        self.client.post(reverse("users:manage_unverify", args=[self.user.pk]))
        self.user.refresh_from_db()
        self.assertFalse(self.user.identity_verified)

    def test_cannot_verify_without_documents(self):
        self.client.force_login(self.admin)
        bare = make_user(email="bare@example.com", phone="98000111")
        self.client.post(reverse("users:manage_verify", args=[bare.pk]))
        bare.refresh_from_db()
        self.assertFalse(bare.identity_verified)

    def test_suspend_needs_reason_then_reactivate(self):
        self.client.force_login(self.admin)
        url = reverse("users:manage_suspend", args=[self.user.pk])
        response = self.client.post(url, {"reason": "short"})
        self.assertIn("reason", response.context["form"].errors)
        self.client.post(url, {"reason": "Fake identity document."})
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_suspended)
        self.assertFalse(self.user.is_active)
        self.client.post(reverse("users:manage_reactivate", args=[self.user.pk]))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_suspended)
        self.assertTrue(self.user.is_active)

    def test_admin_cannot_suspend_or_delete_self(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("users:manage_suspend", args=[self.admin.pk]), {"reason": "Testing myself here."})
        self.client.post(reverse("users:manage_delete", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_suspended)
        self.assertFalse(self.admin.is_deleted)

    def test_admin_cannot_demote_self(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("users:manage_edit", args=[self.admin.pk]), {
            "first_name": "Amel", "last_name": "Admin", "email": "admin@coride.tn", "user_type": "PASSENGER",
        })
        self.assertIn("user_type", response.context["form"].errors)

    def test_edit_user_type_syncs_staff(self):
        self.client.force_login(self.admin)
        data = {"first_name": "Sami", "last_name": "Ben Ali", "email": "sami@example.com",
                "phone_number": "22123456", "user_type": "ADMINISTRATOR"}
        self.client.post(reverse("users:manage_edit", args=[self.user.pk]), data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_staff)
        data["user_type"] = "PASSENGER"
        self.client.post(reverse("users:manage_edit", args=[self.user.pk]), data)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)

    def test_delete_user(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("users:manage_delete", args=[self.user.pk]))
        self.assertRedirects(response, reverse("users:manage"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_deleted)
        self.assertNotContains(self.client.get(reverse("users:manage")), "sami@example.com")

    def test_create_admin(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("users:manage_new_admin"), {
            "first_name": "Nour", "last_name": "Haddad", "email": "nour@coride.tn",
            "password1": PASSWORD, "password2": PASSWORD,
        })
        new = User.objects.get(email="nour@coride.tn")
        self.assertRedirects(response, reverse("users:manage_detail", args=[new.pk]))
        self.assertTrue(new.is_administrator)
        self.assertTrue(new.is_staff)
