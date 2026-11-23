"""Module 1 - Gestion des utilisateurs  ·  Owner: Alaaeddine Guouider  ·  Branch: Gestion-Utilisateurs"""
from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "users"
    verbose_name = "Utilisateurs"
