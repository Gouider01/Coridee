"""
Module 2 - Gestion des véhicules
Owner: Abdallah Salhi  ·  Branch: Gestion-vehicules
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from users.views import admin_required
from .forms import (
    VehicleCreateForm,
    VehicleEditForm,
    VehicleRefuseForm,
    VehicleSearchForm,
)
from .models import Document, Vehicle


# --------------------------------------------------------------------------- #
# Passenger / Driver Views (Front Office)
# --------------------------------------------------------------------------- #
@login_required
def vehicle_list(request):
    """List of all vehicles owned by the logged-in user."""
    vehicles = (
        Vehicle.objects.filter(owner=request.user)
        .prefetch_related("documents")
        .order_by("-created_at")
    )
    count = vehicles.count()
    return render(
        request,
        "vehicles/vehicle_list.html",
        {
            "vehicles": vehicles,
            "vehicle_count": count,
            "can_add": count < 3,
            "max_vehicles": 3,
        },
    )


@login_required
def vehicle_add(request):
    """Add a new vehicle with mandatory document uploads (max 3 per user)."""
    if request.user.vehicles.count() >= 3:
        messages.error(
            request, "You already have 3 vehicles registered. You cannot add more."
        )
        return redirect("vehicles:index")

    form = VehicleCreateForm(
        request.POST or None,
        request.FILES or None,
        owner=request.user,
    )
    if request.method == "POST" and form.is_valid():
        vehicle = form.save()
        messages.success(
            request,
            f"Vehicle {vehicle.brand} {vehicle.model} ({vehicle.plate_number}) has been registered! "
            "Our team will review your documents shortly.",
        )
        return redirect("vehicles:detail", pk=vehicle.pk)

    return render(
        request,
        "vehicles/vehicle_form.html",
        {"form": form, "is_edit": False},
    )


@login_required
def vehicle_detail(request, pk):
    """Display vehicle details, status, and documents."""
    vehicle = get_object_or_404(
        Vehicle.objects.select_related("owner", "verified_by").prefetch_related("documents"),
        pk=pk,
    )
    if vehicle.owner != request.user and not request.user.is_administrator:
        raise PermissionDenied

    documents = vehicle.documents.all()
    return render(
        request,
        "vehicles/vehicle_detail.html",
        {"vehicle": vehicle, "documents": documents},
    )


@login_required
def vehicle_edit(request, pk):
    """Edit vehicle information or update document scans."""
    vehicle = get_object_or_404(Vehicle, pk=pk)
    if vehicle.owner != request.user and not request.user.is_administrator:
        raise PermissionDenied

    form = VehicleEditForm(
        request.POST or None,
        request.FILES or None,
        instance=vehicle,
    )
    if request.method == "POST" and form.is_valid():
        was_accepted = vehicle.is_accepted
        updated_vehicle = form.save()
        if was_accepted and updated_vehicle.is_pending:
            messages.warning(
                request,
                "Vehicle details updated. Because key information or documents changed, "
                "your vehicle is pending review again.",
            )
        else:
            messages.success(request, "Vehicle information has been updated.")
        return redirect("vehicles:detail", pk=updated_vehicle.pk)

    return render(
        request,
        "vehicles/vehicle_form.html",
        {"form": form, "vehicle": vehicle, "is_edit": True},
    )


@login_required
def vehicle_delete(request, pk):
    """Delete a vehicle and its associated documents."""
    vehicle = get_object_or_404(Vehicle, pk=pk)
    if vehicle.owner != request.user and not request.user.is_administrator:
        raise PermissionDenied

    if request.method == "POST":
        plate = vehicle.plate_number
        is_admin = request.user.is_administrator
        # Clean up private document files from disk
        for doc in vehicle.documents.all():
            if doc.file:
                doc.file.delete(save=False)
        vehicle.delete()
        messages.info(request, f"Vehicle {plate} and its documents were successfully deleted.")
        if is_admin and vehicle.owner != request.user:
            return redirect("vehicles:manage")
        return redirect("vehicles:index")

    return render(
        request,
        "vehicles/vehicle_confirm_delete.html",
        {"vehicle": vehicle},
    )


@login_required
def document_file(request, pk):
    """Serve a private vehicle document file to its owner or an administrator."""
    doc = get_object_or_404(Document.objects.select_related("vehicle__owner"), pk=pk)
    if doc.vehicle.owner != request.user and not request.user.is_administrator:
        raise PermissionDenied

    if not doc.file:
        raise Http404

    try:
        handle = doc.file.open("rb")
    except FileNotFoundError:
        raise Http404

    response = FileResponse(handle)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


# --------------------------------------------------------------------------- #
# Administrator Views (Back Office)
# --------------------------------------------------------------------------- #
@admin_required
def manage_list(request):
    """Admin dashboard listing all submitted vehicles."""
    search = VehicleSearchForm(request.GET or None)
    vehicles = (
        Vehicle.objects.select_related("owner", "verified_by")
        .prefetch_related("documents")
        .all()
    )

    q = ""
    status = ""
    if search.is_valid():
        q = search.cleaned_data.get("q", "").strip()
        status = search.cleaned_data.get("status", "")

    if q:
        vehicles = vehicles.filter(
            Q(plate_number__icontains=q)
            | Q(brand__icontains=q)
            | Q(model__icontains=q)
            | Q(owner__first_name__icontains=q)
            | Q(owner__last_name__icontains=q)
            | Q(owner__email__icontains=q)
        )

    if status:
        vehicles = vehicles.filter(status=status)

    all_vehicles = Vehicle.objects.all()
    return render(
        request,
        "vehicles/manage/list.html",
        {
            "vehicles": vehicles,
            "search": search,
            "q": q,
            "selected_status": status,
            "total_count": all_vehicles.count(),
            "pending_count": all_vehicles.filter(status=Vehicle.VehicleStatus.PENDING).count(),
            "accepted_count": all_vehicles.filter(status=Vehicle.VehicleStatus.ACCEPTED).count(),
            "refused_count": all_vehicles.filter(status=Vehicle.VehicleStatus.REFUSED).count(),
        },
    )


@admin_required
def manage_detail(request, pk):
    """Admin inspection view for a vehicle and its uploaded documents."""
    vehicle = get_object_or_404(
        Vehicle.objects.select_related("owner", "verified_by").prefetch_related("documents"),
        pk=pk,
    )
    documents = vehicle.documents.all()
    return render(
        request,
        "vehicles/manage/detail.html",
        {"vehicle": vehicle, "documents": documents},
    )


@admin_required
@require_POST
def manage_accept(request, pk):
    """Admin action to approve a vehicle and promote its owner to Driver."""
    vehicle = get_object_or_404(Vehicle.objects.select_related("owner"), pk=pk)
    vehicle.accept(admin=request.user)
    messages.success(
        request,
        f"Vehicle {vehicle.plate_number} has been approved! "
        f"{vehicle.owner.get_full_name()} is now recognized as a verified driver.",
    )
    return redirect("vehicles:manage_detail", pk=vehicle.pk)


@admin_required
def manage_refuse(request, pk):
    """Admin action to refuse a vehicle with a required reason."""
    vehicle = get_object_or_404(Vehicle.objects.select_related("owner"), pk=pk)
    form = VehicleRefuseForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        reason = form.cleaned_data["reason"]
        vehicle.refuse(reason=reason, admin=request.user)
        messages.warning(
            request,
            f"Vehicle {vehicle.plate_number} has been refused. Reason recorded.",
        )
        return redirect("vehicles:manage_detail", pk=vehicle.pk)

    return render(
        request,
        "vehicles/manage/refuse.html",
        {"vehicle": vehicle, "form": form},
    )
