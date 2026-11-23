---
version: 1
slug: "templates-base-html"
primary_target: "templates/base.html"
related_targets: ["users/templates/users"]
---

# Surface brief: CoRide app shell and Users module (Sprint 1)

Scope: the shared app shell (base template, navigation, design system used by all five modules) and the Users module pages: sign up, log in, my profile, edit profile, change password, delete account, and the in-app admin pages (user list, user detail with ID + selfie, create admin, edit, verify, suspend/reactivate, delete).

Visitor mode: **Operate**. Built code-led.

Audience and job: anyone travelling between Tunisian cities, on phone and computer equally; admins on a computer. Jobs: create a trustworthy account fast; see and manage one's own data; for admins, compare ID and selfie and decide.

Constraints: English only, Django server-rendered templates, input validation visible on every field, Sprint 1 CRUD only.

Memorable moment: the verified seal turning from an unfired outline to a fired cobalt tile.

Unresolved: none blocking.

## Direction contract

THESIS: Trust is a fired object. A verified identity is shown as a cobalt eight-point tile seal, the only ornament in the app; everything around it is a calm, exact working surface on tin-glaze white. Refuses the category default of rounded floating cards, soft shadows and a small teal check.

OWN-WORLD: Cool glaze-white ground with pure white sheets and 1px glaze-line borders, no shadows. Ink near-black text on one nine-step blue-tinted neutral ramp. Cobalt for trust, identity, links and focus. CoRide red only for the brand mark and the one primary action per screen. Copper green for active/success, saffron for pending, deep red outlines for destructive. Readex Pro, self-hosted, tabular figures. Everything on an 8px cell grid.

STORY: A visitor sees a serious local product, signs up on one page, and lands on a profile whose seal is an unfired dashed outline reading "Verification pending". When an admin compares ID and selfie and verifies, the seal is fired: solid cobalt. Admins scan a dense table where every row carries the same seal state.

FIRST VIEWPORT: Ink top bar: brand mark at the start, module navigation, language switch and account menu at the end. Below, two columns on desktop (identity sheet 400px; details sheet fluid), one column on phone: photo, name at 32px, the 56px seal with its state line, then the details grid in label/value pairs; one red primary action, secondary outline actions, and Delete isolated at the far end.

FORM: Nabeul Glaze (Nabeul tin-glaze ceramics), position 5 on the ordered grounded list; signature move: the fired/unfired khatem seal as the verification state everywhere a person appears. Raises kept: single tonal ramp (Exposure Record), isolated outlined destructive actions (Developer Console), one 8px cell grid (Grid Specimen). seed: none (unavailable)

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
