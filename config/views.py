from django.shortcuts import render


def home(request):
    """Public home page (visible to visitors)."""
    return render(request, "home.html")
