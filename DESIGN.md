---
name: "EarningsNerd"
description: "The Investor’s Research Desk: calm, precise, evidence-led interfaces for SEC filing research."
colors:
  brand: "#4F7A63"
  brand-strong: "#3C6650"
  brand-emphasis: "#345C48"
  brand-weak: "#ECF2EE"
  brand-border: "#CFE0D6"
  brand-dark: "#7FB295"
  brand-strong-dark: "#98C5AD"
  brand-fill-dark: "#569272"
  brand-weak-dark: "rgba(127,178,149,0.14)"
  brand-border-dark: "rgba(127,178,149,0.28)"
  background-light: "#F4F3EE"
  background-dark: "#0B1120"
  panel-light: "#FBFAF6"
  panel-dark: "#1F2937"
  text-primary-light: "#1A1A17"
  text-primary-dark: "#D7DADC"
  text-secondary-light: "#374151"
  text-secondary-dark: "#9CA3AF"
  text-tertiary-light: "#6B7280"
  border-light: "#E5E7EB"
  border-dark: "#374151"
  white: "#FFFFFF"
  overlay: "rgba(11, 17, 32, 0.55)"
  gain-light: "#16A34A"
  gain-text: "#15803D"
  gain-dark: "#34D399"
  gain-soft: "#DCFCE7"
  gain-soft-dark: "rgba(52,211,153,0.14)"
  loss-light: "#DC2626"
  loss-text: "#B91C1C"
  loss-dark: "#FB7185"
  loss-soft: "#FEE2E2"
  loss-soft-dark: "rgba(251,113,133,0.14)"
  flat-light: "#6B7280"
  flat-dark: "#9CA3AF"
  success-light: "#15803D"
  success-dark: "#22C55E"
  warning-light: "#92400E"
  warning-dark: "#F59E0B"
  error-light: "#B91C1C"
  error-dark: "#F87171"
  error-emphasis: "#991B1B"
  info-light: "#2563EB"
  info-text: "#1D4ED8"
  info-dark: "#60A5FA"
  chart-1: "#3E8E84"
  chart-2: "#B8812F"
  chart-3: "#5B7CC0"
  chart-4: "#CF7159"
  chart-5: "#6E7E9C"
  chart-6: "#8B7BC0"
typography:
  display:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, system-ui, sans-serif"
    fontSize: "3.75rem"
    fontWeight: 600
    lineHeight: "1.05"
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, system-ui, sans-serif"
    fontSize: "1.875rem"
    fontWeight: 600
    lineHeight: "2.25rem"
    letterSpacing: "-0.016em"
  title:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: "2rem"
    letterSpacing: "-0.012em"
  card-title:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: "1.25rem"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, Inter, system-ui, \"Segoe UI\", Roboto, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: "1.5"
  body-base:
    fontFamily: "-apple-system, BlinkMacSystemFont, Inter, system-ui, \"Segoe UI\", Roboto, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: "1.6rem"
  ui:
    fontFamily: "-apple-system, BlinkMacSystemFont, Inter, system-ui, \"Segoe UI\", Roboto, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: "1.25rem"
  button:
    fontFamily: "-apple-system, BlinkMacSystemFont, Inter, system-ui, \"Segoe UI\", Roboto, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: "1.25rem"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, Inter, system-ui, \"Segoe UI\", Roboto, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: "1rem"
    letterSpacing: "0.08em"
  data:
    fontFamily: "\"Geist Mono\", ui-monospace, SFMono-Regular, \"SF Mono\", Menlo, Consolas, monospace"
    fontFeature: "\"tnum\" 1"
  data-xs:
    fontFamily: "\"Geist Mono\", ui-monospace, SFMono-Regular, \"SF Mono\", Menlo, Consolas, monospace"
    fontSize: "0.6875rem"
    lineHeight: "1rem"
    letterSpacing: "0em"
  filing-reader:
    fontFamily: "Newsreader, \"New York\", ui-serif, Georgia, serif"
    fontSize: "1.1875rem"
    fontWeight: 400
    lineHeight: "1.7"
rounded:
  sm: "0.25rem"
  DEFAULT: "0.5rem"
  lg: "0.75rem"
  xl: "1rem"
  "2xl": "1.5rem"
  full: "9999px"
spacing:
  "1": "0.25rem"
  "1.5": "0.375rem"
  "2": "0.5rem"
  "2.5": "0.625rem"
  "3": "0.75rem"
  "3.5": "0.875rem"
  "4": "1rem"
  "5": "1.25rem"
  "6": "1.5rem"
  "8": "2rem"
  "10": "2.5rem"
  "12": "3rem"
  "16": "4rem"
  "20": "5rem"
  "24": "6rem"
  "13": "3.25rem"
  "18": "4.5rem"
  "4.5": "1.125rem"
  gutter: "1.5rem"
components:
  button-primary:
    backgroundColor: "{colors.brand}"
    textColor: "{colors.white}"
    rounded: "{rounded.lg}"
    padding: "0 1rem"
    typography: "{typography.button}"
    height: "2.5rem"
  button-primary-hover:
    backgroundColor: "{colors.brand-strong}"
    textColor: "{colors.white}"
  button-primary-active:
    backgroundColor: "{colors.brand-emphasis}"
    textColor: "{colors.white}"
  button-primary-dark:
    backgroundColor: "{colors.brand-dark}"
    textColor: "{colors.background-dark}"
    rounded: "{rounded.lg}"
    padding: "0 1rem"
    typography: "{typography.button}"
    height: "2.5rem"
  button-primary-dark-hover:
    backgroundColor: "{colors.brand-strong-dark}"
    textColor: "{colors.background-dark}"
  button-primary-dark-active:
    backgroundColor: "{colors.brand-fill-dark}"
    textColor: "{colors.background-dark}"
  button-secondary:
    textColor: "{colors.brand-strong}"
    rounded: "{rounded.lg}"
    padding: "0 1rem"
    typography: "{typography.button}"
    height: "2.5rem"
    backgroundColor: "transparent"
  button-secondary-hover:
    backgroundColor: "{colors.brand-weak}"
  button-secondary-dark:
    textColor: "{colors.brand-strong-dark}"
    backgroundColor: "transparent"
  button-ghost:
    textColor: "{colors.brand-strong}"
    rounded: "{rounded.lg}"
    padding: "0 1rem"
    typography: "{typography.button}"
    height: "2.5rem"
    backgroundColor: "transparent"
  button-ghost-hover:
    backgroundColor: "{colors.brand-weak}"
  button-ghost-dark:
    textColor: "{colors.brand-strong-dark}"
    backgroundColor: "transparent"
  button-destructive:
    backgroundColor: "{colors.error-light}"
    textColor: "{colors.white}"
    rounded: "{rounded.lg}"
    padding: "0 1rem"
    typography: "{typography.button}"
    height: "2.5rem"
  button-destructive-hover:
    backgroundColor: "{colors.error-emphasis}"
    textColor: "{colors.white}"
  input:
    backgroundColor: "{colors.white}"
    textColor: "{colors.text-primary-light}"
    rounded: "{rounded.lg}"
    padding: "0.625rem 0.875rem"
  input-search:
    backgroundColor: "{colors.white}"
    textColor: "{colors.text-primary-light}"
    rounded: "{rounded.lg}"
    padding: "0.625rem 0.875rem 0.625rem 2.75rem"
  input-dark:
    textColor: "{colors.text-primary-dark}"
    rounded: "{rounded.lg}"
    backgroundColor: "rgba(255,255,255,0.05)"
  input-compact:
    backgroundColor: "{colors.white}"
    textColor: "{colors.text-primary-light}"
    rounded: "{rounded.lg}"
    padding: "0.375rem 0.75rem"
    height: "2.25rem"
  segmented-control:
    backgroundColor: "{colors.panel-light}"
    textColor: "{colors.text-secondary-light}"
    rounded: "{rounded.lg}"
    padding: "0.25rem"
  segmented-control-selected:
    backgroundColor: "{colors.brand}"
    textColor: "{colors.white}"
    rounded: "0.5rem"
    fontSize: "0.75rem"
    fontWeight: 600
    height: "1.625rem"
  segmented-control-dark:
    backgroundColor: "{colors.panel-dark}"
    textColor: "{colors.text-secondary-dark}"
    rounded: "{rounded.lg}"
    padding: "0.25rem"
  segmented-control-selected-dark:
    backgroundColor: "{colors.brand-dark}"
    textColor: "{colors.background-dark}"
    rounded: "0.5rem"
  card:
    backgroundColor: "{colors.panel-light}"
    textColor: "{colors.text-primary-light}"
    rounded: "{rounded.xl}"
  card-dark:
    backgroundColor: "{colors.panel-dark}"
    textColor: "{colors.text-primary-dark}"
    rounded: "{rounded.xl}"
  card-body:
    padding: "1rem 1.25rem"
  badge-new:
    textColor: "{colors.warning-light}"
    rounded: "{rounded.full}"
    padding: "0.125rem 0.625rem"
    backgroundColor: "rgba(146,64,14,0.10)"
  badge-new-dark:
    textColor: "{colors.warning-dark}"
    rounded: "{rounded.full}"
    padding: "0.125rem 0.625rem"
    backgroundColor: "rgba(245,158,11,0.15)"
  navigation:
    textColor: "{colors.text-secondary-light}"
    typography: "{typography.ui}"
  navigation-dark:
    textColor: "{colors.text-secondary-dark}"
    typography: "{typography.ui}"
  data-table:
    textColor: "{colors.text-primary-light}"
  modal:
    backgroundColor: "{colors.panel-light}"
    textColor: "{colors.text-primary-light}"
    rounded: "{rounded.2xl}"
  modal-dark:
    backgroundColor: "{colors.panel-dark}"
    textColor: "{colors.text-primary-dark}"
    rounded: "{rounded.2xl}"
---

# Design System: EarningsNerd

## Overview

**Creative North Star: "The Investor’s Research Desk"**

EarningsNerd is calm, precise and evidence-led. Warm cream and espresso give the light interface the familiarity of a working document; deep navy carries the same structure into dark mode. Sage identifies actions, links and the product itself. Financial direction, status and chart series have separate color vocabularies so the interface can express their different meanings clearly.

The system is refined, readable and quietly confident. Inter headings organize the work, system-first body text supports scanning, and Geist Mono makes figures and evidence recognizable. Newsreader is reserved for the original filing reader. Depth is structural and restrained: light cards lift from the page, while dark cards separate through fill and hairlines. Decorative gradients remain outside the established visual language.

**Key Characteristics:**
- One sage brand accent, with explicit light and dark treatments.
- Warm page grounds, brighter light panels and low-noise dark panels.
- Type roles that distinguish interface, data and original filing prose.
- Compact controls and data tables within more generous page layouts.
- Source context, visible focus and truthful state feedback.

This document records the implementation at [`1a79637e4094f8f6ceeb9802014a6a1172283416`](https://github.com/neilmac91/EarningsNerd/tree/1a79637e4094f8f6ceeb9802014a6a1172283416); the links below open the current files. Token definitions remain in [`frontend/tailwind.config.js`](frontend/tailwind.config.js) and [`frontend/app/globals.css`](frontend/app/globals.css); the frontmatter is their portable snapshot, and [`designSnapshotParity.spec.ts`](frontend/tests/unit/designSnapshotParity.spec.ts) checks it against them. [`frontend/DESIGN_SYSTEM.md`](frontend/DESIGN_SYSTEM.md) retains current implementation conventions and verification gates. [AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md#design-documentation) route UI work through both documents and define maintenance. Actual token definitions and component code take precedence over a stale snapshot. Refresh affected visual content and [its sidecar](.impeccable/design.json) together when the documented system changes; routing-only edits can leave an unchanged sidecar intact. The descriptive language above was confirmed by the project owner.

The public homepage was inspected visually and sampled for computed styles in light mode on 2026-10-04. Dark treatments and responsive rules below were extracted from source; this pass does not claim a visual audit of authenticated routes or dark mode. Sidecar component samples illustrate appearance without reproducing application behavior; their dark treatment follows the app's own `html.dark` theme signal and their responsive rules follow the space available to them. The sidecar carries no tonal ramps: the project defines no tonal scale, and Impeccable's detector accepts every ramp step as a palette color.

## Colors

The palette combines sage, warm cream, espresso and deep navy with distinct semantic and categorical colors. Frontmatter values are normative for this snapshot; names below explain their use. The snapshot deliberately omits `text-tertiary-dark` (it fails as muted text on navy), the `chart.*` chrome sub-tokens that `Chart.tsx` derives from surface, text and flat colors, and the aliases `text-heading-*` (equal to `text-primary-*`) and bare `gain` / `loss` (equal to their `-light` values).

### Primary

- **Sage** (`brand`): primary button fill in light mode, with white labels. It is not the light-mode link ink.
- **Deep Sage** (`brand-strong`) and **Pressed Sage** (`brand-emphasis`): accent text and hover/active action states.
- **Pale Sage** (`brand-weak`) and **Sage Hairline** (`brand-border`): selected/tinted accents and borders, rather than the default card surface.
- **Light Sage** (`brand-dark`), **Bright Sage** (`brand-strong-dark`) and **Pressed Dark Sage** (`brand-fill-dark`): dark-mode action states. Primary labels use navy ink throughout these states.
- **Dark Sage Tint** and **Dark Sage Hairline** (`brand-weak-dark`, `brand-border-dark`): translucent accents on dark surfaces.

**The Separate Signals Rule.** Sage signals brand and activity. Gain/loss signals financial direction; status colors signal actual UI states. Progress indicators use sage until a terminal confirmation warrants success green.

### Neutral

- **Warm Cream** (`background-light`) and **Deep Navy** (`background-dark`): page grounds.
- **Warm Paper** (`panel-light`) and **Slate Panel** (`panel-dark`): card/container surfaces.
- **Espresso** (`text-primary-light`) and **Soft Chalk** (`text-primary-dark`): both body and heading ink. Hierarchy does not introduce another heading color.
- **Secondary Ink** (`text-secondary-light`, `text-secondary-dark`): supporting copy. Dark-mode muted labels use the secondary token.
- **Tertiary Ink** (`text-tertiary-light`): small labels on sufficiently bright panels; use secondary ink for muted copy on bare cream.
- **Light Hairline** and **Dark Hairline** (`border-light`, `border-dark`): separators. Dark cards specifically use white at 10% opacity rather than the general dark border.
- **White** (`white`): field fill, light primary-action label, and interactive light-card hover fill. **Modal Scrim** (`overlay`) uses translucent navy in both themes.

### Semantic and chart colors

Financial gain/loss have separate graphic and text tokens. Use `gain-text` / `loss-text` for light-mode delta text and `gain-dark` / `loss-dark` for dark-mode delta text. The brighter light graphic tokens belong to graphics, not small text. Apply financial tone through the existing metric-aware helpers: a rise in debt can be negative and some series are neutral.

Success, warning, error and info are state colors. The info tint's light label uses `info-text`; destructive buttons use the darker light error fill with white text in both themes. Quiet guidance is generally brand-tinted rather than a loud status panel.

Chart series follow the configured order: **Teal → Honey → Cornflower → Coral → Slate Blue → Periwinkle** (`chart-1` through `chart-6`). Preserve this sequence. At five or more series, add labels, markers or dash patterns because color alone is insufficient. Neither sage nor gain/loss colors are series colors. Use [`Chart.tsx`](frontend/components/ui/Chart.tsx) for theme-aware chart chrome.

**The Actual Surface Rule.** Check text contrast against its actual page, panel or mixed tint in both themes. The existing convention targets at least 4.5:1 for body text and 3:1 for meaningful non-text graphics; token membership alone is not a contrast guarantee.

## Typography

**Display Font:** Inter, reached through `--font-inter`, followed by the implementation's system fallbacks. Headings use optical sizing and weight 600.

**Body Font:** Apple system first, then the loaded Inter font, then generic system and platform fallbacks. Preserve the system-first order.

**Label/Mono Font:** Geist Mono, reached through `--font-geist-mono`, for figures, tickers, data columns and Ask-this-Filing answers. UI labels otherwise use the body or heading register appropriate to their component.

**Editorial Font:** Newsreader, reached through `--font-newsreader`, for the original filing's own words in `.filing-reader` only.

**Character:** Clear sans-serif structure surrounds an exact, aligned data register. The editorial serif marks a distinct reading context, not a general accent style. Inter, Geist Mono and Newsreader are self-hosted through `next/font` in [`layout.tsx`](frontend/app/layout.tsx); platform fonts are fallbacks rather than embedded assets.

### Hierarchy

| Role | Implemented treatment | Use |
| --- | --- | --- |
| Display | 600; 36px base, 48px from `sm`, 60px from `lg`; live desktop sample 60/63px | Homepage headline; responsive sizes belong to this surface |
| Headline | 600; 30/36px with −0.016em tracking; marketing section headings step up to 36/40px (−0.02em) from `lg` | Large section/page heading role |
| Title | 600; 24/32px; tighter tracking | Section headings; smaller component titles follow their own recipe |
| Card title | 600; 14/20px; sentence case | Compact container headings |
| Body | 400; root browser sample 16/24px; `text-base` explicitly sets 16/25.6px | General prose; local leading utilities can override the scale |
| UI | 14/20px, commonly 500 or 600 for controls | Navigation, forms and medium buttons |
| Metric label | 12/16px; 600; uppercase with 0.08em eyebrow tracking | Table headers and metric labels |
| Data | Geist Mono; tabular figures; size follows context | Financial values, tickers and evidence output |
| Dense data annotation | 11/16px | Compact chart annotations and in-card micro-labels |
| Filing reader | Newsreader 19px, line-height 1.7, optical sizing | Original filing prose |

The frontmatter `display` token records the large desktop step and `headline` the base step; neither is a universal heading size. Frontmatter font stacks leave out the app-only `var(--font-*)` entries so they resolve outside the app. The source tracking ramp progresses from +0.01em for captions through zero for body text to −0.025em for large display text. Use the existing type scale and CSS tracking variables rather than inventing new tracking utilities.

**The Source Voice Rule.** Newsreader means original filing prose. AI summaries use body sans; Ask answers use the mono evidence register. `.tabular` supplies mono plus tabular digits; `.tnum` preserves the current face and only aligns digits.

In the filing reader, prose children have a 68ch measure and tables/figures can use the 88ch outer rail. AI `.markdown-body` content fills its pane with no measure cap. Summary paragraphs are justified and hyphenated at viewport widths of 640px and above. Below that breakpoint, summary paragraphs remain ragged-right; the original filing reader stays ragged-right at every width. Preserve underlined sage links in both reading surfaces.

## Layout

Use shared page grounds around distinct content panels. Controls and tables are compact; reading and marketing sections use larger gaps. There is no single universal column count or container width for every route.

- The homepage hero and site header use a 1280px maximum container with 16px horizontal padding, then 24px from `sm` and 32px from `lg`. Other marketing sections use the established 1024px maximum convention.
- The hero stacks until `lg`, then uses two columns with a 64px gap; its stacked gap is 40px. The headline, CTA and search sit beside the filing example. This is a homepage composition, not a system-wide requirement.
- The shared responsive conventions use `sm` at 640px, `md` at 768px and `lg` at 1024px. Desktop header navigation appears at `lg`; the mobile menu occupies the smaller range.
- Spacing follows Tailwind's base scale plus the configured 18px, 52px, 72px and 24px gutter additions. Frontmatter records frequently used steps and the named gutter; component padding is recorded separately.
- Comfortable table rows use 10px vertical cell padding; compact rows use 4px. Numeric columns align right and use tabular figures. Wide tables scroll within their container.
- Modal sizes cap at 384px, 448px or 512px. Their outer inset bounds them to the viewport; the panel scrolls internally and reserves 24px scroll padding. The footer stacks actions on small screens and switches to a row from `sm`.

The stacking vocabulary is sticky 30, consent 32, scrim 35, header 50, popover/overlay 60, modal 70 and toast 80. The consent layer is the cookie-consent bar alone: it sits above in-page sticky chrome, beneath the workspace sheets' scrims and the workspace sheets, launchers and coachmark, and, while it is mounted, publishes its height as `--consent-inset` on the root element, so the bottom-anchored launchers, the Copilot coachmark and the workspace sheets add that inset to their bottom offset instead of being covered by it or covering its choices, and the document's bottom scroll padding reserves the same height; the coachmark waits until the bar is gone, and the "preferences saved" confirmation is an ordinary top-centre toast. The scrim layer is the workspace and rail bottom sheets' backdrop: an open sheet dims the bar and makes it inert, as any modal does, and the bar is operable again once the sheet closes. Preserve the documented workspace-sheet and internal table-layer exceptions in the detailed implementation guide. Several other sites still use numeric z utilities, including the header and its account and notification menus (`z-50`), `SecondaryHeader` and the Copilot coachmark (`z-40`), the feedback widget (`z-30`), the search dropdowns (`z-10` / `z-20`) and the workspace pane resizer (`z-10`). This snapshot records the ladder without renaming those sites.

## Elevation & Depth

Depth gives structure to the workspace. Light cards use warm paper, a hairline and a small shadow to lift from cream. Dark cards keep the slate fill and a faint white hairline with no resting card shadow. Interactive light cards brighten on hover; dark separation follows the component's explicit theme rules. Avoid describing a fill change as a universal dark-card hover behavior when the source does not define it.

### Shadow Vocabulary

The exact source shadow strings are stored in the sidecar's `extensions.shadows`. The configured `glow-brand*` shadows are unused and intentionally left out.

| Token | Role |
| --- | --- |
| `e1` | Low lift for small controls such as the switch thumb and pricing-period toggle, the popular-ticker and quick-access chips, and some tiles; the Badge primitive carries no shadow |
| `e2` | Default light card lift |
| `e3` | Featured/hero surface emphasis |
| `e4` / `e5` | `e4` for popovers (alert bell, source trace) and the Copilot coachmark; `e5` for the shared Modal, bottom sheets, the citation-chip popover and the cookie-consent banner, light mode only. Header menus use `e2` and search dropdowns `e3` |
| `ring-brand` / `ring-brand-dark` | Keyboard focus; fields also show the ring on focus |
| `ring-error` | Invalid fields and destructive-action focus |

**The Lifted Paper Rule.** On cream, default cards use the brighter panel fill, a hairline and restrained shadow. Pale sage is an accent tint, not the default card fill. Dark cards separate with fill and hairline.

The theme-aware hero search glow is a specific search treatment; it is not permission to add glows to ordinary components. The remaining authentication glass treatment and marketing mockup frame follow their existing scoped CSS recipes.

## Shapes

The established radius scale is 4 / 8 / 12 / 16 / 24px, with fully rounded pills for chips. Buttons and inputs use the 12px step at all standard sizes. Cards default to 16px and support a featured 24px variant; dialogs use 24px. The configured 10px `md` radius remains a legacy value and is intentionally excluded from the portable scale.

Borders are thin separators and control boundaries. Tables use row hairlines rather than full cell grids. Shape should follow the component recipe: avoid adding conflicting utility classes to simulate a variant that the component already exposes.

## Components

Components are **refined, readable and quietly confident**. Reuse [`components/ui`](frontend/components/ui) and its supported variants. The sidecar's eleven samples are static, dependency-free visual translations; they do not replace the React components, form guards, routing, sorting or dialog focus management.

### Buttons

- **Shape and size:** 12px radius. Small: 32px high, 12px horizontal padding, 12px label. Medium: 40px high, 16px horizontal padding, 14px label. Large: 48px high, 20px horizontal padding, 16px label. `icon-sm` is 32px square with zero padding.
- **Primary:** sage fill and white label in light mode; light sage fill and navy label in dark mode. Hover and active use the corresponding named brand states.
- **Secondary / Ghost:** transparent ground and sage text; secondary adds a sage hairline. Hover adds a tint; active strengthens it. `tertiary` is only a deprecated alias of ghost.
- **Destructive:** error fill with white label; darker error hover and active states. Preserve its error focus ring.
- **Focus and busy:** use the shared focus recipe. Loading keeps the resting appearance, adds a spinner and `aria-busy`, and refuses repeated activation. Controls made unavailable by their own request stay focusable using the established `aria-disabled`/handler guards. A form that locks its text fields while submitting uses `readOnly` rather than native `disabled`; the contact form does, while login and registration leave fields editable. Native disabled styles exist for other unavailable states.

[`Button.tsx`](frontend/components/ui/Button.tsx) also exports `buttonVariants` for real links styled as buttons. Standard color feedback uses the fast motion token. Spinner animation remains the existing utility with a reduced-motion fallback; this document introduces no new timing for it.

### Segmented controls

[`SegmentedControl.tsx`](frontend/components/ui/SegmentedControl.tsx) is the shared single-choice toggle group: a `role="group"` of `aria-pressed` buttons with every option visible, so it is neither a radiogroup nor a tablist. The shell is the panel fill with a hairline, 12px radius, 4px padding and the small lift; dark mode keeps the fill and a white 10% hairline with no shadow. Segments have an 8px radius and 12px semibold labels in secondary ink that turn primary on hover; the selected segment takes the primary-button colorway (sage with a white label, light sage with a navy label in dark mode). Segments are 26px high (`sm`), 36px (`md`) or adaptive (36px below `sm`, 26px from `sm`). Options that are codes (10-K, 10-Q) set their label in the data face. A full-width group stretches its segments below `sm` and wraps them when the labels outgrow the card, so no option is clipped or scrolled out of reach. The calendar's Week/Month switch and the filings index's form filter use it; one selected colour per group, and "All" is a segment like any other, never an ink fill.

### Chips

Pill-shaped, 12px semibold labels with 10px horizontal and 2px vertical padding. Brand/pro variants use the sage tint and hairline; only pro uppercases its label. Solid chips use deep sage with white labels in light mode and navy labels on light sage in dark mode. Quiet chips, info/warning tints and gain/loss chips keep their distinct meanings. `new` adds the existing warning-tint pulse dot, which becomes static for reduced motion. Info is a UI-state tint, not a document-type colour: the filings index sets form codes typographically.

### Cards / Containers

The base [`Card`](frontend/components/ui/Card.tsx) supplies shape, fill, border and elevation, but **no internal padding**. `CardHeader` and `CardBody` add 20px horizontal / 16px vertical padding; `CardFooter` uses 20px / 12px. Titles are sentence-case 14px semibold headings. Set `as`, `interactive`, `elevation` and `radius` through the API; an interactive appearance alone does not supply link or button semantics.

### Inputs / Fields

[`Input.tsx`](frontend/components/ui/Input.tsx) shares a bright white light fill and translucent white dark fill, 12px radius, hairline and 14px text. Standard padding is 10px vertical / 14px horizontal. Search fields explicitly reserve 44px on the leading side for their icon. Hover strengthens the border; focus shows the brand border/ring. Invalid fields use the error treatment with an associated error message. The composer textarea is transparent inside its own field shell to avoid double borders. A compact density (`density="compact"` on `inputClasses` and `Select`) gives toolbar fields, such as the filings index's year filter beside a segmented control, a 36px height with 6px vertical and 12px horizontal padding from `sm`; below `sm` they keep the standard field height.

### Navigation

[`Header.tsx`](frontend/components/Header.tsx) uses a sticky, translucent page-ground strip and hairline with 14px medium-weight links. Desktop links have a 32px gap, secondary ink at rest, primary ink on hover and a visible brand focus ring. The header currently does not implement a route-active link color; do not invent one in this snapshot. Below `lg`, links move into the collapsible menu and the menu trigger maintains a 44px minimum target. Logo and theme toggle belong to the shared header.

### Data tables and charts

[`DataTable.tsx`](frontend/components/ui/DataTable.tsx) supports comfortable and compact density, row hairlines, optional sticky columns, right-aligned mono numeric cells, sorting, loading, empty and error states. Sort controls are buttons; `aria-sort` belongs to the header cell. Financial tones come from the existing helpers. Chart captions, axes and tooltips keep their theme-aware styles; use the categorical sequence described in Colors. The summary's Financial Highlights ([`FinancialMetricsTable.tsx`](frontend/features/summaries/components/FinancialMetricsTable.tsx)) stacks each metric into one card below `md` (768px) — name with its XBRL chip, the current, prior and change figures under eyebrow labels in the data face, then the takeaway with its chip — and keeps the DataTable unchanged from `md` up; both presentations are rendered and switched by CSS, so the inactive one is `display:none` (out of the accessibility tree and the tab order) and the active one carries the caption (the table's `<caption>`, the list's `aria-label`).

### Index lists

The company filings list ([`FilingIndex.tsx`](frontend/features/filings/components/FilingIndex.tsx)) is the recipe for a list of primary documents: one card, year groups and rows separated by hairlines in the table manner, one grid template shared by the column header and every row, and each row a single link named by its period of report, with EDGAR as a sibling link in the actions track. Form codes are set in the data face with no per-type colour, stripe, tint or icon; the latest filing's lead carries the page's one primary action; rows brighten on hover like interactive cards. Loading keeps the list's own tracks as a skeleton, and errors render a notice with a retry in place.

### Dialogs and evidence

Use [`Modal.tsx`](frontend/components/ui/Modal.tsx) for ordinary dialogs: translucent navy scrim, rounded panel, shared focus trap, Escape handling, opener focus restoration and internal scrolling. Keep the documented bespoke sheets/native calendar-dialog exceptions rather than creating additional dialog systems. Static sidecar samples demonstrate the visual shell only.

The signature evidence treatment is a compact citation/source chip attached to a figure or passage, with a route to inspect its source. [`CopilotMessage.tsx`](frontend/features/filings/components/copilot/CopilotMessage.tsx) is the production Ask answer renderer. A source match describes attribution within its stated scope; it must not imply that every claim in an answer was verified. Keep citation labels and evidence states faithful to the renderer.

Motion supports state changes and reading continuity. The source has fast (150ms), base (200ms), slow (600ms) and ambient (1800ms) timings; standard easing is the default and pop easing is reserved for the success check. These live in CSS variables with a JS mirror. The convention is a reduced-motion fallback for every animation: the `globals.css` animation classes guard themselves, and shimmer, count-up, citation highlighting and chart drawing have fallbacks. Some Tailwind animation utilities are not yet guarded, notably the `animate-fade-up` entrances on the login form, registration form and auth shell, the Copilot streaming `animate-pulse` indicators and standalone `animate-spin` loaders. Give new animation a fallback and keep the existing ones. Motion values and breakpoints belong in the sidecar, not new frontmatter groups.

## Do's and Don'ts

### Do:

- **Do** keep light/dark pairs explicit and use navy labels on dark-mode primary buttons.
- **Do** preserve the different roles of brand, financial direction, UI state and chart series.
- **Do** use the shared components, source token definitions and existing typography variables.
- **Do** keep cards brighter than the cream page, and dark cards separated by fill and hairline.
- **Do** use mono/tabular numerals for data while preserving the filing reader's distinct serif voice.
- **Do** keep keyboard focus visible and controls focusable during their own pending action.
- **Do** scope claims about source matching to what the implementation actually establishes.
- **Do** regenerate the Markdown and sidecar together after relevant implementation changes.

### Don't:

- **Don't** restore retired mint branding, decorative gradients or general-purpose glow effects.
- **Don't** use sage as a chart-series or financial-direction color.
- **Don't** use light gain/loss graphic colors for small delta text or tertiary dark ink for muted labels.
- **Don't** use the legacy 10px radius for new components or uppercase ordinary card titles.
- **Don't** apply the filing reader's serif to AI summaries or cap pane-filling summaries to a prose rail.
- **Don't** treat illustrative sidecar markup as production tokens or behavior, or add synthetic tonal ramps to the sidecar.
- **Don't** create another dialog primitive or remove existing reduced-motion fallbacks.
