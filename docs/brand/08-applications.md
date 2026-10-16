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
| Pricing section | `PricingSection.tsx` | No "Most popular" badge: the beta has no popularity figure behind one, and the Pro card's brand ring carries the emphasis. The two Multi-Period lines list only while the flag ships it, and the exports line reads "PDF, CSV and Excel exports" only then ("PDF and CSV exports" otherwise), since the Excel export is the analysis workbook. Each line keyed to a flag names it in a field (`flag: 'analysis'`), not by its wording. The Free card reads "10-K, 10-Q and 20-F filings from SEC EDGAR", with no "Supported" hedge, 20-F only while `NEXT_PUBLIC_ENABLE_FPI_FILINGS` mirrors the API's flag (`flag: 'fpi'`; "10-K and 10-Q filings from SEC EDGAR" otherwise). The billing radios carry the brand ring on their own className. |
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
  EDGAR" in place of "Access to all filings": no "Supported" hedge, and 20-F only while
  `NEXT_PUBLIC_ENABLE_FPI_FILINGS` mirrors the API's `ENABLE_FPI_FILINGS` ("10-K and 10-Q filings from SEC
  EDGAR" otherwise; the deploy sets the API's flag on, its code default is off; tasks/todo.md F39). The Pro list reads "Ask
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
  /waitlist, /login, /register, /forgot-password, /check-email, /verify-email, /reset-password,
  /contact, /privacy, /terms, /security, /delete-account and the flag-off /search join the routes
  `tests/e2e/text-floors.spec.ts` visits; three census cases hold the list to the sitemap's static
  core (`STATIC_ENTRIES`), the auth shell's routes (`AUTH_ROUTES`) and every `page.tsx` under `app/`,
  static or dynamic (visited, a dynamic route by a representative path, or named in `NOT_VISITED`
  with its reason), and it reads which of them render in
  the auth shell from `lib/authShellRoutes.ts`, the list `SiteChrome.tsx` uses.
- **Consent bar** (`frontend/components/CookieConsent.tsx`): "Cookies on this site", then what the
  cookies do: essential cookies keep you signed in; analytics cookies and session recording stay off
  until allowed. PostHog, the analytics tool that sets cookies, initialises only after consent
  (`frontend/app/posthog-provider.tsx`); Vercel Web Analytics is cookieless and runs for every
  visitor, which is why the clause names analytics cookies. The categories, the controls and the
  privacy link are unchanged.
- **Contact** (`frontend/app/contact/page.tsx`, `frontend/features/contact/components/ContactForm.tsx`):
  "Contact us", then one line on what to write about. "What to expect" keeps the response time
  (typically within 1–2 business days); the support-hours line (Monday–Friday, 9:00 AM–5:00 PM ET)
  is gone, as the founder decided on 2026-10-15 (D-040): an unenforced promise. The "automated
  confirmation email" line is gone too: the receipt `backend/app/routers/contact.py` sends carries
  no copy of the message, and the route answers success when that send fails. The form's limits are
  the server's (`tests/unit/contactValidationParity.spec.ts` reads `backend/app/schemas/contact.py`),
  so a one-letter name, or a message over 2,000 characters, is refused before sending, counted in
  code points as the server counts (no field carries a native `maxLength`, which counts UTF-16 units
  and would cut an emoji-heavy message the server accepts), and an email whose shape the server's
  `EmailStr` refuses (`ada@gmail`, with no dot in the domain) is refused with "Please enter a valid
  email address." A name or message under the floor says "Your name needs at least 2 characters."
  or "Your message needs at least 10 characters."; over its maximum, "Your message can be at most
  2,000 characters.", the numbers read from the limits, and the hint under the message reads "10 to
  2,000 characters"; the message placeholder is "What happened, or what you'd like to know".
  Every failure shows in an error Notice titled "Message not sent". A rate limit is read from the
  status and says "Too many messages from this connection. Try again in an hour."; a 422 the form
  could not foresee says "Check the fields and send again."; a 5xx says the surface's sentence, since
  the route's own 500 detail is developer wording; any other failure shows the backend's own detail,
  or the surface's sentence when the body carried none: "We couldn't send your message. Try again in
  a minute." The success heading is an h2.
  The prose links on /contact are underlined and carry the brand focus ring. The /security links
  are unchanged, because /security is a legal page under the founder's boundary; the ring triple
  on its five links rides the founder-gated security-claims PR.

## 3. Inside the product

- **Generation** (`frontend/app/filing/[id]/StreamingSummaryDisplay.tsx`): five new loading quips in
  the voice and one kept ("Reading the size-8 fine print…"), signed "Reading the filing"; the stalled line and the timeout error say what happened
  and what to do. The heading "Generation interrupted" stays.
- **Company page** (`frontend/app/company/[ticker]/page-client.tsx`,
  `features/companies/components/CompanySearch.tsx`, `features/peers`, `features/insiders`,
  `features/fundamentals`, `features/filings/components/FilingsHistoryNote.tsx`,
  `features/filings/components/FilingIndex.tsx`): a company that fails
  to load says "Couldn’t load this company" with a Retry and never prints the raw error; only a 404
  reads "Company not found", an answer in the empty card (the error card stays for the load failure),
  with the search's scope ("No company with a ticker on SEC EDGAR matches
  …"). The watched star keeps the button's own ink, its fill and `aria-pressed` carrying the state. The
  search field reads "Search company or ticker" everywhere (the landing's string) and its result rows
  take the inset focus ring. Sector peers and financial trends pick their metric through a compact select
  sized to its content beside its "Metric" label (nine and up to 23 options, in sentence case on its
  face); insider activity picks its window through the SegmentedControl; headings in sentence case; the
  percentile is an ordinal ("21st percentile"); a trade's type carries a hidden ▲ or ▼ beside its
  label and the discretionary net keeps its sign; the 10b5-1 note says what a plan trade is. "Full
  history on SEC EDGAR" opens the company's EDGAR list through the shared company link the lead
  uses (`edgarCompanyUrl`: every form, and EDGAR's own defaults in place of the old `owner=include`
  and `count=40`), in the filing identity's quiet link. `earningsnerd/no-hand-rolled-toggle-group`
  (new ESLint rule) fails a hand-built role="group" of pressed buttons outside the SegmentedControl's own
  file, reading a pressed `<button>` or `<Button>` in the group's own markup, through a same-file wrapper
  and through the DS Button under another name (a row without role="group", an imported wrapper and a
  wrapper of a wrapper are outside its reach, review-checked); `tests/unit/segmentedControlOptionCount.spec.ts`
  (new) fails a SegmentedControl given more than five options, so a long set takes the compact select,
  and the filings form filter, a set known only at run time, renders as the toolbar's compact select
  past five (a filer with both domestic and foreign forms), so no SegmentedControl ever shows more than
  five; `tests/unit/formatters.spec.ts` holds `ordinal` and the signed `fmtShares`.
- **Financial Highlights** (`frontend/features/summaries/components/FinancialMetricsTable.tsx`): a
  currency row keeps the precision it was served with, so a per-share "$7.46" no longer displays as
  "$7.5" (a Phase 9 fix; compact figures keep their rounding).
- **Calendar** (`frontend/features/calendar/components/EarningsCalendarPage.tsx`, `MonthView.tsx`,
  `WeekView.tsx`): the coverage chip and the "+N more" and "Show top 5" controls rest in the ink,
  sage only under the pointer (D-030). `tests/unit/calendarCoverageChip.spec.tsx` renders the page
  on a bounded payload under the known universe: the chip shows there and nowhere else.
- **Counts elsewhere in the product** (D-030): the dashboard feed's "See all N companies" link, the
  check-email countdown, the period quick picks, the narrative's "Show the N source figures" summary
  and its bracketed Sources chip, the data notes' checked count, the peer rank and the summary's
  section index rest in the ink, and so do the values beside them: a What-changed chip's rising
  delta on the dashboard (the primary ink, the icon carrying the direction), the filing viewer's
  "Showing ·" caption, which prints a section's name, and the "Sources & checks" links, which under
  the fundamentals chart print a figure's fiscal year. The controls among them that turn sage under
  the pointer compose the count control, `countControlClass` (`frontend/DESIGN_SYSTEM.md`): the
  whole label in the secondary ink as one text run, sage under the pointer (a link set among lines
  of text keeps its underline). The calendar day's "+N more", which never turns sage, and the
  countdown, at full strength in the same ink while its control waits, rest in the ink outside it.
  `brandCopyRules.spec.ts` rule 2 reads the whole app and follows sage through a class, a ui Button
  or Badge variant, a resting state such as `aria-pressed:`, `visited:` or `focus:`, an opacity
  modifier and a component that sets it or is given it, reads a same-file literal through the file's
  own bindings its header names (a variable's every value, what the file puts in it included,
  fields, indices, destructuring with its rest, a loop's variable, a parameter at each of the file's
  calls, a named callback's included, and React's child utilities), and its count-control check
  fails a control resting in sage, its own or inherited where it is rendered (a component that
  renders its children inside a control counting as one), that holds its count in a span of its own
  ink, and its one-source check fails a count control rebuilt by hand, whose classes written in its
  file turn it sage under the pointer; its header names what stays review-checked.
- **The Copilot's links and the prose links** (D-030): a Copilot source's locator, which prints a
  citation's section name as the model wrote it, composes the count control's `link` kind, with the
  new-tab icon the app's other links to the original draw. A link inside a Copilot answer, the
  filing reader, the summary or the analysis narrative prints words the product does not write, so
  it rests in its prose's own ink with a quiet underline and turns sage only under the pointer
  (`app/globals.css`); a citation chip among the prose keeps its own chip. `brandCopyRules.spec.ts`
  rule 2 reads as a value every field the API types declare that the server or the model writes a
  figure into (a formatted figure, a date or a period, the text written about the filing, a table's
  rows and a list's items among it), and fails a field they declare that can hold a string and that
  it has not classified; its stylesheet check fails a rule that sets sage at rest.
- **Exports and mail** (`backend/app/services/export_service.py`, `excel_export_service.py`,
  `email_service.py`, `app/routers/contact.py`): mastheads and footers read "EarningsNerd · AI
  summaries of SEC filings"; the waitlist subjects lose their exclamation marks and emoji; the
  verification mail ends "Verify your email address and you can start reading."
- **Admin invites and feedback** (`frontend/app/admin/`, `frontend/features/admin/components/`): an
  invite is "created", and "emailed" only when Email invites was on and the backend's best-effort send
  went through (the API's `emailed` flag). A batch reads "3 invites created · 3 emailed", "3 invite
  links created" with email off, or warns "3 invites created · 2 emailed. Copy the rest from the list
  below."; the results head "3 created · 2 emailed" and mark each link still to share "Not emailed";
  the resend dialog says "Invite re-sent" and "We emailed it to {email}." only when it was emailed,
  "New invite link ready" otherwise. A link-only row's actions are named "Resend this link-only
  invite" and "Revoke this link-only invite". The empty lists are one plain line in the card ("No
  invites yet. Send your first one above.", "No feedback yet. Reports appear here as people send
  them."), a failed load is a Notice with a Retry, and the section headings carry no icon. The status
  chips put the status ink on the quiet ground (DESIGN_SYSTEM.md §4), the feedback type chip beside
  them takes the same quiet ground in dark (no fill, its hairline kept), "New" feedback takes an unread
  envelope in place of the sparkle, an already-invited chip reads "· already invited" in its own ink,
  and the remaining admin controls carry the brand ring (`statusChipContrast.spec.ts`,
  `inviteOutcomeEmailed.spec.tsx`, `siteChromeFocusRing.spec.ts`).
- **Earnings calendar** (`frontend/app/calendar/page.tsx`, `features/calendar/components/*`): the
  page, its metadata and its footer say where each date comes from: a reported date from the
  company's 8-K results filing on SEC EDGAR, an estimated date and EPS estimate from a market-data
  provider, and "usually" for a time the company has not confirmed. Nothing claims a confirmed
  date, a reporting pattern or "the most-anticipated" reports; the day dialog groups the day by report
  time (before open, after close, then the rest) and orders each group "large caps and most followed
  first". The anticipation flame is gone: the order already ranks the rows, and the
  warning colour is for status. A signed-out bell offers an email the morning a company reports, and
  its second action follows the registration mode ("Request an invite" while invite-only). The error
  card's "Try again" is a `RetryButton`. `brandCopyRules.spec.ts` rule 1d bans the old claims under
  the calendar, and `tests/unit/calendarEventRow.spec.tsx` holds the row without a marker.
- **Full-text search** (`frontend/app/search/page.tsx`, `features/search/components/FullTextSearch.tsx`):
  the form code is set in the data face, not as a chip, and `earningsnerd/no-form-code-badge` now
  flags a hand-rolled eyebrow chip around a form as well as a `Badge`, alone or leading a meta line
  such as "{form} · Filed {ago}" (the notable-filing card, dormant off `/`, moved to the data face
  with it). The form toggles, "Clear dates" and Retry (a `RetryButton`) carry the brand ring, the
  result rows an inset one inside the clipped list. The rows and the unselected form toggles brighten
  on hover to the row tint (`brand-weak`), never darken. The field stops at the length the backend
  accepts, and `tests/unit/searchQueryLimitParity.spec.tsx` reads that bound from the router; an
  error shows the backend's own detail, or the surface's sentence ("Search did not load. Try again
  in a minute.") when the body carried none, a bodiless 503 or 413 included. The description no
  longer promises every filing, and the title is in sentence case.

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
  excerpts; on the public surfaces no sage-coloured element renders a digit (D-030 later widened this to the whole app, to computed values and to the sage a variant, a resting state or a component sets); the
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
