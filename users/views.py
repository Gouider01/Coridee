"""Module 1 - User management  ·  Owner: Alaaeddine Guouider  ·  Branch: Gestion-Utilisateurs"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST

from .forms import (
    AdminUserForm,
    CreateAdminForm,
    DeleteAccountForm,
    LoginForm,
    ProfileForm,
    SearchForm,
    SignUpForm,
    StyledPasswordChangeForm,
    SuspendForm,
)
from .models import User


def admin_required(view):
    """Logged-in administrators only; everyone else gets the 403 page."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_administrator:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def _not_self(request, person, action):
    if person.pk == request.user.pk:
        messages.error(request, f"You cannot {action} your own account.")
        return False
    return True


# --------------------------------------------------------------------------- #
# Visitor
# --------------------------------------------------------------------------- #
def signup(request):
    if request.user.is_authenticated:
        return redirect("users:profile")
    form = SignUpForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, f"Welcome to CoRide, {user.first_name}! Your account is ready. "
                                  "Our team will check your ID soon.")
        return redirect("users:profile")
    return render(request, "users/signup.html", {"form": form})


class LoginView(auth_views.LoginView):
    template_name = "users/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("home")

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.info(request, "You are logged out. See you on the road!")
        return response


# --------------------------------------------------------------------------- #
# My account
# --------------------------------------------------------------------------- #
@login_required
def profile(request):
    user = request.user
    fire_seal = False
    if user.identity_verified and user.verified_at:
        # Play the firing animation once per verification.
        stamp = user.verified_at.isoformat()
        if request.session.get("seal_seen") != stamp:
            request.session["seal_seen"] = stamp
            fire_seal = True
    return render(request, "users/profile.html", {"person": user, "fire_seal": fire_seal})


@login_required
def profile_edit(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        was_verified = request.user.identity_verified
        identity_changed = form.identity_changed
        form.save()
        if was_verified and identity_changed:
            messages.warning(request, "Profile saved. Because you changed your ID document, "
                                      "our team will verify your identity again.")
        else:
            messages.success(request, "Your profile has been saved.")
        return redirect("users:profile")
    return render(request, "users/profile_edit.html", {"form": form})


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "users/password_change.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("users:profile")

    def form_valid(self, form):
        messages.success(self.request, "Your password has been changed.")
        return super().form_valid(form)


@login_required
def account_delete(request):
    form = DeleteAccountForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = request.user
        logout(request)
        user.anonymize()
        messages.info(request, "Your account has been deleted. Your personal data and documents were erased.")
        return redirect("home")
    return render(request, "users/account_delete.html", {"form": form})


@login_required
def identity_document(request, pk, kind):
    """Serve a private ID photo or selfie to its owner or to an administrator."""
    if kind not in ("id", "selfie"):
        raise Http404
    person = get_object_or_404(User, pk=pk)
    if person.pk != request.user.pk and not request.user.is_administrator:
        raise PermissionDenied
    file = person.id_document_image if kind == "id" else person.selfie
    if not file:
        raise Http404
    try:
        handle = file.open("rb")
    except FileNotFoundError:
        raise Http404
    response = FileResponse(handle)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


# --------------------------------------------------------------------------- #
# Administration
# --------------------------------------------------------------------------- #
@admin_required
def manage_list(request):
    search = SearchForm(request.GET or None)
    people = User.objects.filter(deleted_at__isnull=True).select_related("verified_by")
    q = search.cleaned_data["q"].strip() if search.is_valid() else ""
    if q:
        people = people.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q)
            | Q(email__icontains=q) | Q(phone_number__icontains=q.replace(" ", ""))
        )
    members = User.objects.filter(deleted_at__isnull=True)
    return render(request, "users/manage/list.html", {
        "people": people, "q": q, "search": search,
        "total": members.count(),
        "verified_count": members.filter(identity_verified=True).count(),
        "pending_count": members.filter(identity_verified=False).exclude(user_type=User.UserType.ADMINISTRATOR).count(),
        "suspended_count": members.filter(account_status=User.AccountStatus.SUSPENDED).count(),
    })


@admin_required
def manage_detail(request, pk):
    person = get_object_or_404(User, pk=pk, deleted_at__isnull=True)
    fire_seal = request.GET.get("fired") == "1" and person.identity_verified
    return render(request, "users/manage/detail.html", {"person": person, "fire_seal": fire_seal})


@admin_required
def manage_edit(request, pk):
    person = get_object_or_404(User, pk=pk, deleted_at__isnull=True)
    form = AdminUserForm(request.POST or None, instance=person, acting_admin=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{person.get_full_name()} has been updated.")
        return redirect("users:manage_detail", pk=person.pk)
    return render(request, "users/manage/edit.html", {"form": form, "person": person})


@admin_required
@require_POST
def manage_verify(request, pk):
    person = get_object_or_404(User, pk=pk, deleted_at__isnull=True)
    if not (person.id_document_image and person.selfie):
        messages.error(request, "This user has not uploaded both an ID photo and a selfie yet.")
    else:
        person.verify_identity(request.user)
        messages.success(request, f"{person.get_full_name()}'s identity is now verified.")
        return redirect(f"{reverse('users:manage_detail', args=[person.pk])}?fired=1")
    return redirect("users:manage_detail", pk=person.pk)


@admin_required
@require_POST
def manage_unverify(request, pk):
    person = get_object_or_404(User, pk=pk, deleted_at__isnull=True)
    person.unverify_identity()
    messages.info(request, f"The verification of {person.get_full_name()} has been removed.")
    return redirect("users:manage_detail", pk=person.pk)


@admin_required
def manage_suspend(request, pk):
    person = get_object_or_404(User, pk=pk, deleted_at__isnull=True)
    if not _not_self(request, person, "suspend"):
        return redirect("users:manage_detail", pk=person.pk)
    form = SuspendForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        person.suspend(form.cleaned_data["reason"])
        messages.success(request, f"{person.get_full_name()} has been suspended and can no longer log in.")
        return redirect("users:manage_detail", pk=person.pk)
    return render(request, "users/manage/suspend.html", {"form": form, "person": person})


@admin_required
@require_POST
def manage_reactivate(request, pk):
    person = get_object_or_404(User, pk=pk, deleted_at__isnull=True)
    person.reactivate()
    messages.success(request, f"{person.get_full_name()} has been reactivated.")
    return redirect("users:manage_detail", pk=person.pk)


@admin_required
def manage_delete(request, pk):
    person = get_object_or_404(User, pk=pk, deleted_at__isnull=True)
    if not _not_self(request, person, "delete"):
        return redirect("users:manage_detail", pk=person.pk)
    if request.method == "POST":
        name = person.get_full_name()
        person.anonymize()
        messages.success(request, f"The account of {name} has been deleted.")
        return redirect("users:manage")
    return render(request, "users/manage/delete.html", {"person": person})


@admin_required
def manage_new_admin(request):
    form = CreateAdminForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        admin = form.save()
        messages.success(request, f"{admin.get_full_name()} is now an administrator.")
        return redirect("users:manage_detail", pk=admin.pk)
    return render(request, "users/manage/new_admin.html", {"form": form})
