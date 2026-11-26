# CoRide

**A carpooling web app for Tunisia.** Drivers share the seats they would drive empty, passengers book them and split the fuel cost, and every member is verified with an ID and a selfie.

> Software Engineering project · 3IA · ESPRIT · 2026-2027 · Team **Blackberry**
> Scrum, 3 sprints of 2 weeks · **Sprint 1 validation: Friday 27/11/2026**

---

## 1. Team and branches

| # | Module | Owner | Branch | App folder | Sprint 1 status |
|---|---|---|---|---|---|
| 1 | Users | Alaaeddine Guouider | `Gestion-Utilisateurs` | `users/` | ✅ Done, merged into `main` |
| 2 | Vehicles | Abdallah Salhi | `Gestion-vehicules` | `vehicles/` | ✅ Done, Sprint 1 complete |
| 3 | Trips | Wasim Snoussi | `Gestion-Trajets` | `trips/` | ✅ Done, Sprint 1 CRUD complete |
| 4 | Reservations | Selim Aschi | `Gestion-Reservations` | `reservations/` | To do |
| 5 | Communication & reviews | Ahmed Ridha Lazhari | `Gestion-Communication` | `communication/` | To do |

**`main`** = the shared, finished version (structure, design, Users module). You **never** work directly on `main`.

---

## 2. Get started (do this today)

1. **Accept the GitHub invitation** you received by e-mail.
2. **Get the code and switch to your branch:**
   ```bash
   git clone https://github.com/Gouider01/Coridee.git
   cd Coridee
   git checkout Gestion-Trajets          # ← your own branch
   git pull origin main                  # get the latest main (Users module + design)
   ```
3. **Install and run:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate                # Linux / macOS: source .venv/bin/activate
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py createsuperuser      # log in with your e-mail
   python manage.py runserver
   ```
4. Open **http://127.0.0.1:8000/**. You can sign up, log in, see your profile and, as superuser, manage users at `/users/manage/`.

Requirements: Python 3.10+ and Git.

---

## 3. What YOU must do for Friday (Sprint 1)

Sprint 1 = **project structure + full CRUD (create, read, update, delete) on your module's main entities, with input validation on every form.**

### Your module checklist

**Module 2 · Vehicles** (`vehicles/`)
- [x] Models `Vehicle` and `Document` (+ statuses)
- [x] A passenger adds, views, edits and deletes their vehicles (max 3) and uploads licence, registration, insurance
- [x] Admin: list vehicles, validate or reject one with a reason
- [x] When a vehicle is validated, call `vehicle.owner.promote_to_driver()`
- [x] Validation: Tunisian plate format, year, seats, file type, expiry date

**Module 3 · Trips** (`trips/`)
- [x] Models `Trip` and `Stop` (+ status)
- [x] A driver creates, views, edits and cancels a trip (route, stops, date, seats, price)
- [x] Passengers list and search trips by route and date
- [x] Admin: list and delete trips
- [x] Validation: departure in the future, seats ≤ vehicle seats, different cities, price > 0

**Module 4 · Reservations** (`reservations/`)
- [ ] Model `Reservation` (+ statuses)
- [ ] A passenger books seats, views and cancels their bookings
- [ ] A driver accepts or refuses a request
- [ ] Admin: list all reservations
- [ ] Validation: seats available, cannot book your own trip, cancellation rules

**Module 5 · Communication & reviews** (`communication/`)
- [ ] Models `Conversation`, `Message`, `Review`
- [ ] Send, view and delete messages; write, edit and delete reviews
- [ ] Admin: delete inappropriate reviews
- [ ] Validation: rating 1–5, one review per person per trip, message not empty

### For the validation, each member also brings
- [ ] **Sprint backlog:** your Sprint 1 stories with points and status (update your row on the "Sprint 1 board" slide of `CoRide_Project_Presentation_v17.pptx`)
- [ ] **Burndown data:** your story points remaining per day of the sprint
- [ ] **Demo:** your CRUD working live, with error messages when a form is wrong
- [ ] **Git:** regular commits on your branch with clear messages

---

## 4. Rules of the project

### Work only in your app folder
| You may change | Ask the team first (pull request to `main`) |
|---|---|
| `your_app/models.py`, `forms.py`, `views.py`, `urls.py`, `admin.py`, `tests.py` | `config/` (settings, root urls) |
| `your_app/templates/your_app/` | `templates/base.html`, `templates/partials/` |
| `static/your_app/` (only if really needed) | `static/css/coride.css`, `static/js/coride.js` |
| your app's `migrations/` | the `users/` app (Module 1) |

### Linking to users (Module 1)
Always point to the user with `settings.AUTH_USER_MODEL`, never import `User` in a model:
```python
from django.conf import settings
from django.db import models

class Trip(models.Model):
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trips")
    vehicle = models.ForeignKey("vehicles.Vehicle", on_delete=models.PROTECT, related_name="trips")  # other module: use a string
```

What the user gives you:

| Helper | Meaning |
|---|---|
| `user.is_passenger`, `user.is_driver`, `user.is_administrator` | the user's role (a driver is a passenger too) |
| `user.identity_verified` | the admin has checked the ID and the selfie (show the seal) |
| `user.promote_to_driver()` | Module 2 calls it when a vehicle is validated |
| `@login_required` (Django) | the page needs a logged-in user |
| `from users.views import admin_required` → `@admin_required` | the page is for administrators only (others get a 403 page) |

A deleted account is **anonymised**, not removed, so your `on_delete=CASCADE` never wipes other people's data.

### Never commit
`db.sqlite3`, `media/`, `private_media/`, `.venv/` (already in `.gitignore`). **Do** commit your migrations: `python manage.py makemigrations your_app`.

---

## 5. Design: one look for the whole app ("Cobalt Night")

Every module uses the same design. You don't write CSS: you reuse the ready-made pieces. A page looks like this:

```django
{% extends "base.html" %}
{% block title %}My trips{% endblock %}
{% block content %}
<header class="page-head">
  <div>
    <h1 class="page-head__title">My trips</h1>
    <p class="page-head__lede">Trips you published as a driver.</p>
  </div>
  <a class="btn btn--primary" href="{% url 'trips:create' %}">Publish a trip</a>
</header>

<section class="sheet">
  <form class="form" method="post" novalidate>
    {% csrf_token %}
    {% include "partials/_form.html" with form=form submit_label="Save" %}
  </form>
</section>
{% endblock %}
```

| Piece | Use it for |
|---|---|
| `page-head` + `page-head__title` + `page-head__lede` | page title on the cobalt band |
| `sheet` | a white content block (never put a sheet inside a sheet) |
| `btn btn--primary` | the **one** main red action of the page |
| `btn btn--secondary`, `btn--ghost`, `btn--trust` (cobalt) | other actions |
| `btn btn--danger` inside `<div class="actions__danger">` | delete / cancel: always outlined and set apart |
| `{% include "partials/_form.html" with form=form %}` | a whole form, errors under each field |
| `{% include "partials/_field.html" with field=form.x %}` | one field (for custom layouts) |
| `<div class="sheet sheet--flush"><div class="table-wrap"><table class="table">` | lists (trips, vehicles, bookings…) |
| `badge badge--active` / `--pending` / `--suspended` / `--neutral` | statuses |
| `{% include "partials/_seal.html" with fired=person.identity_verified %}` | the verified seal next to a person |
| `{% include "partials/_avatar.html" with person=p size="md" %}` | photo or initials |
| `<svg class="icon"><use href="#i-search"/></svg>` | icons (list in `templates/partials/_icons.html`) |

**Your link in the top bar:** name your module's main page `index` and it appears automatically:
```python
# trips/urls.py
app_name = "trips"
urlpatterns = [path("", views.trip_list, name="index"), ...]
```

Look at the Users pages (`users/templates/users/`) for complete examples: list with search, detail, form, delete confirmation.

---

## 6. Git: your daily routine

```bash
git checkout Gestion-Trajets             # always on YOUR branch
git pull origin main                     # get the team's latest finished work
# ... work ...
python manage.py test trips              # your tests pass
git add trips/
git commit -m "Trips: create and edit a trip with validation"
git push origin Gestion-Trajets
```

- **Commit often** (every task), with a clear message: `Module: what you did`.
- **Never** push to `main`, never `git push --force`.
- When your module is finished and tested, open a **pull request** from your branch into `main` on GitHub. It is reviewed, then merged.
- Problem or conflict? Ask in the team chat before forcing anything.

---

## 7. Useful commands

| Command | What it does |
|---|---|
| `python manage.py runserver` | start the app on http://127.0.0.1:8000 |
| `python manage.py makemigrations your_app` | create migrations after changing a model |
| `python manage.py migrate` | apply migrations to your local database |
| `python manage.py createsuperuser` | create an administrator (log in with e-mail) |
| `python manage.py test your_app` | run your tests |
| `python manage.py check` | check the project for errors |

---

## 8. Project at a glance

```
Coridee/
├── config/          settings, root URLs, home page
├── users/           Module 1 · Users (done)
├── vehicles/        Module 2 · Vehicles
├── trips/           Module 3 · Trips
├── reservations/    Module 4 · Reservations
├── communication/   Module 5 · Communication & reviews
├── templates/       base.html, home.html, partials/ (shared)
├── static/          css/coride.css, js/coride.js, fonts/, img/ (shared)
└── requirements.txt
```

**Sprints:** Sprint 1 · structure and CRUD → Sprint 2 · filters, search, pagination, PDF / CSV / Excel export, business rules → Sprint 3 · AI features in every module.
