# EarningsNerd Design System — usage conventions

**Drop-in replacement for `frontend/DESIGN_SYSTEM.md`** (synced July 2026: single Sage accent,
type v2, cream-audited contrast). Token *definitions* live in `frontend/tailwind.config.js`;
this doc is the *how/why* + the rules learned the hard way. Read it before touching any UI;
subagent briefs for UI work should link here.

> TL;DR: **brand = ONE Sage accent in both themes** (the sage/slate split is retired).
> Mint/emerald/`primary`/blue/sky/teal are **not** brand. Contrast is audited against the warm
> cream `#F4F3EE`, not white. Type v2 has three fixed roles (the font switcher is retired).
> Cards lift off the cream with a soft shadow (not a tint). Verify in **both themes**.

## 1. Palette roles (don't mix them)

| Role | Light | Dark | Use for |
|------|-------|------|---------|
| **Brand** | `brand #4F7A63` (**fill only**) / `brand-strong #3C6650` (text/links) / `brand-emphasis #345C48` (active) / `brand-weak #ECF2EE` (tint) / `brand-border #CFE0D6` | `brand-dark #7FB295` (fill/accent) / `brand-strong-dark #98C5AD` (text/links) / `brand-fill-dark #569272` (active) / `brand-weak-dark` / `brand-border-dark` | Primary actions, links, accents, focus rings, active states |
| **Surface** | `background-light #F4F3EE` (cream page) / `panel-light #FBFAF6` (card) | `background-dark #0B1120` / `panel-dark #1F2937` | Page + card backgrounds |
| **Text** | `text-primary-light #1A1A17` (espresso — heading ink is the SAME value; walnut `#3A2E26` retired) / `secondary #374151` / `tertiary #6B7280` | `text-primary-dark #D7DADC` / `secondary #9CA3AF` | Body + headings (see §4) |
| **Border** | `border-light #E5E7EB` | `border-dark` / `white/10` | Hairlines |
| **Status** | success `#15803D` · warning `#92400E` · error `#B91C1C` (+ `error.emphasis #991B1B` destructive hover) · info `#2563EB` (in-tint label: `info.text #1D4ED8`) | success `#22C55E` · warning `#F59E0B` · error `#F87171` · info `#60A5FA` | Genuine state messages only |
| **Financial** | `gain.text #15803D` / `loss.text #B91C1C` for delta **text**; `gain.light #16A34A` / `loss.light #DC2626` are **graphic/chip-only** (3:1 non-text floor); `flat #6B7280` (+ `-soft` tints) | `gain.dark #34D399` / `loss.dark #FB7185` (text-safe on navy) | Money/% direction only — never brand |
| **Chart** | `chart-1..6`: `#3E8E84` teal · `#B8812F` honey · `#5B7CC0` cornflower · `#CF7159` coral · `#6E7E9C` slate-blue · `#8B7BC0` periwinkle | same hexes (≥3:1 vs both cream and navy) | Chart series — a SEQUENCE, taken 1→N in order, never re-sorted |

**Legacy / banned as brand:** `mint-*`, `emerald-*`, `primary-*` (back-compat **alias for mint**),
`green/blue/sky/teal/cyan/indigo-*` as a primary color, and `shadow-glow-mint*`. The old chart hexes
(`#D99E4A` honey, `#5E9A6E` green) are retired — the green competed with sage; honey failed the
3:1 graphic floor on cream.

**Contrast floors are audited against cream `#F4F3EE`, not white.** Text ≥ 4.5:1 in both themes;
text on a tinted bg is measured against the mixed tint; non-text UI (bars, sparklines,
hairlines-as-meaning) ≥ 3:1.

## 2. Theme-responsiveness is mandatory

Every color on a surface that renders in **both** themes must be a light/dark **pair**:
`bg-x-light dark:bg-x-dark`, `text-…-light dark:text-…-dark`. Never ship a single-theme color on a
shared surface (it caused white-on-cream and dark-on-cream bugs across the app).

- **Muted text on dark = `secondary`, never `tertiary-dark`** (`text-text-tertiary-dark` fails WCAG AA
  on dark panels). Pattern for muted: `text-text-tertiary-light dark:text-text-secondary-dark`.
- The theme-aware **effect classes** (`.glass-card`, `.mockup-frame`, `.hero-search-glow`,
  `.text-accent-strong` — a solid ink, not a gradient) switch on `.dark` in `globals.css`, each as
  a full light/dark pair — don't add `bg-*` overrides to them. The legacy `.text-gradient-mint`
  alias is **purged** (cutover scan returned 0 uses); only `.text-accent-strong` exists.

## 3. Type v2 — three fixed roles (the font switcher is retired)

- **Headings:** Inter loaded WITH the variable `opsz` axis (`font-optical-sizing: auto` = SF-style
  Text↔Display cuts). ONE display weight: **600** (700/800 collapse to it). One theme-aware ink via
  `--heading-color` (`#1A1A17` / `#D7DADC`) — hierarchy comes from size + weight, never a second color.
- **Body & UI:** `-apple-system → Inter` (system-first; Apple hardware renders SF Pro, everyone
  else falls through to Inter — Inter sits BEFORE generic `system-ui` on purpose).
- **Data:** Geist Mono + `tabular-nums` — money, %, tickers, XBRL anchors, verbatim excerpts,
  Ask-this-Filing output. `.tabular` = mono evidence register; `.tnum` = tabular figures in the
  CURRENT (body) face — numerals inside prose/UI copy only. Data tables and KPI tiles are **not**
  `.tnum` surfaces: their numerics render mono (DataTable numeric cells, StatCard figures — the
  data-role rule).
- **Editorial serif (Newsreader)** is wired to exactly ONE surface: the real filing viewer
  (**`.filing-reader`**, 19/1.7, opsz auto — Item 1A, MD&A, notes). Serif = the filing's own words.
  **`.markdown-body` is NOT serif**: it carries the reader's list + heading + table manners on the
  **body sans**, but FILLS its pane with no measure cap (it renders inside a card/pane, where any
  capped measure reads as dead space — field-tested twice) — its app consumer is
  the AI-generated summary, and AI output never renders in the filing's voice. Ask output stays mono.
  **Links in both surfaces:** Tailwind preflight strips anchor color AND underline, so a shared
  globals rule restores them — `:is(.markdown-body, .filing-reader) a` =
  `text-brand-strong underline underline-offset-4 dark:text-brand-strong-dark`.
- **Tracking ramp** (`--track-*`): +0.01em ≤12px · 0 at 13–19px · −0.012em 20–24px · −0.016em
  26–32px · −0.02em 34–44px · −0.025em 48px+ · `--track-eyebrow 0.08em` for uppercase micro-labels.
- 12px UI-type floor (`text-data-xs` 11px only for dense numeric annotations). UPPERCASE tracked
  eyebrows are reserved for metric labels — never card titles (`CardTitle` is sentence case,
  14px/600 heading ink; it shipped as an eyebrow in v2 and was fixed in v2.1).
- **Figtree and Helvetica are retired.** `--font-active` survives as a permanent alias of the body
  role so existing `font-sans` usage keeps resolving; don't reference Figtree in new code.

## 4. Canonical component patterns

**Compose the component layer, don't hand-roll** — `components/ui/*` (Button, Badge, Input, Card,
DataTable, Skeleton, GuidanceCard, Notice) + `components/AskFilingAnswer.tsx` (v2.2: reworked to
the SHIPPED copilot data model — see below). Every component defines
default / hover / active / focus-visible / disabled / loading plus the system states (empty,
skeleton via the shared shimmer keyframe, error).

```
Primary button   <Button>  ·  LIGHT: white label on bg-brand, hover bg-brand-strong, active bg-brand-emphasis
                 DARK: NAVY-INK label on bg-brand-dark (text-background-dark), hover bg-brand-strong-dark,
                 active bg-brand-fill-dark.  White-on-fill-dark is 3.7:1 — never revert to it.

Secondary button <Button variant="secondary">  — panel fill + hairline + soft lift; BRIGHTENS on hover
                 bg-panel-light border border-border-light shadow-e1 hover:bg-brand-weak hover:shadow-e2
                 dark:bg-panel-dark dark:border-white/10 dark:shadow-none dark:hover:bg-white/5
                 (never hover:opacity — it darkens)

Ghost button     <Button variant="ghost">  — brand.strong text on transparent, tint hover
                 (`variant="tertiary"` is accepted as a deprecated alias of ghost — pre-v2 API)

Link as button   buttonVariants({ variant, size })  — the class-string factory for <Link>/<a>
                 styled as buttons; <Button> composes the same factory. Raw fields that the
                 <Input> component can't wrap use inputClasses({ invalid }).

Accent text/link text-brand-strong dark:text-brand-strong-dark   (never brand.DEFAULT as text on cream)
Focus ring       focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark;
                 destructive + invalid fields use shadow-ring-error

Card / panel     bg-panel-light dark:bg-panel-dark + border + shadow-e2 dark:shadow-none
                 (e1 chips · e2 cards · e3 hero/featured · e4/e5 menus & overlays)

Input            <Input>  — fill is the BRIGHTEST surface so the field reads on BOTH the cream page
                 AND an off-white card: bg-white dark:bg-slate-900/60 + hairline + brand focus ring

Delta text       text-gain-text dark:text-gain-dark  /  text-loss-text dark:text-loss-dark
                 (the 600-level gain/loss are chips + graphics only — the 3:1 non-text floor).
                 lib/financialTone.directionText IS this recipe — route delta text through it.

Solid chip       <Badge variant="solid">  — the primary colorway as a chip (brand.strong fill +
                 white label; dark: NAVY ink on brand.dark) for brand-weak TINTED grounds where the
                 tint chips vanish ("Recommended"). <Badge variant="info"> = interim-filing tint
                 (10-Q/6-K; light label ink = info.text); <Badge variant="warning"> = warning tint
                 (replaces raw-amber hand-rolls). beat/miss/new double as tonal recipes via icon={null}.

Inline notice    <Notice variant="error|info|success">  — compact icon + title + message + action
                 for form/auth flows and in-card states (role="alert" on error; action slot takes a
                 small Button). GuidanceCard is a STANDALONE centered panel — never nest it inside a
                 Card; inside a Card, Notice is the right scale.

Search field     <Input icon={<Magnifier/>}>  — leading glyph with an explicit pl-11 inset (px-3.5 +
                 a pl-11 override is Tailwind conflict-order-dependent — don't). Raw fields:
                 inputClasses({ leadingIcon: true }).

Chat composer    <Textarea variant="composer">  — transparent, auto-growing, chrome-free field; the
                 app-owned shell carries inputClasses() + focus-within:border-brand +
                 focus-within:shadow-ring-brand (never double chrome).

Semantic card    <Card as="section">  — same recipe on a semantic element.

Ask answer       <AskFilingAnswer>  — the SHIPPED copilot contract: status reading|streaming|done|error;
                 answer = GFM markdown (react-markdown + remark-gfm); markers [n] AND [F1]/[f1]/[F 1]
                 (case/whitespace tolerant) become chips showing the BRACKETED marker; unmatched markers
                 stay literal text — never a dead button. CopilotCitation = { n, excerpt, section_ref,
                 verified, fragment_url } — `verified` drives the Verified/Cited trust badge; never ship
                 a renderer that drops it.
                 REPO REALITY: this file is the design-system REFERENCE implementation (0 importers).
                 The wired production renderer is features/filings/components/copilot/CopilotMessage.tsx,
                 which implements the same contract plus viewer deep-linking, popovers, streaming-perf
                 rendering and follow-ups — change copilot rendering THERE, styled to this design.
```

- **Radius scale is 4 / 8 / 12 / 16 / 24** — buttons + inputs 12 (`rounded-lg`), chips full,
  cards 16 (`rounded-xl`). Config `md` (10px) is legacy off-scale — don't use in new code.
- **Skeleton a11y (codified v2.2):** `SkeletonText`/`SkeletonStat` carry their OWN `role="status"` +
  sr-only label — never wrap them in another `role="status"` (double announcement). Raw `<Skeleton>`
  bones are `aria-hidden` — a wrapper composed of raw bones needs `role="status"` + an sr-only label.
- **Evidence identity:** the Ask-this-Filing header tile uses the Phosphor `quotes` glyph;
  `sparkle` appears ONLY on the "AI summary" chip.
- Sortable table headers render as buttons with `aria-sort`, ▲/▼, and the brand focus ring.

## 5. Headings

Type v2 supersedes the old "no global heading color" rule: the global `h1–h6` rule now sets
`font-family: var(--font-heading)`, `font-optical-sizing: auto`, `font-weight: 600`, and
`color: var(--heading-color)` — theme-safe by construction (`.dark` re-points the var), so the
dark-hero bug that motivated the old rule can't recur. Don't add per-heading color overrides
unless the heading sits on a surface that inverts against its theme.

## 6. Cards must *lift*, not tint

`brand-weak` (#ECF2EE) is **darker** than the cream page (#F4F3EE) — as a card *fill* it's
~1.02:1 (invisible). Cards on cream use a **lighter** fill (`panel-light`) + hairline + soft
`shadow-e*`; **brighten** on hover (`hover:bg-white`), never darken. In dark, separation is fill
contrast + hairline with `shadow-none`. `brand-weak` is an accent/hover/tint color only.

## 7. Marketing surfaces

Flat **solid** surfaces — no decorative gradients anywhere; the only glow is the theme-aware hero
search glow. The hero accent word is solid `text-brand-strong dark:text-brand-strong-dark`.
`.mockup-frame` is flat navy (the decorative slate gradient is retired).

## 8. Theme mechanics

- **One** `<ThemeToggle/>`, in the global `Header` (desktop + mobile). No page-level toggles.
- `app/layout.tsx` runs a **pre-paint theme bootstrap script** (saved `localStorage.theme` else
  system pref) to prevent FOUC. Keep `suppressHydrationWarning` on `<html>`.
- Logo: `<EarningsNerdLogo mode="auto" />` follows the app theme — don't hardcode `mode="dark"`.
- Fonts are self-hosted via `next/font` (Inter with `axes: ['opsz']`, Geist Mono, Newsreader) —
  see `app/layout.tsx`; SF Pro / New York are platform-licensed and must never be embedded.

## 9. Exemptions

- **Google / Apple sign-in buttons**: keep their brand-mandated surfaces (white / black). Only
  their focus rings get rebranded.
- **Status + financial colors are semantic** — keep them; reserve loud status colors for genuine
  state. A default guidance/info container is subdued/brand-tinted, not loud blue (see `GuidanceCard`).
- **Progress / step / completion indicators use the BRAND accent (sage), not success-green.**
  Green is for a genuine terminal *confirmation* state; in-progress ticks are brand activity.

## 10. Charts (recharts)

Series colors come from **`chart-1..6`** — a CVD-validated **sequence** (blue↔yellow axis
alternates early), taken 1→N in order, never skipped or re-sorted. At ≥5 series add direct
labels/markers — color no longer carries alone. **Gain/loss never appear as series colors**
(direction only) and **sage never appears inside a plot area**. Direction vocabulary is the app's
`lib/financialTone.ts` `Direction` (`'up' | 'down' | 'flat'`) — derive with `directionOf()`, color
with `directionTone()`/`directionTextTone()` from `ui/Chart.tsx`. Chart chrome (grid, axis, labels,
crosshair, tooltip) uses the `chart.grid/axis/label/crosshair/ref/tip` sub-tokens — theme-aware via
`useContext(ThemeContext)?.theme === 'dark'` (not `useTheme()`, which throws in provider-less
chart unit tests). Axis labels: 11–12px data face + tabular-nums; dark labels use `secondary`.
Tooltip cursors: `crosshairProps(dark)` on LINE charts; `barCursorProps(dark)` on BAR charts — a
category-band FILL wash (chart.1 teal @ 8% light / 16% dark), not a hairline. `yAxisProps` width 44
is a default — currency/ticker labels routinely override: `<YAxis {...yAxisProps(dark)} width={56} />`.

**Financial tone register (metric-aware).** Sign-based direction is a *default*, not a law: for
some metrics an increase is a cost/risk signal, for others direction carries no fixed valence.
The register ships from the backend on each analysis series as `tone`
(`trend_analysis_service._SERIES_TONE` — single source of truth, like `percent`) and is applied
via `features/analysis/lib/tonePolicy.applySeriesTone`:

| `tone` | Metrics (today) | Rendering |
|--------|-----------------|-----------|
| `inverted` | long-term debt, current liabilities | up = **loss** text, down = **gain** text |
| `neutral` | capex, investing CF, financing CF | always **flat** — a capex ramp or financing swing is a strategic choice, not good/bad news |
| `normal` | everything else | sign-based (up = gain, down = loss) |

Never invert or neutralize by hardcoding concept names in the frontend — consume the dataset's
`tone` field so backend concept changes can't silently desync the coloring.

## 11. Motion — tokens only

Four durations + two curves, defined ONCE (`globals.css` `:root`; JS mirror `lib/motion.ts` for
Recharts/rAF, which need numbers). **No raw ms or bezier strings anywhere else.**

| Token | Value | Use |
|-------|-------|-----|
| `--duration-fast` / `duration-fast` | 150ms | hover + color feedback |
| `--duration-base` / `duration-base` | 200ms | crossfades, theme switch, skeleton→content — also the bare `transition-*` default |
| `--duration-slow` / `duration-slow` | 600ms | entrances, draw-ins, count-up |
| `--duration-ambient` / `duration-ambient` | 1800ms | ambient loops + attention decay: shimmer, pulse, citation-flash |
| `--ease-standard` | cubic-bezier(0.4, 0, 0.2, 1) | everything |
| `--ease-pop` | cubic-bezier(0.34, 1.56, 0.64, 1) | the success check-pop ONLY |

- **Count-up is `hooks/useCountUp`** (rAF, slow/standard, `format` per content fundamentals —
  `"$391.0B"` — render in `tnum font-data`) — the `animate-count-up` keyframe is retired; it was a fade.
- **Skeleton→content**: `animate-content-in` fires on the loading→loaded flip (wired in DataTable +
  AskFilingAnswer) — never on first paint of never-loading views.
- **Stagger**: `animate-fade-up-stagger` + `--stagger-index` (0-based; step = fast; capped at 4;
  first paint only). `fade-up-delay-1/2/3` are retired.
- **Reduced motion**: one source — `hooks/usePrefersReducedMotion`. Every animation has a fallback:
  `animation: none` for transform entrances, static bone (shimmer), static tint (citation-flash),
  instant final value (count-up, Recharts `lineProps(reduced)`), `scroll-behavior: auto`.
- **Nothing decorative** — `animate-float` is retired. Signature set: count-up, citation-flash,
  skeleton→content, sparkline draw-in, check-pop.

## 12. Definition-of-done for any theme/token change

1. **App-wide, not just the obvious page** — public *and* authenticated.
2. **Grep gate** — zero residual legacy brand colors AND legacy type roles:
   ```
   grep -rnE '\b(mint-[0-9]|glow-mint|(bg|text|ring|border|from|to)-primary-[0-9]|emerald-[0-9]|(from|to|bg|text|border|ring)-(sky|indigo|cyan|teal|violet|fuchsia)-[0-9]|bg-blue-[0-9]|Figtree|font-grotesque|#3A2E26|#D99E4A|#92A0E2)' app components features
   ```
   For motion changes also: raw durations outside the token homes —
   ```
   grep -rnE '[0-9]+(\.[0-9]+)?m?s\b|cubic-bezier' app components features | grep -v 'var(--'
   ```
3. **Font-var gate** (repeat offender — missed in BOTH the v2 and v2.1 exports): every
   `fontFamily` stack in `tailwind.config.js` and every `:root` font var in `globals.css`
   leads with its `next/font` variable (`var(--font-inter)` / `var(--font-geist-mono)` /
   `var(--font-newsreader)`; body keeps `-apple-system` first, then the var). next/font
   self-hosts under hashed family names exposed ONLY as these vars — a literal-only stack
   silently never resolves.
4. **Verify in BOTH themes** on the Vercel preview — green CI ≠ correct visuals.
5. Run `npm run typecheck`, `npm run lint` (`--max-warnings 0`), `npm run build`, `npm run test`.
