"""Shared template context for the CoRide shell."""
from django.urls import NoReverseMatch, reverse

# Top-bar links for logged-in users. A link only appears once its module
# defines a route named "<app>:index" (see README > Navigation).
MODULE_NAV = [
    ("trips:index", "Find a trip"),
    ("reservations:index", "My bookings"),
    ("vehicles:index", "My vehicles"),
    ("communication:index", "Messages"),
]


# Account links come from Module 1 (users). Missing routes are simply hidden.
ACCOUNT_URLS = {
    "login": "users:login",
    "signup": "users:signup",
    "logout": "users:logout",
    "profile": "users:profile",
    "manage": "users:manage",
}


def _safe_reverse(name):
    try:
        return reverse(name)
    except NoReverseMatch:
        return None


def navigation(request):
    account = {key: _safe_reverse(name) for key, name in ACCOUNT_URLS.items()}
    items = []
    for url_name, label in MODULE_NAV:
        url = _safe_reverse(url_name)
        if url is None:
            continue
        items.append({"url": url, "label": label, "active": request.path.startswith(url)})
    return {"module_nav": items, "account_urls": account}
