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
  text-tertiary-light: "#636A77"
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
  section-title:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: "1.75rem"
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
    padding: "0.625rem 2.5rem 0.625rem 2.75rem"
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
    rounded: "{rounded.DEFAULT}"
    padding: "0 0.875rem"
    height: "1.625rem"
  segmented-control-dark:
    backgroundColor: "{colors.panel-dark}"
    textColor: "{colors.text-secondary-dark}"
    rounded: "{rounded.lg}"
  segmented-control-selected-dark:
    backgroundColor: "{colors.brand-dark}"
    textColor: "{colors.background-dark}"
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
    textColor: "{colors.brand-strong}"
    rounded: "{rounded.full}"
    padding: "0.125rem 0.625rem"
    backgroundColor: "{colors.brand-weak}"
  badge-new-dark:
    textColor: "{colors.brand-strong-dark}"
    rounded: "{rounded.full}"
    padding: "0.125rem 0.625rem"
    backgroundColor: "{colors.brand-weak-dark}"
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

The system is refined, readable and quietly confident. Inter headings organize the work, system-first body text supports scanning, and Geist Mono makes figures and evidence recognizable. Newsreader is reserved for the filing's own words: the filing reader and the passages the product located. Depth is structural and restrained: light cards lift from the page, while dark cards separate through fill and hairlines. Decorative gradients remain outside the established visual language. One graphic device, the margin and the mark, makes a surface recognisable without the logo: a located passage is highlighted and a cited figure carries a bracketed marker whose twin sits in a margin on the same line. Inside the product it marks every passage the server located.

**Key Characteristics:**
- One sage brand accent, with explicit light and dark treatments.
- Warm page grounds, brighter light panels and low-noise dark panels.
- Type roles that distinguish interface, data and original filing prose.
- Compact controls and data tables within more generous page layouts.
- Source context, visible focus and truthful state feedback.
- One graphic device, the margin and the mark, that only ever means "located" and "cited".

The October 2026 brand studio ([`docs/brand/`](docs/brand/README.md)) added the graphic device, the icon and imagery rules and the public-page clause of the Source Voice Rule; tokens and type roles are unchanged and the mark is untouched. This document records the implementation at [`1a79637e4094f8f6ceeb9802014a6a1172283416`](https://github.com/neilmac91/EarningsNerd/tree/1a79637e4094f8f6ceeb9802014a6a1172283416), updated for the October 2026 design critique's filing-page changes (tertiary ink `#636A77`, the section-title role, the callout well, evidence rows, the filing identity strip and the Source pane), its company-page changes (the segmented control, the compact toolbar field, the filings index, the company lead and the Compare periods card) and its homepage changes (the search option's filing line, the one-surface example and the trust strip) and its loading and motion changes (pages that load as their own frame over destination-shaped bones, and every animation stopping under reduced motion) and the device inside the product (the filing page's Risks rows as a marked copy and the Source pane's located passage in the mark's tint and hairline, D-044), with the earlier changes folded in by the pull requests that made them: the consent and scrim layers ([#1107](https://github.com/neilmac91/EarningsNerd/pull/1107)), stacked metric cards below `md` ([#1108](https://github.com/neilmac91/EarningsNerd/pull/1108)), the site chrome's focus ring ([#1142](https://github.com/neilmac91/EarningsNerd/pull/1142)), content-width selects with their chevron inset ([#1180](https://github.com/neilmac91/EarningsNerd/pull/1180)), the password field's trailing inset ([#1188](https://github.com/neilmac91/EarningsNerd/pull/1188)), the search fields' busy spinner ([#1228](https://github.com/neilmac91/EarningsNerd/pull/1228)), the invalid field's error tone ([#1233](https://github.com/neilmac91/EarningsNerd/pull/1233)), the field focus ring without the forms plugin's ([#1234](https://github.com/neilmac91/EarningsNerd/pull/1234)), the composer shell's focus border under hover ([#1241](https://github.com/neilmac91/EarningsNerd/pull/1241)), the admin email chip's 16px radius ([#1344](https://github.com/neilmac91/EarningsNerd/pull/1344)), the `new` chip's brand tint ([#1379](https://github.com/neilmac91/EarningsNerd/pull/1379)), the admin status chips on Badge's status set ([#1433](https://github.com/neilmac91/EarningsNerd/pull/1433)), the summary status chips on the watchlist and dashboard rows ([#1459](https://github.com/neilmac91/EarningsNerd/pull/1459)), the calendar's status ladder on that set, with its tentative chip ([#1460](https://github.com/neilmac91/EarningsNerd/pull/1460)) and the missing-value element ([#1473](https://github.com/neilmac91/EarningsNerd/pull/1473)); the links below open the current files. Token definitions remain in [`frontend/tailwind.config.js`](frontend/tailwind.config.js) and [`frontend/app/globals.css`](frontend/app/globals.css); the frontmatter is their portable snapshot, and [`designSnapshotParity.spec.ts`](frontend/tests/unit/designSnapshotParity.spec.ts) checks it against them. [`frontend/DESIGN_SYSTEM.md`](frontend/DESIGN_SYSTEM.md) retains current implementation conventions and verification gates. [AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md#design-documentation) route UI work through both documents and define maintenance. Actual token definitions and component code take precedence over a stale snapshot. Refresh affected visual content and [its sidecar](.impeccable/design.json) together when the documented system changes; routing-only edits can leave an unchanged sidecar intact. The descriptive language above was confirmed by the project owner.

The public homepage was inspected visually and sampled for computed styles in light mode on 2026-10-04. Dark treatments and responsive rules below were extracted from source; this pass does not claim a visual audit of authenticated routes or dark mode. Sidecar component samples illustrate appearance without reproducing application behavior; their dark treatment follows the app's own `html.dark` theme signal and their responsive rules follow the space available to them. The sidecar carries no tonal ramps: the project defines no tonal scale, and Impeccable's detector accepts every ramp step as a palette color.

The sticky-column hover guidance was refreshed from [`DataTable.tsx` at `4903ae55`](https://github.com/neilmac91/EarningsNerd/blob/4903ae5501f62f507ed19efd1b06a9e8551802ef/frontend/components/ui/DataTable.tsx) on 2026-10-10. Its analysis-page hover was inspected in both themes on the protected preview with mocked identity and data; this does not establish authenticated production behavior. The sidecar's ordinary-row table specimen remains unchanged.

## Colors

The palette combines sage, warm cream, espresso and deep navy with distinct semantic and categorical colors. Frontmatter values are normative for this snapshot; names below explain their use. The snapshot deliberately omits `text-tertiary-dark` (it fails as muted text on navy), the `chart.*` chrome sub-tokens that `Chart.tsx` derives from surface, text and flat colors, and the aliases `text-heading-*` (equal to `text-primary-*`) and bare `gain` / `loss` (equal to their `-light` values).

### Primary

- **Sage** (`brand`): primary button fill in light mode, with white labels. It is not the light-mode link ink.
- **Deep Sage** (`brand-strong`) and **Pressed Sage** (`brand-emphasis`): accent text and hover/active action states.
- **Pale Sage** (`brand-weak`) and **Sage Hairline** (`brand-border`): selected/tinted accents and borders, rather than the default card surface.
- **Light Sage** (`brand-dark`), **Bright Sage** (`brand-strong-dark`) and **Pressed Dark Sage** (`brand-fill-dark`): dark-mode action states. Primary labels use navy ink throughout these states.
- **Dark Sage Tint** and **Dark Sage Hairline** (`brand-weak-dark`, `brand-border-dark`): translucent accents on dark surfaces.

**The Separate Signals Rule.** Sage signals brand and activity, never a value: a count, a date, an index name or a price rests in the ink everywhere in the app; a control that carries one rests in the ink and turns sage only under the pointer, keyboard focus drawing the ring (the count control in `frontend/DESIGN_SYSTEM.md`), and so does a link in prose, which prints words the product does not write (the reading surfaces' links and a Copilot answer's). Gain/loss signals financial direction; status colors signal actual UI states. Progress indicators use sage until a terminal confirmation warrants success green; a step's number rests in the ink.

### Neutral

- **Warm Cream** (`background-light`) and **Deep Navy** (`background-dark`): page grounds.
- **Warm Paper** (`panel-light`) and **Slate Panel** (`panel-dark`): card/container surfaces.
- **Espresso** (`text-primary-light`) and **Soft Chalk** (`text-primary-dark`): both body and heading ink. Hierarchy does not introduce another heading color.
- **Secondary Ink** (`text-secondary-light`, `text-secondary-dark`): supporting copy. Dark-mode muted labels use the secondary token.
- **Tertiary Ink** (`text-tertiary-light`): captions, counts and micro-labels. At 4.9:1 on cream, 5.2:1 on panel and 4.8:1 in the pale sage tint it passes AA on every light ground; secondary ink still carries anything the reader must read.
- **Light Hairline** and **Dark Hairline** (`border-light`, `border-dark`): separators. Dark cards specifically use white at 10% opacity rather than the general dark border.
- **White** (`white`): field fill, light primary-action label, and interactive light-card hover fill. **Modal Scrim** (`overlay`) uses translucent navy in both themes.

### Semantic and chart colors

Financial gain/loss have separate graphic and text tokens. Use `gain-text` / `loss-text` for light-mode delta text and `gain-dark` / `loss-dark` for dark-mode delta text. The brighter light graphic tokens belong to graphics, not small text. Apply financial tone through the existing metric-aware helpers: a rise in debt can be negative and some series are neutral.

Success, warning, error and info are state colors. The info tint's light label uses `info-text`; destructive buttons use the darker light error fill with white text in both themes. Quiet guidance is generally brand-tinted rather than a loud status panel.

Chart series follow the configured order: **Teal → Honey → Cornflower → Coral → Slate Blue → Periwinkle** (`chart-1` through `chart-6`). Preserve this sequence. At five or more series, add labels, markers or dash patterns because color alone is insufficient. Neither sage nor gain/loss colors are series colors. Use [`Chart.tsx`](frontend/components/ui/Chart.tsx) for theme-aware chart chrome.

**The Actual Surface Rule.** Check text contrast against its actual page, panel or mixed tint in both themes. The existing convention targets at least 4.5:1 for body text and 3:1 for meaningful non-text graphics; token membership alone is not a contrast guarantee.

## Typography

**Display Font:** Inter, reached through `--font-inter`, followed by the implementation's system fallbacks. Headings use optical sizing and weight 600. Promotional emphasis uses the genuine Inter italic face loaded locally by [`BrandEmphasis.tsx`](frontend/features/marketing/components/BrandEmphasis.tsx), shared by every homepage headline variant, the authentication pane and the waitlist; the root font definitions remain unchanged.

**Body Font:** Apple system first, then the loaded Inter font, then generic system and platform fallbacks. Preserve the system-first order.

**Label/Mono Font:** Geist Mono, reached through `--font-geist-mono`, for figures, tickers, data columns, Ask-this-Filing answers and a code a reader may retype (the waitlist referral link). UI labels otherwise use the body or heading register appropriate to their component.

**Editorial Font:** Newsreader, reached through `--font-newsreader`, for the filing's own words only: the filing reader (`.filing-reader`) and a passage the product located, set as a marked block (`.en-marked`).

**Character:** Clear sans-serif structure surrounds an exact, aligned data register. The editorial serif marks a distinct reading context, not a general accent style. Inter, Geist Mono and Newsreader are self-hosted through `next/font` in [`layout.tsx`](frontend/app/layout.tsx); platform fonts are fallbacks rather than embedded assets.

### Hierarchy

| Role | Implemented treatment | Use |
| --- | --- | --- |
| Display | 600; 36px base, 48px from `sm`, 60px from `lg`; live desktop sample 60/63px | Homepage headline; responsive sizes belong to this surface |
| Headline | 600; 30/36px with −0.016em tracking | Large section/page heading role |
| Title | 600; 24/32px; tighter tracking | Section headings, the landing's row titles among them; smaller component titles follow their own recipe |
| Section title | 600; 20/28px, −0.012em; a 12px data-face index (`01`) beside it that the table of contents repeats | The filing summary's section headings, set on the page without a card; subheadings under them are 14/600 |
| Card title | 600; 14/20px; sentence case | Compact container headings |
| Body | 400; root browser sample 16/24px; `text-base` explicitly sets 16/25.6px | General prose; local leading utilities can override the scale |
| UI | 14/20px, commonly 500 or 600 for controls | Navigation, forms and medium buttons |
| Metric label | 12/16px; 600; uppercase with 0.08em eyebrow tracking | Table headers and metric labels |
| Data | Geist Mono; tabular figures; size follows context | Financial values, tickers, evidence output and a code a reader may retype |
| Dense data annotation | 11/16px | Compact chart annotations and in-card micro-labels; never a provenance chip, which is 12px |
| Filing reader | Newsreader 19px, line-height 1.7, optical sizing; a marked block sets the face at 16/26px | Original filing prose; a located passage's marked block (the filing page's Risks rows and located quotes, the hero example's evidence row) |

The frontmatter `display` token records the large desktop step and `headline` the base step; neither is a universal heading size. Frontmatter font stacks leave out the app-only `var(--font-*)` entries so they resolve outside the app. The source tracking ramp progresses from +0.01em for captions through zero for body text to −0.025em for large display text. Use the existing type scale and CSS tracking variables rather than inventing new tracking utilities. A role is a treatment, not an element: pick the heading element for its place in the page outline and never skip a level, so one Card title is an h3 inside an h2 section and an h2 where its card stands in for a page's content under the page h1 ([`GuidanceCard`](frontend/components/ui/GuidanceCard.tsx)'s `headingLevel`; [`frontend/DESIGN_SYSTEM.md`](frontend/DESIGN_SYSTEM.md) §5).

**The Source Voice Rule.** Newsreader means original filing prose. AI summaries use body sans; Ask answers use the mono evidence register. `.tabular` supplies mono plus tabular digits; `.tnum` preserves the current face and only aligns digits.

On a public page, Newsreader appears only inside a quoted passage that the product located in a filing (the hero example's evidence row, the social card's excerpt), never for a headline, a tagline or a claim of ours; the italic "Nerd" of the wordmark is Inter. Promotional emphasis uses Inter italic 600 across its current surfaces, keeping the filing's serif voice reserved for located source prose. Inside the product Newsreader sets the filing reader and the passages the server located, each in its marked block (the filing page's Risks rows and the summary's located quotes, D-044); a summary, an answer, a heading, a speaker's name or a label of ours never takes it ([`designSystemDoneGate.spec.ts`](frontend/tests/unit/designSystemDoneGate.spec.ts) holds the surfaces).

In the filing reader, prose children have a 68ch measure and tables/figures can use the 88ch outer rail. AI `.markdown-body` content fills its pane with no measure cap. Summary paragraphs are justified and hyphenated at viewport widths of 640px and above. Below that breakpoint, summary paragraphs remain ragged-right; the original filing reader stays ragged-right at every width. Links in both reading surfaces, and in a Copilot answer, keep their underline and rest in the prose's own ink, turning sage only under the pointer: they print words the product does not write, a figure or a date among them (the Separate Signals Rule).

## Layout

Use shared page grounds around distinct content panels. Controls and tables are compact; reading and marketing sections use larger gaps. There is no single universal column count or container width for every route.

- The homepage hero, the site header and the landing's rows after the hero share a 1280px maximum container with 16px horizontal padding, then 24px from `sm` and 32px from `lg`, so every row's rule runs the width of the hero's trust strip and the label column starts under the logo.
- The hero stacks until `lg`, then uses two columns with a 64px gap; its stacked gap is 40px. The headline, CTA and search sit beside the filing example. This is a homepage composition, not a system-wide requirement.
- After the hero, every landing section is one ruled row ([`LandingRow`](frontend/features/marketing/components/LandingRow.tsx), D-045): a hairline across the container, then a 14rem label column (the section's number in the data face, counted in CSS so a section that omits itself takes none; its title in the Title role, the section's h2; one line in secondary ink) beside the content. The columns open at 64rem at the reader's text size, and below it the label stacks above the content. No row alternates and none lays its items out four across; pricing is one table, the plans as columns and what each includes as rows; the page closes with one line, not a banner. The label column is the margin of a 10-K, so the page reads as a filing's items.
- The shared responsive conventions use `sm` at 640px, `md` at 768px and `lg` at 1024px. Desktop header navigation appears at `lg`; the mobile menu occupies the smaller range.
- Spacing follows Tailwind's base scale plus the configured 18px, 52px, 72px and 24px gutter additions. Frontmatter records frequently used steps and the named gutter; component padding is recorded separately.
- A surface's inset is a capped step: padding step N becomes `p-cap-N`, `min(N × 0.25rem, N vw)` ([`tailwind.config.js`](frontend/tailwind.config.js), steps 3, 4, 5, 6, 8 and 10, for every side: `px-cap-6`, `sm:p-cap-8`). From a 25rem viewport up (400px at the default text size, 800px under a 200% text setting) it is the step itself; below that it is N% of the viewport, so a p-6 card keeps 24px at 1440px, 23.4px at 390px and 19.2px at 320px, and at 320px under 200% text keeps 19.2px where p-6 took 48px. A surface is a Card, a Modal's panel, a frame (a full border and a radius: the Card recipe copied by hand, a well), the Card's and the dialog's sections, a native dialog's sections, and what is written directly inside a Card, a Modal or a frame that sets no padding of its own; each takes the cap from step 5, and a frame inside a dialog's body from step 4 (the cookie dialog's category cards).
- Comfortable table rows use 10px vertical cell padding; compact rows use 4px. Numeric columns align right and use tabular figures. Wide tables scroll within their container.
- Modal sizes cap at 384px, 448px or 512px. Their outer inset bounds them to the viewport; the panel scrolls internally and reserves its capped inset as scroll padding (24px from a 400px viewport up), and its sections' sides, the header's top and the footer's bottom take that capped 24px. The header's icon and title wrap as one group beside the close button: where the title cannot keep 9rem beside its icon (a phone at 200% text), it goes under the icon, so the close button keeps the top right and the title never runs under it or past the panel. The footer stacks actions on small screens and switches to a row from `sm`.

**The Capped Inset Rule.** Under enlarged text a surface's inset stops growing at narrow widths: a Card, a frame and a dialog's sections set padding of step 5 or more as the capped step (`p-cap-N`, `min(N × 0.25rem, N vw)`), and a frame inside a dialog's body from step 4, so a reader who doubles the text on a phone keeps the measure for the words rather than for the padding, while nothing moves from 400px up at the default size or from 800px up under a 200% text setting.

The stacking vocabulary is sticky 30, consent 32, scrim 35, header 50, popover/overlay 60, modal 70 and toast 80. The consent layer is the cookie-consent bar alone: it sits above in-page sticky chrome, beneath the workspace sheets' scrims and the workspace sheets, launchers and coachmark, and, while it is mounted, publishes its height as `--consent-inset` on the root element, so the bottom-anchored launchers, the Copilot coachmark and the workspace sheets add that inset to their bottom offset instead of being covered by it or covering its choices, and the document's bottom scroll padding reserves the same height; the coachmark waits until the bar is gone, and the "preferences saved" confirmation is an ordinary top-centre toast. The scrim layer is the workspace and rail bottom sheets' backdrop: an open sheet dims the bar and makes it inert, as any modal does, and the bar is operable again once the sheet closes. Preserve the documented workspace-sheet and internal table-layer exceptions in the detailed implementation guide. Several other sites still use numeric z utilities, including the header and its account menu (`z-50`), `SecondaryHeader` and the Copilot coachmark (`z-40`), the feedback widget (`z-30`), the search dropdowns (`z-10` / `z-20`) and the workspace pane resizer (`z-10`). This snapshot records the ladder without renaming those sites.

## Elevation & Depth

Depth gives structure to the workspace. Light cards use warm paper, a hairline and a small shadow to lift from cream. Dark cards keep the slate fill and a faint white hairline with no resting card shadow. Interactive light cards brighten on hover; dark separation follows the component's explicit theme rules. Avoid describing a fill change as a universal dark-card hover behavior when the source does not define it.

### Shadow Vocabulary

The exact source shadow strings are stored in the sidecar's `extensions.shadows`. The configured `glow-brand*` shadows are unused and intentionally left out.

| Token | Role |
| --- | --- |
| `e1` | Low lift for small controls such as the switch thumb and pricing-period toggle, the popular-ticker and quick-access chips, and some tiles; the Badge primitive carries no shadow |
| `e2` | Default light card lift |
| `e3` | Featured/hero surface emphasis |
| `e4` / `e5` | `e4` for popovers (alert bell, source trace), the Copilot coachmark and toasts; `e5` for the shared Modal, bottom sheets, the citation-chip popover and the cookie-consent banner, light mode only. Header menus use `e2` and search dropdowns `e3` |
| `ring-brand` / `ring-brand-dark` | Opaque 3px keyboard focus, at least 3:1 on page, panel and tinted control surfaces; fields also show it on focus |
| `ring-brand-inset` / `ring-brand-inset-dark` | The same focus ink inside clipped scroll regions and calendar cells |
| `ring-error` / `ring-error-dark` | Invalid fields and destructive-action focus, with opaque ink in each theme |

**The Lifted Paper Rule.** On cream, default cards use the brighter panel fill, a hairline and restrained shadow. Pale sage is an accent tint, not the default card fill. Dark cards separate with fill and hairline.

The theme-aware hero search glow is a specific search treatment; it is not permission to add glows to ordinary components. The remaining authentication glass treatment and marketing mockup frame follow their existing scoped CSS recipes.

## Shapes

The established radius scale is 4 / 8 / 12 / 16 / 24px, with fully rounded pills for one-line chips. A chip whose label can wrap takes the 16px step instead, a pill on one line and a rounded box once it wraps, since a full radius turns a wrapped chip into a capsule whose curve crosses its text: the provenance chip and the email chip of the admin invites form ([`EmailChipsInput`](frontend/features/admin/components/EmailChipsInput.tsx)). Buttons and inputs use the 12px step at all standard sizes. Cards default to 16px and support a featured 24px variant; dialogs use 24px. The configured 10px `md` radius remains a legacy value and is intentionally excluded from the portable scale.

Borders are thin separators and control boundaries. Tables use row hairlines rather than full cell grids. Shape should follow the component recipe: avoid adding conflicting utility classes to simulate a variant that the component already exposes.

## Graphic device

The margin and the mark are the brand's one device, and they are the product's own behaviour made visible ([`docs/brand/06-system.md`](docs/brand/06-system.md) §6). The mark is a highlight under a phrase or beside a passage: the pale sage tint from 62% of the line box down with a sage hairline at the baseline (`.en-mark` in [`globals.css`](frontend/app/globals.css)); on a block it is a 3px sage bar on the left edge with the tint behind (`.en-marked`). The margin is a fixed gutter with a sage hairline on its inner edge holding bracketed marks (`[F1]`, `[1]`) in the data face, each positioned on the line of the in-text marker it twins (`.en-margin`, `.en-margin-mark`; [`MarkedCopy`](frontend/components/ui/MarkedCopy.tsx) measures the markers). In dark the tint, hairline, bar and marks take their dark tokens. The hairline stays 2px at every size; the margin is 44px from `sm` and 36px on phones, and below a measure it gives way: a marked copy narrower than 13em at the reader's text size (a phone under 200% text) drops the margin and its twins, and the marker in the heading stays; marks are 11px, the one place the dense annotation size is allowed beside copy, because a mark is a twin of a marker and never carries a claim of its own.

Promotional phrases use the approved C5 treatment through [`BrandEmphasis`](frontend/features/marketing/components/BrandEmphasis.tsx): a full Bright Sage (`brand-strong-dark`, `#98C5AD`) fill in both themes, 8px corners and genuine Inter italic 600. Its ink is opaque espresso (`text-primary-light`, `#1A1A17`) in light and navy (`background-dark`, `#0B1120`) at 90% in dark, with no hairline or shadow. Every homepage headline variant, the authentication pane and the waitlist share this recipe. The phrase stays together when it fits and wraps at a word boundary when enlarged text makes it wider than its container. Current share, social, print and email templates use the same fill, crisp italic ink and rounded enclosure with medium-appropriate layout; email uses the client's font and keeps its plain classic Outlook fallback. Located-passage treatments retain their separate annotation recipes. The implementation is specified in [`frontend/DESIGN_SYSTEM.md`](frontend/DESIGN_SYSTEM.md#7-marketing-surfaces).

Inside the product the device marks every passage the server located, because there it is literal (D-044). The filing page's Risks section is a marked copy: a row whose excerpt the server located carries a bracketed marker on its heading, numbered among the located rows, its twin sits in the margin on the marker's line, and the excerpt is a marked block in the filing's face; a row not located keeps the plain quotation and no marker. A quote in the summary whose evidence the server located takes the marked block alone, the quote in the filing's face: no marker and no twin, since a quote block has no heading to carry one; any other quote keeps the neutral hairline. The Source pane paints a passage the server located with the mark's tint and its 2px hairline, so the reader shares the standard inline mark's appearance: the Highlight API paints colours and decorations only, so the tint fills the line's content area and the hairline is an unbroken underline where the tint ends, and the passage reads in the primary ink (the reader's secondary ink is 4.49:1 on the dark tint over the slate panel). A jump the server did not locate (a summary chip's section heading, a Cited source, the text an XBRL fact's jump finds) lands in the reader's neutral find highlight, the brand sage at 22% with no hairline, so the reader still sees where it landed. Ask this Filing's answers and the Multi-Period narrative keep their citation chips: a cited line carries several markers there, and their twins would overprint. The two forms stay apart: a located passage set as a block (the landing's evidence row, a Risks excerpt, a located quote) takes the marked block, a located passage inside running text (the Source pane's) takes the tint and hairline, nothing unlocated takes either, and inside the product only the Risks rows carry a marker and its twin.

**The Marked Copy Rule.** A mark means "located in the filing" and a bracket means "cited"; inside the product the device marks every passage the server located and nothing else, one marker per row so the twins never overprint. A located passage set as a block takes the marked block and one inside running text takes the tint and hairline, never the other's form, and nothing unlocated takes either. One highlight per surface may sit under a phrase of ours as the brand's signature, and none ever sits on a figure, a price, an unverified claim or a competitor's name. Promotional phrases share the rounded, full-fill Inter italic treatment across homepage variants, authentication, waitlist and current brand templates; located passages keep their annotation marks. The margin appears only beside text that carries at least one marker, never as decoration and never beside Ask answers or the Multi-Period narrative, which keep their citation chips, and the filing's words inside a marked block keep the filing's voice.

## Components

Components are **refined, readable and quietly confident**. Reuse [`components/ui`](frontend/components/ui) and its supported variants. The sidecar's ten samples are static, dependency-free visual translations; they do not replace the React components, form guards, routing, sorting or dialog focus management.

### Buttons

- **Shape and size:** 12px radius. Small: 32px high, 12px horizontal padding, 12px label. Medium: 40px high, 16px horizontal padding, 14px label. Large: 48px high, 20px horizontal padding, 16px label. `icon-sm` is 32px square with zero padding. The optional `wrap` prop (also on `buttonVariants`) replaces a text button’s fixed height with that size’s minimum height and lets its label wrap with vertical padding; `icon-sm` stays square. Callers constrain width without overriding height or whitespace. Below a 24rem viewport (384px at the default text size, 768px under a 200% browser text setting) every labelled size takes that wrap state on its own, centred on tight leading and keeping a caller's own minimum height, so a phone with enlarged text does not scroll sideways to reach a button.
- **Primary:** sage fill and white label in light mode; light sage fill and navy label in dark mode. Hover and active use the corresponding named brand states.
- **Secondary / Ghost:** transparent ground and sage text; secondary adds a sage hairline. Hover adds a tint; active strengthens it. `tertiary` is only a deprecated alias of ghost.
- **Destructive:** error fill with white label; darker error hover and active states. Preserve its error focus ring.
- **Focus and busy:** use the shared focus recipe. Loading keeps the resting appearance, adds a spinner and `aria-busy`, and refuses repeated activation. A button whose loading label is longer than its resting one can keep that room at rest (`reserveLoadingText`), so the swap never resizes it or moves what sits beside it; the retry button does, for "Trying again…". Controls made unavailable by their own request stay focusable using the established `aria-disabled`/handler guards. A form that locks its text fields while submitting uses `readOnly` rather than native `disabled`; the contact form does, while login and registration leave fields editable. Native disabled styles exist for other unavailable states.

A single-choice toggle group is the [`SegmentedControl`](frontend/components/ui/SegmentedControl.tsx): a panel shell with a hairline, 8px segments with semibold labels (12px at the 26px height, 14px at 36px; the 26px height is 1.625rem, so it scales with the root and holds its label at 200% text), the pressed segment in the primary colorway (navy label on light sage in dark mode), and codes such as 10-K in the data face. Its options are all visible, so it is a group of pressed buttons rather than tabs or radios. On a phone, a full-width control spans its row with 36px segments and wraps whole segments onto another row when they do not fit; a label never breaks. Options unavailable before selection can remain visible in the native disabled state. With `focusableDisabled`, unavailable options retain keyboard focus and their explanation; the controlled selected value keeps its primary treatment even when unavailable. A long set of options, such as a chart's metric picker, is not a segmented control: it is a compact select sized to its content beside its label, which never overflows; the control keeps short sets such as a time window's three codes, and [`segmentedControlOptionCount.spec.ts`](frontend/tests/unit/segmentedControlOptionCount.spec.ts) fails a `SegmentedControl` given more than five options and pins, with its reason, a site whose options it cannot count statically: the filings index's form filter, All plus the company's forms, a set [`FilingIndex`](frontend/features/filings/components/FilingIndex.tsx) counts at run time and renders as the toolbar's compact select past five, so no `SegmentedControl` ever shows more than five. A hand-built `role="group"` of pressed buttons outside the primitive's own file fails lint (`earningsnerd/no-hand-rolled-toggle-group`): the rule reads a pressed `<button>` or `<Button>` in the group's own markup, through a same-file wrapper component and through the DS `Button` imported under another name; a row without `role="group"`, a wrapper imported from another file and a wrapper that renders another wrapper are outside its reach (review-checked).

[`Button.tsx`](frontend/components/ui/Button.tsx) also exports `buttonVariants` for real links styled as buttons. Standard color feedback uses the fast motion token. Spinner animation remains the existing utility with a reduced-motion fallback; this document introduces no new timing for it.

### Chips

Pill-shaped, 12px semibold labels with 10px horizontal and 2px vertical padding. Brand, pro and new variants use the sage tint and hairline; only pro uppercases its label. Solid chips use deep sage with white labels in light mode and navy labels on light sage in dark mode. Quiet chips, info/warning tints, status chips and gain/loss chips keep their distinct meanings; a gain/loss chip is a direction with its ▲/▼, never a status. The status chips are one set, `success`, `error`, `info-status`, `warning-status` and `neutral-status`: the status ink on the quiet ground, with no fill in dark. The info, warning and neutral chips are the tints and the quiet chip, so their status forms have names of their own; the admin lists' invite and feedback statuses, the summary statuses on the watchlist and dashboard rows and the labs research evidence pack's review status are drawn from the set. Its sixth, `tentative`, is a status not yet settled, the calendar's estimated date ("Est."): the neutral status ink on a dashed hairline, with no fill in either theme. The calendar's whole status ladder is drawn from the set, reading dashed, blue, quiet: "Est." on `tentative`, "Confirmed", a firm and upcoming date, on `info-status`, and "Reported", the event over, on `neutral-status`, its EPS figure carrying the news. A chip's ground, ink and hairline come from its variant, never from a class on top, which wins or loses by stylesheet order. `new` adds a pulse dot in its sage ink, which becomes static for reduced motion: a new filing is news, not a caution, so it takes no warning tint. A form code (10-K, 10-Q, 6-K) is never a chip: it is text in the data face.

Icons are Phosphor through `lib/icons`, in `currentColor`; three glyphs are reserved: the quotes glyph for a filing passage, the braces for an XBRL fact, and the sparkle for the AI summary chip alone. Section headings carry no icon. The brand uses no photography and no illustration: its images are the filing's identity line, a figure with its fact, a quoted passage with its mark, a tally, and real product components fed verified data ([`docs/brand/06-system.md`](docs/brand/06-system.md) §4 and §5).

The provenance chip ([`SourceTrace`](frontend/features/filings/components/SourceTrace.tsx)) is its own recipe: 12px/500 in the data face, 20px tall, the 16px radius of a chip that can wrap, a hairline on the panel fill with secondary ink, a quotes glyph for a filing passage and braces for an XBRL figure. The chip the open research pane is answering takes the sage tint, whether the pane shows its passage or says why it cannot.

### Cards / Containers

The base [`Card`](frontend/components/ui/Card.tsx) supplies shape, fill, border and elevation, but **no internal padding**. `CardHeader` and `CardBody` add 20px horizontal / 16px vertical padding; `CardFooter` uses 20px / 12px; their sides are the capped step (`px-cap-5`), and a caller's padding on a Card of step 5 or more is the capped step too (the Capped Inset Rule). Titles are sentence-case 14px semibold headings. Set `as`, `interactive`, `elevation` and `radius` through the API; an interactive appearance alone does not supply link or button semantics.

The filing summary is a document rather than a stack of cards: its sections sit on the page ground under section titles, and hairlines live inside the content. A callout inside a section is an inset well ([`Callout`](frontend/features/summaries/components/Callout.tsx)): panel fill, one hairline, the 8px radius and no shadow, with its tone carried by the label word. A thick left border on a rounded container, the side-tab stripe, is not part of the system. The change report's wording comparison ([`WordingChanges`](frontend/features/filings/components/WordingChanges.tsx)) is a redline in the section's own ink: inserted words underlined in primary ink, removed words struck through in muted ink, each named for assistive tech, with a label word carrying a whole paragraph's state; neither the mark nor a financial tone means "edited". A Pro reader's review of those changes is two pressed-state toggles on each row (Reviewed, Follow up: fill and weight together carry the pressed state), the j/k and 1/2 keys on the list, a counted progress line, and, once every change is marked, a receipt in an inset well that names the two texts compared and copies as plain text.

A list of primary documents is one surface ([`FilingIndex`](frontend/features/filings/components/FilingIndex.tsx)): hairline rows and year groups inside the section card, one link per row named by its form, period and filed date, the original on EDGAR as a sibling link, and no per-form color. The company page leads with the filing page's identity vocabulary ([`CompanyIdentity`](frontend/features/companies/components/CompanyIdentity.tsx)) and its one primary action, opening the latest filing; the watchlist sits beside it as a secondary button. Beside the filings, the Compare periods card ([`ComparePeriodsCard`](frontend/features/filings/components/ComparePeriodsCard.tsx)) previews the newest annual report's change report in that report's own vocabulary, counts its risk-factor wording changes, and links to it. Every hero headline accent takes the shared `BrandEmphasis` treatment above; the hero example's evidence row is a marked block in the filing's face with its margin mark. The homepage example ([`HeroExample`](frontend/features/marketing/components/HeroExample.tsx)) is the product on one surface: the filing's identity, the summary's opening, a hairline strip of figures and one evidence row, with no frame mockup or card inside the card; plain trust statements sit under the hero.

### Inputs / Fields

[`Input.tsx`](frontend/components/ui/Input.tsx) shares a bright white light fill and translucent white dark fill, 12px radius, hairline and 14px text. Standard padding is 10px vertical / 14px horizontal. Search fields explicitly reserve 44px on the leading side for their icon. The password field reserves 40px on the trailing side for its reveal toggle. A search field reserves the same 40px for its 16px busy spinner, whether or not it is busy, and marks itself busy while it loads; the spinner never covers typed text. A company search result names the filing a pick lands on: under the company and its ticker, one data-face line in the filing identity's vocabulary ("Latest 10-K · fiscal year ended … · filed … · summary ready"). Hover strengthens the border; focus shows the brand border/ring, and only that ring: every field resets the forms plugin's own blue focus ring. An invalid field takes the error tone in place of that one, with an associated error message: an error border that holds on hover, and the error ring on focus. A raw destructive-confirm field uses `inputClasses({ tone: 'danger' })`: its resting and hover borders stay neutral, with an error border and ring only on focus. This action tone does not mark the value invalid; an actual invalid value takes precedence. A toolbar field beside a segmented control, and a field inside a table row, use the compact density: 36px tall from `sm` up, keeping the standard 42px field height on phones. A select reserves 36px on its trailing side for its chevron. A select beside its label, in a toolbar or in a table cell sizes to its content, capped at its container, rather than filling the row. The composer textarea is transparent inside its own field shell to avoid double borders; the shell shows the brand border and ring while anything in it has focus, hovered or not.

A checkbox is the shared [`Checkbox`](frontend/components/ui/Checkbox.tsx), never a raw input: Deep Sage under the forms plugin's white check when checked in light, and in dark the Primary's own pairing, Light Sage under a navy check (7.8:1; the white check on it would be 2.4:1), drawn from the `--check-navy` stylesheet variable; the flat ink is the unchecked edge, with the brand focus ring.

### Navigation

[`Header.tsx`](frontend/components/Header.tsx) uses a sticky, translucent page-ground strip and hairline with 14px medium-weight links. Desktop links have a 32px gap, secondary ink at rest, primary ink on hover and a visible brand focus ring. Every header control (logo, links, theme toggle, the account and notification menus and their items, the mobile menu button and its links) shows that ring on keyboard focus, never the browser's outline. The header currently does not implement a route-active link color; do not invent one in this snapshot. Below `lg`, links move into the collapsible menu and the menu trigger maintains a 44px minimum target. Below a 24rem viewport (384px at the default text size, 768px under a 200% browser text setting) the theme toggle, a preference rather than a next step, moves from the bar into that menu, so the bar keeps one row: the logo, the account link and the menu button, with the link's label wrapping before the bar does; only where even that cannot sit beside the logo does the bar wrap. In the menu the toggle takes the first row, directly under the bar, so it opens in view. The header is never taller than the viewport: the bar keeps its own height, and an open menu longer than the screen scrolls in the space below it, so its last rows (Log out, the account link) are reached by scrolling the menu. The open menu is a disclosure, not a dialog: it does not lock the page, and a scroll inside it never chains to the page behind it. Logo and theme toggle belong to the shared header.

### Data tables and charts

[`DataTable.tsx`](frontend/components/ui/DataTable.tsx) supports comfortable and compact density, row hairlines, optional sticky columns, right-aligned mono numeric cells, sorting, loading, empty and error states. Ordinary rows brighten to white on light hover and use a translucent white tint on dark hover. With the sticky first column enabled, its body cells retain the opaque dark panel fill on hover so scrolled values cannot show through; their light hover still brightens to white. Sort controls are buttons; `aria-sort` belongs to the header cell. Financial tones come from the existing helpers. Chart captions, axes and tooltips keep their theme-aware styles; use the categorical sequence described in Colors. The summary's Financial Highlights ([`FinancialMetricsTable.tsx`](frontend/features/summaries/components/FinancialMetricsTable.tsx)) stacks each metric into one card below `md` (768px) — name with its XBRL chip, the current, prior and change figures under eyebrow labels in the data face, then the takeaway with its chip, the missing-value element read as "no takeaway" where the summary wrote none — and keeps the DataTable unchanged from `md` up; both presentations are rendered and switched by CSS, so the inactive one is `display:none` (out of the accessibility tree and the tab order) and the active one carries the caption (the table's `<caption>`, the list's `aria-label`).

A value the page does not have is the [`MissingValue`](frontend/components/ui/MissingValue.tsx) element, in a table cell, a detail row or a line of copy: the missing-value token (`—`, the one sanctioned em-dash) in the ink around it, hidden from assistive tech, beside words a screen reader reads in its place. The words are "unavailable" by default, the analysis evidence's word for a missing figure, or the site's own where "unavailable" would claim more than its data says: "no cohort" for an invite minted without one, "no page" for feedback sent from none, "no role listed" for an insider row that lists neither a title nor a role, "name unavailable" for a name the read lacks, "no percentage" for a change from a zero prior, "no takeaway" for a Financial Highlights row the summary wrote no takeaway for, "Not included" for a plan without a row's feature. The element positions itself, so its words stay inside a truncating cell or a table's scroll box. A formatter returns nothing for a missing value and its caller renders the element, so a string fallback stays for a CSV, a title or an aria label; the token is never written by hand, nor hidden with no words ([`missingValueToken.spec.ts`](frontend/tests/unit/missingValueToken.spec.ts)).

### Dialogs and evidence

Use [`Modal.tsx`](frontend/components/ui/Modal.tsx) for ordinary dialogs: translucent navy scrim, rounded panel, shared focus trap, Escape handling, opener focus restoration and internal scrolling. Keep the documented bespoke sheets/native calendar-dialog exceptions rather than creating additional dialog systems. Static sidecar samples demonstrate the visual shell only.

A transient confirmation is a Sonner toast at the top centre, in the theme the reader chose on the site: a panel card with a hairline and primary ink, `e4` in light (the overlay step, as the popovers) and no shadow in dark. A status toast (success, error, warning or info) keeps the panel ground and colours only its icon, in its status ink.

The signature evidence treatment is a compact citation/source chip attached to a figure or passage, with a route to inspect its source. [`CopilotMessage.tsx`](frontend/features/filings/components/copilot/CopilotMessage.tsx) is the production Ask answer renderer. A source match describes attribution within its stated scope; it must not imply that every claim in an answer was verified. Keep citation labels and evidence states faithful to the renderer.

**The Calculation Provenance Rule.** A calculation describes a figure’s origin, not a failed check. Multi-period analysis uses a neutral † for calculated figures and lettered data notes grouped by their underlying reasons. A figure opens its source, calculation and applicable note in the shared Modal. Only unresolved source concerns use warning ink; missing validation makes no passed-check claim. An unavailable table value is — with its note letter, explained as “Unavailable” in the evidence view and exports. Values and comparisons are counted separately, including inherited concerns. Expanded notes locate each basis among the actual latest-available headline figures, the revenue or net-interest-income growth chart, and the table’s selected comparisons; repeated appearances do not increase totals. A narrowed table window states how many are currently shown. Citation-only and illustrative notes make no report-surface claims. A hairline Data notes disclosure names the relevant letters beside each resting count, then places each letter beside its reason, affected periods and counts. When every populated figure passed, it says “No figures need review” with a neutral checked count, even when a comparison carries its own note. Checks distinguish SEC XBRL admission from calculations with compatible periods and units; neither is an audit. Headline metrics form a two-up phone and four-up desktop definition list, collapsing to one card when the component is narrower than 17 em at its actual text size: shared rows align the metric labels, source-linked values and independently wrapping period/delta line. An older populated metric states its actual period and “latest available”. Analysis tables keep equal rem-based period columns and semantic row headers. The labels stick only when a whole period fits beside them; otherwise the label column scrolls and has its own snap stop. Its width is capped to the MetricsTable card’s content width, keeping labels readable at Home and preventing an oversized snap area from resting between columns. The shared `useOverflowRegion` hook measures the scroll box and its first child and adds a named region and Tab stop only while content exceeds the box by more than one CSS pixel. Surface-specific hints and scrolling behavior stay with the caller. On phones, “← Earlier quarters” appears only while earlier columns are off-screen; its line keeps its space at the start so keyboard scrolling does not move the page. Dark sticky row headers retain their opaque panel fill during hover. Mandatory column snapping includes trailing space for a whole-column scroll range, measured before paint and recomputed without losing the selected column when the viewport or text size changes. Native resize scrolling cannot overwrite that column using stale measurements. Table arrows, Home/End and page keys scroll the focused region; focused cells remain wholly visible. Fallback YoY labels occupy their own line, and data cells align at the top. The reader can show all periods, the newest six or the earliest six without changing charts, headline figures, note totals or exports. A status line announces the window; a new report or snapshot resets it. Illustrative tables keep their full range without window controls. Quarter headers keep full accessible names, while the annual final header names the full report range and CAGR; percent-unit rows show the window’s percentage-point change. The table’s Notes chip names letters present in visible cells in report order, including unavailable values and annual window comparisons. Legends explain n/m, fiscal quarters and the Q4 flow-figure dagger without marking balance-sheet figures as calculated. Table figures use compact display precision when needed to keep amounts and note marks together; the rounding disclosure directs readers to full-precision evidence. Charts keep bars filled and mark affected observations with hollow points or note letters. Letters retain panel-colour halos in SVG and PNG, and each plot becomes a named keyboard scroll region only while it overflows. A separate named chart-values stop retains Recharts Left/Right tooltip navigation, including per-period YoY values that the quarterly table does not always show; changing tooltips use a live status and name each value or YoY concern by its own note letter. Formatting follows the original series identity before that letter is added. Inner arrow keys reveal the selected mark without competing native pixel scrolling; tooltips wrap and stay inside the measured viewport. Pointer inspection does not scroll a still-focused chart; the next keyboard arrow releases the hover and resumes its retained period. Outer arrows keep native scrolling, and Tab leaves and returns without trapping focus. PNG notes use the same grouped reasons without repeating a recorded gap. Chart lines break at gaps. Evidence dialogs label supplied values “As stored”, explain checks before methods, and retain recorded lineage. A noted comparison identifies the recorded input carrying its concern, or states that the input identity is absent. Each source control describes its comparison note once; the visual change mark does not repeat it. Missing figures read “Unavailable”; quarterly evidence states the quarter end and explains that changes needing a gap are not shown. Source links have distinct figure-and-period names. Narrative amounts use financial display forms while preserving meaningful differences. Up to three source operands remain inline with their citations; longer lists fold beneath a neutral summary naming their note letters. Printing opens Data notes and narrative evidence, then restores the reader’s disclosure choices. The Analysis title and company rows wrap at enlarged text sizes. Its narrative card uses 16px phone padding and the capped 24px from sm (`sm:p-cap-6`); export and refresh buttons use the shared `wrap` state to keep their minimum height while growing to wrap their labels within the card. A compact period selector uses plain recent-period actions and data-face From/To fields. The Analysis route is an inline-size query container: below 13 em of its actual text size, the main gutter uses spacing 2 and the control card uses inline spacing 1.5, preserving complete period tokens without changing text or shared field padding. Unavailable modes stay focusable beside an explanation. A controlled mode that becomes unavailable keeps its selected appearance until the reader chooses another mode; unavailable activation still does nothing. A status message announces when changing an endpoint moves the other end to preserve the range cap or order. Source dates, definitions and material gaps travel with exports.

The calculation states above were added from source in October 2026; their focused component and export tests do not by themselves establish visual acceptance in both themes.

The filing page states its filing once, as a signpost ([`FilingIdentity`](frontend/features/filings/components/FilingIdentity.tsx)): company and ticker, then one data-face line of form, period of report (an 8-K's event date), filed date, exchange and the original on SEC EDGAR, followed by a verification tally in scoped words that counts only what the server could check ("checkable figures matched the company's XBRL", "located in the filing text", "withheld"). Risks are a marked copy (D-044): each row a heading cut from its excerpt and its chip, and, where the server located the excerpt, a bracketed marker on the heading with its twin in the margin and the excerpt as a marked block in the filing's face; a row not located keeps the excerpt in blockquote manners and no marker. A quote whose evidence the server located is a marked block with no marker. The research pane is named for the source: "Source", with the tabs Filing · Ask; it is a dialog only where it is a bottom sheet, below `lg`, and a complementary pane beside the summary from `lg` up.

Motion supports state changes and reading continuity. The source has fast (150ms), base (200ms), slow (600ms) and ambient (1800ms) timings; standard easing is the default and pop easing is reserved for the success check. These live in CSS variables with a JS mirror. Every animation stops under reduced motion: the `globals.css` animation classes guard themselves, each Tailwind animation utility carries its reduced-motion guard (a lint rule holds new ones to it), and count-up, citation highlighting and chart drawing have their own fallbacks. A spinner becomes its static glyph, a skeleton a static bone, an entrance shows at once. A loading page is never a full-page spinner: it renders its own header over bones in the shapes of the cards that will replace them, and the content crossfades in on arrival. Motion values and breakpoints belong in the sidecar, not new frontmatter groups.

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
- **Do** use the margin and the mark where a passage was located or a figure cited, and keep the filing's words in the filing's face inside a marked block.

### Don't:

- **Don't** restore retired mint branding, decorative gradients or general-purpose glow effects.
- **Don't** use sage as a chart-series or financial-direction color.
- **Don't** use light gain/loss graphic colors for small delta text or tertiary dark ink for muted labels.
- **Don't** use the legacy 10px radius for new components or uppercase ordinary card titles.
- **Don't** apply the filing reader's serif to AI summaries or cap pane-filling summaries to a prose rail.
- **Don't** treat illustrative sidecar markup as production tokens or behavior, or add synthetic tonal ramps to the sidecar.
- **Don't** create another dialog primitive or remove existing reduced-motion fallbacks.
- **Don't** put a thick left stripe on a rounded container or set a form code as a chip; callouts are inset wells and forms are data-face text.
- **Don't** put the mark on a figure or a status, draw a margin without a marker, or scale the device's hairline with the type.
