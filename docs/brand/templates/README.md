# Brand templates

Applications of the system in [06-system.md](../06-system.md): the lockup, the tokens and the one
device (the margin and the mark). Each file carries a comment at the top with its measurements and
the reasoning behind them. Fonts are the committed Inter variable and Geist Mono under
`frontend/scripts/brand/fonts/` (OFL); no file in this folder links outside the repository.

| File | Format · file size | Use | Where the real thing renders | Fonts |
|---|---|---|---|---|
| `social-post-1080x1350.html` | 1080 × 1350 px · 6.2 KB | Source of the social post: one verified figure, its source line, the margin with `[F1]` on the marker's line, the tagline with the highlight | Nowhere yet; the 1200 × 630 sibling is `frontend/scripts/brand/og-template.html` (the og-image) | `@font-face`, relative: Inter variable, Geist Mono |
| `social-post-1080x1350.png` | 1080 × 1350 px · 82.4 KB | The render to post (PNG, under the 400 KB cap) | n/a | rendered with the committed files |
| `business-card-front.svg` | 85 × 55 mm + 3 mm bleed (91 × 61 mm) · 4.1 KB | Card front: horizontal lockup top-left on cream, the tagline with the highlight under "shows its work", the address, fill-in name and role | Print only | Inter, Geist Mono by family name (see Print) |
| `business-card-back.svg` | 85 × 55 mm + 3 mm bleed (91 × 61 mm) · 2.9 KB | Card back: navy, stacked lockup in its dark colours centred, tagline beneath | Print only | Inter by family name |
| `pdf-cover.html` | A4 portrait, 210 × 297 mm · 7.2 KB | Cover page for the filing summary PDF: lockup, "Filing summary", the filing identity, the marked headline, the tally line with named fields | `backend/app/services/pdf_branding.py` (`render_branded_pdf`, the page-1 masthead) on the shell that `backend/app/services/export_service.py` (`generate_pdf_html`) builds | `@font-face`, relative: Inter variable, Geist Mono |
| `email-header.html` | fluid to 600 px, with Outlook's 600 px tables; table layout, inline styles · 11.6 KB | Header block (lockup, hairline, marked tagline) and footer line for transactional email | `backend/app/services/email_service.py`, `_wrap_html` | Inline stacks led by Inter; `@font-face` (Inter, upright and italic) for the preview and its reflow check (`frontend/tests/e2e/mail-header-reflow.spec.ts`) only |
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
  system monospace; the highlight is drawn for Inter's metrics, and the marked phrase carries a
  `textLength` so its width still matches the highlight under a substitute.
- **Sizes.** Nothing under 7 pt. The mark's clear space (one E-bar, 11.6% of its width) is kept
  on every side; each file's comment states the measurement. The device's hairline is 0.3 mm.
- **Layers.** Groups are named for Inkscape (`inkscape:groupmode="layer"`) and import as groups
  elsewhere: `artwork`, `fill-in`, `trim-guide`.

## Notes

- **The highlight in HTML** is two nested spans, not `.en-mark`'s background: the outer span's
  own font box is sized to the lower 38% of the line box and lowered onto it, its bottom border is
  the hairline, and the inner span restores the ink. It matches `.en-mark` to the pixel in
  Chromium and, unlike a positioned box, also renders in WeasyPrint 70 (the backend's PDF engine,
  checked for this folder). It needs only inline backgrounds, borders and `vertical-align`, which
  mail clients support; it has not been tested in a mail client. The formula is in each file's
  comment.
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
