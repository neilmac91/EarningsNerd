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
| `earningsnerd-logo-mono.svg` | Full lockup in `currentColor`, for print in one ink, embroidery and watermarks. One colour: the italic "Nerd" keeps its italic, not its colour. |
| `earningsnerd-logo-stacked-light.svg` | Stacked lockup, mark centred over the wordmark, one E-bar between, for light surfaces in square-ish placements: social avatars, the business card back, merch. |
| `earningsnerd-logo-stacked-dark.svg` | Stacked lockup for navy. |
| `earningsnerd-logo-stacked-mono.svg` | Stacked lockup in `currentColor`. |
| `earningsnerd-mask-icon.svg` | Safari pinned-tab mask: the mark letterboxed in a square, black on transparent (Safari recolours it; `app/layout.tsx` declares it with the sage colour). |
| `earningsnerd-mark-sage.png` | The sage mark rasterized at 256 px wide on transparent, byte-identical to the backend's Excel raster. Served at `/assets/earningsnerd-mark-sage.png` for transactional email, whose clients drop inline SVG; generated, never edited, and a published URL (see Rules). |

## In-app usage

Never inline the mark by hand — compose the components:

- `components/EarningsNerdLogoIcon.tsx` — the monogram in `currentColor`
  (`mode="auto"` = `text-brand-strong dark:text-brand-dark`). Single source of
  the geometry, kept in sync with `earningsnerd-mark-mono.svg`.
- `components/EarningsNerdLogo.tsx` — the ONE source of the two-tone wordmark:
  `variant="full"` (mark + wordmark; AuthShell), `"icon-only"` (Footer; Header
  below `sm`) or `"wordmark"` (Header at `sm`+, beside its icon-only mark).
  "Earnings" in the primary ink + italic "Nerd" in `text-brand-strong
  dark:text-brand-strong-dark`; size it with scale classes via
  `wordmarkClassName`. Never hand-compose the wordmark at a call site
  (gate: `tests/unit/wordmarkSingleSource.spec.ts`).

## Generated binaries

`npm run brand:assets` (see `scripts/generate-brand-assets.mjs`) regenerates the
committed binaries from this directory: `favicon.ico`, `apple-touch-icon.png`
(180, full-bleed — Apple applies its own corner mask), `icons/icon-{192,512}.png`
(+ `-maskable` full-bleed variants, mark at 0.62 for the r=40% safe zone), and
`og-image.png` (deterministic Playwright render with the committed Inter woff2), and the
sage mark raster in two places, `assets/earningsnerd-mark-sage.png` here and
`backend/app/assets/brand/earningsnerd-mark.png`.

## Rules

- **The mark and the wordmark do not change.** The paths in `earningsnerd-mark-mono.svg` and the
  wordmark rule ("Earnings" in the surface's primary ink, italic "Nerd" in the brand accent) are
  fixed by the founder (2026-10-11; `lessons/brand-the-mark-is-protected.md`). New renditions reuse
  the same paths and the same rule; nobody redraws a stroke, moves the arrowhead, re-spaces the
  wordmark or recolours the mark outside this table.
- Mark aspect ratio is 94.6:73.2 (~1.29:1) — never stretch; letterboxing in a
  square box is expected.
- **Clear space:** one E-bar on every side. The E's top bar is 11 units tall in the 94.6-unit
  viewBox, so the clear space is 11.6% of the mark's width (7 mm at 60 mm wide, 4 px at 36 px).
  Nothing else enters it: no text, no rule, no edge of a panel.
- **Minimum sizes.** Bare mark: 32 px on screen, 8 mm in print; below that the E and the N fuse,
  so use the self-backgrounded app tile (`earningsnerd-appicon.svg`), which reads down to 16 px on
  light and dark chrome. Horizontal lockup: 120 px wide on screen, 30 mm in print. Stacked lockup:
  64 px wide on screen, 16 mm in print. Embroidery: 60 mm wide and above (the thinnest stroke is
  about 6 mm there, the E's open counters 2.9 mm; the E and the N kiss, which a satin stitch joins
  and the mark survives). Evidence: `docs/brand/05-mark.md`.
- **Published URLs stay put.** `/assets/earningsnerd-mark-sage.png` is the mark's address in
  transactional email, and a sent message keeps its image addresses for as long as it is kept, so
  the file stays at that path for good: never rename, move or remove it, and keep it the sage mark
  (regenerating it from the same source is fine). A new rendition takes a new name. Gate:
  `frontend/tests/unit/publishedAssetUrls.spec.ts`, which lists every published path.
- **Where it goes.** The mark sits top-left on every surface the brand owns (the site header, the
  OG card, the PDF masthead, the email shell, the business card front); the stacked lockup is for
  square placements; never centre the horizontal lockup as a hero.
- **Misuse.** Never on a photograph, never recoloured outside this table, never with a drop shadow,
  outline or gradient, never rotated, never with the arrow pointing anywhere but up-right, never
  beside a competitor's mark at a different size.
- Brand accents only: sage as identity, never in a numeric/price context
  (gain/loss colors carry data meaning — see DESIGN_SYSTEM.md).
- The wordmark's "Nerd" is always italic in the brand accent; "Earnings" is
  always the surface's primary ink.
