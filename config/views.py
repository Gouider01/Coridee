from django.shortcuts import render

# Example trips shown on the visitor home page (clearly labelled "Example trips").
# Module 3 (trips) will replace them with real upcoming trips.
EXAMPLE_TRIPS = [
    {"dep": "07:30", "arr": "09:45", "from": "Tunis · Bab Saadoun", "to": "Sousse · Sahloul", "dur": "2 h 15",
     "driver": "Leila K.", "initials": "LK", "car": "Peugeot 208", "rating": "4.9", "taken": 1, "total": 3, "price": "12.5"},
    {"dep": "08:10", "arr": "11:20", "from": "Sfax · Centre", "to": "Tunis · Lac 2", "dur": "3 h 10",
     "driver": "Youssef H.", "initials": "YH", "car": "Kia Picanto", "rating": "4.8", "taken": 2, "total": 4, "price": "18"},
    {"dep": "17:45", "arr": "18:50", "from": "Bizerte · Corniche", "to": "Tunis · Ariana", "dur": "1 h 05",
     "driver": "Nour B.", "initials": "NB", "car": "Renault Clio", "rating": "5.0", "taken": 3, "total": 3, "price": "7"},
]

MARQUEE_ROUTES = ["Tunis → Sousse", "Sfax → Tunis", "Bizerte → Nabeul", "Monastir → Sousse", "Kairouan → Tunis"]


def home(request):
    """Public home page (visible to visitors)."""
    trips = []
    for trip in EXAMPLE_TRIPS:
        trip = dict(trip)
        trip["seats"] = [i < trip["taken"] for i in range(trip["total"])]
        trip["left"] = trip["total"] - trip["taken"]
        trips.append(trip)
    return render(request, "home.html", {"trips": trips, "routes": MARQUEE_ROUTES * 2})
