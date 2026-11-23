"""
Module 3 - Gestion des trajets
Owner: Wasim Snoussi  ·  Branch: Gestion-Trajets

Entities to implement (see the class diagram): Trip, Stop

To link a user, always use settings.AUTH_USER_MODEL (Module 1):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
"""
from django.conf import settings  # noqa: F401
from django.db import models  # noqa: F401
