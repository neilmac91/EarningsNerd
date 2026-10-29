# A link the backend builds on FRONTEND_URL names a page the frontend serves

**Date:** 2026-10-29 · **Area:** architecture / mail

**Context:** The waitlist's welcome mail asked every new member to verify their address "to secure
your place" through `{FRONTEND_URL}/api/waitlist/verify/{token}`. No frontend route served that
path: a GET answered 404 on www, and the API route that would have taken the token answered only a
POST. Nothing read the flag it set, either. The link went out in every welcome mail until E46 (2)
dropped the step, its sentence, its token and its route. No test tied a mail's link to a page.

**Rule:** A link the backend builds on `settings.FRONTEND_URL`, in a mail, a redirect or a response,
names a page, a route handler for GET or a public file under `frontend/`. When a page moves or goes,
change or remove every link to it in the same PR. A step a mail asks for needs both a page that takes
it and a reader of what it records, or the mail does not ask for it.

**Evidence:** E46 (2), closed by the pull request that added this lesson;
`backend/app/services/waitlist_service.py` (the removed `build_verification_link`).
`backend/tests/unit/test_frontend_links_resolve.py` is the gate for the first sentence. Every
`FRONTEND_URL` read in `backend/app` must be followed to a link that resolves against `frontend/app` or
`frontend/public`, or the gate fails. A bare origin passes only in a function `BARE_ORIGINS` lists, as
often as it lists. The two forms the scan cannot read are named in its docstring and planted as gaps:
an alias another module imports, and `getattr`. No gate checks the last sentence, whether a step has a
reader: review checks it.
