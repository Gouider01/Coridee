"""Create dummy users, conversations, messages and reviews for manual testing.

    python manage.py seed_communication           # add demo data
    python manage.py seed_communication --reset   # delete previous demo data first

All demo accounts use the password "Demo12345!" and e-mails ending in @demo.coride.tn.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from communication.identity import participant_for_user
from communication.models import (
    Conversation,
    ConversationMembership,
    Message,
    MessageReaction,
    Review,
)
from communication.services import (
    close_conversation,
    create_message,
    mark_trip_completed,
    open_conversation,
)

DOMAIN = "demo.coride.tn"
PASSWORD = "Demo12345!"

USERS = [
    ("amine", "Amine", "Ben Salah", "DRIVER"),
    ("sarra", "Sarra", "Trabelsi", "PASSENGER"),
    ("youssef", "Youssef", "Gharbi", "DRIVER"),
    ("ines", "Ines", "Mansour", "PASSENGER"),
    ("karim", "Karim", "Jlassi", "PASSENGER"),
]


class Command(BaseCommand):
    help = "Seed demo users, chats, messages and reviews for the communication module."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete earlier demo data first.")

    @transaction.atomic
    def handle(self, *args, **opts):
        User = get_user_model()
        if opts["reset"]:
            Conversation.objects.filter(reservation_reference__startswith="DEMO-").delete()
            Conversation.objects.filter(title__startswith="[demo]").delete()
            User.objects.filter(email__endswith="@" + DOMAIN).delete()

        u = {}
        for key, first, last, kind in USERS:
            email = f"{key}@{DOMAIN}"
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User.objects.create_user(
                    email=email, password=PASSWORD,
                    first_name=first, last_name=last, user_type=kind,
                )
            u[key] = user

        now = timezone.now()
        say = self._say

        # 1) Upcoming trip, chat open: Sarra (passenger) <-> Amine (driver)
        c1 = open_conversation(
            reservation_reference="DEMO-R1", trip_reference="9001",
            passenger=u["sarra"], driver=u["amine"],
            departure_at=now + timedelta(days=2),
        )
        if not c1.messages.exists():
            m = say(c1, u["sarra"], "Hi Amine! Is the departure still 8am from Tunis?", 50)
            say(c1, u["amine"], "Hello Sarra, yes. Meet me in front of the Lac 2 station.", 45)
            say(c1, u["sarra"], "Perfect. Can I bring a small suitcase?", 40)
            r = say(c1, u["amine"], "Of course, there is plenty of room.", 35, reply_to=m)
            self._react(r, u["sarra"], "👍")
            say(c1, u["sarra"], "Thanks, see you then!", 30)

        # 2) Finished trip: reviews unlocked. Ines <-> Youssef
        c2 = open_conversation(
            reservation_reference="DEMO-R2", trip_reference="9002",
            passenger=u["ines"], driver=u["youssef"],
            departure_at=now - timedelta(hours=5),
        )
        if not c2.messages.exists():
            say(c2, u["ines"], "Hello, I am at the meeting point.", 600)
            say(c2, u["youssef"], "Arriving in 2 minutes, grey Golf.", 595)
            say(c2, u["ines"], "Great ride, thank you!", 120)
        mark_trip_completed("9002", now - timedelta(hours=2))
        self._review(c2, u["ines"], u["youssef"], 5, "Safe driving and very punctual.")
        self._review(c2, u["youssef"], u["ines"], 4, "Nice passenger, on time.")

        # 3) Another finished trip, with no review yet (to test the review form)
        c3 = open_conversation(
            reservation_reference="DEMO-R3", trip_reference="9003",
            passenger=u["karim"], driver=u["amine"],
            departure_at=now - timedelta(hours=8),
        )
        if not c3.messages.exists():
            say(c3, u["karim"], "Thanks for the lift to Sousse!", 400)
            say(c3, u["amine"], "My pleasure, take care.", 390)
        mark_trip_completed("9003", now - timedelta(hours=6))

        # 4) Cancelled reservation: closed chat
        c4 = open_conversation(
            reservation_reference="DEMO-R4", trip_reference="9004",
            passenger=u["ines"], driver=u["amine"],
            departure_at=now + timedelta(days=1),
        )
        if not c4.messages.exists():
            say(c4, u["ines"], "Sorry, I have to cancel my booking.", 20)
        close_conversation("DEMO-R4", Conversation.CloseReason.CANCELLED)

        # 5) Group chat
        g = Conversation.objects.filter(title="[demo] Tunis - Sfax carpool").first()
        if g is None:
            owner = participant_for_user(u["youssef"])
            g = Conversation.objects.create(
                chat_type=Conversation.ChatType.GROUP,
                title="[demo] Tunis - Sfax carpool",
                participant_one=owner,
                trip_reference="9005",
                departure_at=now + timedelta(days=3),
            )
            for key in ("youssef", "sarra", "karim", "ines"):
                ConversationMembership.objects.get_or_create(
                    conversation=g, participant=participant_for_user(u[key])
                )
            say(g, u["youssef"], "Welcome everyone, leaving Friday at 7am.", 90)
            say(g, u["karim"], "I'll be at Bab Saadoun.", 80)
            say(g, u["ines"], "Can we pick me up in Ariana?", 70)
            say(g, u["youssef"], "Yes, Ariana works, I pass there anyway.", 60)

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write(f"Password for every demo user: {PASSWORD}")
        for key, *_ in USERS:
            self.stdout.write(f"  {key}@{DOMAIN}")
        self.stdout.write(f"Group invite path: /communication/chat/join/{g.invite_code}/")

    def _say(self, conversation, user, text, minutes_ago, reply_to=None):
        msg = create_message(
            conversation=conversation, sender=participant_for_user(user),
            content=text, reply_to=reply_to,
        )
        Message.objects.filter(pk=msg.pk).update(
            sent_at=timezone.now() - timedelta(minutes=minutes_ago)
        )
        return msg

    def _react(self, message, user, emoji):
        MessageReaction.objects.get_or_create(
            message=message, participant=participant_for_user(user), emoji=emoji
        )

    def _review(self, conversation, reviewer, target, rating, comment):
        Review.objects.get_or_create(
            conversation=conversation, trip_reference=conversation.trip_reference,
            reviewer=reviewer, target=target,
            reviewer_participant=participant_for_user(reviewer),
            target_participant=participant_for_user(target),
            defaults={"rating": rating, "comment": comment},
        )
