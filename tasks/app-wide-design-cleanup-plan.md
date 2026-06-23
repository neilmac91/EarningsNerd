# Entire-app design-system cleanup (PR #403)

User feedback round 3: 4 public pages off-system + "fix everywhere". Decisions:
- Scope = ENTIRE APP (public + authenticated).
- Merge = final Vercel preview review by user BEFORE merging to main.
Follow CLAUDE.md + the design system (brand sage/slate, flat solid, raised-card+shadow,
status tokens, no legacy mint/emerald/primary/blue/sky/teal as brand).

## Canonical patterns (apply consistently)
- Primary button: `bg-brand-strong text-white hover:bg-brand-light dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark focus-visible:outline-brand-light` (drop text-slate-950 / mint / glow).
- Accent text/link/icon: `text-brand-strong dark:text-brand-strong-dark`. Focus rings: `outline-brand-light`.
- Page bg: `bg-background-light dark:bg-background-dark`. Raised card: `bg-panel-light dark:bg-panel-dark border border-border-light dark:border-white/10 shadow-e2 dark:shadow-none` (chips e1, hero/featured e3).
- Input: `bg-panel-light dark:bg-slate-900/60 border-border-light dark:border-white/10 text-text-primary-* placeholder:text-text-tertiary-light dark:placeholder:text-text-secondary-dark` + brand focus.
- Text: primary/secondary token pairs; muted on dark = SECONDARY (never tertiary-dark). Headings need explicit color.
- Status: success (checkmarks/savings), warning, error, info — use tokens w/ dark pairs.
- Charts: use design-system `chart.1..6` palette (NOT emerald #10b981); axis/grid/tooltip theme-aware.
- Remove duplicate page-level <ThemeToggle>: compare:74, pricing:166, dashboard:184.
- LEAVE brand-mandated surfaces: Google white / Apple black buttons (fix only their mint focus rings).

## Batches (parallel-friendly, disjoint files)
- [ ] B1 4 flagged public pages: contact(+ContactForm), compare(+SubscriptionGate spinner; rm toggle:74), pricing(rm toggle:166; featured card->brand+panel; FAQ contrast), search/FullTextSearch (full theming).
- [ ] B2 Public auth+legal: login/register/forgot/reset/check-email/verify-email, PasswordField, Google/Apple focus rings; privacy/terms/security/waitlist(+Waitlist* comps)/delete-account; error.tsx. (mint->brand links/CTAs — uniform.)
- [ ] B3 Shared/app-wide: StateCard, CookieConsent(blue->brand), GlobalErrorBoundary(blue->brand), global-error(blue->brand), UpgradeModal, EmailVerificationModal, PeekLocked, TrialBanner, EmptyState, SummaryProgress(primary->brand).
- [ ] B4 Auth nav/dashboard: UserMenu, NotificationBell, SecondaryHeader, dashboard(rm toggle:184), company/[ticker] teal:343, FilingPulse.
- [ ] B5 Filing TickerFilingsView (dark-only) + copilot/ (8 files). [DECISION: copilot pane theme-responsive vs intentionally-dark.]
- [ ] B6 Charts: FinancialCharts, FundamentalsTrendChart, PeerComparisonPanel, ComparisonMetricChart, DeltaBar, Sparkline — chart palette + theme-aware hexes. (careful; review closely.)

## Judgment calls (recommend, confirm with user)
1. Copilot workspace panes: RECOMMEND theme-responsive (consistency) — but could stay intentionally dark.
2. Off-brand BLUE primary CTAs (cookie/error boundaries): RECOMMEND -> brand.
3. Charts: RECOMMEND design-system chart palette (chart.1 primary) + theme-aware axis/tooltip.

## Verify + merge
Per-batch typecheck/lint; final combined typecheck+lint+build(24)+vitest; grep no legacy mint/emerald/primary/blue/sky/teal-as-brand remain; push; PING USER for preview review in both themes; MERGE only after their OK.
