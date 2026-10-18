# The system (2026-10-11)

Phase 6 of the brand studio brief. The identity is built with the tokens the product already
defines; this phase adds no colour and no type role. It adds one graphic device (the margin and
the mark), writes the rules that were missing (icons, imagery, the device), and records the
measurements. The normative sources are unchanged: `frontend/tailwind.config.js` and
`frontend/app/globals.css` define, `DESIGN.md` and `frontend/DESIGN_SYSTEM.md` describe,
`.impeccable/design.json` previews. This page is the brand's reading of them, with evidence.

## 1. Palette, measured

WCAG contrast ratios computed for this page (relative luminance, sRGB) against the light grounds
(cream `#F4F3EE`, panel `#FBFAF6`, the pale sage tint `#ECF2EE`) and the dark grounds (navy
`#0B1120`, slate panel `#1F2937`, the dark sage tint, which is `#7FB295` at 14% over navy). Text needs
4.5:1; meaningful graphics 3:1.

| Light token | hex | on cream | on panel | in pale sage tint |
|---|---|---|---|---|
| text-primary | `#1A1A17` | 15.70 | 16.70 | 15.37 |
| text-secondary | `#374151` | 9.28 | 9.87 | 9.08 |
| text-tertiary | `#636A77` | 4.90 | 5.21 | 4.80 |
| brand (fill only) | `#4F7A63` | 4.40 | 4.68 | 4.31 |
| brand-strong (text) | `#3C6650` | 5.89 | 6.27 | 5.77 |
| brand-emphasis | `#345C48` | 6.82 | 7.26 | 6.68 |
| gain-text | `#15803D` | 4.51 | 4.80 | 4.42 |
| gain-light (graphic only) | `#16A34A` | 2.97 | 3.16 | 2.90 |
| loss-text | `#B91C1C` | 5.82 | 6.19 | 5.70 |
| loss-light (graphic only) | `#DC2626` | 4.35 | 4.62 | 4.25 |
| flat | `#6B7280` | 4.35 | 4.63 | 4.26 |
| success | `#15803D` | 4.51 | 4.80 | 4.42 |
| warning | `#92400E` | 6.38 | 6.79 | 6.25 |
| error | `#B91C1C` | 5.82 | 6.19 | 5.70 |
| info | `#2563EB` | 4.65 | 4.95 | 4.55 |
| info-text | `#1D4ED8` | 6.03 | 6.42 | 5.90 |
| chart-1 … chart-6 | teal, honey, cornflower, coral, slate blue, periwinkle | 3.50, 3.04, 3.71, 3.07, 3.69, 3.32 | 3.72, 3.23, 3.95, 3.26, 3.92, 3.53 | 3.42, 2.97, 3.64, 3.00, 3.61, 3.25 |

| Dark token | hex | on navy | on slate panel | in dark sage tint |
|---|---|---|---|---|
| text-primary-dark | `#D7DADC` | 13.41 | 10.45 | 10.73 |
| text-secondary-dark | `#9CA3AF` | 7.42 | 5.78 | 5.94 |
| brand-dark (fill and accent) | `#7FB295` | 7.80 | 6.08 | 6.25 |
| brand-strong-dark (text) | `#98C5AD` | 9.80 | 7.64 | 7.84 |
| brand-fill-dark | `#569272` | 5.16 | 4.02 | 4.13 |
| gain-dark | `#34D399` | 9.79 | 7.64 | 7.84 |
| loss-dark | `#FB7185` | 7.00 | 5.45 | 5.60 |
| success / warning / error / info (dark) | `#22C55E` `#F59E0B` `#F87171` `#60A5FA` | 8.26, 8.77, 6.81, 7.41 | 6.44, 6.83, 5.31, 5.77 | 6.62, 7.02, 5.45, 5.93 |
| chart-1 … chart-6 | same hexes | 4.85, 5.58, 4.56, 5.52, 4.60, 5.10 | 3.78, 4.35, 3.56, 4.31, 3.58, 3.98 | 3.88, 4.47, 3.65, 4.42, 3.68, 4.09 |

What the tables settle: every text token clears 4.5:1 on every ground it is allowed on; the two
light graphic tokens (`gain-light`, `brand` as fill) stay graphic; `chart-2` and `chart-4` sit at the
3:1 floor inside the pale tint, so charts stay on panel or cream, never inside a tint; the device's
own colours (below) are hairlines and tints and are never asked to carry text.

**No token changes are proposed.** The §12 done-gate therefore needs no re-run for colour; the
grep is run anyway with the frontend gate.

## 2. Type

The three roles stand (DESIGN.md "Typography"): Inter 600 for headings with the tracking ramp,
system-first body, Geist Mono with tabular figures for data, evidence and Ask answers, Newsreader
only for the filing's own words. Direction B adds no role.

One clarification for the public pages, so the Source Voice Rule holds there as it does in the
product: Newsreader may appear on a marketing surface only inside a quoted passage that the
product located in a filing (the hero example's evidence row, the social card's excerpt), set in
quotation marks, never for a headline, a tagline, an aside or a claim of ours. The italic "Nerd"
in the wordmark is Inter, and stays the brand's only typographic flourish.

Inside the product Newsreader sets the filing reader and the passages the server located, each in
its marked block: the filing page's Risks rows and the summary's located quotes (D-044). A summary,
an answer, a heading, a speaker's name or a label of ours never takes it
(`frontend/tests/unit/designSystemDoneGate.spec.ts` names the surfaces).

## 3. Spacing, radius, elevation

As they stand: Tailwind's base scale with the 18, 52, 72 px and 24 px gutter additions; radii
4 / 8 / 12 / 16 / 24 with pills for chips; elevation e1 to e5 in light and fill-plus-hairline in
dark; the stacking ladder sticky 30 · consent 32 · scrim 35 · header 50 · popover 60 · modal 70 ·
toast 80. No additions. The device has no radius and no shadow: the marked block's bar sits on
square corners, because a stripe never sits on a rounded container (DESIGN.md, the side-tab
stripe).

## 4. Icons

Phosphor, through `lib/icons`, at 16 px in chips and 20 px in controls, `currentColor`, never
filled duotone. Three glyphs carry meaning and are reserved: the quotes glyph marks a filing
passage, the curly braces mark an XBRL fact, and the sparkle appears only on the AI summary chip
(the "Full summary" badge and the generation card). No other glyph may use them, and no decorative
icon tiles on the public pages: the three how-it-works tiles keep their icons because each names an
action (search, pick, summarise); the "Also in Pro" tiles keep theirs because each names a file
kind. A section heading never gets an icon.

## 5. Imagery

The brand uses no photography and no illustration. Its images are typographic and data images:
the filing's identity line, a figure with its fact, a quoted passage with its mark, a tally. A
product screen is shown only as the real component fed verified data (the landing page's rule
since the October redesign), never as a mockup, a stock render or a device frame. If a surface
needs an image and has none of these, it has no image. Should illustration ever enter (a
notebook cover, a conference banner), it is one style, line-drawn in one weight in the brand ink,
drawn by one hand, and approved by the founder; nothing enters without that approval.

## 6. The graphic device: the margin and the mark

The one element that makes a surface recognisable without the logo. It is the product's own
behaviour made visible: a located passage is highlighted, a cited figure carries a bracketed
marker, and the marker's twin sits in a margin beside the line it belongs to.

**The mark** is a highlight under a phrase or beside a passage: pale sage (`brand-weak`) from 62%
of the line box down, with a `brand-border` hairline at the baseline (`.en-mark` in
`frontend/app/globals.css`). In dark it is the dark sage tint with the dark hairline. On a block,
it is a 3 px `brand` bar on the left edge with the tint behind (`.en-marked`).

**The margin** is a gutter of fixed width with a `brand-border` rule on its inner edge, holding
bracketed marks (`[F1]`, `[1]`) in the data face at 11 px, `brand-strong` ink, each positioned on
the line of the marker it twins (`.en-margin`, `.en-margin-mark`). The twin is decorative
(`aria-hidden`). The in-text marker is the product's own citation marker and the accessible one:
the data face, semibold, in brackets, at the provenance chip's 12 px (`EnRef` in
`frontend/components/ui/MarkedCopy.tsx`).

Rules:

- **Scale.** The mark's hairline is 2 px on screen at every size, 0.3 mm in print; the highlight
  never exceeds 38% of the line box. The margin is 44 px on desktop and 36 px on phones; in print
  it is 12 mm on A4 and 6 mm on a card. The in-text marker is never smaller than the provenance
  chip (12 px); its twin is 11 px, the one sub-12 px text beside copy, because it repeats a marker
  the reader already has; 7 pt in print. The gutter and its twins show at every width.
- **Placement.** The mark goes under one phrase of ours per surface (the hero's accent phrase, the
  social card's promise) or beside a located passage; the margin goes on the left of a marked copy
  surface only. On a public page that is one passage. Inside the product the device marks every
  passage the server located, because there it is literal (D-044): the filing page's Risks section
  is a marked copy (a marker on each located row's heading, its twin in the margin, the excerpt a
  marked block; a row not located keeps the plain quotation and no marker), a quote in the summary
  whose evidence the server located takes the marked block alone (no marker and no twin: a quote has
  no heading to carry one; any other quote keeps the neutral hairline), and the Source pane paints
  the passage it locates with the mark's tint and its 2 px hairline. One marker per row, so
  the twins never overprint; the one-highlight limit stays for a phrase of ours. Ask this Filing's
  answers and the Multi-Period narrative keep their citation chips: a cited line carries several
  markers, and their twins would overprint. Never both marks on a headline, never a mark on a figure
  (sage never colours a number: the Separate Signals Rule), never a margin without at least one
  marker in the text. `frontend/tests/unit/brandCopyRules.spec.ts` rule 3 holds the places.
- **Colour.** Light: tint `#ECF2EE`, hairline `#CFE0D6`, bar `#4F7A63`, marks `#3C6650`. Dark: tint
  `rgba(127,178,149,0.14)`, hairline `rgba(127,178,149,0.28)`, bar `#7FB295`, marks `#98C5AD`. The
  tint is a surface, never a fill for text; measured, the hairline reads 1.24:1 on cream and the
  tint 1.02:1, which is the point: the device is quiet, and the ink on it (15.4:1 light, 10.7:1
  dark) carries the words. The words on the tint are the primary ink: in the Source pane the
  reader's secondary ink would be 4.49:1 on the dark tint over the slate panel, so the located
  passage takes the primary ink there (8.1:1).
- **Meaning.** A mark means "located in the filing" and a bracket means "cited". A highlight on a
  phrase we wrote is allowed once per surface, as the brand's signature; it is never put on an
  unverified claim, a number, a price or a competitor's name.
- **Misuse.** No mark on a figure; no margin as decoration; no mark in gain, loss, warning or any
  status colour; no mark across more than one line of a headline at phone width (the highlight
  breaks per line, so keep the phrase short); no mark on a photograph; no scaling the hairline with
  the type.

Specification in code: `frontend/app/globals.css` ("Brand device") and
`frontend/components/ui/MarkedCopy.tsx` (the margin and the marker), consumed by
`frontend/features/marketing/components/*` on the landing page,
`frontend/features/summaries/components/SummaryRisks.tsx` and the Source pane's highlight
(`frontend/features/filings/components/copilot/highlightInDom.ts`) on the filing page,
`frontend/scripts/brand/og-template.html` on the social card, and the templates under
[templates/](templates/).
