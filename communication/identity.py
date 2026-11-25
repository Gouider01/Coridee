"""Maps the logged-in Module 1 user to a chat participant."""
from django.db.models import Q

from .models import CommunicationParticipant


def participant_for_user(user):
    participant, _ = CommunicationParticipant.objects.get_or_create(user=user)
    return participant


def get_request_participant(request):
    """The participant of the logged-in user, or None for visitors."""
    user = request.user
    if not user.is_authenticated or not user.is_active:
        return None
    return participant_for_user(user)


def participant_identity_q(field_name, participant):
    return Q(**{f"{field_name}_id": participant.pk})
