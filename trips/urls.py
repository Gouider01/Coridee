"""Module 3 - routes. `index` feeds the "Find a trip" link of the top bar."""
from django.urls import path

from . import views

app_name = "trips"

urlpatterns = [
    path("", views.index, name="index"),
    path("new/", views.create, name="create"),
    path("mine/", views.mine, name="mine"),
    path("manage/", views.manage, name="manage"),
    path("manage/<int:pk>/delete/", views.manage_delete, name="manage_delete"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/cancel/", views.cancel, name="cancel"),
    path("<int:pk>/complete/", views.complete, name="complete"),
]
