"""Module 1 - User management  ·  Owner: Alaaeddine Guouider  ·  Branch: Gestion-Utilisateurs"""
from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "users"
    verbose_name = "Users"
