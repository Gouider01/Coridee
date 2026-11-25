"""Module 4 - routes. `index` feeds the "My bookings" link of the top bar."""
from django.urls import path

from . import views

app_name = "reservations"

urlpatterns = [
    path("", views.index, name="index"),
    path("trips/", views.available_trips, name="available"),
    path("book/<int:trip_id>/", views.book, name="book"),
    path("requests/", views.driver_requests, name="requests"),
    path("manage/", views.manage, name="manage"),
    path("manage/<int:pk>/delete/", views.manage_delete, name="manage_delete"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/cancel/", views.cancel, name="cancel"),
    path("<int:pk>/accept/", views.accept, name="accept"),
    path("<int:pk>/refuse/", views.refuse, name="refuse"),
]
