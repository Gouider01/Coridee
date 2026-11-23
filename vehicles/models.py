"""
Module 2 - Gestion des véhicules
Owner: Abdallah Salhi  ·  Branch: Gestion-vehicules

Entities to implement (see the class diagram): Vehicle, Document

To link a user, always use settings.AUTH_USER_MODEL (Module 1):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
"""
from django.conf import settings  # noqa: F401
from django.db import models  # noqa: F401
