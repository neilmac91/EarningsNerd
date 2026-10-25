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
| text-primary-dark | `#EAECEF` | 15.91 | 12.40 | 12.74 |
| text-secondary-dark | `#D1D5DB` | 12.78 | 9.96 | 10.23 |
| text-tertiary-dark | `#9CA3AF` | 7.42 | 5.78 | 5.94 |
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
in the wordmark is Inter. Promotional claim emphasis uses Inter's genuine italic at 600, locally
loaded by `BrandEmphasis.tsx` on the web and by a separate `Inter Claim` face in the current
OG, social and PDF-cover templates, not Newsreader. Email uses the client's italic fallback when
the committed face is unavailable. This scopes the change to the claim; root font definitions
and the broader wordmark/font work remain unchanged (§6).

Inside the product Newsreader sets the filing reader and the passages the server located, each in
its marked block: the filing page's Risks rows and the summary's located quotes (D-044). A summary,
an answer, a heading, a speaker's name or a label of ours never takes it
(`frontend/tests/unit/designSystemDoneGate.spec.ts` names the surfaces).

## 3. Spacing, radius, elevation

As they stand: Tailwind's base scale with the 18, 52, 72 px and 24 px gutter additions; radii
4 / 8 / 12 / 16 / 24 with pills for chips; elevation e1 to e5 in light and fill-plus-hairline in
dark; the stacking ladder sticky 30 · consent 32 · scrim 35 · header 50 · popover 60 · modal 70 ·
toast 80. No additions. Source annotations have no radius or shadow; promotional emphasis uses
the existing 8px radius (§6). The marked block's bar sits on
square corners, because a stripe never sits on a rounded container (DESIGN.md, the side-tab
stripe).

## 4. Icons

Phosphor, through `lib/icons`, at 16 px in chips and 20 px in controls, `currentColor`, never
filled duotone. Three glyphs carry meaning and are reserved: the quotes glyph marks a filing
passage, the curly braces mark an XBRL fact, and the sparkle appears only on the AI summary chip
(the "Full summary" badge and the generation card). No other glyph may use them, and no decorative
icon tiles on the public pages: the three how-it-works tiles keep their icons because each names an
action (search, pick, summarise); the "Also in Pro" extras, a ruled list since the landing's rows
(D-045), carry none and name their file kinds and forms as text in the data face. A section heading
never gets an icon.

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

**The source mark** is a highlight inside or beside a located passage: pale sage (`brand-weak`) from 62%
of the line box down, with a `brand-border` hairline at the baseline (`.en-mark` in
`frontend/app/globals.css`). In dark it is the dark sage tint with the dark hairline. On a block,
it is a 3 px `brand` bar on the left edge with the tint behind (`.en-marked`). A promotional phrase
uses the separate C5 emphasis below; it does not claim that those words were located in a filing.

**The margin** is a gutter of fixed width with a `brand-border` rule on its inner edge, holding
bracketed marks (`[F1]`, `[1]`) in the data face at 11 px, `brand-strong` ink, each positioned on
the line of the marker it twins (`.en-margin`, `.en-margin-mark`). The twin is decorative
(`aria-hidden`), and assistive tech skips the in-text marker too. The in-text marker is the
product's own citation marker: the data face, semibold, in brackets, at the provenance chip's 12 px
(`EnRef` in `frontend/components/ui/MarkedCopy.tsx`). Its number points at a twin assistive tech
never reaches, and the chip beside the passage carries the claim, so a heading's name is its words
alone.

Rules:

- **Scale.** The source mark's hairline is 2 px on screen at every size, 0.3 mm in print; its highlight
  never exceeds 38% of the line box. Promotional emphasis instead fills the phrase's enclosure. The margin is
  44 px on desktop and 36 px on phones; in print it is 12 mm on A4 and 6 mm on a card. The in-text marker is never smaller than the provenance
  chip (12 px); its twin is 11 px, the one sub-12 px text beside copy, because it repeats a marker
  the reader already has; 7 pt in print. The gutter and its twins show at every width at the default
  text size; below a measure (a marked copy narrower than 13em at the reader's text size, as on a phone
  under 200% text) they give way, and the marker stays in its heading.
- **Placement.** C5 emphasis encloses one phrase of ours per surface (the hero's accent phrase, the
  social card's promise); the source mark locates a passage, and the margin goes on the left of a marked copy
  surface only. On a public page that is one passage. Inside the product the device marks every
  passage the server located, because there it is literal (D-044): the filing page's Risks section
  is a marked copy (a marker on each located row's heading, its twin in the margin, the excerpt a
  marked block; a row not located keeps the plain quotation and no marker), a quote in the summary
  whose evidence the server located takes the marked block alone (no marker and no twin: a quote has
  no heading to carry one; any other quote keeps the neutral hairline), and the Source pane paints
  a passage the server located with the mark's tint and its 2 px hairline (a jump it did not locate,
  a summary chip's section heading or an XBRL fact's, lands in the reader's neutral sage find
  highlight, with no hairline). One marker per row, so
  the twins never overprint; the one-highlight limit stays for a phrase of ours. Ask this Filing's
  answers and the Multi-Period narrative keep their citation chips: a cited line carries several
  markers, and their twins would overprint. Never both marks on a headline, never a mark on a figure
  (sage never colours a number: the Separate Signals Rule), never a margin without at least one
  marker in the text. The two forms stay apart: a located passage set as a block (a Risks excerpt, a
  located quote) takes the marked block, a located passage inside running text (the Source pane's)
  takes the tint and hairline, nothing unlocated takes either, and inside the product only the Risks
  rows carry a marker and its twin. `frontend/tests/unit/brandCopyRules.spec.ts` rule 3 holds the
  places.
- **Colour.** Light: tint `#ECF2EE`, hairline `#CFE0D6`, bar `#4F7A63`, marks `#3C6650`. Dark: tint
  `rgba(127,178,149,0.14)`, hairline `rgba(127,178,149,0.28)`, bar `#7FB295`, marks `#98C5AD`. The
  tint is a surface, never a fill for text; measured, the hairline reads 1.24:1 on cream and the
  tint 1.02:1, which is the point: the device is quiet, and the ink on it (15.4:1 light, 12.7:1
  dark) carries the words. The words on the tint are the primary ink: in the Source pane the
  reader's secondary ink was 4.49:1 on the dark tint over the slate panel while it was gray-400, so
  the located passage takes the primary ink there (9.6:1); the secondary ink is gray-300 since
  2026-10-25 (7.7:1 there), and the passage keeps the primary ink, the device's words.
- **Promotional emphasis (C5).** Every homepage headline variant, the auth-shell promise and the
  waitlist headline use `BrandEmphasis`: a full Bright Sage (`brand-strong-dark`, `#98C5AD`) fill
  in both themes, 8px corners and genuine Inter italic 600. Light uses opaque espresso (`#1A1A17`,
  9.07:1 on the fill); dark uses navy (`#0B1120`) at 90%. There is no hairline or shadow. The phrase
  stays together when it fits and wraps at a word boundary if enlarged text makes it wider than
  its container. The current OG/social, mail, card-front and PDF-cover prototype carry the same
  full fill and crisp light ink, with output-specific mechanics described in
  [templates/README.md](templates/README.md). The fixed-size OG/social/PDF templates use a filled
  inline block; the card uses a rounded rectangle scaled for print. Email retains a plain-text
  fallback for classic Outlook and cannot guarantee a downloaded font. The web's reflow-safe
  paint, proportional padding and local font loading are specified in
  `frontend/DESIGN_SYSTEM.md` §7. This is decorative emphasis, not a control or a source annotation;
  the reader's located passages retain their tint and hairline. Historical audit/direction images
  remain records of the earlier treatment.
- **Meaning.** A mark means "located in the filing" and a bracket means "cited". A highlight on a
  phrase we wrote is allowed once per surface, as the brand's signature; it is never put on an
  unverified claim, a number, a price or a competitor's name.
- **Misuse.** No mark on a figure; no margin as decoration; no mark in gain, loss, warning or any
  status colour. Keep promotional phrases short and together where they fit; a narrower measure or
  wider browser font metrics may wrap at a word boundary, as may a reader's enlarged text, rather
  than push the page sideways. The B headline at 320px in WebKit is one such default-size case;
  Chromium's current default-size phrases remain on one line. `BrandEmphasis` and the mail's tagline
  permit those wraps (D-048). No mark on a photograph; no scaling a source hairline with the type.

Specification in code: `frontend/app/globals.css` ("Brand device") and
`frontend/components/ui/MarkedCopy.tsx` (the margin and the marker), consumed by
`frontend/features/marketing/components/*` on the landing page,
`frontend/features/summaries/components/SummaryRisks.tsx`, `SummaryBlocks.tsx` (the located
quotes) and the Source pane's highlight
(`frontend/features/filings/components/copilot/highlightInDom.ts`) on the filing page,
`frontend/scripts/brand/og-template.html` on the social card, and the templates under
[templates/](templates/).
