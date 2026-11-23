"""Module 1 - User management  ·  Owner: Alaaeddine Guouider  ·  Branch: Gestion-Utilisateurs"""
from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    # Visitor
    path("signup/", views.signup, name="signup"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    # My account
    path("profile/", views.profile, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("profile/password/", views.PasswordChangeView.as_view(), name="password_change"),
    path("profile/delete/", views.account_delete, name="account_delete"),
    path("<int:pk>/document/<str:kind>/", views.identity_document, name="identity_document"),
    # Administration
    path("manage/", views.manage_list, name="manage"),
    path("manage/new-admin/", views.manage_new_admin, name="manage_new_admin"),
    path("manage/<int:pk>/", views.manage_detail, name="manage_detail"),
    path("manage/<int:pk>/edit/", views.manage_edit, name="manage_edit"),
    path("manage/<int:pk>/verify/", views.manage_verify, name="manage_verify"),
    path("manage/<int:pk>/unverify/", views.manage_unverify, name="manage_unverify"),
    path("manage/<int:pk>/suspend/", views.manage_suspend, name="manage_suspend"),
    path("manage/<int:pk>/reactivate/", views.manage_reactivate, name="manage_reactivate"),
    path("manage/<int:pk>/delete/", views.manage_delete, name="manage_delete"),
]
