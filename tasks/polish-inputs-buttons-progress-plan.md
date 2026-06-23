# Polish round: inputs / secondary buttons / progress / settings density

User feedback (round 4) on authenticated pages. Locked design decisions:
- Inputs: BRIGHTER fill + clear border (inputs should pop/sink vs their card).
- Secondary buttons: FILLED + border + soft shadow (one canonical style).
- Progress completed-step indicators: BRAND sage (match the ring), not green.
- Settings density: tighten (judgment).
Follow CLAUDE.md + frontend/DESIGN_SYSTEM.md. OPEN DECISION: centralize into shared
components vs inline-consistent classes (asking user).

## Root-cause gaps (from audits)
1. Input pattern uses `bg-panel-light` on a `panel-light` card -> no light-mode fill contrast (dark ok).
2. No codified SECONDARY button -> 5 ad-hoc recipes; several `hover:opacity-90` (darkens, violates DS).
3. SummaryProgress completed-state = raw success green while ring = sage (outlier; copilot/verify-email checks are already brand). StreamingSummaryDisplay has same split.
4. No shared Button/Input component (components/ui/ has only EmptyState) -> drift.

## Scope (from sweep)
- Inputs (~14 flagged): ContactForm(4), ChangePasswordForm(3), ProfileForm, NotificationPreferencesForm(select), compare ticker, settings delete-confirm, delete-account confirm (bg-white-on-bg-white), CopilotComposer textarea (transparent), PasswordField + auth pages (borderline: fill==AuthShell pane). Fix: light fill -> bg-white (brightest, robust on page+card) + border-border-light; keep dark bg-slate-900/60.
- Secondary buttons (~8-9): filing Export PDF/CSV/Save Summary/Regenerate, BillingPanel Manage billing, ConnectedAccounts Sign out, company Add-to-watchlist + inactive filter chips, CopilotMessage follow-up chips. Canonical secondary: `bg-panel-light border border-border-light shadow-e1 hover:bg-brand-weak hover:shadow-e2 dark:bg-panel-dark dark:border-white/10 dark:shadow-none dark:hover:bg-white/5` + text-primary. (Drop hover:opacity-90.)
- Progress: SummaryProgress completed-state success->brand + tokenize its gray/slate/white literals; StreamingSummaryDisplay completed circle success->brand. KEEP genuine "Saved"/"Just added" confirmations green (semantic, DS §8).
- Settings density: BillingPanel + sibling sections — tighten space-y, strengthen value emphasis + label<->value association, group the action with its row.
- Docs: update DESIGN_SYSTEM.md §3 input pattern (brighter fill) + add a Secondary-button pattern + note progress=brand. 

## Verify
typecheck, lint (--max-warnings 0), build (24pp), vitest; both-theme preview; PR (draft) -> user review before merge.
