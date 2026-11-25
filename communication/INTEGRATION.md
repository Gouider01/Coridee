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

---
# UI polish (v2) - handover

Presentation-only changes: no model, migration, URL or JS-API change.
`manage.py check` is clean and the 7 communication tests pass. Checked in a headless
Chromium (desktop 1280px and mobile 390px) on the demo data; not tested on a real phone,
in Safari/Firefox, or with the voice call and attachments flows.

## What changed
| Area | Change | Files |
|---|---|---|
| Layout | `.page` now uses the navbar's container (`--page-max`) so titles line up with the logo | `communication.css` |
| Chat list | Last-message preview ("You: ...", "Sarra: ..." in groups), time/"Yesterday", sorted by latest activity, compact search next to "New chat", better empty state | `views.py` (`conversation_list`), `conversation_list.html` |
| Conversation | Bubbles: own messages right-aligned in cobalt, others left in white; names hidden in private chats (header names the person); day separators; times as HH:MM (24h) | `communication.css`, new `chat_polish.js`, `conversation_detail.html` |
| Chat header | Subtitle shows "Trip N - departs <date>" instead of repeating the name; "Pins" button hidden while 0 | `conversation_detail.html`, `chat_polish.js` |
| Chat height | Sub-nav hidden on the chat page; the card fills the viewport | `communication.css` |
| Review form | Clickable stars (radio buttons), no default rating (was "1 star") | `forms.py` (`RadioSelect`), `review_form.html`, CSS |
| Mobile | Chat header stacks vertically | `communication.css` |

## How the JS works
`static/communication/chat_polish.js` is loaded after `conversation_detail.js`. It only
decorates the DOM (separators, time format, pin button) and re-runs through a
`MutationObserver` when polling or "load older" adds `.message` nodes. If a message
looks wrong after a future change to `createMessage()` in `conversation_detail.js`,
look there first. Removing the `<script>` tag restores the old look (bubbles stay).

## Test data (not part of the app, safe to delete)
`python manage.py seed_communication [--reset]` and `python manage.py seed_vehicles [--reset]`
(in `communication/management/commands/`). Demo accounts: `@demo.coride.tn`, password
`Demo12345!`, admin: `admin@demo.coride.tn`. `seed_vehicles` imports `vehicles.models`,
so do not push it to a branch that has no vehicles app.

## Known gaps / next steps
1. Not covered by screenshots: New chat page, join page, group chat, moderation and "My reviews"
   pages. They inherit the new container and tokens but were not reviewed one by one.
2. Group avatar in the list is two dots; replace it with an icon or member initials.
3. Reaction/Reply/... toolbar is hover-only on desktop and always visible on mobile; a long-press
   menu would be nicer on touch.
4. `Message.sender`, `Review.reviewer/target` duplicate the participant links (see items above).
5. Trips and Reservations must still call `open_conversation` / `close_conversation` /
   `mark_trip_completed`; until then chats only exist through the seed or the invite flow.
6. Time is shown in the browser's timezone; the server renders UTC-aware values.

## Floating messages bubble (added after UI polish v2)
A small "Messages" pill at the bottom-right of every page for logged-in users (hidden inside the
chat module itself). The red badge is the total unread count; clicking it opens a popover with the
5 most recent chats, each linking to its conversation, plus "See all".
- **One line in a shared file:** `templates/base.html` now ends with
  `{% if user.is_authenticated and request.resolver_match.app_name != "communication" %}{% include "communication/_chat_bubble.html" %}{% endif %}`
  (needs the `request` context processor, which Coridee already enables). Other modules' teams should
  keep that line when they merge `base.html`.
- New files: `communication/templates/communication/_chat_bubble.html`, `static/communication/chat_bubble.css|js`.
- New endpoint: `communication:chat_bubble_state` (`/communication/chat/bubble/`, JSON, GET, login required).
  The chat list logic moved into `_conversation_overview()` in `views.py` and is shared by the list page and the bubble.
- Refreshes every 30 s while the tab is visible, and when it becomes visible again (no websockets).
- Verified on the home page in headless Chromium (badge, popover, hidden on chat pages). Not tested on a phone:
  below 640 px the label is hidden and only the icon + badge show.
