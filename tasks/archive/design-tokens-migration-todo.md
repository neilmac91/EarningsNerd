# Design-tokens migration — authenticated app views (follow-up to PR #399)

Branch base: `origin/main` @ 96f7080 (includes the merged design system).
Goal: migrate the authenticated app views the user named — **dashboard, company, filing** —
and their supporting components from hardcoded slate/blue/red/green/amber classes (and the
legacy `mint`/`primary` accent) to the design-system tokens.

## Scope & exclusions
- IN: dashboard view, company/[ticker] view, filing/[id] view + their supporting components;
  mint/primary -> brand accent swaps within those areas.
- OUT (bespoke/intentional or not named): marketing/landing (`app/page.tsx`, pricing, waitlist,
  HowItWorks, Hero*, FeatureShowcase, CtaBanner, SocialProof), auth pages (login/register/reset/
  verify/forgot), legal (privacy/terms/security), `global-error.tsx`, hero gradients, navy code
  blocks. Recharts series colors passed as hex props -> possible follow-up (not Tailwind classes).

## Delivery: focused per-view PRs (each verified independently)
- [ ] PR A — Dashboard: app/dashboard/page.tsx, app/dashboard/watchlist/page.tsx, app/dashboard/error.tsx,
      components/dashboard/{FilingFeed,EarningsCalendar,WhatChangedCard}.tsx, components/watchlist/WatchlistAddSearch.tsx
- [ ] PR B — Company: app/company/[ticker]/page-client.tsx, components/{FinancialCharts,FinancialMetricsTable}.tsx,
      features/peers/.../PeerComparisonPanel.tsx, features/insiders/.../InsiderActivityPanel.tsx,
      features/fundamentals/.../FundamentalsTrendChart.tsx
- [ ] PR C — Filing: app/filing/[id]/page-client.tsx, components/{SummarySections,SummaryBlock,SourceTrace}.tsx,
      features/filings/components/*.tsx (+ copilot/*)

## Canonical token mapping (same as PR #399)
surfaces bg-white/dark:bg-slate-800 -> bg-panel-light dark:bg-panel-dark; inputs dark:bg-slate-900 -> dark:bg-background-dark;
borders slate-200/700,300/600 -> border-border-light dark:border-border-dark;
text 900/white -> text-text-primary-*; 700/600,300/400 -> text-text-secondary-*; 500 -> text-text-tertiary-*;
brand: blue/mint primary buttons -> bg-brand-strong hover:bg-brand-light text-white dark:bg-brand-dark dark:text-background-dark;
links/blue text -> text-brand-strong dark:text-brand-strong-dark; focus:ring-blue-500 -> focus:ring-brand-light;
status: green->success, red->error/loss (soft bg -> loss-soft/gain-soft, BARE for *-soft-dark rgba), amber->warning;
data semantics in financial tables/figures: up/positive -> gain, down/negative -> loss.
Opacity modifiers only on hex tokens (brand/loss-light/gain/success/warning/error/border/text/bg) — never on *-soft-dark (rgba).

## Process
Each PR: agent does mechanical edits (edit-only, no commit) -> I review diffs -> npm run typecheck + lint + build + test -> I commit + push + open draft PR.

## Review
(filled in as PRs land)
