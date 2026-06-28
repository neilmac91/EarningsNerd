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
- [x] Run multi-agent audit (6 finders by area + adversarial per-finding verify) → 30 confirmed, 0 rejected
- [x] Fix issue 1: add `.dark` overrides to `.markdown-body` family (theme tokens; light unchanged)
- [x] Fix issue 2: make dashboard search container theme-responsive (panel + border + shadow)
- [x] Fix every other confirmed instance from the audit
- [x] Grep gate: zero unconditional `*-dark` color utilities on shared surfaces; zero `tertiary-dark` text
- [x] Verify: typecheck ✓, lint (--max-warnings 0) ✓, build ✓ (26 routes), test ✓ (211/211)
- [x] Compiled-CSS proof of the `.dark .markdown-body` rules + both-theme reasoning per surface
- [x] Commit, push, draft PR (#459)

## Audit findings (verified — 30 confirmed, 0 rejected)

Multi-agent audit: 6 area finders → 1 adversarial verifier per candidate (36 agents). Consolidated fixes:

**Reported (high):**
- `globals.css` `.markdown-body` ×7 rules → added `dark:` token pairs (body/p = secondary-dark, h2/h3/th = primary-dark, borders = border-dark, blockquote accent = brand-dark). Light unchanged.
- `dashboard/page.tsx:201-202` → search card now `bg-panel-light dark:bg-panel-dark` + border; label themed.

**Other confirmed (P1 dark-leaks-into-light):**
- `copilot/AskAboutSelection.tsx:113` → "Ask about this" pill: `bg-brand-strong text-white … dark:bg-brand-dark dark:text-background-dark` pair.

**P2 single-theme surfaces:**
- `UserMenu.tsx:110` "Verify your email" → `text-amber-700 dark:text-amber-300` (was pale-yellow-on-near-white).
- `ChartErrorBoundary.tsx:35-36` fallback → panel + border + text token pairs (was `bg-gray-50`/`text-gray-600`).
- `WaitlistForm.tsx:260` + `WaitlistStatus.tsx:65` error banners → `error-*` token pairs (was raw `red-50/200/700`).
- `TrendingTickers.tsx` ×3 flame icon → `text-orange-500 dark:text-orange-300` (was washed-out in light).
- `SummarySections.tsx:333` active-tab underline + `SummaryBlock.tsx:15` accent stripe → added `dark:` brand border.

**P3 contrast/token misuse:**
- `FilingViewer.tsx:155` passage-missing banner → `text-warning-light dark:text-warning-dark` (was light-on-light).
- **App-wide `dark:text-text-tertiary-dark` → `dark:text-text-secondary-dark` migration (16 files):** the
  documented "muted text on dark must be secondary, never tertiary-dark (fails WCAG AA ~2.5:1)" rule.
  Covered the flagged auth/waitlist instances **plus** settings/, error.tsx, auth/, modals the per-slice
  finders didn't all reach.

**Verified NOT a bug (correctly skipped):** `lib/financialTone.ts` `directionTextOnDark` — intentional
unconditional `-dark` map for permanently-dark surfaces (documented exemption).

## Review

Surgical, design-system-driven sweep: **25 files, +57/−53**, almost entirely additive `dark:` token
pairs — no light-mode pixels changed for the markdown body (compiled CSS confirms identical light
values). Every fix uses canonical tokens from `tailwind.config.js`; no new raw/legacy-brand colors.

- **Issue 1** proven via compiled `.dark .markdown-body` CSS: dark body = #9CA3AF (secondary-dark,
  ~5.9:1), headings = #D7DADC (primary-dark, ~9:1) — readable; light untouched.
- **Issue 2**: dashboard search card now matches its sibling cards' `panel + border + shadow-sm` pattern.
- Gates: zero unconditional `*-dark` leaks in app/components/features; zero `tertiary-dark` text tokens.
- CI/build/lint/typecheck/tests all green. Final both-theme visual confirmation available on the Vercel
  preview once the branch rebuilds.
