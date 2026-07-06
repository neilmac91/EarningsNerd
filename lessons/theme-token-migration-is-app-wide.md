# Treat a theme/token migration as app-wide by default; the repo-wide grep is the done-gate

**Area:** design-system · **Date:** 2026-06-23

Adopting the new design system, I converted the landing page + chrome and called it done. The
user then found the *same* class of issues (legacy mint/emerald/`primary`/blue/sky/teal as brand,
unthemed surfaces) on Contact, Compare, Pricing, Search — and a codebase sweep surfaced ~37 more
files (compare/result, the copilot workspace, charts, modals, auth/legal pages). They only came to
light page-by-page via the user's screenshots.

**Rule:** treat a design-token/theme migration as **app-wide by default** (public *and*
authenticated). Enumerate the blast radius up front with a repo-wide grep for the legacy tokens and
make that grep the done-gate — never scope to the page that prompted the change. (Conventions +
the grep live in `frontend/DESIGN_SYSTEM.md`.)
