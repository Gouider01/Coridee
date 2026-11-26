"""One command that floods the database with demo data for EVERY module.

    uv run manage.py seed_all --reset     # wipe the demo accounts' data, then seed (recommended)
    uv run manage.py seed_all             # add what is missing (users, vehicles); trips only if none

All accounts end in @coride.tn and share the password  Demo12345!
It uses the real services (book / accept / refuse / cancel / complete), so chats, seats,
statuses and review unlocking behave exactly like in the app.

What you get
  Users        3 administrators (admin, nadia, omar), verified members, 2 waiting for identity check, 1 suspended
  Vehicles     ACCEPTED, PENDING (all docs / 1 doc), REFUSED (reason), DOCUMENTS_EXPIRED, expiring soon
  Trips        open, full, cancelled, completed (with and without reviews), left-but-not-completed
  Bookings     PENDING, ACCEPTED, REFUSED, CANCELLED, COMPLETED, EXPIRED
  Admin inbox  admin chats with 2 colleague admins, a driver, a passenger and a team group
  Chats        direct chats with messages + reactions, a closed chat, a group chat
  Reviews      given on completed trips; one completed trip left unreviewed for the review form
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from communication.identity import participant_for_user
from communication.management.commands.seed_vehicles import PDF, png_bytes
from communication.models import (
    Conversation,
    ConversationMembership,
    Message,
    MessageReaction,
    Review,
)
from communication.services import create_message
from reservations.models import Reservation, ReservationStatus
from reservations.services import accept_request, book_seats, cancel_booking, refuse_request
from trips.models import Stop, Trip
from trips.services import cancel_trip, complete_trip
from vehicles.models import Document, Vehicle

DOMAIN = "coride.tn"
PASSWORD = "Demo12345!"
D, V = Document.DocumentType, Vehicle.VehicleStatus

# key, first, last, type, phone, city, verified, suspended
USERS = [
    ("admin", "Admin", "CoRide", "ADMINISTRATOR", None, "Tunis", True, False),
    ("nadia", "Nadia", "Ferchichi", "ADMINISTRATOR", None, "Tunis", True, False),   # support admin
    ("omar", "Omar", "Dev", "ADMINISTRATOR", None, "Ariana", True, False),          # developer admin
    ("leila", "Leila", "Khemiri", "DRIVER", "22111222", "Tunis", True, False),
    ("youssef", "Youssef", "Haddad", "DRIVER", "23222333", "Sfax", True, False),
    ("amine", "Amine", "Ben Salah", "DRIVER", "26555666", "Tunis", True, False),
    ("rania", "Rania", "Mejri", "DRIVER", "27666777", "Nabeul", False, False),   # ID waiting for check
    ("sami", "Sami", "Ben Salah", "PASSENGER", "24333444", "Tunis", True, False),
    ("nour", "Nour", "Bouzid", "PASSENGER", "25444555", "Sousse", True, False),  # vehicle PENDING
    ("karim", "Karim", "Jlassi", "PASSENGER", "28777888", "Ariana", True, False),
    ("ines", "Ines", "Mansour", "PASSENGER", "29888999", "Tunis", True, False),
    ("hedi", "Hedi", "Zouari", "PASSENGER", "50111222", "Bizerte", False, False),  # ID waiting for check
    ("marwen", "Marwen", "Trabelsi", "PASSENGER", "51222333", "Gabès", False, True),  # suspended
]

ok = lambda days, status="VALID", kind="png": (days, status, kind)
# plate, brand, model, color, year, seats, owner, status, reason, documents
VEHICLES = [
    ("205 TU 1234", "Peugeot", "208", "White", 2021, 4, "leila", V.ACCEPTED, "",
     {D.LICENSE: ok(700), D.REGISTRATION: ok(600, kind="pdf"), D.INSURANCE: ok(300)}),
    ("188 TU 9087", "Volkswagen", "Golf", "Grey", 2019, 4, "youssef", V.ACCEPTED, "",
     {D.LICENSE: ok(500), D.REGISTRATION: ok(400), D.INSURANCE: ok(12)}),   # insurance expires soon
    ("145 TU 3021", "Hyundai", "Tucson", "Black", 2022, 4, "amine", V.ACCEPTED, "",
     {D.LICENSE: ok(800), D.REGISTRATION: ok(700), D.INSURANCE: ok(350, kind="pdf")}),
    ("23456 RS", "Dacia", "Duster", "Blue", 2020, 5, "amine", V.ACCEPTED, "",
     {D.LICENSE: ok(800), D.REGISTRATION: ok(650), D.INSURANCE: ok(250)}),
    ("310 TU 6677", "Renault", "Symbol", "Silver", 2018, 3, "rania", V.ACCEPTED, "",
     {D.LICENSE: ok(400), D.REGISTRATION: ok(400), D.INSURANCE: ok(200)}),
    ("170 TU 5521", "Renault", "Clio", "Red", 2018, 3, "nour", V.PENDING, "",      # admin: accept -> Nour becomes driver
     {D.LICENSE: ok(400, "PENDING"), D.REGISTRATION: ok(300, "PENDING", "pdf"), D.INSURANCE: ok(200, "PENDING")}),
    ("91 TU 7730", "Fiat", "Punto", "Blue", 2008, 3, "ines", V.REFUSED,
     "Insurance document is unreadable. Please upload a clear scan.",
     {D.LICENSE: ok(100, "VALID"), D.INSURANCE: ok(100, "REJECTED")}),
    ("66 TU 4182", "Kia", "Picanto", "Yellow", 2018, 3, "karim", V.DOCUMENTS_EXPIRED, "",
     {D.LICENSE: ok(-40, "EXPIRED"), D.REGISTRATION: ok(200), D.INSURANCE: ok(-5, "EXPIRED", "pdf")}),
    ("402 TU 1099", "Hyundai", "i10", "Silver", 2023, 4, "hedi", V.PENDING, "",   # only 1 of 3 documents
     {D.LICENSE: ok(365, "PENDING")}),
]


class Command(BaseCommand):
    help = "Seed users, vehicles, trips, bookings, chats and reviews for every module."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Delete the @coride.tn demo accounts and everything attached first.")

    @transaction.atomic
    def handle(self, *args, **opts):
        self.User = get_user_model()
        if opts["reset"]:
            self.reset()
        self.users = self.make_users()
        self.admin = self.users["admin"]
        self.vehicles = self.make_vehicles()

        if Trip.objects.filter(driver__email__endswith="@" + DOMAIN).exists():
            self.stdout.write(self.style.WARNING(
                "Demo trips already exist: users and vehicles were completed, trips/bookings/chats "
                "skipped. Run with --reset for a clean, complete dataset."))
        else:
            self.now = timezone.now().replace(minute=0, second=0, microsecond=0)
            self.make_trips_and_bookings()
            Reservation.objects.expire_overdue()
        self.make_admin_chats()
        self.summary()

    # ------------------------------------------------------------------ reset
    def reset(self):
        demo = self.User.objects.filter(email__endswith="@" + DOMAIN)
        Conversation.objects.filter(
            Q(participant_one__user__in=demo) | Q(participant_two__user__in=demo)
            | Q(memberships__participant__user__in=demo)).distinct().delete()
        Review.objects.filter(Q(reviewer__in=demo) | Q(target__in=demo)).delete()
        Reservation.objects.filter(Q(passenger__in=demo) | Q(trip__driver__in=demo)).delete()
        Trip.objects.filter(driver__in=demo).delete()
        for vehicle in Vehicle.objects.filter(owner__in=demo):
            for doc in vehicle.documents.all():
                doc.file.delete(save=False)
        Vehicle.objects.filter(owner__in=demo).delete()
        for user in demo:
            for field in ("id_document_image", "selfie", "profile_photo"):
                f = getattr(user, field)
                if f:
                    f.delete(save=False)
        demo.delete()
        self.stdout.write("Previous demo data deleted.")

    # ------------------------------------------------------------------ users
    def make_users(self):
        users = {}
        for key, first, last, kind, phone, city, verified, suspended in USERS:
            email = f"{key}@{DOMAIN}"
            user = self.User.objects.filter(email=email).first()
            if user is None:
                user = self.User.objects.create_user(
                    email=email, password=PASSWORD, first_name=first, last_name=last,
                    user_type=kind, phone_number=phone, city=city,
                    date_of_birth=date(1994, 5, 17), is_staff=(kind == "ADMINISTRATOR"),
                    is_superuser=(kind == "ADMINISTRATOR"))
                if kind != "ADMINISTRATOR":
                    user.id_document_type = "CIN"
                    user.id_document_number = f"0{abs(hash(key)) % 10_000_000:07d}"
                    user.id_document_image.save("id.png", ContentFile(png_bytes((200, 200, 215))), save=False)
                    user.selfie.save("selfie.png", ContentFile(png_bytes((150, 120, 100))), save=False)
                    user.save()
            users[key] = user
        admin = users["admin"]
        for key, *_rest in USERS:
            _k, _f, _l, _t, _p, _c, verified, suspended = next(u for u in USERS if u[0] == key)
            user = users[key]
            if verified and not user.identity_verified and user.user_type != "ADMINISTRATOR":
                user.verify_identity(admin)
            if suspended and user.account_status != "SUSPENDED":
                user.suspend("Fake identity photos reported by several members.")
        return users

    # --------------------------------------------------------------- vehicles
    def make_vehicles(self):
        vehicles = {}
        for plate, brand, model, color, year, seats, owner, status, reason, docs in VEHICLES:
            vehicle = Vehicle.objects.filter(plate_number=plate).first()
            if vehicle is None:
                vehicle = Vehicle.objects.create(
                    owner=self.users[owner], brand=brand, model=model, color=color, plate_number=plate,
                    year=year, seats=seats, status=status, rejection_reason=reason)
                if status in (V.ACCEPTED, V.REFUSED):
                    vehicle.verified_at = timezone.now() - timedelta(days=3)
                    vehicle.verified_by = self.admin
                    vehicle.save(update_fields=["verified_at", "verified_by"])
                for dtype, (days, dstatus, kind) in docs.items():
                    doc = Document(vehicle=vehicle, document_type=dtype, status=dstatus,
                                   number=f"{dtype[:3]}-{vehicle.pk:04d}",
                                   expiry_date=date.today() + timedelta(days=days))
                    doc.file.save(f"demo.{kind}", ContentFile(PDF if kind == "pdf" else png_bytes((30, 60, 160))),
                                  save=False)
                    doc.save()
            vehicles[plate] = vehicle
        return vehicles

    # ----------------------------------------------------------------- trips
    def trip(self, driver, plate, dep, arr, days, hours, seats, price, stops=(), notes=""):
        trip = Trip.objects.create(
            driver=self.users[driver], vehicle=self.vehicles[plate], departure_city=dep, arrival_city=arr,
            departure_datetime=self.now + timedelta(days=days, hours=hours), seats=seats,
            price_per_seat=price, notes=notes)
        for position, city in enumerate(stops, start=1):
            Stop.objects.create(trip=trip, city=city, order=position)
        return trip

    def book(self, who, trip, seats, outcome="PENDING", chat=None, by=None):
        """Book through the real service, then apply the outcome (driver / passenger decision)."""
        reservation = book_seats(self.users[who], trip.pk, seats)
        driver = trip.driver
        if outcome in ("ACCEPTED", "COMPLETED"):
            accept_request(reservation.pk, driver)
            if chat:
                self.talk(reservation, chat)
        elif outcome == "REFUSED":
            refuse_request(reservation.pk, driver)
        elif outcome == "CANCELLED":
            cancel_booking(reservation.pk, self.users[who])
        reservation.refresh_from_db()
        return reservation

    def talk(self, reservation, lines):
        conversation = Conversation.objects.get(reservation_reference=str(reservation.pk))
        passenger, driver = reservation.passenger, reservation.trip.driver
        first = None
        for index, (who, text) in enumerate(lines):
            sender = passenger if who == "p" else driver
            message = create_message(conversation=conversation, sender=participant_for_user(sender),
                                     content=text, reply_to=first if index == 3 else None)
            Message.objects.filter(pk=message.pk).update(
                sent_at=timezone.now() - timedelta(minutes=(len(lines) - index) * 7))
            first = first or message
        if first and len(lines) > 1:
            MessageReaction.objects.get_or_create(
                message=first, participant=participant_for_user(driver), emoji="👍")
        return conversation

    def depart(self, trip, hours_ago):
        """Pretend the trip left `hours_ago` hours ago (bookings were made while it was upcoming)."""
        when = timezone.now() - timedelta(hours=hours_ago)
        Trip.objects.filter(pk=trip.pk).update(departure_datetime=when)
        Conversation.objects.filter(trip_reference=str(trip.pk)).update(departure_at=when)
        trip.refresh_from_db()

    def review(self, reservation, rating_p, text_p, rating_d, text_d):
        conversation = Conversation.objects.get(reservation_reference=str(reservation.pk))
        p, d = reservation.passenger, reservation.trip.driver
        for reviewer, target, rating, text in ((p, d, rating_p, text_p), (d, p, rating_d, text_d)):
            if rating:
                Review.objects.get_or_create(
                    conversation=conversation, trip_reference=conversation.trip_reference,
                    reviewer=reviewer, target=target,
                    reviewer_participant=participant_for_user(reviewer),
                    target_participant=participant_for_user(target),
                    defaults={"rating": rating, "comment": text})

    def make_trips_and_bookings(self):
        P = "205 TU 1234"  # leila's Peugeot
        G = "188 TU 9087"  # youssef's Golf
        T, DS = "145 TU 3021", "23456 RS"  # amine's Tucson / Duster
        SY = "310 TU 6677"  # rania's Symbol

        # ---- upcoming trips -------------------------------------------------
        t1 = self.trip("leila", P, "Tunis", "Sousse", 2, 1, 4, "12.50", ["Hammamet"], "Meeting point: Lac 2 station.")
        t2 = self.trip("leila", P, "Tunis", "Sfax", 4, 2, 3, "22.00", ["Hammamet", "Sousse"], "One suitcase per person.")
        t3 = self.trip("youssef", G, "Sousse", "Tunis", 2, 6, 2, "11.00", ["Enfidha"])
        t4 = self.trip("amine", T, "Tunis", "Bizerte", 1, 3, 4, "9.00", [], "Non-smoking car.")
        t5 = self.trip("amine", DS, "Sfax", "Gabès", 6, 0, 5, "14.00", [])
        t6 = self.trip("rania", SY, "Nabeul", "Tunis", 3, 2, 3, "8.50", [])
        self.trip("youssef", G, "Tunis", "Monastir", 8, 1, 3, "16.00", ["Sousse"])       # no bookings
        self.trip("leila", P, "Tunis", "Djerba", 10, 0, 4, "45.00", ["Sfax", "Gabès"], "Long trip, 1 break.")  # no bookings
        t9 = self.trip("amine", T, "Tunis", "Kairouan", 5, 4, 3, "10.00")                 # will be cancelled

        # ---- bookings on upcoming trips ------------------------------------
        r1a = self.book("sami", t1, 1, "PENDING")                                          # waiting for Leila
        r1b = self.book("nour", t1, 2, "ACCEPTED", chat=[
            ("p", "Hi Leila! Is the departure still at the Lac 2 station?"),
            ("d", "Hello Nour, yes. I will be in a white Peugeot 208."),
            ("p", "Perfect. Can I bring a small suitcase?"),
            ("d", "Of course, there is plenty of room."),
            ("p", "Thanks, see you then!")])
        r2a = self.book("sami", t2, 2, "ACCEPTED", chat=[
            ("p", "Hello, I will get on in Hammamet if that is OK."),
            ("d", "Yes, Hammamet works. Be there 10 minutes early."),
            ("p", "Great, thank you.")])
        r2b = self.book("ines", t2, 1, "PENDING")                                          # trip becomes FULL
        r3a = self.book("karim", t3, 1, "ACCEPTED", chat=[
            ("p", "Salam Youssef, where exactly do we meet in Sousse?"),
            ("d", "In front of the train station at 6 pm.")])
        r3b = self.book("hedi", t3, 1, "PENDING")                                          # trip becomes FULL
        r4a = self.book("sami", t4, 1, "REFUSED")
        r4b = self.book("ines", t4, 1, "CANCELLED")
        r4c = self.book("nour", t4, 1, "ACCEPTED", chat=[
            ("p", "Hello Amine, do you stop in Ariana?"),
            ("d", "Yes, I pass through Ariana around 9:30.")])
        r6a = self.book("sami", t6, 1, "PENDING")
        r6b = self.book("ines", t6, 1, "ACCEPTED", chat=[("p", "Hi Rania, see you on Saturday!"),
                                                         ("d", "See you, safe travels.")])
        t9_a = self.book("karim", t9, 1, "PENDING")
        t9_b = self.book("sami", t9, 2, "ACCEPTED", chat=[("p", "Hi, is there still room for luggage?")])
        cancel_trip(t9.pk, t9.driver)                                                      # CANCELLED trip + closed chat

        # ---- finished trips (reviews unlocked) -------------------------------
        past1 = self.trip("leila", P, "Tunis", "Sousse", 3, 0, 3, "12.00", ["Hammamet"])
        p1 = self.book("sami", past1, 1, "ACCEPTED", chat=[
            ("p", "I am at the meeting point."), ("d", "Two minutes, white Peugeot."),
            ("p", "Great ride, thank you!")])
        p1b = self.book("karim", past1, 1, "ACCEPTED", chat=[("p", "Thanks for the lift!")])
        self.depart(past1, 72)
        complete_trip(past1.pk, past1.driver)
        self.review(p1, 5, "Safe driving and very punctual.", 4, "Nice passenger, on time.")
        self.review(p1b, 4, "Comfortable car, good music.", 0, "")

        past2 = self.trip("youssef", G, "Sfax", "Tunis", 4, 0, 4, "18.00", ["Sousse"])
        p2 = self.book("ines", past2, 2, "ACCEPTED", chat=[("p", "Hello!"), ("d", "Hello Ines, on my way.")])
        self.depart(past2, 120)
        complete_trip(past2.pk, past2.driver)
        self.review(p2, 3, "Late by 20 minutes but friendly.", 5, "Perfect passenger.")

        past3 = self.trip("amine", T, "Tunis", "Hammamet", 2, 0, 3, "7.00")
        p3 = self.book("nour", past3, 1, "ACCEPTED", chat=[("p", "Thank you Amine!"), ("d", "My pleasure.")])
        self.depart(past3, 48)
        complete_trip(past3.pk, past3.driver)                                               # NO review: test the review form

        # ---- left but NOT completed: driver sees "Mark as completed" ----------
        past4 = self.trip("leila", P, "Tunis", "Nabeul", 0, 5, 3, "6.00")
        p4a = self.book("sami", past4, 1, "ACCEPTED", chat=[("p", "On my way to the meeting point.")])
        p4b = self.book("hedi", past4, 1, "PENDING")                                        # will EXPIRE on completion
        self.depart(past4, 3)
        self.group_chat(t2)

    def group_chat(self, trip):
        owner = trip.driver
        group = Conversation.objects.create(
            chat_type=Conversation.ChatType.GROUP, title="Tunis - Sfax carpool",
            participant_one=participant_for_user(owner), trip_reference=str(trip.pk),
            departure_at=trip.departure_datetime)
        for key in ("leila", "sami", "ines", "karim"):
            ConversationMembership.objects.get_or_create(
                conversation=group, participant=participant_for_user(self.users[key]))
        for key, text, ago in (("leila", "Welcome everyone, leaving at 7 am sharp.", 90),
                               ("karim", "I will be at Bab Saadoun.", 80),
                               ("ines", "Can we pick me up in Ariana?", 70),
                               ("leila", "Yes, Ariana works, I pass there anyway.", 60)):
            msg = create_message(conversation=group, sender=participant_for_user(self.users[key]), content=text)
            Message.objects.filter(pk=msg.pk).update(sent_at=timezone.now() - timedelta(minutes=ago))
        self.group_invite = group.invite_code

    # ---------------------------------------------------------- admin chats
    def private_chat(self, a, b, lines, title=""):
        """A private chat that does not come from a reservation (like "New chat" in the app)."""
        pa, pb = participant_for_user(self.users[a]), participant_for_user(self.users[b])
        conversation = Conversation.objects.create(
            chat_type=Conversation.ChatType.PRIVATE, participant_one=pa, participant_two=pb, title=title)
        conversation.participants.add(pa, pb)
        for index, (who, text) in enumerate(lines):
            sender = self.users[a if who == "a" else b]
            msg = create_message(conversation=conversation, sender=participant_for_user(sender), content=text)
            Message.objects.filter(pk=msg.pk).update(
                sent_at=timezone.now() - timedelta(hours=len(lines) - index, minutes=index * 3))
        return conversation

    def make_admin_chats(self):
        """Give the administrators a real inbox: colleagues, a driver and a passenger."""
        admin_p = participant_for_user(self.admin)
        if Conversation.objects.filter(Q(participant_one=admin_p) | Q(participant_two=admin_p)).exists():
            return
        self.private_chat("admin", "nadia", [
            ("b", "Hi! 3 identity checks are waiting in the queue (Rania, Hedi and one more)."),
            ("a", "Thanks Nadia, I will take Rania and Hedi this afternoon."),
            ("b", "Perfect. Marwen was suspended yesterday, fake selfie reported by 3 members."),
            ("a", "Noted. Please keep the reports in the account notes."),
            ("b", "Done ✅")])
        self.private_chat("admin", "omar", [
            ("b", "Heads up: I deployed the new trips module on staging."),
            ("a", "Nice. Did you test cancelling a trip that has accepted bookings?"),
            ("b", "Yes, the bookings are cancelled and the chats get closed."),
            ("a", "Great. And 'Mark as completed' unlocks the reviews?"),
            ("b", "It does. I will add the pagination in Sprint 2."),
            ("a", "Perfect, ping me when the PDF export is ready.")])
        self.private_chat("admin", "leila", [
            ("b", "Hello, my insurance renews next week. Can I upload the new one before it expires?"),
            ("a", "Yes, edit your vehicle and replace the insurance file. We re-check it within 24 hours."),
            ("b", "Thank you, I will do it today.")])
        self.private_chat("admin", "nour", [
            ("b", "Hi, my Renault Clio has been pending for 2 days. Is something missing?"),
            ("a", "Hello Nour, we are reviewing your documents now. You will be notified shortly."),
            ("b", "Thanks a lot!")])
        group = Conversation.objects.create(
            chat_type=Conversation.ChatType.GROUP, title="CoRide team",
            participant_one=admin_p)
        for key in ("admin", "nadia", "omar"):
            ConversationMembership.objects.get_or_create(
                conversation=group, participant=participant_for_user(self.users[key]))
        for key, text, ago in (("omar", "Sprint 1 validation is Friday, please check the demo data.", 300),
                               ("nadia", "Verification queue is clean on my side.", 240),
                               ("admin", "Vehicles queue too. Thanks both!", 200)):
            msg = create_message(conversation=group, sender=participant_for_user(self.users[key]), content=text)
            Message.objects.filter(pk=msg.pk).update(sent_at=timezone.now() - timedelta(minutes=ago))

    # --------------------------------------------------------------- summary
    def summary(self):
        w = self.stdout.write
        w(self.style.SUCCESS("\nDemo data ready. Password for every account: " + PASSWORD))
        w(f"  users {self.User.objects.filter(email__endswith='@'+DOMAIN).count()} · vehicles {Vehicle.objects.count()} · "
          f"trips {Trip.objects.count()} · bookings {Reservation.objects.count()} · "
          f"chats {Conversation.objects.count()} · messages {Message.objects.count()} · reviews {Review.objects.count()}")
        w("\nWhat to log in as (all @coride.tn):")
        w("  admin    : own inbox (chats with nadia, omar, leila, nour + 'CoRide team' group) · users (verify Rania / Hedi, suspended Marwen), vehicles (accept Nour's, refuse), trips, bookings")
        w("  leila    : driver, trips in every state, a pending request (Sami), 'Mark as completed' on Tunis→Nabeul")
        w("  youssef  : driver, FULL trip, a finished trip with reviews")
        w("  amine    : driver with 2 vehicles, cancelled trip, finished trip WITHOUT review (Nour can review him)")
        w("  rania    : driver whose identity check is still pending")
        w("  sami     : passenger: pending, accepted, refused, cancelled bookings, chats, can review Leila")
        w("  nour     : passenger whose vehicle is PENDING (admin accepts -> she becomes a driver)")
        w("  ines, karim, hedi : more passengers (hedi: ID pending, 1-document vehicle) · marwen: suspended")
