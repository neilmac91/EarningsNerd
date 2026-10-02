# Keep a dialog's opener mounted while the dialog is open, so focus has somewhere to return

Date: 2026-10-02   Area: frontend

**Context**: The cookie settings panel moved to `ui/Modal`, which returns focus to its opener on
close. But `handleOpenSettings` hid the banner as it opened the dialog, which unmounted the
Customize button that opened it. Modal captured `<body>` as the opener. After Cancel, Escape, the
✕ or a scrim click, the cookie UI was gone and keyboard focus restarted at the top of the page. The
real-build keyboard pass passed only because it recorded "BODY" as expected. The founder's call: keep
the banner mounted beneath the dialog so Cancel returns focus to it.

**Rule**:

(a) Opening a dialog must not unmount the element that opened it. Render the dialog beside the
opener; the scrim covers it. Hide the opener only on a path that finishes the flow (Save here).

(b) A keyboard pass never accepts `<body>` as where focus lands after a dialog closes. Name the
element it should land on.

(c) For each consumer, a spec asserts the focus-return target per close path.

**Evidence**: `frontend/components/CookieConsent.tsx` (`handleOpenSettings` no longer hides the
banner). `frontend/tests/unit/CookieConsent.spec.tsx`: Escape, Cancel and ✕ each return focus to
Customize. Mutation: restoring `setShowBanner(false)` fails 4 of 6 cases. The real-build keyboard
pass (both themes, 1440 and 375) returns focus to Customize after Escape, Cancel and a scrim click.
A static gate cannot see "the opener unmounts" in general; the per-consumer spec is the enforcement
(rule 12).
