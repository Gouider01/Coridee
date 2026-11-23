# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Everyone who travels between Tunisian cities: commuters, students, workers, families. Use is split evenly between phone and computer, so every page must be fully usable on both. Four roles:

- **Visitor** (not logged in): discovers CoRide and signs up.
- **Passenger** (any adult with an account): searches and books trips, chats with the driver, rates.
- **Driver** (a passenger whose vehicle was validated): publishes trips, accepts passengers.
- **Administrator** (platform staff, mostly on a computer): manages users, verifies identities and vehicles, moderates content.

## Product Purpose

A carpooling web app that connects people travelling in the same direction. Drivers share their empty seats, passengers book them and split the fuel cost. It replaces informal social-media groups, where nobody is verified, seats are not managed, prices have no reference and there is no way to know who is reliable.

Success: a person can sign up, find a trip and book a seat quickly, and feels safe getting into a stranger's car.

## Positioning

**Trust and safety first.** Every user uploads an ID and a selfie; identities are checked by an administrator; only cars with valid papers can offer trips; people rate each other after each trip. This is what a Facebook group cannot offer. Low cost and convenience matter, but trust is the headline.

## Operating Context

- University project (Software Engineering, 3IA, ESPRIT, 2026-2027), team "Blackberry", five members, one module each: Users, Vehicles, Trips, Reservations, Communication & reviews.
- Built with Scrum in 3 sprints; currently Sprint 1 (structure + CRUD). Sprint 2 adds filters, pagination, search, PDF/CSV/Excel export. Sprint 3 adds AI features.
- All five modules share one base template and one design system, so the app looks like one product.
- Admin work (verifying identities, suspending accounts) happens mostly on a computer.

## Capabilities and Constraints

- Stack: Python, Django 5.2 server-rendered templates, SQLite in development. Bootstrap 5 currently linked from a CDN.
- **Language: English only.**
- New accounts are active immediately; identity verification is done afterwards by an administrator and shown as a "verified" badge. Suspicious accounts are suspended by an administrator, never automatically.
- A user must be 18 or older. Phone numbers are Tunisian. Prices are in Tunisian dinars (TND).
- Privacy: Tunisian law 2004-63 and GDPR principles; a phone number is visible only after a booking is accepted.
- Performance targets: search under 2 s, chat messages under 1 s. A booking takes at most 3 clicks from the search results.

## Brand Commitments

- Product name: **CoRide**. App icon: a white "C" route with two dark stops on red (`static/img/coride-icon.png`). Brand red `#c8102e`, ink `#1b1e24`.
- Team name: **Blackberry**, with its own logo (`static/img/blackberry-logo.png`, dark purple berries with a green `#1fb873` leaf). Used for team credit, not as the product brand.

## Evidence on Hand

- Project presentation and course brief (outside the repo). No real users, testimonials, statistics or partners exist yet: do not invent any.

## Product Principles

1. **Trust is visible.** Verification status, ratings and validated documents are shown clearly wherever a person or a car appears.
2. **Fast to the seat.** Searching and booking take as few steps as possible.
3. **One product, five modules.** Shared components and patterns, so no module looks different.
4. **Works everywhere.** Phone and computer, treated as equals.

## Accessibility & Inclusion

- Clear form errors for every field (input validation is a graded requirement).
