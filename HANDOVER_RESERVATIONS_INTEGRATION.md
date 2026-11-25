# Handover: Reservations (Module 4) merged on top of Vehicles + Communication

## Result
`Coridee-main` (users + vehicles + communication) + `Coridee-Gestion-Reservations` (reservations + temporary trips).
`manage.py check` clean, `makemigrations --check` clean, **94 tests pass** (full suite), demo seed + page smoke test OK
(`/`, `/reservations/`, `/reservations/trips/`, `/vehicles/`, `/communication/chat/` all 200 when logged in).

## What was taken from where
| Source | Taken |
|---|---|
| Vehicles/Communication zip (**base**) | everything: users, vehicles, communication, settings (`COMMUNICATION_*`, `testserver` host), context_processors (admin -> `vehicles:manage`), `base.html` (chat bubble include line) |
| Reservations zip | whole `reservations/` app (models, services, views, forms, templates, migration `0001`, tests, `seed_reservations_demo`), `trips/` temporary Trip model + migration, `static/css/coride-admin.css`, `templates/admin/base_site.html` |
`users/`, `coride.css`, `coride.js` were identical in both zips (ignoring CRLF), so nothing to reconcile.

## Changes I made (only these)
1. **`reservations/services.py` - Communication hooks** (what `communication/INTEGRATION.md` asked for):
   - `accept_request` -> `communication.services.open_conversation(reservation_reference=reservation.pk, trip_reference=trip.pk, passenger, driver, departure_at)`
   - `refuse_request` -> `close_conversation(pk, "REFUSED")`; `cancel_booking` -> `close_conversation(pk, "CANCELLED")`
   - Done inside the existing `@transaction.atomic` functions; `close_conversation` is a no-op if no chat exists.
2. **`reservations/tests.py`**: fixed a stale assertion (`test_permissions`: admin on `reservations:index` expected 403, but the view intentionally redirects admins to `manage`); added `ChatIntegration` test (accept opens chat, cancel closes it).
No model or migration changes; no new migration needed.

## Still open (not done)
1. **`trips/` is still the TEMPORARY minimal model** (Trip with driver, cities, datetime, seats, remaining_seats, price_per_seat, status OPEN/FULL/CANCELLED/COMPLETED). Wasim's real module must keep those names and the migration chain
   (`reservations.0001` depends on `trips.0001_initial`; if his migration has another name, update that dependency). It also has no `trips:index` route, so "Find a trip" is hidden in the navbar; use `/reservations/trips/` meanwhile.
2. **`mark_trip_completed(trip_reference)`** (communication) is not called anywhere yet: it must be called when a trip becomes COMPLETED (Trips module) so reviews unlock. Reservation statuses BOARDED/COMPLETED/NO_SHOW exist but nothing sets them yet (Sprint 2: QR scan).
3. Vehicles are not linked to Trip (no `trip.vehicle`); drivers are not checked for a validated vehicle when a trip is created (belongs in Trips).
4. `SPRINT_1.md` / `README.md` come from the base zip; I did not update the status table for Reservations.
5. Review URL needs integer trip pk (`trip_id`): the temp Trip has an int pk, keep it so.

## Run it
```
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_reservations_demo      # admin@coride.tn, leila/youssef (drivers), sami/nour (passengers), pw Demo12345!
python manage.py runserver
python manage.py test                        # 94 tests
```
Optional chat demo data: `seed_communication`, `seed_vehicles` (in `communication/management/commands/`).
Cron: `python manage.py close_conversations`.
