# Module 5 (Communication) - integration notes

## What changed vs. SE-CORIDE
- **No more guests / names typed by hand.** Every chat identity is a real logged-in
  `users.User`. `CommunicationParticipant` is now a thin 1:1 row per user
  (`display_name`, `session_key`, guest logic and `COMMUNICATION_GUEST_MODE` removed).
- **Names come from the profile**: `first_name + last_name` (Module 1 has no `username`);
  anonymised accounts show "Deleted user". E-mail is never displayed.
- **Visitors** are redirected to `users:login` (with `?next=`); invite links also require login.
- `communication:index` ("Messages" in the navbar) redirects to the chat list.
- **Templates** extend Coridee's `base.html` (navbar, fonts, footer). `communication.css`
  is scoped under `.comm` so it cannot affect other modules.
- **Attachments** are stored in `PRIVATE_MEDIA_ROOT` (like ID documents), served only by a permission-checked view.
- Migrations squashed into a fresh `0001_initial` (Coridee had no communication tables).
- Settings added: `COMMUNICATION_BLOCKED_TERMS`, `COMMUNICATION_ICE_SERVERS`.
- Tests rewritten for real users (`python manage.py test communication`).

## Hooks the other modules must call (communication/services.py)
- Reservations accepted -> `open_conversation(reservation_reference, trip_reference, passenger, driver, departure_at)`
- Cancelled/refused -> `close_conversation(reservation_reference, reason)`
- Trip finished -> `mark_trip_completed(trip_reference)` (unlocks reviews)
- Cron: `python manage.py close_conversations`
- Link to reviews: `communication:review_create` with `trip_id` (INTEGER) and `user_id`.

## Needs rework / decisions (please check)
1. Merged on top of the `Gestion-vehicules` branch (Vehicles module is present). Trips/Reservations are still stubs there.
   are still stubs here, so nothing in this module depends on them yet. Re-run `git merge` on that branch.
2. `Review`/`Conversation` keep both `User` FKs and `Participant` FKs (redundant now). Safe to drop the
   User-side duplicates (`Message.sender`, `Review.reviewer/target`, ...) in a later cleanup migration.
3. `trip_id` in the review URL is an int but `trip_reference` is a string: keep Trips pks numeric.
4. Suspended users (`is_active=False`) can't log in; their old chats stay visible to the other party.
5. Chat UI is dark-themed and polls (no websockets); restyle with Coridee tokens if you want a unified look.
6. Voice calls need HTTPS + a TURN server in production.
7. Not verified in a browser (no UI screenshots): only Django tests + `check` were run.
