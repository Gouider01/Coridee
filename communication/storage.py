"""Private storage for chat attachments (same pattern as users' ID documents).

Files live in settings.PRIVATE_MEDIA_ROOT, have no public URL and are served
only by views.message_attachment, which checks conversation membership.
"""
import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateAttachmentStorage(FileSystemStorage):
    @property
    def base_location(self):
        return str(settings.PRIVATE_MEDIA_ROOT)

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None


def get_attachment_storage():
    return PrivateAttachmentStorage()
