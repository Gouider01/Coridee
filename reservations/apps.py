"""Module 4 - Gestion des réservations  ·  Owner: Selim Aschi  ·  Branch: Gestion-Reservations"""
from django.apps import AppConfig


class ReservationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "reservations"
    verbose_name = "Réservations"
