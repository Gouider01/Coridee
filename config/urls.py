from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("admin/", admin.site.urls),
    path("users/", include("users.urls")),                  # Module 1
    path("vehicles/", include("vehicles.urls")),            # Module 2
    path("trips/", include("trips.urls")),                  # Module 3
    path("reservations/", include("reservations.urls")),    # Module 4
    path("communication/", include("communication.urls")),  # Module 5
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
