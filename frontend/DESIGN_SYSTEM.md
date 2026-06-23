# EarningsNerd Design System — usage conventions

The single source of truth for **how to use** the design tokens in `frontend/tailwind.config.js`
and the effect classes in `frontend/app/globals.css`. Read this before touching any UI; subagent
briefs for UI work should link here. (Token *definitions* live in `tailwind.config.js`; this doc is
the *how/why* + the rules learned the hard way.)

> TL;DR: **brand = sage (light) / slate (dark).** Mint/emerald/`primary`/blue/sky/teal are **not**
> brand. Every surface is theme-responsive via light/dark token **pairs**. Cards lift off the cream
> with a soft shadow (not a tint). Headings carry an explicit color. Verify in **both themes**.

## 1. Palette roles (don't mix them)

| Role | Light | Dark | Use for |
|------|-------|------|---------|
| **Brand** | sage `brand-light #4F7A63` / `brand-strong #3C6650` / `brand-weak #ECF2EE` | slate `brand-dark #92A0E2` / `brand-strong-dark #B4BEEE` | Primary actions, links, accents, focus rings, active states |
| **Surface** | `background-light #F4F3EE` (cream page) / `panel-light #FBFAF6` (card) | `background-dark #0B1120` / `panel-dark #1F2937` | Page + card backgrounds |
| **Text** | `text-primary-light #1A1A17` (espresso) / `text-secondary-light #374151` / `text-tertiary-light #6B7280` / `text-heading-light #3A2E26` | `text-primary-dark #D7DADC` / `text-secondary-dark #9CA3AF` | Body/headings (see §4) |
| **Border** | `border-light #E5E7EB` | `border-dark` / `white/10` | Hairlines |
| **Status** | `success`/`warning`/`error`/`info` (each has `-light`/`-dark`) | — | Genuine state messages only |
| **Financial** | `gain`/`loss`/`flat` (+ `-soft` tints) | — | Money/% direction only |
| **Chart** | `chart-1..6` (`#3E8E84`, `#5B7CC0`, `#D99E4A`, `#CF7159`, `#8B7BC0`, `#5E9A6E`) | same | Chart series colors |
| **Elevation** | `shadow-e1..e5` | (use `dark:shadow-none`) | Card lift |

**Legacy / banned as brand:** `mint-*`, `emerald-*`, `primary-*` (it is a back-compat **alias for mint**),
`green-*`/`blue-*`/`sky-*`/`teal-*`/`cyan-*`/`indigo-*` used as a primary/brand color, and `shadow-glow-mint*`.
Mint tokens are kept only as a back-compat alias — never introduce new usages.

## 2. Theme-responsiveness is mandatory

Every color on a surface that renders in **both** themes must be a light/dark **pair**:
`bg-x-light dark:bg-x-dark`, `text-…-light dark:text-…-dark`. Never ship a single-theme color on a
shared surface (it caused white-on-cream and dark-on-cream bugs across the app).

- **Muted text on dark = `secondary`, never `tertiary-dark`** (`text-text-tertiary-dark` fails WCAG AA
  on dark panels). Pattern for muted: `text-text-tertiary-light dark:text-text-secondary-dark`.
- The theme-aware **effect classes** (`.glass-card`, `.mockup-frame`, `.hero-search-glow`,
  `.text-gradient-mint`) already switch on `.dark` in `globals.css` — don't add `bg-*` overrides to
  them; only theme their children.

## 3. Canonical component patterns

**Use the shared components, don't hand-roll** — `components/ui/Button.tsx` (`<Button variant>` +
`buttonVariants()` for `<Link>`/`<a>`) and `components/ui/Input.tsx` (`<Input>` + `inputClasses` for
`<textarea>`/`<select>`). They centralize the patterns below so buttons/fields can't drift again
(before they existed there were 5 ad-hoc "secondary" button recipes).

```
Primary button   <Button>  ·  bg-brand-strong text-white hover:bg-brand-light
                 dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark   (no text-slate-950, no glow)

Secondary button <Button variant="secondary">  — panel fill + hairline + soft lift; BRIGHTENS on hover
                 bg-panel-light border border-border-light shadow-e1 hover:bg-brand-weak hover:shadow-e2
                 dark:bg-panel-dark dark:border-white/10 dark:shadow-none dark:hover:bg-white/5   (never hover:opacity-90)

Tertiary button  <Button variant="tertiary">  — ghost: transparent + border, hover bg-brand-weak

Accent text/link text-brand-strong dark:text-brand-strong-dark
Focus ring       outline-brand-light  /  ring-brand-light  /  focus:border-brand-light

Card / panel     bg-panel-light dark:bg-panel-dark + border-border-light dark:border-white/10
                 shadow-e2 dark:shadow-none            (e1 chips · e2 cards · e3 hero/featured)

Input            <Input>  — fill is the BRIGHTEST surface so the field reads on BOTH the cream page
                 AND an off-white card (never reuse the card's own fill — the field would vanish):
                 bg-white dark:bg-slate-900/60 border-border-light dark:border-white/10
                 text-text-primary-light dark:text-text-primary-dark
                 placeholder:text-text-tertiary-light dark:placeholder:text-text-secondary-dark + brand focus

Soft accent fill bg-brand-strong/10 dark:bg-brand-dark/15   ·   Accent border border-brand-light/40 dark:border-brand-dark/40
```

- **One** secondary-button style (above). Don't invent `brand-weak`-fill or bare `panel-light` buttons,
  and never `hover:opacity-90` (it darkens; secondary buttons brighten toward `brand-weak`).
- Inputs must **delineate** from their surface — the bright `<Input>` fill is what makes a field
  visible on a same-tone card (the password fields previously vanished into their panel).

## 4. Headings

There is **no global heading color** (a global `h1–h6 { color }` rule painted brown ink on the
always-dark hero in light theme). Every heading needs an explicit color:
`text-text-primary-light dark:text-text-primary-dark` (or `text-heading-*`). Headings keep the
fixed grotesque font via the global `h1–h6 { font-family }` rule only.

## 5. Cards must *lift*, not tint

`brand-weak` (#ECF2EE) is **darker** than the cream page (#F4F3EE) — using it as a card *fill* gives
~1.02:1 contrast (invisible). Cards on cream use a **lighter** fill (`panel-light`) + hairline +
a soft `shadow-e*`; **brighten** on hover (`hover:bg-white`), never darken. `brand-weak` is an
accent/hover/tint color only — not a card surface.

## 6. Marketing surfaces

Flat **solid** surfaces — no decorative multi-hue gradients. A single subdued brand accent
(the hero accent word is a solid `text-brand-strong dark:text-brand-strong-dark`, not a gradient).
Light hero/CTA = `bg-background-light` / a `bg-panel-light`/`bg-brand-weak` panel; dark = navy/slate.

## 7. Theme mechanics

- **One** `<ThemeToggle/>`, in the global `Header` (desktop + mobile). No page-level toggles
  (Compare/Pricing/Dashboard had duplicates — removed).
- `app/layout.tsx` runs a **pre-paint theme bootstrap script** (mirrors `ThemeProvider`: saved
  `localStorage.theme` else system pref) to prevent FOUC. Keep `suppressHydrationWarning` on `<html>`.
- Logo: `<EarningsNerdLogo mode="auto" />` follows the app theme (reads the `.dark` class via
  MutationObserver) — don't hardcode `mode="dark"`.

## 8. Exemptions

- **Google / Apple sign-in buttons**: keep their brand-mandated surfaces (white / black). Only their
  focus rings get rebranded.
- **Status colors** (success green, warning amber, error red, info blue) and **gain/loss** are
  semantic — keep them; only convert *brand/primary* uses off the legacy palette. Reserve loud
  status colors for genuine state — a default guidance/info container should be subdued/brand-tinted,
  not loud blue (see `StateCard` `info` variant).
- **Progress / step / completion indicators use the BRAND accent (sage), not success-green.** Green
  is for a genuine terminal *confirmation* state ("Saved", "Just added"); in-progress step ticks and
  the completed steps of a running operation are brand activity, so they match the sage progress ring
  (`SummaryProgress` + the streaming-summary stepper).

## 9. Charts (recharts)

Series colors come from the **`chart-1..6`** palette (not emerald). Axis/grid/tooltip hexes must be
**theme-aware**: read the theme via `useContext(ThemeContext)?.theme === 'dark'` (light fallback) —
**not** `useTheme()`, which throws in the provider-less chart unit tests. Reference values:
grid `#374151`/`#E5E7EB`, axis text `#9CA3AF`/`#6B7280`, tooltip bg `#1F2937`/`#FBFAF6`,
border `rgba(255,255,255,0.1)`/`#E5E7EB`, text `#D7DADC`/`#1A1A17`.

## 10. Definition-of-done for any theme/token change

1. **App-wide, not just the obvious page.** A migration is app-wide by default — public *and*
   authenticated (dashboard, company, filing/copilot, charts, modals, auth/legal pages).
2. **Grep gate** — confirm zero residual legacy brand colors before claiming done:
   ```
   grep -rnE '\b(mint-[0-9]|glow-mint|(bg|text|ring|border|from|to)-primary-[0-9]|emerald-[0-9]|(from|to|bg|text|border|ring)-(sky|indigo|cyan|teal|violet|fuchsia)-[0-9]|bg-blue-[0-9])' app components features
   ```
3. **Verify in BOTH themes** on the Vercel preview — green CI ≠ correct visuals.
4. Run `npm run typecheck`, `npm run lint` (`--max-warnings 0`), `npm run build`, `npm run test`.
