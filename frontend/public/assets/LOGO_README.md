# EarningsNerd Brand Assets

The sage "EN" monogram set (July 2026 rebrand — replaces the legacy teal/amber mark).
The mark is the letters **E + N** with the N's final stroke rising into an arrow.

## Renditions

| File | Use |
|------|-----|
| `earningsnerd-appicon.svg` | The app tile: sage `#4F7A63` squircle + cream mark. Source for favicon.ico, PWA icons, and the SVG favicon (self-backgrounded — legible on light AND dark tab chrome). |
| `earningsnerd-icon-light.svg` | Bare mark in `#3C6650` (brand.strong) — light surfaces. |
| `earningsnerd-icon-dark.svg` | Bare mark in `#7FB295` (brand.dark) — navy surfaces. |
| `earningsnerd-logo-light.svg` | Full lockup: mark + wordmark ("Earnings" ink `#1A1A17`, italic "Nerd" `#3C6650`) — light surfaces. |
| `earningsnerd-logo-dark.svg` | Full lockup for navy (`#7FB295` mark, `#D7DADC` ink). |
| `earningsnerd-mark-sage.svg` | Bare mark, fixed sage `#3C6650`. |
| `earningsnerd-mark-navy.svg` | Bare mark, fixed navy `#0B1120` (for light non-brand surfaces). |
| `earningsnerd-mark-white.svg` | Bare mark, fixed white (for photos / dark fills). |
| `earningsnerd-mark-mono.svg` | Bare mark in `currentColor` — the geometry source for in-app components and the asset pipeline. |

## In-app usage

Never inline the mark by hand — compose the components:

- `components/EarningsNerdLogoIcon.tsx` — the monogram in `currentColor`
  (`mode="auto"` = `text-brand-strong dark:text-brand-dark`). Single source of
  the geometry, kept in sync with `earningsnerd-mark-mono.svg`.
- `components/EarningsNerdLogo.tsx` — icon-only or the full two-tone lockup.
- Wordmark-as-text (Header/AuthShell): `Earnings` in primary ink +
  `<em class="italic text-brand-strong dark:text-brand-dark">Nerd</em>`.

## Generated binaries

`npm run brand:assets` (see `scripts/generate-brand-assets.mjs`) regenerates the
committed binaries from this directory: `favicon.ico`, `apple-touch-icon.png`
(180, full-bleed — Apple applies its own corner mask), `icons/icon-{192,512}.png`
(+ `-maskable` full-bleed variants, mark at 0.62 for the r=40% safe zone), and
`og-image.png` (deterministic Playwright render with the committed Inter woff2).

## Rules

- Mark aspect ratio is 94.6:73.2 (~1.29:1) — never stretch; letterboxing in a
  square box is expected.
- Brand accents only: sage as identity, never in a numeric/price context
  (gain/loss colors carry data meaning — see DESIGN_SYSTEM.md).
- The wordmark's "Nerd" is always italic in the brand accent; "Earnings" is
  always the surface's primary ink.
