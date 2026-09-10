# EarningsNerd landing redesign · rationale

Files: `Landing (redesign).dc.html` (live, fluid, both themes via the header toggle or Tweaks), `Landing (redesign) — Breakpoints.dc.html` (380 / 768 / 1280 / 1440 × light / dark), `Landing (current).dc.html` (the shipped page, recreated from `frontend/app/page.tsx` for comparison).

## Headline

**A — "Every number in the filing, traced to the filing."** The audience is sceptical of AI numbers; the sentence names the mechanism (XBRL trace) before the outcome. B and C are wired as a Tweak (`headline`) for the A/B. If A or B wins, set the page `<title>` and `og:title` to match; the OG card's accent word becomes "traced to the filing".

## `[FOUNDER: confirm]` items relied on

- **Access line:** designed as public registration ("Create a free account", "Free account · 5 AI summaries a month · no credit card"). Tweak `access=invite` swaps every instance to "Request an invite" / "Private beta · request an invite". Pick one before launch; the current /register form rejects email signups, so the invite variant is the honest default until that is fixed.
- **Measured-claims strip publishes:** 100% numeric accuracy (26 filings × 3 runs, `backend/evals/baseline_scores.json`), ~30 s streaming (harness mean 30.3 s). Citation fidelity (0.70) is not on the page.
- **"Every company that files with the SEC"** kept in the coverage claim and in the How-it-works copy.
- **7-day trial** shown with "Card required. One trial per account. Cancel any time in the 7 days at no charge."
- **Beta pricing:** "Free for beta members" is behind Tweak `showBeta` (off by default).
- **Cost position** appears only as rationale on the pricing intro ("Summaries are generated once per filing and shared. That is what makes unlimited reading possible at this price."). No per-summary cost figure is on the page.
- **Reporting this week** renders below the argument, behind `showReporting`; production keeps its render-only-with-data rule. Notable filings is omitted (off in production).

## Tokens and patterns extended

- **Bound design system vs repo:** the attached kit predates the July 2026 system (Figtree body, slate dark accent, walnut heading). The page is built on the repo's `tailwind.config.js` / `globals.css` values: Inter (opsz) headings 600, system→Inter body, Geist Mono data, single Sage in both themes (`brand-dark #7FB295`, `brand-strong-dark #98C5AD`), heading ink `#1A1A17`. The kit's stylesheets are loaded and the changed aliases are overridden in the page's theme scope. Recommend regenerating the kit from the current repo.
- **Measured-claims tile (new):** `dl` grid, `minmax(200px, 1fr)`; figure in `font-data` 24–30px/600 tabular, `--track-title2`; label `sm` `text-secondary`. No icon, no card chrome.
- **Marketing pricing card (new):** two `Card` columns (`rounded-xl`, `panel`, hairline, `e2`); Pro gets `brand-border` + `e3` and `Badge variant="solid"` "Most popular". Price in `font-data` 40px/600. Billing toggle is a `radiogroup` segmented control on a `panel` pill with `brand-weak` selected state.
- **Reader-quote slot (new, empty):** dashed `brand-border` figure, Phosphor `quotes`, heading-face blockquote in `text-tertiary`. Behind `showQuoteSlot`, off until a real quote exists.
- **Container rhythm:** hero and header `max-w-7xl`; every other section `max-w-5xl`; section padding `py-20 sm:py-24` (`clamp(80px, 8vw, 96px)`).
- **Cards:** one recipe everywhere (`panel` + hairline + `e2`, brighten on hover). `.glass-card` is retired on the marketing page. Product screens use `.mockup-frame` at `rounded-xl` with `e3`; the fake traffic-light dots are dropped.
- **Hero example on mobile:** the full `HeroExample` card renders at every width (its content is a superset of `ExampleSummaryCard`), so mobile shows the same evidence as desktop. `ExampleSummaryCard` can be retired on this route.
- **Mono in chips:** tickers in the popular-company chips and the source labels ("Revenue · SEC XBRL") render in `font-data` per the data-role rule.

## Token flags

- `text-tertiary-light #6B7280` on cream is 4.35:1. The page uses it only for 11px uppercase eyebrows in the *inside-card* register (on `panel`/`white`, ≥4.6:1) and for the kbd hint; all readable page-background text is `text-secondary-light`. Fix app-wide: darken tertiary-light to ≥ `#5F6672` or route page-background muted text to secondary.
- Dark-mode muted text is `secondary` throughout (never `tertiary-dark`).
- The `mockup-frame` title-bar dots use raw red/yellow; removed here rather than tokenised.

## Screens the founder must capture from the live app (both themes)

The mocks in the design carry `data-capture` attributes. Replace each with a real capture, or keep the DOM-rendered version fed by live data:

1. **Hero example card** (`HeroExample`, Apple FY2025 10-K): the excerpt, three metric values/deltas and filing date shown are illustrative — the live ISR fetch is the source of truth.
2. **Financial Highlights excerpt** (`FinancialMetricsTable`): Revenue, Net income, Diluted EPS rows with per-row source labels and the Investor Takeaway text. Takeaway copy in the design is placeholder.
3. **Trace-to-Source popover** (`SourceTrace`) open on a verified claim: the MD&A excerpt shown is placeholder; capture a real verified excerpt and its EDGAR link.
4. **Quality badge** (`SummaryDisplay` header): the "Full summary" verdict appears in the hero example card only; the separate quality-verdict card was removed from the evidence block at the founder's request.
5. **Ask this Filing** (`CopilotMessage` + `CitationChip`): one answer with a `[1]` text chip and an `[F1]` XBRL chip, both Verified. The Services question/answer in the design is placeholder. Note the two chip kinds are a product convention from `CitationChip.tsx`: `[n]` cites a passage, `[Fn]` cites an XBRL financial fact; the footnote rows on the page label them "Passage" / "XBRL figure" so a first-time reader does not need to know this.
6. **Multi-Period Analysis** (`KpiStrip` + `TrendCharts` + `MetricsTable`), Apple FY2019–FY2025 annual. Chart and grid values are illustrative.
7. **Change Report** (`WhatChanged`) against the prior 10-K: risk-factor lines are shown as skeleton bones until captured.
8. **Reporting this week** with a real week's companies.

## Company logos

The page reuses the production pattern from `components/CompanyLogo.tsx` verbatim rather than a new one: a fixed-size circular slot renders the ticker monogram immediately, then Logo.dev's ticker-keyed PNG (`img.logo.dev/ticker/{TICKER}?size=2x&format=png&retina=true`) fades in over it on `load`; on `error` the monogram stays. No layout shift, no broken image, no ticker→domain lookup. The token is `NEXT_PUBLIC_LOGO_DEV_TOKEN`, a publishable client key already allow-listed in `next.config.js` (`images.remotePatterns`), so no proxy is needed. In this design, paste the token into the **Company logos → logoToken** tweak and every mark (8 hero chips, the Apple example card, Reporting this week) resolves live; empty shows the monogram, which is also what production renders when the env var is unset. Recommendation for the route: keep hotlinking (Logo.dev caches per ticker), `loading="lazy"` on marks below the fold, and only the Apple example mark eager. Keep the Logo.dev attribution line in the footer; it is a free-tier requirement.

## Gaps noted (deleted rather than invented)

- No user counts, testimonials, press or customer logos.
- No "risk factor analysis" feature card: the capability is shown inside the Change Report screen only.
- Free-tier "Historical filing access" is folded into "Company search and historical filings".
- The 40-F form type is not advertised (brief lists 20-F/6-K as the foreign-issuer coverage to state).
- Performance: the page renders the H1 as LCP, no hero image, one preconnect to `img.logo.dev`; the ≤300 KB JS budget is an implementation requirement for the Next.js route, not verifiable in this design.
