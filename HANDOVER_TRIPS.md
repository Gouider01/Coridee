# Handover: Trips (Module 3) - Sprint 1 CRUD complete

## Result
`trips/` is now the real module (the temporary model is replaced; field names used by `reservations` are unchanged).
`manage.py check` clean, `makemigrations --check` clean, **76 new trips tests pass**.

## What was built
- **Models**: `Trip` (+ `vehicle` FK to a validated vehicle, `notes`, `cancelled_at`, `updated_at`, DB check constraints, status OPEN/FULL/CANCELLED/COMPLETED), `Stop` (0-5 ordered stops).
  Migration `trips/0002_sprint1_trips_and_stops` (depends on `trips.0001_initial`, so `reservations.0001` is unaffected).
- **Driver**: publish (`/trips/new/`), list (`/trips/mine/`), edit, cancel, mark completed. Needs a VALIDATED vehicle, otherwise redirected to `/vehicles/`.
- **Passenger**: search by from / to / date / seats (`/trips/`); stops count and direction is respected (boarding at a stop works, wrong direction does not). Detail page with "Book a seat" -> reservations.
- **Admin**: `/trips/manage/` list + search + status filter, delete with confirmation.
- **Validation**: departure in the future (max 180 days), seats <= vehicle seats, different cities, valid city names, price 0 < p <= 500, stops differ from route/each other (max 5), one trip per driver per departure time, notes <= 300.
- **Rules when passengers have booked**: route, date, price and vehicle are locked; seats cannot go below booked seats; `remaining_seats`/status re-synced from real bookings.
- **Integration**: cancelling a trip cancels PENDING/ACCEPTED bookings and closes chats; completing a trip sets reservations COMPLETED/EXPIRED and calls `communication.services.mark_trip_completed` (reviews unlock). Admin delete closes chats first.
- Navbar "Find a trip" now appears (`trips:index`).

## Files
`trips/{models,services,forms,views,urls,admin,cities,tests}.py`, `trips/templates/trips/*`, `static/trips/trips.css`,
`trips/management/commands/seed_trips_demo.py`, `trips/migrations/0002_*.py`. `SPRINT_1.md` status updated.

## Demo data
`uv run manage.py seed_all --reset` seeds every module (see its docstring and the README). `seed_trips_demo` still works on its own.

## Known / for later (Sprint 2+)
- Pagination, PDF/Excel export, richer filters (Sprint 2). AI price suggestion (Sprint 3).
- `Trip.vehicle` is nullable only for legacy/demo rows; the form always requires it.
- Full-project test suite was run after packaging; see the final message of the session.
