# Treat a design-token/theme migration as app-wide by default

Date: 2026-06-23   Area: frontend

**Context**: Adopting the new design system, converted the landing page + chrome and called it done. The user then found the same class of issues (legacy mint/emerald/`primary`/blue/sky/teal as brand, unthemed surfaces) on Contact, Compare, Pricing, Search — and a codebase sweep surfaced ~37 more files, discovered only page-by-page via the user's screenshots.

**Rule**: Treat a design-token/theme migration as app-wide by default (public AND authenticated). Enumerate the blast radius up front with a repo-wide grep for the legacy tokens and make that grep the done-gate — never scope to the page that prompted the change.

**Evidence**: ~37 more files (compare/result, the copilot workspace, charts, modals, auth/legal pages); conventions + the grep live in `frontend/DESIGN_SYSTEM.md`.
