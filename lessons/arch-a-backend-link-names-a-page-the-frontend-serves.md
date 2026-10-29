# A link the backend builds on FRONTEND_URL names a page the frontend serves

**Date:** 2026-10-29 · **Area:** architecture / mail

**Context:** The waitlist's welcome mail asked every new member to verify their address "to secure
your place" through `{FRONTEND_URL}/api/waitlist/verify/{token}`. No frontend route served that
path: a GET answered 404 on www, and the API route that would have taken the token answered only a
POST. Nothing read the flag it set, either. The link shipped in every welcome mail until E46 (2)
dropped the step, its sentence, its token and its route. No test linked a mail's link to a page.

**Rule:** A link the backend builds on `settings.FRONTEND_URL`, in a mail, a redirect or a response,
names a page, a route handler or a public file under `frontend/`. When a page moves or goes, change
or remove every link to it in the same PR. A step a mail asks for needs both a page that takes it and
a reader of what it records, or the mail does not ask for it.

**Evidence:** E46 (2) (`tasks/todo.md`, closed with this lesson); `backend/app/services/waitlist_service.py`
(the removed `build_verification_link`); `backend/tests/unit/test_frontend_links_resolve.py` (the gate:
each f-string or `+` that starts from `FRONTEND_URL` in `backend/app` resolves against `frontend/app`
or `frontend/public`, its planted forms including the removed link).
