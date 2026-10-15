# EarningsNerd Brand Assets

The sage "EN" monogram set (July 2026 rebrand — replaces the legacy teal/amber mark).
The mark is the letters **E + N** with the N's final stroke rising into an arrow.

## Renditions

| File | Use |
|------|-----|
| `earningsnerd-appicon.svg` | The app tile: sage `#4F7A63` squircle + cream mark. Source for favicon.ico, PWA icons, the SVG favicon and `earningsnerd-appicon.png` (self-backgrounded — legible on light AND dark tab chrome). |
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
| `earningsnerd-mark-sage.png` | The sage mark rasterized at 256 px wide on transparent, byte-identical to the backend's Excel raster. Served at `/assets/earningsnerd-mark-sage.png`: first offered as the mail header's mark, kept at its URL since the header took the tile (D-035), though no mail references it; generated, never edited, and held to the published-URL rule (see Rules). |
| `earningsnerd-appicon.png` | The app tile rasterized at 128 px square, transparent outside the squircle. Served at `/assets/earningsnerd-appicon.png` for the transactional mail header, which shows it at 32 px beside the text wordmark: mail clients drop inline SVG, and the apps that darken a message leave its images alone, so the mark comes on its own ground; generated, never edited, and a published URL (see Rules). |

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
(+ `-maskable` full-bleed variants, mark at 0.62 for the r=40% safe zone),
`og-image.png` (deterministic Playwright render with the committed Inter woff2),
`assets/earningsnerd-appicon.png` (the tile at 128 px, served at a fixed URL for the mail header),
and the sage mark raster, written twice from one buffer: `assets/earningsnerd-mark-sage.png`
(served at a fixed URL) and `backend/app/assets/brand/earningsnerd-mark.png` (embedded in the
Excel export).

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
- **Published URLs stay put.** A path that sent mail references is published: a message keeps its
  image addresses for as long as it is kept, and nobody can edit it after sending. The register,
  `frontend/tests/unit/publishedAssetUrls.json`, names the origin mail addresses these paths on and
  holds two paths: `/assets/earningsnerd-appicon.png`, the app tile in the transactional mail header
  (`backend/app/services/email_service.py`, `_wrap_html`), and `/assets/earningsnerd-mark-sage.png`,
  the bare mark's raster, first offered as the header's mark and kept at its URL when the header
  took the tile (D-035); no mail references it, and the rule holds it all the same. Each file stays
  at its path for good and stays served: never rename, move, remove or replace it, never redirect or
  rewrite its path, and keep it the same image, byte for byte (regenerating it is fine while it
  comes back identical); a new rendition takes a new name. Mail addresses these paths on the origin
  that answers without a redirect (`https://www.earningsnerd.io`), so that origin keeps serving them
  without one. A change that puts a new path in mail adds it to the register in the same PR. Gates:
  `frontend/tests/unit/publishedAssetUrls.spec.ts` checks that each registered file is present and
  is the file that was published (its sha256), that it lies outside `middleware.ts`'s matcher (which
  leaves out `/assets/`), so the middleware never runs on it, and that no redirect, rewrite or
  basePath in `next.config.js` or `vercel.json` reaches it, read in a production build's
  environment; that no path leaves the register; and that the register's origin is the root
  layout's `metadataBase`. `backend/tests/unit/test_mail_published_assets.py` holds the backend to
  the rule: a string in `backend/app`, read as the code builds it, that addresses a file the site
  serves from `frontend/public` spells a whole registered path, with nothing filled in after it and
  no origin of the site's, second slash or unstripped `FRONTEND_URL` in front of it; a registered
  path is used whole, never changed or handed on; the header's tile is built on `FRONTEND_URL` with
  any trailing slash stripped; and `FRONTEND_URL`'s default is the register's origin. Its header
  names the forms it cannot see (a path after a placeholder that holds another origin, one written
  without its leading slash or after a bare word, an address a function hands back that its caller
  changes, one a route serves). Whether the origin answers without a
  redirect, the response headers a route or a headers rule sets on these paths (a Content-Type that
  stops a mail client showing the image), and anything set only in the Vercel dashboard (a variable
  a rule reads, or a redirect) are review-checked.
- **Where it goes.** The mark sits top-left on every surface the brand owns (the site header, the
  OG card, the PDF masthead, the email shell, the business card front); the email shell carries it
  as the app tile, which brings its own ground into mail apps that darken a message; the stacked
  lockup is for square placements; never centre the horizontal lockup as a hero.
- **Misuse.** Never on a photograph, never recoloured outside this table, never with a drop shadow,
  outline or gradient, never rotated, never with the arrow pointing anywhere but up-right, never
  beside a competitor's mark at a different size.
- Brand accents only: sage as identity, never in a numeric/price context
  (gain/loss colors carry data meaning — see DESIGN_SYSTEM.md).
- The wordmark's "Nerd" is always italic in the brand accent; "Earnings" is
  always the surface's primary ink.
