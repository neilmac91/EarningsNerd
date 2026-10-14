# Phase 8: the applications

The system from [06-system.md](06-system.md) and the voice from [07-voice.md](07-voice.md), applied
to every surface a stranger or a reader meets, in code where the surface is code and as files
where it is not. The rule set is short: one device that means "located" and "cited" (the Marked
Copy Rule), sage never on a number (the Separate Signals Rule), Newsreader only for the filing's
own words (the Source Voice Rule), every figure verified against SEC XBRL, and the EN monogram and
wordmark untouched (D-015). What follows is the inventory, surface by surface, with the file that
carries each change. The stress test on the result is [09-stress-test.md](09-stress-test.md).

## 1. The landing page, in code

| Section | File | What changed |
|---|---|---|
| Hero headline | `frontend/features/marketing/components/HeroHeadline.tsx`, `lib/headline.ts` | The accent phrase carries the mark (`.en-mark`) on the primary ink instead of sage text. Variant A ("Read the filing faster. Keep the source in view.") survives as the served default, with the mark under "the source" so it never breaks across lines; B and C become "Read it faster. Check it anyway." and "The summary that shows its work." |
| Hero subhead and access line | `LandingHero.tsx` | "AI summaries of 10-Ks and 10-Qs for investors who still check the source. Figures are checked against the company's XBRL where they can be, and quotes against the filing's own text." The scope is the server's: it checks a figure only when the metric maps to an XBRL concept of at least $1M (`backend/app/services/provenance_service.py`). The access line is unchanged ("Private beta · request an invite"). |
| Hero example | `HeroExample.tsx` | The fallback is Apple's FY2025 10-K (filed 2025-10-31) with the verified figures; the evidence row is a `MarkedCopy` block: the claim with its `[1]` bracket, the bracket's twin in the margin, and the filing's sentence in a `.en-marked` blockquote set in the editorial face. Live data renders the same way. The excerpt wears quotation marks, the closing one after the clip's ellipsis. A live figure carries no XBRL hover and the link reads "Source filing · check the figures on SEC EDGAR", since a live figure is the summary's highlight, which the hero cannot vouch for as an XBRL match; only the checked fallback names its XBRL concepts and reads "Figures from the company's XBRL · check them on SEC EDGAR" (one verb on both links). Each fallback concept is text inside its term, visually hidden, so every reader reaches it; the hover repeats it for a mouse. The link carries the brand focus ring (`tests/unit/hero-example-surface.spec.tsx`). |
| Founder slot | Retired | The empty component, configuration and hero mount have been removed (see §6). |
| Trust strip | `TrustStrip.tsx` | Four statements the product keeps, no hedges: sourced from SEC EDGAR; risk excerpts are the filing's own words (main said "quoted excerpts"; a Forward Signals quote can stand unmatched, so the founder's review narrowed it); one summary per filing, generated once and shared; not investment advice. |
| Claims strip | `MeasuredClaims.tsx` | "Figures / Risks / Nine parts / SEC EDGAR", each with the behaviour it names, in place of the four pseudo-statistics; the figures line says the server checks them where it can, and the risks line that unmatched excerpts are withheld and counted. |
| Evidence section | `EvidenceSection.tsx`, `TraceToSourceDemo.tsx`, `CatchCard.tsx` (new) | "Figures with their receipts." over the FY2025 Financial Highlights table (the two totals read SEC XBRL; the per-share row reads Cited, as a real payload's would) and the trace demo; beneath them the catch, "The number you remember": $391.0B from memory (FY2024, struck through) beside $416.2B in the filing (FY2025) with its chip, `{ } Total net sales · SEC XBRL`; the two amounts share a line while they fit and stack when they do not, at 200% text and in the desktop column (`tests/e2e/catch-card-reflow.spec.ts`). The table's footer explains its one Cited row, "Diluted EPS reads Cited: per-share figures are not matched to XBRL.", instead of repeating the lead, and the net income chip reads "Net income", not the concept name `NetIncomeLoss`. |
| Contents | `SummaryContents.tsx` | The nine parts the live schema produces, from The Print to Notable Footnotes, in reading order. The card's note reads "Up to nine parts": the list is the schema's outline, and the Apple sample's own page omits Segments. |
| How it works | `HowItWorks.tsx` | Three steps without "supported" or "selected": search any company with a ticker on SEC EDGAR (the coverage search has: SEC's ticker file), pick a filing, read the summary. |
| Pro section | `ProDepth.tsx`, `ChangeReportDemo.tsx` | "More ways to read one filing." with the Ask, Multi-Period and Change Report demos; the Change Report sample is FY2025 against FY2024. The Multi-Period row, its call to action, the Excel tile and the lead's "read its periods side by side" render only while `NEXT_PUBLIC_ENABLE_ANALYSIS` ships the route, which 404s otherwise (`tests/unit/analysis-route-hidden.spec.tsx`). |
| Pricing section | `PricingSection.tsx` | No "Most popular" badge: the beta has no popularity figure behind one, and the Pro card's brand ring carries the emphasis. The two Multi-Period lines list only while the flag ships it, and the exports line reads "PDF, CSV and Excel exports" only then ("PDF and CSV exports" otherwise), since the Excel export is the analysis workbook. Each line keyed to a flag names it in a field (`flag: 'analysis'`), not by its wording. The Free card reads "10-K, 10-Q and 20-F filings from SEC EDGAR", with no "Supported" hedge. The billing radios carry the brand ring on their own className. |
| Reader quote | `ReaderQuoteSlot.tsx`, `lib/readerQuote.ts` (new) | Mounted under the pricing section; renders nothing while `READER_QUOTE` is `null`, so no placeholder testimonial ships and the reader-quote slot stays unrendered (§6; 01-interview.md §2; `tests/unit/readerQuoteSlot.spec.tsx`). It fills only with a real reader's words and the naming they approved in writing; the voice rules of #1288 (`brandVoiceRules.spec.ts`) gate the shipped value once that PR merges. The placeholder strings are gone. |
| Sample data | `lib/landing-samples.ts` | Every sample on the page is Apple's FY2025 10-K against FY2024: revenue $416.2B vs $391.0B (+6.4%), net income $112.0B vs $93.7B (+19.5%) and diluted EPS $7.46 vs $6.08 (+22.7%) from SEC companyfacts; Services $109.2B vs $96.2B (+13.5%), a dimensioned fact companyfacts does not carry, from the 10-K's own inline XBRL; and the verbatim Item 7 sentence on Services (00-audit.md §4, D-021). The Multi-Period demo is the one exception (§8). The Ask demo answers "How much did net sales grow, and what drove Services?" as a live run would: total net sales of $416.2B [1] and its 6.4% growth [2], two XBRL chips written as `copilot_tools.fact_to_citation` writes them (a fact the tool can fetch, and the growth `compute_metric` derives from it), then the Item 7 sentence on Services [3]. The markers are numbered as the server numbers them, never [F1]. `tests/unit/landingSamplesVerified.spec.ts` holds every figure, chip label and marker on the page's samples and the hero fallback to the verified set, ties each XBRL chip's label and figure to the concept its section ref names, and ties the answer's figure before each marker to that chip. The Copilot teaser's blurred sample (`CopilotTeaser.tsx`, #1295) answers a Services question instead: its Services figures are a dimensioned fact the tool cannot fetch, so its citations are passages from the filing, not XBRL facts; the two answers differ for that reason, and the spec clause over the teaser asserts that citation kind once both PRs are on main. |
| Notable filings | `app/page.tsx`, `features/filings/components/NotableFilings.tsx` | Unmounted (see §7). |
| Footer | `components/Footer.tsx` | The tagline, "The summary that shows its work." |
| Metadata | `app/page.tsx`, `app/layout.tsx`, `app/manifest.ts` | Descriptions and the social image's alt text say what the product does in the voice; the Safari pinned-tab icon is declared (`mask-icon`, §4). |

## 2. The other public surfaces

- **404** (`frontend/app/not-found.tsx`): "We looked. The link is mistyped or out of date. Start from
  the homepage search, or open your dashboard." The heading stays "Page not found".
- **Auth pane** (`frontend/features/auth/components/AuthShell.tsx`): the tagline with the mark, one
  FY2025 sentence, and the $416.2B figure with its direction chip. The three grey placeholder bars
  are gone. This is the brand pane beside the login and register forms; the auth logic and
  `features/auth/api/auth-api.ts` are untouched.
- **Pricing** (`frontend/app/pricing/page.tsx`): the free plan's call to action reads the
  registration mode (`features/marketing/api/access-api.ts`, the client twin of the server's
  `fetchSignupConfig`), so a guest under the invite gate sees "Request an invite" and goes to the
  waitlist instead of a closed sign-up form; until the mode answers, it fails closed to that invite
  copy. The Pro card's guest path is the upgrade flow's own and unchanged. The plan copy says what
  each plan is for and that the same summaries serve every reader; the annual saving label and the
  trial note are set in the ink, not sage. Prices and limits are untouched: the prices are main's
  (#1009, merged into this branch), and so are the Pro line and the saving label's wording. The Pro
  card carries no "Most popular" badge. The Free plan reads "10-K, 10-Q and 20-F filings from SEC
  EDGAR" in place of "Access to all filings": no "Supported" hedge, and 20-F because the API's deploy
  sets `ENABLE_FPI_FILINGS=true` (its code default is off; tasks/todo.md F39). The Pro list reads "Ask
  this Filing, with cited answers", and names Multi-Period Analysis and "PDF, CSV and Excel exports"
  only while `NEXT_PUBLIC_ENABLE_ANALYSIS` ships them ("PDF and CSV exports" otherwise: the Excel
  export is the analysis workbook). The check marks are in the brand ink and hidden from
  assistive tech. The history and "Unlimited" lines wait on the founder (pub/F03, pub/F05).
- **Waitlist** (`frontend/app/waitlist/page.tsx`, `features/waitlist/components/*`): the headline is
  the fourth brand headline with the mark ("The 10-K, read for you, with receipts."); the three
  cards, three of the four steps and the feature grid are rewritten (search coverage stated as
  companies with a ticker on SEC EDGAR); the share text matches; the counter renders only from 25
  signups (`COUNT_FLOOR`), and its count-up is clamped to that floor so no frame reads "0+"; the
  count and the step numbers are set in the ink, not sage. The trust panel reads "Before you join"
  over its three tiles with no lead (the clarity promise is gone, and a lead only repeated the first
  tile's source line), and its middle tile
  is "Security", whose body waits on the founder with the /security claims. The problem cards and the
  joined heading are h2, so the outline does not skip a level after the h1 when the example beside
  the form loads (it has no heading; `tests/unit/waitlistPage.spec.tsx`); the unused `WaitlistStatus`
  component is deleted, with the `getWaitlistStatus` client it alone called. The example link and the "Join the waitlist" pill carry the brand focus ring.
  /waitlist, /login, /register, /forgot-password, /contact, /security and the flag-off /search join
  the routes `tests/e2e/text-floors.spec.ts` visits; it reads which of them render in the auth shell
  from `lib/authShellRoutes.ts`, the list `SiteChrome.tsx` uses.
- **Consent bar** (`frontend/components/CookieConsent.tsx`): "Cookies on this site", then what the
  cookies do: essential cookies keep you signed in; analytics cookies and session recording stay off
  until allowed. PostHog, the analytics tool that sets cookies, initialises only after consent
  (`frontend/app/posthog-provider.tsx`); Vercel Web Analytics is cookieless and runs for every
  visitor, which is why the clause names analytics cookies. The categories, the controls and the
  privacy link are unchanged.

## 3. Inside the product

- **Generation** (`frontend/app/filing/[id]/StreamingSummaryDisplay.tsx`): five new loading quips in
  the voice and one kept ("Reading the size-8 fine print…"), signed "Reading the filing"; the stalled line and the timeout error say what happened
  and what to do. The heading "Generation interrupted" stays.
- **Financial Highlights** (`frontend/features/summaries/components/FinancialMetricsTable.tsx`): a
  currency row keeps the precision it was served with, so a per-share "$7.46" no longer displays as
  "$7.5" (a Phase 9 fix; compact figures keep their rounding).
- **Exports and mail** (`backend/app/services/export_service.py`, `excel_export_service.py`,
  `email_service.py`, `app/routers/contact.py`): mastheads and footers read "EarningsNerd · AI
  summaries of SEC filings"; the waitlist subjects lose their exclamation marks and emoji; the
  verification mail ends "Verify your email address and you can start reading."

## 4. The mark's files and the icons

The EN monogram and the wordmark do not change (D-015, `lessons/brand-the-mark-is-protected.md`).
Phase 5 added the renditions the system needs around them, under `frontend/public/assets/`:
`earningsnerd-logo-mono.svg`, the stacked lockups (`-stacked-light`, `-stacked-dark`,
`-stacked-mono`) and `earningsnerd-mask-icon.svg` for Safari's pinned tab (declared in
`app/layout.tsx`). The favicon and the app icon stay as they were. `LOGO_README.md` carries the
arrangement rules: clear space of one E-bar, the minimum sizes measured on the icon board, the
four sanctioned colours, and the list of things never done to the mark (the misuse board in
[09-stress-test.md](09-stress-test.md) shows them). The social image is regenerated from
`frontend/scripts/brand/og-template.html` (`npm run brand:assets`); the template is the 1200 × 630
sibling of the social post below.

## 5. Templates and merch

[templates/](templates/) holds the five applications and their README: the social post (1080 ×
1350, with its PNG), the business card front and back (SVG with trim guide and fill-in layer), the
PDF cover (A4, with the fields the backend fills named), the email header (600 px tables, inline
styles) and the A5 notebook cover (SVG with its preview). Every figure in the folder is from the
verified FY2025 set; every colour is a token; the mark's paths are byte-identical to
`earningsnerd-mark-mono.svg`. Two decisions were taken while checking them: the notebook's margin
carries no printed bracket marks, because a cover has no text for them to twin (D-016), and the
email footer uses the app's own sentence form of the disclaimer (D-017).

## 6. The founder slot

The dormant slot has been retired: its empty configuration, component and hero mount are
removed. It rendered nothing under the committed configuration, so the landing page's visible
content is unchanged. The brief's reader-quote slot stays unrendered
([01-interview.md](01-interview.md) A5).

## 7. Notable filings

The section is unmounted from `app/page.tsx` and its fetcher removed from the page, and the
component carries a DORMANT note: the week's list read as microcap 8-Ks under a "high-signal"
heading (audit T7). The fetcher, the card and its spec stay for the day a curation rule exists (a
known-good set, a size floor, or 10-K and 10-Q only). The mount gate
(`tests/unit/landing-sections-mounted.spec.ts`) records the omission as deliberate.

## 8. Left for the founder

- The Multi-Period demo (`frontend/features/analysis/demo/demo-analysis.json`) is a pipeline
  snapshot ending at FY2024; it is regenerated through the pipeline, not edited, so the landing
  page shows FY2019 to FY2024 in that one demo until the founder runs it to FY2025.
- A curation rule for §7.

Each has its own line in `tasks/todo.md`, as does the landing composition (tell T4).

## 9. Gates touched

Specs updated with the copy they pin: `pro-depth.spec.tsx`, `hero-example-surface.spec.tsx`,
`waitlist-example.spec.tsx`, `landing-tweaks.spec.tsx`, `landing-sections-mounted.spec.ts`,
`PricingPage.spec.tsx` (new case: the invite gate's call to action), `busyControls.forms.spec.tsx`,
`CookieConsent.spec.tsx`, `FinancialMetricsCards.spec.tsx` (new case: a per-share figure keeps its
cents in both layouts), `tests/e2e/not-found-page.spec.ts` (the 404 body's contrast check reads the
new sentence) and `backend/tests/unit/test_export_service.py`.

New gates, each with a mutation proof in the PR (CLAUDE.md rule 12):

- `brandCopyRules.spec.ts`: shipped copy never says "each figure" or "every figure" without the
  server's scope beside it, never promises nine parts for every filing, and on the public surfaces
  never promises that quotes are withheld or are the filing's own words unless it names risk
  excerpts; on the public surfaces no sage-coloured element renders a digit; the
  highlight never sits on a figure or a price, the hero accents included; the margin exists only
  inside `MarkedCopy`, and every `MarkedCopy` carries a marker.
- `markSingleSource.spec.ts`: every rendition of the EN monogram (the assets, the templates, the
  social card, `EarningsNerdLogoIcon.tsx`, the chart export) copies the canonical outlines byte for
  byte, places them through the canonical groups with nothing else moving an outline, and never
  stretches them.
- `markedCopy.spec.tsx`: the margin twin is anchored at its marker's midpoint and centres itself
  there, at the default, 20px and 32px root sizes.
- `tests/e2e/catch-card-reflow.spec.ts`: the catch card's amounts never overlap or leave the card,
  at 390px (default and 200% text), 320px and 1280px under a 200% root font, in both themes.
- `founderNote.spec.tsx` was retired with the unused slot described in §6.
- `waitlistCounter.spec.tsx`: no number below the floor, no "0+" frame, the count in neutral ink.

The design gates
(`designSnapshotParity.spec.ts`, the ESLint design rules, `no-em-dash-copy.spec.ts`,
`wordmarkSingleSource.spec.ts`) run unchanged against the new surfaces; their tails are in the
handoff ([README.md](README.md)).
