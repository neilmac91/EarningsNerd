# EarningsNerd Design System

**AI-powered SEC filing analysis.** EarningsNerd turns dense 10-K and 10-Q filings into clear, evidence-backed summaries — business performance, financials, risks, and management discussion — so investors can understand a company in minutes instead of hours. It's a financial-data product: calm, credible, and precise, never a flashy fintech "casino."

Status: pre-launch (waitlist). Live: earningsnerd.io · API: api.earningsnerd.io.

## Products represented
- **Marketing site** — homepage hero + ticker search, trending filings, how-it-works, pricing, legal. Public, theme-toggleable.
- **App** — authenticated dashboard (watchlist feed, usage, saved summaries), company pages, and the AI **filing summary** (executive snapshot, KPI tiles, evidence-backed sections, "Ask this Filing").

## Sources used to build this system
- **GitHub:** `neilmac91/EarningsNerd` (private) — primarily `frontend/`. Lifted exact values from `frontend/tailwind.config.js` (tokens), `frontend/app/globals.css` (effect classes), `frontend/DESIGN_SYSTEM.md` (usage rules), and the real components (`components/ui/Button.tsx`, `Input.tsx`, `StatCard.tsx`, `StateCard.tsx`, `Header.tsx`, `Footer.tsx`, `app/page.tsx`, `app/dashboard/page.tsx`). Explore the repo further to design with higher fidelity.
- Logo + icon SVGs and `og-image.png` from `frontend/public/assets/` (now in `assets/`).

---

## CONTENT FUNDAMENTALS — how EarningsNerd writes

**Voice:** confident, plain-spoken expert. It explains finance without dumbing it down or hyping it up. The promise is *clarity and evidence*, not stock tips.

- **Person:** addresses the reader as **you** ("Your first summary is free"); the product is "EarningsNerd" / "we" sparingly. Never first-person "I".
- **Casing:** Sentence case for headings and buttons ("Understand any SEC filing in minutes", "Generate summary", "Upgrade to Pro"). UPPERCASE only for tiny eyebrow labels and metric labels ("REVENUE", "EXECUTIVE SNAPSHOT"), tracked wide.
- **Tone:** benefit-first and concrete. Leads with the outcome ("…in minutes instead of hours"), backs it with proof ("Every bullet must cite a filing excerpt or an XBRL anchor").
- **Numbers:** always specific and sourced — "$391.0B (+2% YoY)", "data-center revenue up 94%". Figures are monospace + tabular. Direction is shown calmly (▲/▼ + muted green/red), never as a loud casino delta.
- **Compliance register:** quiet, persistent disclaimers — "Data sourced from SEC EDGAR. Not investment advice." Trust language ("evidence-backed", "deep-linked citations", "sourced directly from SEC EDGAR") recurs.
- **Emoji:** essentially none in product UI. One 🔥 / flame icon marks "Trending / Hot Filings" — prefer the Phosphor `flame` icon over the emoji. No decorative emoji elsewhere.
- **Examples:** "Understand any SEC filing in minutes." · "AI-powered summaries that turn 100-page 10-Ks and 10-Qs into clear, decision-ready insights." · "Your first summary is free — no signup needed." · "Stop skimming. Start understanding."

---

## VISUAL FOUNDATIONS

**Brand color = sage (light) / slate (dark).** This is the deliberate replacement for a former neon-mint accent. Mint / emerald / blue / sky / teal / `primary-*` are **legacy and banned as brand** — never introduce them as a primary/accent. (The *logo mark* is a separate fixed identity — see Iconography.)

- **Palette:** warm **cream** page (`#F4F3EE`) with off-white **cards** (`#FBFAF6`) in light; deep **navy** (`#0B1120`) with slate cards (`#1F2937`) in dark. Brand sage `#3C6650`/`#4F7A63`, slate `#92A0E2`/`#B4BEEE`. Financial **gain/loss/flat** (green/red/grey) are *data signals*, kept distinct from brand. A 6-color categorical **chart** palette (teal, cornflower, honey, coral, periwinkle, sage) — subdued and warm-leaning.
- **Theme-responsiveness is mandatory.** Every color on a surface that renders in both themes is a light/dark pair (the semantic aliases in `tokens/colors.css` do this — build against `--surface-card`, `--text-body`, `--accent-strong`, etc., and they switch under `.dark`). Muted text on dark uses `secondary`, never `tertiary` (fails AA).
- **Type:** three roles. **Headings** are a neutral grotesque (Helvetica/Arial) — fixed, never switch. **Body** is **Figtree** (friendly, approachable). **Data** (money, %, tickers, XBRL, AI summary output) is always **monospace + tabular-nums** so columns don't jitter. An editorial serif (Georgia) exists for long-form. Display sizes tighten letter-spacing as they scale up; body stays comfortable.
- **Spacing:** 4px base step with financial in-betweens (18 / 52 / 72px) because dashboards pack tightly. Default gutter 24px.
- **Backgrounds:** flat, solid, on-brand surfaces — **no decorative multi-hue gradients**. Warm cream / deep navy only. A single subdued brand accent (e.g. the hero accent word is solid `brand-strong`, not a gradient). No background images, textures, or patterns on content; the only imagery is the OG card and the logo mark.
- **Cards LIFT, never tint.** `brand-weak` (#ECF2EE) is *darker* than the cream page, so it's invisible as a card fill. Cards use a *lighter* fill (`panel-light`) + a hairline + a soft `e2` shadow; in dark they separate via fill contrast + hairline with **shadow:none**. Hover **brightens** (toward white / `brand-weak`), never darkens.
- **Borders:** 1px hairlines — `#E5E7EB` light, `white/10` dark. Cards `radius-lg` (12px); chips/pills `radius-full`; feature/hero panels `radius-2xl` (24px); inputs `radius-lg`.
- **Elevation:** `e1` chips · `e2` cards · `e3` hero/featured · `e4/e5` menus & overlays. Soft, low-spread, cool-grey shadows (`rgba(16,24,40,…)`).
- **Shadows vs glows:** drop the legacy mint "glow". The only glow is the theme-aware **hero search glow** (a faint brand ring that intensifies on focus-within).
- **Buttons:** one each — **primary** (solid sage/slate), **secondary** (panel fill + hairline + soft lift, **brightens** on hover), **tertiary** (ghost). Never `hover:opacity` on secondary (it darkens). Focus = 2px brand outline, offset 2.
- **Inputs:** fill is the *brightest* surface (white / dark glass) so the field reads on both the cream page and an off-white card; brand focus ring.
- **Transparency & blur:** used sparingly and purposefully — the sticky header is a translucent page color with `backdrop-filter: blur`; `.glass-card` is a translucent surface with blur. Not used decoratively elsewhere.
- **Animation:** restrained. `fade-up` entrances (~0.6s ease-out), a gentle `float` on the hero example card, a success checkmark "pop" (`cubic-bezier(0.34,1.56,0.64,1)`). Streaming summaries reveal progressively. Everything respects `prefers-reduced-motion`. No infinite decorative loops on content.
- **Hover / press:** links underline (offset 4px) or shift to primary text color; secondary surfaces brighten; nav items go muted→primary. Press states are subtle — no aggressive shrink.
- **Imagery vibe:** there's almost none by design — this is a data product. Where present (OG card), it's the deep-navy brand surface with the sage/mint accent. Cool, clean, screenshot-of-product over photography.

---

## ICONOGRAPHY

- **Icon set:** [**Phosphor**](https://phosphoricons.com) (`@phosphor-icons/web` font in the kits, `@phosphor-icons/react` in the app) — clean 256×256 grid, **regular weight** (outline, ~1.5px-equivalent), matched cap geometry. This is the house set; match its weight and roundness. The UI kits load Phosphor's regular-weight web font from CDN (`<i class="ph ph-name"></i>`, sized via `font-size`); the foundation cards inline matching outline SVGs.
  - Common glyphs: `magnifying-glass`, `sparkle` (AI), `file-text`, `chart-line` / `trend-up`, `shield-warning` / `shield-check`, `flame` (trending), `bell`, `bookmark-simple`, `git-diff`, `arrow-right`, `caret-right`, `quotes` / `link` (citations), `check-circle`, `sun` / `moon` (theme).
- **Logo mark:** an **"EN" composite glyph** (EarningsNerd) — a solid, geometric block **"E"** with an **integrated upward graph-line "N"** that valleys exactly at the E's baseline and sweeps up into a prominent breakout arrowhead. The whole glyph is **one solid brand color per theme**: **sage `#3C6650`** in light (on cream, with a fine white keyline + `shadow-e2` lift), **slate `#92A0E2`** in dark (on navy, flat — the graph-line is separated from the E by a navy gap). No gradients; strictly on-palette. Files in `assets/`: `earningsnerd-logo-{light,dark}.svg` (glyph + uniform "EarningsNerd" wordmark — espresso `#3A2E26` light / `#D7DADC` dark) and `earningsnerd-icon-{light,dark}.svg` (glyph only). Use the light files on light/cream, dark files on navy. The mark stays legible down to 24px / favicon size.
- **Tile-less mark variants** (transparent bg, single-color "EN" glyph — for inline use on photos, print, embossing, tight favicons): `assets/earningsnerd-mark-mono.svg` (inherits `currentColor` — set `color:` on the parent), plus fixed `-sage`, `-navy`, and `-white` versions.
- **Emoji:** avoid in UI. The only legacy use is 🔥 for "Trending Filings" — prefer the Phosphor `flame` icon instead.
- **No hand-drawn/AI SVG illustrations** exist in the brand; don't invent any. Use Phosphor glyphs, the logo, and product screenshots.

---

## Index / manifest

**Foundations (root)**
- `styles.css` — the single entry point consumers link (`@import` manifest only).
- `tokens/colors.css` · `tokens/typography.css` · `tokens/spacing.css` · `tokens/fonts.css` — CSS custom properties + the Figtree webfont. Base values **and** theme-responsive semantic aliases (`.dark` re-points them).
- `base.css` — element defaults + effect classes (`.tabular`, `.glass-card`, `.hero-search-glow`, financial-tone helpers, entrances).
- `components.css` — class recipes for the React primitives.

**Foundation cards** (`guidelines/*.card.html`) — Colors (brand, surfaces, financial, state, chart, text), Type (roles, scale, tabular), Spacing (radii, elevation, scale), Brand (logo, icon).

**Components** (`components/`) — React primitives, each `Name.jsx` + `Name.d.ts` + `Name.prompt.md` + a group card:
- `core/` — **Button**, **Badge**, **Card**
- `forms/` — **Input** (input / textarea / select)
- `data/` — **StatCard** (KPI tile + sparkline), **StateCard** (guidance / error)

Mount in HTML via `const { Button } = window.EarningsNerdDesignSystem_3681b9` after `<script src="…/_ds_bundle.js">`.

**UI kits** (`ui_kits/`)
- `marketing/` — homepage hero, search, trending, how-it-works, CTA. Interactive + theme toggle.
- `app/` — dashboard + AI filing summary. Interactive click-through + theme toggle.

**Assets** (`assets/`) — logo & icon SVGs (light/dark), `og-image.png`.

`SKILL.md` — Agent-Skill front-matter so this system works in Claude Code.

---

## CAVEATS
- **Figtree** is loaded from **Google Fonts** here (the production app self-hosts it via `next/font`). Same typeface, different delivery — swap to self-hosted files if you need offline/zero-network.
- Headings, data, and the editorial serif use **OS-native stacks** (Helvetica/Arial, system monospace, Georgia) — no webfont, so they render with whatever the viewer's OS provides.
- The bundled `_ds_bundle.js` is **generated by the compiler**; component cards and UI kits appear blank until it's built (after the first turn completes).
- Direction arrows in financial chips use Unicode ▲/▼ in some demos and inline outline arrows in components — both are on-brand.
- The **logo/icon were redesigned** (June 2026) from the original "nerd glasses on a chart" teal+amber mark to an on-brand **"EN" composite glyph** — a solid block E with an integrated upward graph-line N + breakout arrow, one solid color per theme (sage light / slate dark). The legacy `--logo-*` teal/amber tokens remain in `tokens/colors.css` for reference but are no longer used by the mark.
