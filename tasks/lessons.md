# Lessons

## 2026-06-11 — Adjacent-line edits conflict on merge
While draining the dependabot queue: assumed PRs touching *different lines* of
`backend/requirements.txt` could merge back-to-back without conflicts. Wrong —
git's 3-way merge conflicts when hunks fall within ~3 lines of each other
(context window), not only on identical lines. PR #224 (pydantic, line 4)
conflicted after #222 (python-multipart, line 3) and #223 (email-validator,
line 6) merged.

**Rule:** treat any two PRs editing the same file within a few lines of each
other as conflicting; plan serial merge + rebase between them. Only file-level
disjoint PRs are safely parallel.

## 2026-06-16 — Backend CI runs bandit, not just ruff
The `backend-tests` CI job runs `bandit -r app -ll` as a gate. I verified locally with
ruff + pytest only, so a `hashlib.sha1()` call (legitimately required by the HIBP
k-anonymity protocol) tripped bandit B324 (weak hash, High) and failed CI on the first
push. Fix was `usedforsecurity=False` (bandit's own suggested remedy + semantically correct).

**Rule:** before pushing backend changes, run the full local gate — `ruff check .` AND
`bandit -r app -ll` AND `pytest` — not just ruff + pytest. For intentional weak-hash use
(SHA-1/MD5 required by an external protocol), pass `usedforsecurity=False`.

## 2026-06-16 — Verify against the actual code before "implementing" a plan item
While executing the auth/privacy plan I almost rebuilt analytics consent-gating, the
Privacy Policy, and the GDPR export/delete UI — all three already existed and were
well-built (`posthog-provider.tsx` gates on consent; `/privacy`; `/dashboard/settings`).
The audit/plan flagged them as gaps from a distance; the code said otherwise.

**Rule:** re-read the relevant files immediately before implementing any plan item, even
one the plan marked "missing". Confirm the gap is real before writing code — re-implementing
working code is wasted effort at best and a regression risk at worst.

## 2026-06-23 — A theme/token migration is app-wide, not "the page in the screenshot"
Adopting the new design system, I converted the landing page + chrome and called it done. The
user then found the *same* class of issues (legacy mint/emerald/`primary`/blue/sky/teal as brand,
unthemed surfaces) on Contact, Compare, Pricing, Search — and a codebase sweep surfaced ~37 more
files (compare/result, the copilot workspace, charts, modals, auth/legal pages). They only came to
light page-by-page via the user's screenshots.

**Rule:** treat a design-token/theme migration as **app-wide by default** (public *and*
authenticated). Enumerate the blast radius up front with a repo-wide grep for the legacy tokens and
make that grep the done-gate — never scope to the page that prompted the change. (Conventions +
the grep live in `frontend/DESIGN_SYSTEM.md`.)

## 2026-06-23 — Don't set global element-level colors that fight the surface
A global `h1–h6 { color: var(--heading-color) }` (warm brown in light) painted brown ink on the
always-dark hero when the site was in light theme — the "brown heading" bug. Element-level global
colors override the color a heading would otherwise inherit from its (dark) surface.

**Rule:** never set a global element-level *color* that surfaces opt out of. Keep global rules to
non-conflicting properties (font-family) and give each heading an explicit theme-pair color.

## 2026-06-23 — Theme-paired ≠ readable; check luminance against the actual background
A CTA/card used `bg-brand-weak` (#ECF2EE) as its fill on the cream page (#F4F3EE) — a ~1.02:1
surface contrast (brand-weak is actually *darker* than cream), so the card was invisible. It was a
valid token and a valid dark pair, but unreadable.

**Rule:** for surfaces, verify the **luminance delta vs the background it sits on**, not just that a
token exists. Lift cards with a *lighter* fill (`panel-light`) + a soft `shadow-e*`; brighten on
hover, never darken. `brand-weak` is an accent/tint, not a card fill.

## 2026-06-23 — Reserve loud status colors for genuine status
Mapping `StateCard`'s default `info` variant to the blue `info` token turned every guidance box
(e.g. "Start a comparison") loud blue — off-brand against the sage/slate identity.

**Rule:** brand sage/slate is for actions/accents; loud status colors (blue/green/red) are for real
state messages. A default guidance/empty-state container should be subdued or brand-tinted.

## 2026-06-23 — Green CI ≠ correct visuals; eyeball both themes
Every visual regression this round (brown heading, clashing gradients, invisible cards, blue info
box) passed typecheck/lint/build/tests and was caught only by the user looking at the preview.

**Rule:** for any visual/theme work, "tests pass" is necessary but not sufficient. Review the
deployed preview in **both light and dark** (or get a preview review) before declaring done.

## 2026-06-23 — A frontend gate is not a gate; enforce access server-side
While planning the closed beta I assumed `WAITLIST_MODE` kept the public out. It does not: it's read
**only** in `frontend/middleware.ts` (redirects `/`→`/waitlist`), while the backend register endpoint
(`backend/app/routers/auth.py:608-676`) accepts **anyone** — no allowlist, no invite check. Flipping
`WAITLIST_MODE=false` would have silently opened registration to the entire internet. The "gate" was
cosmetic; a curl to `/api/auth/register` walks straight past it.

**Rule:** any access/gating requirement (waitlist, invite-only, beta cohort, role) must be enforced
in the **backend** at the mutation endpoint — the frontend middleware/redirect is UX only and is
trivially bypassed. Before trusting an existing gate, grep for where the *server* validates it; if the
check lives only in `middleware.ts`/route guards, treat the resource as ungated.
