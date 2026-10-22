# Brand templates

Applications of the system in [06-system.md](../06-system.md): the lockup, the tokens and the one
device (the margin and the mark). Each file carries a comment at the top with its measurements and
the reasoning behind them. Fonts are the committed Inter variable and Geist Mono under
`frontend/scripts/brand/fonts/` (OFL); no file in this folder links outside the repository.

| File | Format · file size | Use | Where the real thing renders | Fonts |
|---|---|---|---|---|
| `social-post-1080x1350.html` | 1080 × 1350 px · 6.5 KB | Source of the social post: one verified figure, its source line, the margin with `[F1]` on the marker's line, the tagline with C5 emphasis | Nowhere yet; the 1200 × 630 sibling is `frontend/scripts/brand/og-template.html` (the og-image) | `@font-face`, relative: Inter variable, scoped Inter Claim italic 600, Geist Mono |
| `social-post-1080x1350.png` | 1080 × 1350 px · 84.0 KB | The render to post (PNG, under the 400 KB cap) | n/a | rendered with the committed files |
| `business-card-front.svg` | 85 × 55 mm + 3 mm bleed (91 × 61 mm) · 4.7 KB | Card front: horizontal lockup top-left on cream, C5 emphasis around "shows its work", the address, fill-in name and role | Print only | Inter, Geist Mono by family name; scoped Inter Claim for browser proof (see Print) |
| `business-card-back.svg` | 85 × 55 mm + 3 mm bleed (91 × 61 mm) · 2.9 KB | Card back: navy, stacked lockup in its dark colours centred, tagline beneath | Print only | Inter by family name |
| `pdf-cover.html` | A4 portrait, 210 × 297 mm · 7.7 KB | Proposed cover: lockup, "Filing summary", filing identity, C5 headline, tally line with named fields | Standalone prototype, not included by the runtime PDF exporter. The existing `backend/app/services/pdf_branding.py` page-1 masthead has no promotional tagline | `@font-face`, relative: Inter variable, scoped Inter Claim italic 600, Geist Mono |
| `email-header.html` | fluid to 600 px, with Outlook's 600 px tables; table layout, inline styles · 12.0 KB | Header block (lockup, separator, C5 tagline) and footer line for transactional email | `backend/app/services/email_service.py`, `_wrap_html` | Inline stacks led by Inter; `@font-face` (Inter, upright and italic) for the preview and its reflow check (`frontend/tests/e2e/mail-header-reflow.spec.ts`) only |
| `merch-notebook-cover.svg` | A5, 148 × 210 mm · 2.9 KB | Notebook cover: italic "Nerd" large in sage, the margin as a printed rule 18 mm from the left edge, stacked lockup at the foot | Print only | Inter by family name (see Print) |
| `merch-notebook-cover.png` | 740 × 1050 px | Preview of the notebook cover | n/a | rendered with the committed Inter |

## Figure provenance

Every figure in this folder is from Apple Inc.'s 10-K for FY2025 (accession 0000320193-25-000079,
filed Oct 31, 2025), verified against SEC XBRL: total net sales $416,161M vs FY2024 $391,035M, +6.4%
(`us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`). Source line as printed:
"{ } Revenue · SEC XBRL" with "Apple Inc. · 10-K · FY2025 · filed Oct 31, 2025". The PDF cover's
identity block shows the same filing; its tally counts are named fields (`{matched}`,
`{checkable}`, `{located}`, `{excerpts}`) because no verified count exists to print, and the
cover's comment says how the backend fills them.

## Print (the SVG files)

- **Trim guide.** Each card file has a group `id="trim-guide"` holding a dashed rectangle at the
  cut (3 mm in from every edge). It is for proofing; the printer removes or hides that group
  before output. Everything outside it is bleed: the ground runs to the file's edge.
- **Fill-in.** The card front's group `id="fill-in"` holds the words "Name" and "Role" as labels.
  Replace them with the cardholder's own before print; no person is named in this file.
- **Fonts.** Text is live, set with `font-family="Inter, 'Helvetica Neue', Arial, sans-serif"`
  and `"'Geist Mono', ui-monospace, Menlo, monospace"`. Install Inter (rsms.me/inter) and
  Geist Mono (github.com/vercel/geist-font) as desktop fonts, then convert text to outlines
  before sending to print. Without them the printer substitutes Helvetica Neue or Arial and a
  system monospace; the claim's `Inter Claim` alias uses the committed genuine italic in a browser
  proof and falls back to installed Inter italic in a desktop editor. The fill is drawn for Inter's
  metrics, and the marked phrase carries a `textLength` so its width stays fixed. Confirm the real
  italic face before outlining; a substitute is not a print proof of the approved typography.
- **Sizes.** Nothing under 7 pt. The mark's clear space (one E-bar, 11.6% of its width) is kept
  on every side; each file's comment states the measurement. A source annotation's hairline is
  0.3 mm; C5 claim emphasis has no hairline. The card's 0.706 mm corners scale the web's 8px radius
  at 36px type to its 9pt tagline; its horizontal padding is 0.18em (0.5715 mm).
- **Layers.** Groups are named for Inkscape (`inkscape:groupmode="layer"`) and import as groups
  elsewhere: `artwork`, `fill-in`, `trim-guide`.

## Notes

- **C5 claim emphasis** uses solid Bright Sage `#98C5AD`, opaque espresso `#1A1A17` (9.07:1),
  genuine Inter italic 600 and soft corners, without a hairline or shadow. OG and social use a
  filled inline block: line-height `0.9`, padding `calc(0.04em - 1px) 0.18em 0.06em`, 8px corners,
  leading margin `-0.1em` and zero trailing margin so the full stop stays clear of the fill. Their
  separately named italic face leaves the wordmark unchanged. The fixed canvases keep the phrase
  whole. The PDF prototype converts these values to points and uses an inline block, avoiding
  WeasyPrint's positioned-inline limitation; its claim face declares weight 600 rather than an
  unsupported variable range. The web's reflow-safe paint remains in `BrandEmphasis` and
  `frontend/app/globals.css`; source passages keep their separate tint/hairline treatment.
- **Email adapts the same appearance to client CSS.** An outer inline block groups the phrase and
  full stop; its inner inline span has italic 600, the same solid fill and ink, 8px corners,
  `0.04em 0.18em 0.06em` padding, and `box-decoration-break: clone` (including the WebKit prefix).
  At enlarged text it wraps into filled fragments. The preview loads genuine Inter italic;
  sent mail downloads no font and uses the client's sans-serif italic, which may be synthesized.
  Classic Outlook retains a plain-phrase conditional fallback. Clients ignoring decoration
  cloning may join the middle corners. Browser reflow and template/runtime parity are checked;
  actual inbox rendering, automatic dark mode and font availability remain unverified. No test
  email was sent.
- **One highlight per surface, never on a number.** The social post marks the tagline, not the
  figure; the figure stays in the ink, and sage ink appears only on the brackets, the chip and
  the wordmark.
- **The notebook's margin** is the rule alone. Bracket marks are twins of markers in text
  (06-system.md §6), and a cover carries no text to twin, so none are printed; the owner's own
  marks go beside the rule.
- **The email footer line** names filing data: "Filing data sourced from SEC EDGAR. Not investment
  advice." It sits on every mail, and an earnings-day alert carries a provider's report dates, so it
  narrows the app's sentence form, `SEC_EDGAR_NOT_ADVICE` in `frontend/components/AiDisclaimer.tsx`,
  which labels the Copilot's filing answers alone (D-017, D-043).

## Rendering

Playwright, as `frontend/scripts/generate-brand-assets.mjs` uses it (run from `frontend/`):

```js
// social-post-1080x1350.png
import { chromium } from 'playwright'
const T = new URL('../docs/brand/templates/', `file://${process.cwd()}/`)
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1080, height: 1350 }, deviceScaleFactor: 1 })
await page.goto(new URL('social-post-1080x1350.html', T).href)
await page.evaluate(() => document.fonts.ready)
await page.screenshot({ path: new URL('social-post-1080x1350.png', T).pathname })
await browser.close()
```

For `merch-notebook-cover.png`, place the SVG's markup inline in a page 740 × 1050 px with the
`svg` element sized to fill it and an `@font-face` for Inter pointing at
`frontend/scripts/brand/fonts/Inter-Variable-latin.woff2` (an SVG loaded as an image cannot reach
web fonts), wait for `document.fonts.ready`, and screenshot at the same viewport. `pdf-cover.html`
prints to a single A4 page from Chromium (`page.pdf({ preferCSSPageSize: true, printBackground:
true })`) and from WeasyPrint.

Render the OG template alone at 1200 × 630 with device scale factor 2, wait for fonts, then resize
the screenshot to 1200 × 630 with Sharp, matching the OG step in `generate-brand-assets.mjs`.
The result is `frontend/public/og-image.png`, shared through `lib/socialCard.ts` at `?v=6`.
Do not rerun the entire asset generator for a claim-only update: published mail-logo URLs are
immutable. A local HTTP server may replace `file://` when browser policy blocks local files.

The C5 exports were checked in Chromium with fonts loaded and the claim resolving to the committed
`Inter-Italic` face. The PDF prototype was also rendered with WeasyPrint 70: one A4 page with an
embedded `Inter-Claim-Semi-Bold-Italic` font. Its existing variable-range and optical-sizing warnings
do not affect that separately declared face; WeasyPrint also ignores `font-synthesis`, so the
embedded font was checked directly. SVG proofing used inline markup and committed font faces;
final outlined printer output still needs a physical proof. Historical direction/audit images
and the unmarked notebook/card-back stay unchanged.
