"""
Module 2 - Gestion des véhicules
Owner: Abdallah Salhi  ·  Branch: Gestion-vehicules
"""
from django.urls import path

from . import views

app_name = "vehicles"

urlpatterns = [
    # Passenger / Driver (Front Office)
    path("", views.vehicle_list, name="index"),
    path("add/", views.vehicle_add, name="add"),
    path("<int:pk>/", views.vehicle_detail, name="detail"),
    path("<int:pk>/edit/", views.vehicle_edit, name="edit"),
    path("<int:pk>/delete/", views.vehicle_delete, name="delete"),
    path("document/<int:pk>/", views.document_file, name="document_file"),

    # Administrator (Back Office)
    path("manage/", views.manage_list, name="manage"),
    path("manage/<int:pk>/", views.manage_detail, name="manage_detail"),
    path("manage/<int:pk>/accept/", views.manage_accept, name="manage_accept"),
    path("manage/<int:pk>/refuse/", views.manage_refuse, name="manage_refuse"),
]
