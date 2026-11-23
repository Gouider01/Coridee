# CoRide · Module 1 (Users) · Sprint 1 design

Owner: Alaaeddine Guouider · Branch: `Gestion-Utilisateurs` · Sprint 1 validation: Friday 27/11/2026

## 1. Intent

CoRide is a carpooling web app whose promise is **trust**: people know who they ride with. Module 1 is the front door to that promise: it creates accounts, holds identity documents, and lets an administrator verify people and remove fake ones. It is also the first module the other four depend on (every vehicle, trip, booking and message belongs to a user).

This sprint delivers **full CRUD on users**, with input validation on every field, inside a shared visual design that the four other modules will reuse so the whole app looks like one product.

## 2. Goals

1. A visitor can sign up on one page (personal details + ID document + selfie) and use the app immediately.
2. A user can log in, log out, view, edit and delete their own account, and change their password.
3. An administrator can list and search users, open a user, compare ID and selfie, mark the identity as verified, edit, suspend (with a reason), reactivate, and delete users, and create another administrator.
4. Every form shows a clear error under each invalid field.
5. The interface is in **English** and works on phone and computer.
6. A shared design system (base template, components, tokens) that teammates use for their own pages.

## 3. Non-goals (later sprints)

- Sprint 2: e-mail verification link, password reset by e-mail, lockout after 5 failed logins, user statistics, pagination, advanced filters, PDF/CSV/Excel export.
- Sprint 3: face verification, photo moderation, fake-account detection, chatbot.
- Other modules' pages, models or logic: teammates build those on their own branches.
- Scrum paperwork (sprint backlog, burndown, sequence diagram): separate task.

**Anti-goals** (would make it a failure even if it works): a generic template look; anything that blocks a new user from travelling while waiting for verification; Claude listed anywhere in the Git history.

## 4. Account rules (decided with the owner)

| Rule | Decision |
|---|---|
| After sign-up | Account is **Active** immediately; the user is logged in and lands on their profile. |
| Identity check | Done afterwards by an administrator, who compares the ID photo and the selfie and clicks **Verify**. The profile then shows the verified seal. |
| Account statuses | **Active** and **Suspended** only. ("Pending" is removed from the model.) |
| Verified | Separate yes/no flag, with who verified and when. |
| Fake / wrong ID | Admin **suspends** the account with a reason; a suspended user cannot log in. Admin can **reactivate**. |
| Driver | Nobody chooses "driver" at sign-up. Module 2 promotes a passenger when a vehicle is validated (hook `promote_to_driver()` provided). |
| Administrators | Created by another administrator in the app, or with `createsuperuser`. |
| Delete own account | Allowed, after re-typing the password. |
| Minimum age | 18 (already a model rule). |

## 5. Pages

| # | Page | Who | URL (under `/users/`) |
|---|---|---|---|
| 1 | Home (visitor landing, sign-up call to action) | everyone | `/` |
| 2 | Sign up | visitor | `signup/` |
| 3 | Log in | visitor | `login/` |
| 4 | Log out (POST) | user | `logout/` |
| 5 | My profile | user | `profile/` |
| 6 | Edit my profile (details, photo, ID documents) | user | `profile/edit/` |
| 7 | Change password | user | `profile/password/` |
| 8 | Delete my account (password confirmation) | user | `profile/delete/` |
| 9 | Admin: user list + search | admin | `manage/` |
| 10 | Admin: user detail (ID + selfie side by side; Verify, Edit, Suspend/Reactivate, Delete) | admin | `manage/<id>/` |
| 11 | Admin: edit user (incl. user type, status) | admin | `manage/<id>/edit/` |
| 12 | Admin: suspend (reason) | admin | `manage/<id>/suspend/` |
| 13 | Admin: delete (confirmation) | admin | `manage/<id>/delete/` |
| 14 | Admin: create administrator | admin | `manage/new-admin/` |

Verify and Reactivate are POST actions from page 10. Logged-in users who open sign-up or log-in are redirected to their profile. Non-admins opening `manage/` get a 403 page.

## 6. Validation

Sign up and edit (server-side, shown under each field):
- first and last name required, letters, spaces, hyphens and apostrophes only, max 50;
- e-mail required, valid, unique (case-insensitive);
- phone required, Tunisian format (8 digits, starts 2-9, optional +216), unique;
- date of birth required, age 18 or more, not in the future;
- password: Django's validators (length, common, numeric, similarity) + confirmation must match;
- ID type required; CIN = exactly 8 digits, passport = 6-9 letters/digits;
- ID photo and selfie required at sign-up; images only (JPEG/PNG/WebP), max 5 MB each;
- profile photo optional, same image rules.

Admin actions: suspend requires a reason (min 10 characters); an admin cannot suspend, delete or demote themselves.

## 7. Data model changes

On top of the existing `users.User` (migration `0001` is on every branch):
- `account_status` choices become `ACTIVE`, `SUSPENDED`, default `ACTIVE`;
- add `identity_verified` (bool), `verified_at` (datetime, null), `verified_by` (FK to user, null), `suspension_reason` (text);
- `phone_number` becomes required at sign-up through the form, and unique;
- model labels become English.
Delivered as a new migration `0002` (no rewrite of `0001`).

## 8. Language

English only (`LANGUAGE_CODE = "en"`). Model labels and all interface text are written in English.

## 9. Visual design: "Nabeul Glaze"

Chosen direction (full contract in `.impeccable/surfaces/templates-base-html.md`):
- **Idea:** trust is a fired object. A verified identity is a **cobalt eight-point tile seal**, the only ornament in the app. Unverified = the same seal as a dashed, unfired outline ("Verification pending"). Everything else is a calm, exact working surface.
- **Colour:** cool glaze-white ground, white sheets with 1px borders, no drop shadows; near-black ink on one blue-tinted grey ramp; cobalt `#1d3f8f` for trust, links, focus; CoRide red `#c8102e` only for the brand mark and the one main action per screen; copper green for active, saffron for pending, red outlines for destructive.
- **Type:** Readex Pro, self-hosted, tabular numbers.
- **Layout:** 8px grid; destructive buttons (Delete, Suspend) always outlined and set apart.
- **Shell:** ink top bar: brand at the start, module links, account menu at the end; collapses to a menu on phones.
- **Implementation:** Bootstrap is removed; a small hand-written design system (`static/css/coride.css`: tokens + components: buttons, fields, sheets, tables, badges/seal, alerts, top bar) plus template partials (`_seal.html`, `_field.html`, `_form.html`, `_messages.html`, `_navbar.html`). Teammates use the same partials and classes.

## 10. Git delivery

1. **Shared work → `main`**: design system, base template, partials, home page. Then `main` is merged into all five member branches so everyone has the design.
2. **Module 1 work → `Gestion-Utilisateurs`**: forms, views, URLs, templates, migration `0002`, tests. Merged to `main` by pull request when done.
3. Commits authored by the owner only; **no Claude attribution of any kind**.

## 11. Testing

Django `TestCase` tests for: sign-up validation (each rule, success and failure), login/logout, suspended user cannot log in, profile edit, password change, delete with wrong/right password, admin access control (403 for non-admins), verify/suspend/reactivate/delete, admin cannot act on themselves. All tests pass before merging.

## 12. Left to the builder

Exact component styling within the direction; file split of views/forms; test fixtures; the exact message texts.

## 13. Builder decisions (review these)

Settled by the builder after the design review; change any of them if you disagree.

- **Administrator** = `user_type == ADMINISTRATOR`; that alone opens `manage/`. Creating an admin in the app also sets `is_staff` (Django `/admin/` access); changing someone's type away from Administrator clears `is_staff`. Superusers are never demoted from the app.
- **Re-verification:** changing the ID number, ID photo or selfie removes the verified seal until an admin verifies again. Admins can also **Unverify**.
- **Private documents:** ID photos and selfies get random file names and are served only through a permission-checked view (owner or admin), never through the public `/media/` URL.
- **Delete = anonymize:** the account is closed (`is_active = False`, `deleted_at` set), personal data and uploaded files are erased, the name becomes "Deleted user" and the e-mail a placeholder. The row stays, so other modules' history (trips, bookings, reviews) is not wiped. Teammates may keep `on_delete=CASCADE` without losing other people's data.
- **Phone:** unique when filled in, may be empty (for admins). Sign-up requires it.
- **Create administrator** form: first name, last name, e-mail, password (twice).
- **Git:** shared design work is pushed straight to `main`, then the five member branches are updated from `main`.
