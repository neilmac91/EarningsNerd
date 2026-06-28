# Theme Contrast Bugs — Plan & Review

Branch: `claude/frontend-theme-contrast-bugs-8bcvsa`

## Reported bugs (root causes confirmed)

1. **Executive Summary unreadable in dark mode.**
   `frontend/app/globals.css` `.markdown-body` family (lines ~237–275) hardcodes light-theme
   colors with NO dark variants: `h2/h3 → text-slate-900`, `p → text-slate-700`, table cells
   `bg-slate-100 / text-slate-900 / border-slate-200`, blockquote `text-slate-600`. In dark mode
   these render near-black on the dark navy panel. List items have no color rule, so they inherit
   the wrapper's `dark:text-text-secondary-dark` and stay readable — matching the screenshot.
   Render path: `app/filing/[id]/page-client.tsx:1299` (`<div className="markdown-body …">`).

2. **Dashboard "Jump to any company" search bar dark in light mode.**
   `frontend/app/dashboard/page.tsx:201–202` hardcodes single-theme `bg-panel-dark` +
   `text-text-secondary-dark` with no light pair → dark navy box on the cream light-mode page.
   Violates DESIGN_SYSTEM §2 (theme-responsive pairs mandatory on shared surfaces).

## Scope (confirmed with user)
App-wide sweep: fix the two reported bugs + audit `app/`, `components/`, `features/`, `lib/`,
`globals.css` for the same class of bug (single-theme classes on shared surfaces, hardcoded
slate/hex/status colors, `tertiary-dark` muted-text-on-dark misuse) and fix every confirmed one.

## Plan
- [x] Investigate & confirm root causes of both reported bugs
- [x] Read DESIGN_SYSTEM.md + token definitions; confirm `darkMode: 'class'`
- [ ] Run multi-agent audit (finders by area + adversarial per-finding verify) → verified bug list
- [ ] Fix issue 1: add `.dark` overrides to `.markdown-body` family (theme tokens; light unchanged)
- [ ] Fix issue 2: make dashboard search container theme-responsive (panel + border + shadow)
- [ ] Fix every other confirmed instance from the audit
- [ ] Grep gate: zero unconditional `*-dark` color utilities on shared surfaces; zero legacy-brand leaks
- [ ] Verify: `npm run typecheck`, `npm run lint` (max-warnings 0), `npm run build`, `npm run test`
- [ ] Reason through BOTH themes for each touched surface
- [ ] Commit, push, open draft PR

## Audit findings (verified)
_(to be filled in after the audit workflow completes)_

## Review
_(to be filled in at the end)_
