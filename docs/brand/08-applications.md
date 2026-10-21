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
| Composition (D-045) | `frontend/app/page.tsx`, `LandingRow.tsx` (new) | The two-column hero stays; every section after it is one ruled row: a hairline across the hero's container, a label column with the section's number (a CSS counter, so a section that omits itself takes none and leaves no gap), its title as the section's h2 and one line, one short sentence (a second opens the content column), and the content beside it, opening at 64rem at the reader's text size. No row alternates and nothing lays out four across (`earningsnerd/no-four-up-grid`); `tests/unit/landing-sections-mounted.spec.ts` holds the order, each row to the primitive and the close to one line. A form code in a row's copy is one unbroken run (`FormCodeText`), so no line breaks "10-Q" at its hyphen (`tests/e2e/reflow-200.spec.ts`, at 320 and 390px). The label column is the margin of a 10-K, so the page reads as a filing's items (tell T4, `09-stress-test.md` §2). |
| Hero headline | `frontend/features/marketing/components/HeroHeadline.tsx`, `lib/headline.ts` | The accent phrase carries the mark (`.en-mark`) on the primary ink instead of sage text. Variant A ("Read the filing faster. Keep the source in view.") survives as the served default, with the mark under "the source" so it never breaks across lines; B and C become "Read it faster. Check it anyway." and "The summary that shows its work." |
| Hero subhead and access line | `LandingHero.tsx` | "AI summaries of 10-Ks and 10-Qs for investors who still check the source. Figures are checked against the company's XBRL where they can be, and quotes against the filing's own text." The scope is the server's: it checks a figure only when the metric maps to an XBRL concept of at least $1M (`backend/app/services/provenance_service.py`). The access line is unchanged ("Private beta · request an invite"). Each form code in the subhead is one unbroken run (`FormCodeText`), so under 200% text it no longer breaks "10-Ks" at 390px or "10-Qs" at 1440px (E81, `tests/e2e/reflow-200.spec.ts`). |
| Hero example | `HeroExample.tsx` | The fallback is Apple's FY2025 10-K (filed 2025-10-31) with the verified figures; the evidence row is a `MarkedCopy` block: the claim with its `[1]` bracket, the bracket's twin in the margin, and the filing's sentence in a `.en-marked` blockquote set in the editorial face. Live data renders the same way. The excerpt wears quotation marks, the closing one after the clip's ellipsis. A live figure carries no XBRL hover and the link reads "Source filing · check the figures on SEC EDGAR", since a live figure is the summary's highlight, which the hero cannot vouch for as an XBRL match; only the checked fallback names its XBRL concepts and reads "Figures from the company's XBRL · check them on SEC EDGAR" (one verb on both links). Each fallback concept is text inside its term, visually hidden, so every reader reaches it; the hover repeats it for a mouse. The link carries the brand focus ring (`tests/unit/hero-example-surface.spec.tsx`). Under 200% text (E81) the identity line wraps between its facts, each middot held to the fact before it, the form one run and the date moving under "filed" whole, where "filed Oct 31, 2025" in one run took the page to 329px at 320px; and the three figures wrap one under another inside their one hairline strip, each taking its own width, where in equal thirds each value ran into the next at 390px. The EDGAR receipt holds its middot to the word before it with a no-break space, where at 1440px its second line began "·". `tests/e2e/reflow-200.spec.ts` reads the boxes at 320, 390 and 1440px, the strip's rules among them at both text sizes (only between two figures, the first figure's label flush with the card), and the page at 320px. |
| Founder slot | Retired | The empty component, configuration and hero mount have been removed (see §6). |
| Trust strip | `TrustStrip.tsx` | Four statements the product keeps, no hedges: sourced from SEC EDGAR; risk excerpts are the filing's own words (main said "quoted excerpts"; a Forward Signals quote can stand unmatched, so the founder's review narrowed it); one summary per filing, generated once and shared; not investment advice. |
| Claims strip | `MeasuredClaims.tsx` | "Figures / Risks / Nine parts / SEC EDGAR", each with the behaviour it names, in place of the four pseudo-statistics; the figures line says the server checks them where it can, and the risks line that unmatched excerpts are withheld and counted. The first row, "What a summary does", two across (D-045). |
| Evidence section | `EvidenceSection.tsx`, `TraceToSourceDemo.tsx`, `CatchCard.tsx` (new) | "Figures with their receipts." over the FY2025 Financial Highlights table (the two totals read SEC XBRL; the per-share row reads Cited, as a real payload's would) and the trace demo; beneath them the catch, "The number you remember": $391.0B from memory (FY2024, struck through) beside $416.2B in the filing (FY2025) with its chip, `{ } Total net sales · SEC XBRL`; the two amounts share a line while they fit and stack when they do not, at 200% text and in the desktop column (`tests/e2e/catch-card-reflow.spec.ts`). The label column's line is "Each row in the highlights carries a label."; what each label means opens the content column, above the table. The table's footer explains its one Cited row, "Diluted EPS reads Cited: per-share figures are not matched to XBRL.", instead of repeating that paragraph, and the net income chip reads "Net income", not the concept name `NetIncomeLoss`. |
| Contents | `SummaryContents.tsx` | The nine parts the live schema produces, from The Print to Notable Footnotes, in reading order, as a hairline list rather than a card (D-045). The list's note reads "Up to nine parts": the list is the schema's outline, and the Apple sample's own page omits Segments. |
| How it works | `HowItWorks.tsx` | Three steps without "supported" or "selected": search any company with a ticker on SEC EDGAR (the coverage search has: SEC's ticker file), pick a filing, read the summary. |
| Pro section | `ProDepth.tsx`, `ChangeReportDemo.tsx` | "More ways to read one filing." with the Ask, Multi-Period and Change Report demos, one under another, each pitch above its screen (D-045: no alternating rows); the Change Report sample is FY2025 against FY2024. The Pro chip sits on Ask this Filing and Multi-Period Analysis alone, and the Change Report's line names the metric deltas alone, "What changed against the prior filing, metric by metric, computed from XBRL. Both plans include it.": every reader gets the same report, metric deltas only, since `change_report_service.py` omits its risk lines and production serves no wording diff. Its risk and language clauses come back with `ENABLE_SECTION_CHANGES` (E27); until then `tests/unit/changeReportPlanClaims.spec.tsx` fails the row when it names either, or wears the chip. The extras are a ruled list, two across, with their file kinds and forms as text in the data face, no icon tiles and no chips: Excel export (with the analysis route), Summary export and Filing alerts, and no history extra while no retention is enforced (D-046). The Multi-Period row, its call to action, the Excel extra and the lead's "read its periods side by side" render only while `NEXT_PUBLIC_ENABLE_ANALYSIS` ships the route, which 404s otherwise (`tests/unit/analysis-route-hidden.spec.tsx`). |
| Pricing section | `PricingSection.tsx` | One table since D-045, not two cards: the plans as columns, what each includes as rows (price, summaries, filings, search, Ask this Filing, Multi-Period Analysis, Change Report, alerts, exports, watchlist, priority support; no summary-history row, since nothing enforces `history_retention_days` and the history claims leave until a retention is enforced, D-046), each cell a plan line read through `shipped()` from `lib/planLimits.ts`, a dash read as "Not included" where a plan has none, and the two calls to action in the last row. No "Most popular" badge: the beta has no popularity figure behind one. The Multi-Period row (its label and cells are `ANALYSIS_LINES` entries) lists only while the flag ships it, and the exports cell reads "PDF, CSV and Excel exports" only then ("PDF and CSV exports" otherwise), since the Excel export is the analysis workbook. Each line keyed to a flag names it in a field (`flag: 'analysis'`), not by its wording. The Filings row reads "10-K, 10-Q and 20-F filings from SEC EDGAR" for both plans, with no "Supported" hedge, 20-F only while `NEXT_PUBLIC_ENABLE_FPI_FILINGS` mirrors the API's flag (`flag: 'fpi'`; "10-K and 10-Q filings from SEC EDGAR" otherwise). The Change Report row reads "Included" for both plans: the report's one plan difference, the Item 1A wording block (`entitlements.py`, `section_changes_items`), is served only behind `ENABLE_SECTION_CHANGES`, which `config.py` defaults off and no deploy map sets, and `tests/unit/changeReportPlanClaims.spec.tsx` fails when the flag can ship until the row says what the plans then get. The table fits a 390px phone at the default size and scrolls inside a named region, never the page, when it is wider (`tests/unit/pricing-section.spec.tsx`). `/pricing` keeps its two cards. The billing radios carry the brand ring on their own className. |
| Reader quote | `ReaderQuoteSlot.tsx`, `lib/readerQuote.ts` (new) | Mounted under the pricing section; renders nothing while `READER_QUOTE` is `null`, so no placeholder testimonial ships, the reader-quote slot stays unrendered and it takes no number among the rows; once filled it is a ruled row (§6; 01-interview.md §2; `tests/unit/readerQuoteSlot.spec.tsx`). It fills only with a real reader's words and the naming they approved in writing; the voice rules of #1288 (`brandVoiceRules.spec.ts`) gate the shipped value once that PR merges. The placeholder strings are gone. |
| Sample data | `lib/landing-samples.ts` | Every sample on the page is Apple's FY2025 10-K against FY2024: revenue $416.2B vs $391.0B (+6.4%), net income $112.0B vs $93.7B (+19.5%) and diluted EPS $7.46 vs $6.08 (+22.7%) from SEC companyfacts; Services $109.2B vs $96.2B (+13.5%), a dimensioned fact companyfacts does not carry, from the 10-K's own inline XBRL; and the verbatim Item 7 sentence on Services (00-audit.md §4, D-021). The Multi-Period demo is the one exception (§8). The Ask demo answers "How much did net sales grow, and what drove Services?" as a live run would: total net sales of $416.2B [1] and its 6.4% growth [2], two XBRL chips written as `copilot_tools.fact_to_citation` writes them (a fact the tool can fetch, and the growth `compute_metric` derives from it), then the Item 7 sentence on Services [3]. The markers are numbered as the server numbers them, never [F1]. `tests/unit/landingSamplesVerified.spec.ts` holds every figure, chip label and marker on the page's samples and the hero fallback to the verified set, ties each XBRL chip's label and figure to the concept its section ref names, and ties the answer's figure before each marker to that chip. The Copilot teaser's blurred sample (`CopilotTeaser.tsx`, #1295) answers a Services question instead: its Services figures are a dimensioned fact the tool cannot fetch, so its citations are passages from the filing, not XBRL facts; the two answers differ for that reason, and the spec's teaser clause holds that citation kind: the sample states only the verified Services pair, names the drivers the Item 7 sentence names, and runs markers [1] and [2] with one matched source each and no XBRL marker, locator, tag or braces glyph. |
| Reporting this week | `features/calendar/components/ReportingThisWeek.tsx` | A ruled row of hairline lines (mark, ticker, the day it reports, name), two across, in place of the four-up tiles (D-045); it renders only with live data, so it takes no number without it. |
| Notable filings | `app/page.tsx`, `features/filings/components/NotableFilings.tsx` | A ruled row after Reporting this week since E90 (see §7): one hairline line per filing the backend serves under D-046's rule, in Reporting this week's anatomy, two across, each opening its company page, under the line "The past week's 10-K and 10-Q filings from companies with a summary to read, newest first."; it renders only with a served list, so it takes no number without one. |
| Close | `ClosingLine.tsx` (was `CtaBanner.tsx`) | One line under the last row's rule, not a banner (D-045): "Start with a real filing: read the Apple 10-K summary first, then read your own." with the live example as a text link (the funnel's `cta_banner` placement) and the access mode's call to action as a button at its end. |
| Footer | `components/Footer.tsx` | The tagline, "The summary that shows its work." |
| Metadata | `app/page.tsx`, `app/layout.tsx`, `app/manifest.ts`, `lib/socialCard.ts` | Descriptions and the social image's alt text say what the product does in the voice; the Safari pinned-tab icon is declared (`mask-icon`, §4). Titles put the page first and the brand last ("Read the filing faster. Keep the source in view \| EarningsNerd"); the root default is "AI summaries of SEC filings \| EarningsNerd", and the root's social preview carries no title or description of its own, so Next fills both from each page (D-038). |

## 2. The other public surfaces

- **404** (`frontend/app/not-found.tsx`): "We looked. The link is mistyped or out of date. Start from
  the homepage search, or open your dashboard." The heading stays "Page not found".
- **Auth pane** (`frontend/features/auth/components/AuthShell.tsx`): the tagline with the mark, one
  FY2025 sentence, and the $416.2B figure with its direction chip. The three grey placeholder bars
  are gone. This is the brand pane beside the login and register forms; the auth logic and
  `features/auth/api/auth-api.ts` are untouched. The pages around it say only what the code does.
  Their verb is "Log in" (D-046): the login page reads "Log in to continue to EarningsNerd." over a
  "Log in" button ("Logging in…" while it works), its link for a visitor without an account follows the
  access decision (`ACCESS_COPY`: "Request an invite" to /waitlist while access is by invite, as the
  register page's notice says), the register page's link back reads "Log in", and the provider buttons
  read "Continue with Google" and "Continue with Apple" on both pages, an invited start that fails naming
  its provider under the button ("Couldn't continue with Google. Please try again."). The login page's
  "Request an invite" is `inline-block`, so at 320px or under 200% text it stays one box, its label
  wrapping inside it, and its ring closes round it; the register notice's stays inline inside its
  sentence, wraps with it and draws its ring round each line (`box-decoration-clone`, as a prose link
  does). Neither focus ring draws an open piece (`tests/e2e/reflow-200.spec.ts`).
  /check-email names where links go ("We send verification links to" the address) and never says one
  was just sent, since the account menu's "Verify your email" lands there without sending: "Open the
  newest one to verify your email address. Each link expires 24 hours after we send it.", and Resend is
  what sends. Reached without an address (verify-email's "Get a new link") it offers no Resend and
  says "Open the newest verification link we sent you." then "Need a new one? Log in, open the
  account menu and choose Verify your email.". /verify-email shows the endpoint's own reason for a
  refused link (its two 400 details, listed in `features/auth/lib/verifyEmailFailure.ts` and held to
  `backend/app/routers/auth.py`), "The link has expired, or a newer one replaced it." for a 400
  without one, and "We couldn't check the link just now. Reload this page to try again." for a lost
  connection, a timeout or a server error, never the API client's own text; on success, "Your email
  address is confirmed. Taking you to the home page…" (reading and a password sign-in never waited on
  it). The verification banner says "Verify your email to subscribe.", and the dialog that checkout's
  403 opens says "Subscribing requires a verified email. We send verification links to" the address:
  checkout is the one action that refuses an unverified email, with a 403
  (`tests/unit/authPagesCopy.spec.tsx` holds that 403 to `backend/app/routers/subscriptions.py`, and
  every backend read of `email_verified` to a listed site, so a gate worded any other way fails it), and
  a Google or Apple sign-in links to an existing account only once both sides have verified the
  email, as the login page's conflict sentence says.
  /reset-password and the register form state one rule from `frontend/lib/passwordRules.ts`, mirrored
  from the server's `PASSWORD_MIN_LENGTH`: "At least 12 characters. A longer passphrase is stronger.
  We check new passwords against known data breaches." (true while `PWNED_PASSWORD_CHECK_ENABLED` keeps
  its default; it names the check, not a refusal, because the lookup lets a password through when it
  fails), and the strength meter reads "Too short" under that minimum and "Weak" at it, adding a bar for four
  characters past it, for letters with digits and for a symbol; its bars carry dark twins
  (`tests/unit/themePairs.spec.ts` holds every colour class on a light half, a `-light` token or one
  beside a `<name>-dark` such as `brand-weak`, to a `dark:` colour twin, outside a listed residue,
  and refuses a `-dark` token outside `dark:`, which is why the account menu's
  unverified dot and the banner's dismiss hover now pair their light and dark values). The login page's Google and Apple account-conflict error names the
  provider tried: "This email already has an EarningsNerd account, and the two could not be linked.
  Log in the way you created that account and verify your email. Once the email is verified on
  EarningsNerd and Google, try Google again." (verifying links nothing by itself; the provider links on
  that later sign-in). The register subhead follows the server's config: under the invite gate an
  invited visitor is promised Pro only while the beta promo is on (`betaPricingActive`), otherwise
  reads "Your invite opens an account during the private beta."; an uninvited visitor under the gate
  gets no subhead, the private-beta notice says it; open registration shows the free-plan line to
  everyone, invited or not. That invite-path Pro line is a founder claim, like the pricing pages'
  "Unlimited" line (the founder's review filed both under F32, later F41): this one is conditional on
  the server's promo config, and D-040 keeps "Unlimited" on the plan cards, with the fair-use guardrail
  stated once, in the /pricing FAQ and the filing page's monthly-limit card (D-046). Every page link and button on these routes carries the brand
  focus ring.
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
  EDGAR" otherwise; the deploy sets the API's flag on, its code default is off). The Pro list reads "Ask
  this Filing, with cited passages you can check" (it read "with cited answers" until the Ask this Filing
  PR scoped it: an answer can ship an uncited figure, D-034), and names Multi-Period Analysis and "PDF, CSV and Excel exports"
  only while `NEXT_PUBLIC_ENABLE_ANALYSIS` ships them ("PDF and CSV exports" otherwise: the Excel
  export is the analysis workbook). The check marks are in the brand ink and hidden from
  assistive tech. "Unlimited" stays, with the fair-use guardrail stated once where it is read
  (pub/F05, D-040, E58); the history lines leave until entitlements enforce a retention (pub/F03,
  D-046, E58).
- **Waitlist** (`frontend/app/waitlist/page.tsx`, `features/waitlist/components/*`): the headline is
  the fourth brand headline with the mark ("The 10-K, read for you, with receipts."); the three
  cards, three of the four steps and the feature grid are rewritten (search coverage stated as
  companies with a ticker on SEC EDGAR); the share text matches; the counter renders only from 25
  signups (`COUNT_FLOOR`), and its count-up is clamped to that floor so no frame reads "0+"; the
  count and the step numbers are set in the ink, not sage. The trust panel reads "Before you join"
  over its three tiles with no lead (the clarity promise is gone, and a lead only repeated the first
  tile's source line), and its middle tile
  is "Security", whose body says what the hosting does, held to /security's standard since D-046: "Your
  data travels over HTTPS and is kept in Google Cloud SQL, which encrypts it at rest. Card details stay
  with Stripe." The problem cards and the
  joined heading are h2, so the outline does not skip a level after the h1 when the example beside
  the form loads (it has no heading; `tests/unit/waitlistPage.spec.tsx`); the unused `WaitlistStatus`
  component is deleted, with the `getWaitlistStatus` client it alone called. The example link and the "Join the waitlist" pill carry the brand focus ring.
  The pill, which answered no pointer, rests at the secondary recipe's hover fill and takes its pressed
  fill under the pointer (`hover:bg-brand-border/60`, `dark:hover:bg-brand-border-dark`; E82): on the How
  it works card its label measures 5.77:1 at rest and 5.33:1 hovered in light, 5.81:1 and 4.50:1 in
  dark, and `tests/e2e/text-floors.spec.ts` holds both themes at rest and hovered.
  /waitlist, /login, /register, /forgot-password, /check-email, /verify-email, /reset-password,
  /contact, /privacy, /terms, /security, /delete-account, /calendar (its pinned fixture week painted) and
  /search (its results painted), since CI's e2e build turns the calendar and search on, join the routes
  `tests/e2e/text-floors.spec.ts` visits; three census cases hold the list to the sitemap's static
  core (`STATIC_ENTRIES`), the auth shell's routes (`AUTH_ROUTES`) and every `page.tsx` under `app/`,
  static or dynamic (visited, a dynamic route by a representative path, or named in `NOT_VISITED`
  with its reason), and it reads which of them render in
  the auth shell from `lib/authShellRoutes.ts`, the list `SiteChrome.tsx` uses.
  The referral link in the join response and the waitlist mails lands on `/waitlist?ref=`
  (`backend/app/services/waitlist_service.py`), where the form submits the code with the waitlist
  gate up or down, so a referral counts; the success card states the bonus once, from
  `REFERRAL_BONUS` (`features/waitlist/lib/referral.ts`, mirrored from the backend), and the "A
  numbered spot" card says your link moves you up without the number. The join answers "You're on
  the waitlist." or "This email is already on the waitlist.", without an exclamation mark. A code no
  signup holds comes back as the router's `invalid_referral` (a 400 with no `detail`), which the form
  routes by its code to its own sentence, "We can't find this referral code on the waitlist. Check the
  link with whoever shared it.", where it printed axios's status line before. The first sentence is the
  Notice's title and the second its description, and under them "Join without the code" links to
  `/waitlist` (F47, D-046): the visitor sees what happened and chooses. The page keeps what was typed
  (search params do not remount it) and reads no code from the URL from then on, so the next submit
  joins without one; focus goes back to the email field (`tests/unit/waitlistSuccessCard.spec.tsx`).
  The success card's referral link is set in the data face, whose Geist Mono has no contextual
  alternates, so the x of a code reads as Copy copies it (Inter's draws it as a multiplication sign
  between digits), and the share links wrap inside the card at 200% text.
- **Consent bar** (`frontend/components/CookieConsent.tsx`): "Cookies on this site", then what the
  cookies do: essential cookies keep you logged in; analytics cookies and session recording stay off
  until allowed. PostHog, the analytics tool that sets cookies, initialises only after consent
  (`frontend/app/posthog-provider.tsx`). Vercel Web Analytics is cookieless, which is why the clause
  names analytics cookies, and since D-046 it too loads only after the visitor allows analytics, read
  from the same stored choice (`frontend/app/private-analytics.tsx`;
  `tests/unit/privateAnalytics.spec.tsx`, `tests/e2e/analytics-consent.spec.ts`). The bar's two
  choices say what they set:
  "Essential only" and "Allow analytics" (session recording stays off until it is chosen under
  Customize, D-032), with equal weight: both are secondary buttons, and Customize is the ghost
  beside them; the dialog's headings and its "Save preferences" button are in sentence case.
  After a first choice the bar is gone, and the site footer's "Cookie settings" (`frontend/components/Footer.tsx`,
  a button in the Legal column with the links' recipe and the brand ring) reopens the dialog on the stored
  choices: Save writes them and fires `cookieConsentChanged` as the bar does, so /privacy's withdrawal
  sentence holds ("You can withdraw consent for analytics and session recording at any time through our
  cookie consent banner or settings."; `lib/cookieSettings.ts`, `tests/unit/cookieSettingsReopen.spec.tsx`).
  The auth routes have no site footer (`lib/authShellRoutes.ts`), so the control is not there.
  The banner is the only control, for every visitor (D-049): no browser privacy signal is read, so a first
  visit whose browser sends Do Not Track shows the bar like any other, and the dialog opens on the stored
  choice with its Analytics cookies and Session recording boxes enabled.
  The categories, the handlers and the privacy link are unchanged; the analytics clause in the
  dialog reads D-046's words, "Usage statistics through PostHog, so we can see which pages work. When
  you are logged in they are tied to an internal account id." (chrome/F1, F33), one constant with
  /privacy's analytics cookies line (`ANALYTICS_CONSENT_CLAUSE`, `frontend/lib/consentCopy.ts`). A
  stored choice records the clause it was made under (`CONSENT_VERSION`): an analytics allow made
  while the dialog called the statistics anonymous reads as no choice, so the bar asks that reader
  again, once, and a refusal made then stands (`tests/unit/CookieConsent.spec.tsx`).
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
  The prose links on /contact are underlined and carry the brand focus ring, and the five links on
  /security carry it too (D-046).
- **Security** (`frontend/app/security/page.tsx`): since D-046 every sentence says what the code or
  its hosting does, a fact the repository cannot show (encryption at rest) named as the provider's,
  the headings in sentence case, under a new date (`LEGAL_DATES.security`). Gone: a Redis cache
  (production runs none, ADR-0004), CSP headers against XSS (the site sends frame-ancestors only),
  every API endpoint behind authentication (search, company pages and summaries are public),
  enterprise-grade hosting with 99.9% uptime, and firewalls and intrusion detection. The PostHog
  line says PostHog in the browser waits for the reader's choice, and a sentence of its own, which
  /privacy says too, discloses the account events the API records against the account id whatever
  the reader chose, in words that name no provider (D-051). The runbook bullet and the notification
  bullet name their source beside them (`tasks/security_privacy_runbook.md` §3), and the audit-log
  item names the administrator actions an audit row records. Token renewal and Logging out say what
  holds when requests overlap (E127): each renewal replaces the refresh token, logging out revokes the
  one the browser sends, logging out of all devices revokes every refresh token the account holds at
  that moment, as a password change or reset does, and none of these revokes a session token already
  issued. `tests/unit/legalTruth.spec.tsx` fails on each removed claim's family, on /security (its
  text, each list item and paragraph on its own, and its metadata), on /privacy and /terms, and in the
  waitlist page's copy (its planted forms name the gaps: a claim split across sentences or said in
  other words), and on an
  analytics-consent promise not scoped to the browser; holds the consent dialog's analytics clause and
  /privacy's analytics cookies line to one constant (`ANALYTICS_CONSENT_CLAUSE` in
  `frontend/lib/consentCopy.ts`), with no copy calling the analytics anonymous or anonymised; holds
  the account-events sentence (`ACCOUNT_EVENTS_DISCLOSURE`, the same module) to the backend's callers
  that key an event on the account id and read no consent, the sourced bullets to their section's
  steps, the audit-log item to the backend's audit writers, and the page's numbers and schedules to
  the repository's facts (the backend's defaults, the breach check's prefix, the export's day of the
  month and Dependabot's week); fails on a refresh token that works once, a reused one revoking the account, or a session
  that ends after logging out, within a time or with none named, on every run, until the founder's
  go-ahead on the stronger wording (`tasks/todo.md` F53); and pins each legal page's rendered
  text, by hash, to a ledger row under its date, main's published text first, so a text or date
  change fails until the last row records it (a row on the day of the row before it names the pull
  request that shares the day; a row edited in place passes, and is review-checked, as is whether a
  row's date is the day main's history gives its merge). Its five links carry the brand focus ring, the site chrome's triple;
  `siteChromeFocusRing.spec.ts` holds them, and its residue no longer lists the page. Its two
  addresses break anywhere, as /privacy's four do, so neither page scrolls sideways at 390px under
  200% text (`reflow-200.spec.ts`).

- **Metadata and the social card** (every `app/**/page.tsx` and `layout.tsx`, `lib/socialCard.ts`,
  `scripts/brand/og-template.html`): every route's tab and shared-link preview reads
  "<Page name> | EarningsNerd", from its own page or from a `layout.tsx` beside a client page
  (dashboard, settings, watchlist, the account pages, the admin pages), in sentence case on every
  route but the two pinned in `routeMetadata.spec.ts`'s `TITLE_RESIDUE` (/privacy and /terms, recased
  only with a legal-date bump). Every private route
  stays out of the index. No layout above a public page sets noindex, the root layout included, and
  no public page does either, but for two states kept out by design, each with
  `robots: { index: false, follow: true }` so crawlers still follow its links: a company page for an
  issuer whose coverage status is `unsupported_foreign`, which has no filings and never will, and a
  filing page with no summary to show yet, a stub that would read as one of thousands of
  near-duplicates and joins the index once its summary exists. Company and filing
  pages carry the site card, since a page-level `openGraph` replaces the root one; their titles and
  descriptions say what the page holds in each state (a foreign issuer with no SEC reports is told as
  such, a filing with no summary yet claims none), and a filing's title names its filed date. The
  card's URL is typed once (`?v=5`); its headline breaks before "shows its work." so the highlight
  never crosses a line, and the highlight's hairline is 2px. Under `WAITLIST_MODE=true` (the rollback
  state) the card, the icons, the manifest and /terms stay reachable. The founder declined a
  company-specific or filing-specific card (D8, D-040). Gates: `routeMetadata.spec.ts`,
  `markSingleSource.spec.ts`, `middleware.spec.ts`.

## 3. Inside the product

- **Generation** (`frontend/app/filing/[id]/StreamingSummaryDisplay.tsx`): five new loading quips in
  the voice and one kept ("Reading the size-8 fine print…"), signed "Reading the filing"; the stalled line and the timeout error say what happened
  and what to do. The heading "Generation interrupted" stays. The card reads "Generating the summary"
  and its four steps read "Fetching the 10-K from SEC EDGAR" (the filing's own form), "Reading the
  statements, risk factors and MD&A", "Checking figures against the company's XBRL" and "Writing the
  summary", which the live region announces as they start. Neither "Generating the summary" nor "AI-generated
  summary" carries a glyph beside it: the sparkle is the AI summary chip's alone. A pending step keeps full opacity in the tertiary ink (it
  sat at 2.1:1 under opacity-40). A slow run reads "Taking longer than usual. Still working on it.",
  signed "Still running", without guessing why. A stored summary that failed reads "This summary did
  not finish" over its own sentence, "The last attempt for this filing did not finish. Try again to
  generate it." The pipeline's stream errors are mapped on the client
  (`frontend/features/summaries/lib/streamErrorCopy.ts`): the summary_stages strings are to change
  with the next functional change there, and the mapping holds until then (F35, D-046, E92). The raw
  sentence still decides the paywall card and the retry, and
  `tests/unit/streamErrorCopy.spec.ts` reads the Python (every summary_stages module and
  `services/ai/summary_finalize.py`, whose payload messages two stages stream) so a reworded sentence
  fails until it is mapped. The client's own fallbacks (`features/summaries/api/summaries-api.ts`,
  `features/summaries/hooks/useSummaryGeneration.ts`: a status with no detail, a dropped or closed
  stream, the idle timeout, a failed summary read) are sentences in the voice, never the browser's
  or the API client's transport text, pinned path by path in `tests/unit/summaryStreamFallbacks.spec.tsx`.
  The error card offers its Retry only for a failure a retry can help (`isNonRetryableStreamError`,
  which also stops the stream's automatic retry): Pro's fair-use pause, a sign-in or a permission error
  keeps its sentence and no Retry.
  At 200% text the progress card's header row wraps, the percent keeping to the right on a line of
  its own, and the form code in its meta line ("10-K · Processing…") never breaks at its hyphen.
- **Signup gate** (`frontend/features/summaries/components/GenerateSignupGate.tsx`): it follows the
  one access decision (`features/marketing/lib/access.ts`) through the registration payload the
  pricing page reads. In invite-only mode, and until that payload answers or when it cannot, it reads
  "Summaries need an account" with "Request an invite" and "Log in"; in public mode, "Create a free
  account to summarize this filing". Its two links sit in a row of their own that wraps, each label
  wrapping inside its button, so at 200% text they stack inside the card. The card takes
  GuidanceCard's default glyph, and its trial sentence renders only under `ENABLE_PRO_TRIAL`.
- **The trial's length** (`frontend/lib/planLimits.ts`): `TRIAL_DAYS` is the one source for the
  paywall card, the signup gate, `PricingSection.tsx` and the /pricing CTA, note and FAQ, each read
  under `ENABLE_PRO_TRIAL` (the backend's `PRO_TRIAL_DAYS` defaults to 0).
  `tests/unit/planLimitsLockstep.spec.ts` follows the constant and the flag through the bindings a
  file gives them and reads each piece of copy whole, so a length typed anywhere in it fails.
- **Summary document** (`frontend/features/summaries/components/`): the risks notice says which case
  it is (no excerpt located, the filing text not available to check against, or a summary from
  before excerpts were located), each ending "Read the risk factors in the filing." A section's tone
  is one neutral Badge, "Management tone: positive" or "Management tone: cautious"; the section's
  index and heading are one group that never wraps, so a long heading wraps beside its index, and
  only the badge wraps, beneath the heading where the two do not fit (`SummaryBlocks.tsx`;
  `tests/e2e/text-floors.spec.ts` at 320px and at 390px with 200% text). A verified takeaway's panel
  says "The passage cited for this takeaway was found in the filing text."; the per-ADS ratio source
  is a visible "Ratio source:" line (`PerAdsNote.tsx`). The actions bar reads "Save summary", and a
  stored summary that did not finish offers neither it nor an export, only "Copy filing link"
  (`SummaryActionsBar.tsx`). SourceTrace's "Open in SEC EDGAR" link and its sheet's close button, and
  the actions bar's manual-copy link, carry the brand focus ring. The Risks section is a marked copy
  (D-044, `SummaryRisks.tsx`): a row whose excerpt the server located carries a bracketed marker on
  its heading, the marker's twin sits in the margin on its line, and the excerpt is a marked block in
  the filing's face; below a measure (a phone under 200% text) the margin gives way and the marker stays;
  a row not located keeps the plain quotation and no marker. A quote whose evidence
  the server located takes the marked block alone, in the filing's face, with no marker or twin, and any
  other quote keeps the neutral hairline (`SummaryBlocks.tsx`). The Source pane paints a passage the server
  located in the mark's tint and its 2 px hairline, the passage in the primary ink, and any other jump (a
  summary chip's section heading, an XBRL fact's) in the neutral find highlight, the reader's 22% sage with
  no hairline (`highlightInDom.ts`). Ask's answers and the Multi-Period narrative keep their chips. Gates:
  `brandCopyRules.spec.ts` rule 3 (the device's places, located rows only, one marker per row, its
  planted forms), `designSystemDoneGate.spec.ts` (Newsreader's surfaces), `highlightInDom.spec.ts`,
  `sourcePanePaint.spec.tsx`, `tests/e2e/risk-evidence-rows.spec.ts` and `tests/e2e/copilot-highlight-css.spec.ts`.
- **Ticker route** (`frontend/features/filings/components/TickerFilingsView.tsx`, the /filing/AAPL
  picker): a load failure reads "Filings unavailable" with a "Try again" held through its refetch; a 404 is
  "Company not found", read from the held error so a refetch cannot flip it; a first load paused
  offline is still loading, never not found; none prints the raw error. A filings failure under a
  loaded company is an inline Notice, "Couldn’t load the filings", with its "Try again", inside the "Recent
  filings" card. Each row's action is an "Open filing" text link on the identity strip's recipe, its
  hidden tail naming the form and the accession, and a Badge is a label, never a control
  (`tests/unit/badgeNeverAControl.spec.ts`, which reads a Badge and a control through their
  bindings and the control's whole face). The amendment link carries the brand focus ring.
- **Company page** (`frontend/app/company/[ticker]/page-client.tsx`,
  `features/companies/components/CompanySearch.tsx`, `features/peers`, `features/insiders`,
  `features/fundamentals`, `features/filings/components/FilingsHistoryNote.tsx`,
  `features/filings/components/FilingIndex.tsx`): a company that fails
  to load says "Couldn’t load this company" with "Try again" and never prints the raw error; only a 404
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
- **Dashboard and watchlist** (`frontend/app/dashboard/page.tsx`, `app/dashboard/watchlist/page.tsx`,
  `features/dashboard/components/*`, `features/watchlist/components/SummaryStatusBadge.tsx`): each
  watched company's card states its summary from the server's status (ready, being written, none yet,
  unavailable, failed) with a matching badge ("No summary yet", "Unavailable", "Needs regenerating" in
  sentence case), never from the regeneration flag alone; a failed load shows its error card with a
  "Try again" and no empty card (a run the server still reports as generating after it died reads as being
  written until tasks/todo.md E43 lands). The what-changed chips take `lib/financialTone`'s direction chip, the
  700-level gain and loss inks on their soft grounds with the sign kept, never sage, and the glyph is
  decorative. The feed lead names what it shows ("The latest annual or quarterly report from the
  companies you follow."), the limit banner states the account's own count and nothing about
  Pro's limit (F41, decided by the founder on 2026-10-15, D-040: "Unlimited" stays on the plan cards
  and the lines that quote it, the plan strip's "Unlimited summaries" on this page and BillingPanel's
  "Unlimited" among them, and the fair-use guardrail is stated once, app-wide: `PRO_FAIR_USE_LINE` in
  `frontend/lib/planLimits.ts`, built from `PRO_SUMMARY_MONTHLY_CAP` (the backend's `config.py` default), read by
  the /pricing FAQ and the filing page's monthly-limit card, D-046, `tests/unit/summaryPlanClaims.spec.ts`),
  the search card reads "Find a company by name or ticker", the plan strip's button reads "Manage
  billing", and the route error boundary is in sentence case with a generic line that names no route
  ("This page didn't load. The error has been logged."). Tickers are set in the data face.
  `earningsnerd/direction-text-tokens` (new ESLint rule) bans the 600-level gain and loss as text, and
  sage on a direction glyph it can see by its name, its import or a binding the file writes it to (on
  the glyph, on the element whose ink it inherits, or in a map that pairs it with its classes);
  `tests/unit/whatChangedChip.spec.tsx` holds the chip to the direction chip for the server's tone,
  which no lint can see, and `tests/unit/summaryStatusCopy.spec.tsx` holds the status sentences and the
  "Try again" through its refetch.
- **Notification bell** (`frontend/features/notifications/components/NotificationBell.tsx`): an
  alert reads "New 10-Q from AAPL", the form and ticker in the data face; the unread count rests in
  the ink, not on sage (D-030), while the sage dot still marks an unread row; the menu sits on the
  header's rung with the account menu.
- **Financial Highlights** (`frontend/features/summaries/components/FinancialMetricsTable.tsx`): a
  currency row keeps the precision it was served with, so a per-share "$7.46" no longer displays as
  "$7.5" (a Phase 9 fix; compact figures keep their rounding). The standalone card (the landing's
  evidence table) is titled "Financial highlights", in sentence case; the summary's own section
  heading is the backend's schema title.
- **Calendar** (`frontend/features/calendar/components/EarningsCalendarPage.tsx`, `MonthView.tsx`,
  `WeekView.tsx`): the coverage chip and the "+N more" and "Show fewer" controls rest in the ink,
  sage only under the pointer (D-030). `tests/unit/calendarCoverageChip.spec.tsx` renders the page
  on a bounded payload under the known universe: the chip shows there and nowhere else.
- **Counts elsewhere in the product** (D-030): the dashboard feed's "See all N companies" link, the
  check-email countdown, the period quick picks, the narrative's "Show the N source figures" summary
  and its bracketed Sources chip, the data notes' checked count, the peer rank and the summary's
  section index rest in the ink, and so do the values beside them: the filing viewer's "Showing ·"
  caption, which prints a section's name, and the "Sources & checks" links, which under the
  fundamentals chart print a figure's fiscal year. A What-changed chip on the dashboard is a figure's
  change, so it takes the direction chip above (its gain or loss ink with the sign), never sage. The controls among them that turn sage under
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
- **Exports** (`backend/app/services/export_service.py`, `pdf_branding.py`,
  `excel_export_service.py`, `analysis_export_metadata.py`): mastheads read "EarningsNerd · AI
  summaries of SEC filings". Titles take the middot and sentence case ("BIOGEN INC. · 10-K summary",
  "{company} · Multi-Period Analysis", the feature keeping its name), as do the PDF's source line
  ("Source: SEC EDGAR · {url}") and the CSV, which now carries that source row under its generated
  date; the PDF's closing note splits its one dashed sentence in two, and a quote's attribution
  sits on its own line in the PDF and follows a middot in the CSV, never a dash. The CSV now ends
  with the PDF's closing sentences, verbatim (D-046): after a blank row, the closing note's two
  paragraphs (the masthead line, then the disclaimer), a row each, read from the constant both
  exporters share (`SUMMARY_CLOSING_NOTE`). Tables read as the page's reader tables do
  (D-041, applying D-030): headers in the tertiary ink on no fill, hairline rows and no grid, and a
  column of figures right-aligned in the data face, each figure on one line, where the page sets
  one: the Financial Highlights table's Current Period, Prior Period and Change by name, as
  FinancialMetricsTable does, and any other table's by the page's numeric-column rule; quotes sit on
  a neutral hairline. A PDF link rests in its line's ink with an underline, as the page's prose
  links rest, because print has no pointer to turn it sage, so the wordmark's "Nerd" is the only
  sage text in the exports. The PDFs carry Inter's italic beside its roman
  (`backend/app/assets/fonts/Inter-Variable-Italic-latin.woff2`, the same 4.001 build and latin
  subset), since WeasyPrint never slants a face it lacks: without it the wordmark's "Nerd" and every
  quote printed upright. The workbook's header rows rest in the ink on the neutral ground and its
  labels in the ink. The tertiary ink is its token (#636A77, 4.80:1 on the masthead's tint).
  "Sources & methods" is in sentence case wherever it is named; the data notes print a clause for
  each count that is not zero, singular at one, and the passed count only when no figure needs
  review; a window reads "FY2022–FY2024 · 3 periods"; an operand's fields read "Accession", "Source
  tag" and "Filed", and its concept reads as words. The masthead's mark is held to the canonical
  outlines, with no transform anywhere in either PDF's stylesheet, by
  `backend/tests/unit/test_pdf_mark_geometry.py`; every export colour value to a token in its role
  (no colour function, colour keyword or indirection), the grounds to the page and the masthead's
  tint, every text colour to 4.5:1 on each, sage to the wordmark's "Nerd", every rule that can
  style a PDF link to the ink with an underline, and the italic to an italic face (the family
  declares one, each face's file is the style it is declared as, and every font a rendered PDF
  embeds for italic text is an italic program) by `test_export_palette_parity.py`, which reads a
  stylesheet as WeasyPrint does, nested and conditional rules included; the rendered copy (no em-dash but
  the null token, no exclamation mark or emoji, the headings the exports own in sentence case) by
  `test_export_voice.py`; the eval's blinding of the generation date by a case in
  `test_acceptance_readiness.py` that runs it on a real export; and the backend's hand-composed
  wordmarks to the PDF's and the mail's by `wordmarkSingleSource.spec.ts`.
- **Mail** (`email_service.py`, `app/routers/contact.py`): footers read "EarningsNerd · AI summaries
  of SEC filings"; the waitlist subjects lose their exclamation marks and emoji; the verification
  mail ends "Verify your email address and you can start reading."
- **Toasts** (`frontend/app/providers.tsx`): every toast is a panel card on the tokens, on the
  overlay step of the elevation ladder (`e4`), in the theme the reader chose on the site rather than
  the OS setting; a status toast (success, error, warning, info) keeps the panel
  and colours only its icon, in its status ink (Sonner's own rich colours are off).
- **Feedback widget** (`frontend/features/feedback/components/FeedbackWidget.tsx`): the three kinds
  read "Bug", "Idea" and "General", without emoji, on the token hairlines; hover brightens to white
  in light, never darkening to the page ground.
- **Chart fallback** (`frontend/components/ChartErrorBoundary.tsx`): "This chart could not be
  drawn." in the Card recipe on the filing page, where the boundary wraps one chart with no
  table below it; "These charts could not be drawn." on Multi-Period Analysis when it wraps a grid of more
  than one chart panel (MetricsTable sits below, outside it). It says only what failed.
- **Checkbox** (`frontend/components/ui/Checkbox.tsx`): one recipe for the consent dialog and the
  admin invites page, with a checked fill that holds 3:1 in dark (it was 2.2:1): Light Sage under a
  navy check, as the Primary button pairs them.
- **Status chips** (`frontend/components/ui/Badge.tsx`): `success` and `error` variants for status
  (D-032). The watchlist and dashboard rows say "Ready" on success and "Error" on error, and
  "Unavailable" and "Needs regenerating" on warning; no status borrows the gain and loss colours.
- **Error copy** (`frontend/lib/api/client.ts`): a lost connection reads "Could not reach the server.
  Try again in a moment." instead of naming the backend and its URL, and a validation error shows
  its first message instead of "[object Object]".
- **Settings and subscription** (`frontend/features/settings/`, `frontend/features/subscriptions/`,
  D-033): Filing alerts offer only what the alert jobs read. The digest row states "Daily" in the
  data face ("Alerts that aren't real-time arrive in one email a day.") in place of a frequency
  select no job honoured; real-time alerts read "An email from the hourly filing check, instead of
  the daily digest." and 8-K alerts "Current reports on material events." The Pro list in the
  upgrade dialog is one shared string, and every plan list (the dialog, the /pricing and landing
  plan cards, the /pricing Product JSON-LD) names Multi-Period Analysis only through
  `lib/planLimits.ts`, read through its `shipped()` while that flag ships it (D-040). The trial
  banner and the billing panel state the trial's end date ("Your Pro trial ends Jun 25, 2026."),
  never a countdown, and the banner shows only while the resolved plan is a live Pro trial. In
  settings and the subscription surfaces, commerce carries the Lightning glyph (the Pro badge, the
  trial banner) and "Analyze trends" a chart glyph; the sparkle leaves commerce there (D-031 records
  that it has no sanctioned site until an AI-summary chip exists), and #1295 takes it off the
  Copilot's two upgrade buttons (`CopilotMessage.tsx`, `CopilotTeaser.tsx`). The dead
  SubscriptionGate is gone. The locked overlay reads "Upgrade to Pro". Section headings in settings
  and on the dashboard carry no icon. The dashboard answers a finished checkout ("Pro is active", or
  "Checkout finished" with "Your plan updates in a moment. Reload this page if it still shows Free."
  while the query still says Free) and pricing a cancelled one ("You returned from checkout", then
  "You can choose a plan below." or, for an account already on Pro, "Your plan is Pro."), reading
  only the subscription query and the return URL, which says nothing about a charge. Each page drops
  its return flag from the address once read. On /pricing a signed-in Pro account's Free card names
  the plan, "Free plan", disabled, where it read the guest's "Request an invite" (gate:
  `PricingPage.spec.tsx`).
- **Ask this Filing** (`frontend/features/filings/components/copilot/*`, `features/filings/api/copilot-api.ts`,
  D-034): the teaser, the end-of-summary callout, the coachmark and the rail's empty state claim only
  what the answer card shows ("Cited passages you can check against the filing", "XBRL citations name
  the tag they came from", which had said figures show their tag though an answer can carry an uncited one, and "Answers come from this filing, with cited passages you can check.",
  the one sentence the rail, the callout and the coachmark import as `COPILOT_CLAIM` from
  `copilotClaim.ts`), and so does the Pro section's Ask row ("The answer comes from that filing, with cited
  passages you can check", in `ProDepth.tsx`, which had said the answer cites the figures and passages
  it used), and so does the pricing page's Pro line ("Ask this Filing, with cited passages you can check",
  which #1311 had set as "with cited answers"), and the summary's suggested follow-ups say "Tap a question to ask this filing."; the teaser's blurred
  sample is Apple's FY2025 Services answer with sequential [1] and [2] markers and "2 matched
  sources", cited to passages because the Services figure is a dimensioned fact the Copilot tool cannot
  fetch, while the landing's Ask demo (#1311) answers total net sales with XBRL chips; §1's Sample data
  row says which is which (`landingSamplesVerified.spec.ts` holds the teaser to its kind). The product has one name: "Ask this Filing" on the launcher, the rail and the upgrade
  dialog, "ask this filing" in a sentence, and the usage lines say "free questions" and "Upgrade to
  Pro", with Pro's monthly cap read from the usage response, never "unlimited". A spent allowance,
  a Pro-only gate and the Pro fair-use cap are a quiet answer card with role="status" and the
  server's sentence (a lightning "Upgrade to Pro" except at the fair-use cap), announced because the
  reading card it replaces is already that status region; the error tint stays for real failures. XBRL source rows carry the braces, Ask controls the chat glyph (the landing's Ask demo
  header too, which drew the quotes, a passage's mark) and an upgrade button that carries a glyph the lightning; the in-text marker and every source-check label are 12px; the callout is an inset well
  without an icon tile; the answer counts its matched sources once. Every control in the rail, the
  answer and the reader carries the brand ring. The unused reference renderer `AskFilingAnswer.tsx`
  is gone; DESIGN_SYSTEM.md's "Ask answer" now describes `CopilotMessage`. Gates:
  `oneProductName.spec.ts` (no copy literal says the name in any case: "Copilot" and "co-pilot" in any
  literal, and "copilot" in JSX text, a string of more than one word or a template part open at a
  substitution edge, joined to punctuation or not, so "free copilot questions" and "Ask the copilot: what
  changed" fail while a one-word identifier such as `copilot_question_asked` or `copilot:paneWidth` and a
  class list do not; a one-word copy literal such as `title="copilot"` is its known limit; its residue
  is empty since D-046's /security change named the feature "Ask this Filing"),
  `brandCopyRules.spec.ts` rule 1 (on every surface under app, components, features, hooks and lib, in
  one sentence of one literal with its whitespace collapsed, or of one element's inline children read
  together (`<p>Every answer is <strong>cited</strong> to the filing.</p>`), whatever scope phrase follows:
  no answer, response or reply called cited, citable, grounded, exact, verified, verifiable, sourced or
  backed, under each, every or all, through a copula with any adverb between ("Answers are now cited"),
  set off after its noun ("answers, each cited") or before it ("Grounded answers"); none said to cite; no
  citation or source promised for them ("Sources for every answer", "Answers with citations", "No answer
  without a citation"); no "each" or "every" before "exact", no "never guessed", no "verifiable in one
  click"; another word for the same promise ("Every answer comes with receipts"), a claim past a pattern's
  reach (40 characters, 20 between an answer and the citation it comes "with") and one split across
  separate literals stay review-checked, its self-check pinning them passing, and a negated quantifier
  ("Not every answer is cited.") or an adverb that hedges ("Answers are rarely cited") fails closed while
  "not" and "only" pass ("Answers are only cited where a passage matched."), `copilotClaim.spec.tsx` (the rail, the callout
  and the coachmark render the one sentence, and no other literal types it), `planLimitsLockstep.spec.ts`
  (no "unlimited" in the Copilot's directory and, anywhere under app, components, features, hooks and
  lib, in one literal or one element's inline children read together, a wrapped line included, no list
  "unlimited" heads, read to the sentence end, with an item that names a question, answer, Ask this Filing,
  Copilot or Q&A noun and no count of its own, and no such noun up to 30 characters before it; the pricing
  metadata, which #1311 shipped as "unlimited 10-K and 10-Q analysis, exports, and filing Q&A" and
  "Unlimited AI summaries …, filing Q&A, …", now gives filing Q&A a sentence of its own, "Pro also
  includes filing Q&A."), `dataXsAllowlist.spec.ts` (data-xs
  sites listed with counts, their totals an equality cap lowered in the same commit as each shrink; the
  marker and the source-check labels are 12px) and
  `CopilotMessage.spec.tsx` (the plan card is quiet, a real failure keeps the tint).
- **Admin invites and feedback** (`frontend/app/admin/`, `frontend/features/admin/components/`): an
  invite is "created", and "emailed" only when Email invites was on and the backend's best-effort send
  went through (the API's `emailed` flag). A batch reads "3 invites created · 3 emailed", "3 invite
  links created" with email off, or warns "3 invites created · 2 emailed. Copy the rest from the list
  below."; the results head "3 created · 2 emailed" and mark each link still to share "Not emailed";
  the resend dialog says "Invite re-sent" and "We emailed it to {email}." only when it was emailed,
  "New invite link ready" otherwise. A link-only row's actions are named "Resend this link-only
  invite" and "Revoke this link-only invite". The empty lists are one plain line in the card ("No
  invites yet. Send your first one above.", "No feedback yet. Reports appear here as people send
  them."), a failed load is a Notice with "Try again", and the section headings carry no icon. The status
  chips put the status ink on the quiet ground (DESIGN_SYSTEM.md §4), the feedback type chip beside
  them takes the same quiet ground in dark (no fill, its hairline kept) and Badge's metrics, so the
  row's two chips share one weight, "New" feedback takes an unread envelope in place of the sparkle,
  an already-invited chip reads "· already invited" in its own ink, and the remaining admin controls
  carry the brand ring (`statusChipContrast.spec.ts`, `inviteOutcomeEmailed.spec.tsx`,
  `siteChromeFocusRing.spec.ts`).
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
  the calendar, and `tests/unit/calendarEventRow.spec.tsx` holds the row without a marker. Every
  estimated row shows its "usually" note, the lane's glyph and the words on a line of their own, in
  the week sheet as in the day list and the day dialog, so the footer's sentence describes what the
  rows show. At 200% text nothing is clipped or overlaps: each view picks its layout by its own
  width in em (the day list in place of the sheet, a stacked row without its decorative logo, a month
  day's count of reports in place of its tickers, which a caption says), names wrap instead of
  truncating and the range label wraps between whole dates (`calendarReflow.spec.tsx`,
  `calendarEventRow.spec.tsx`). The bell's popover is placed from its measured height inside what the
  reader can see, scrolling inside when neither side of the bell holds it whole
  (`BellPopover.spec.tsx`).
- **Full-text search** (`frontend/app/search/page.tsx`, `features/search/components/FullTextSearch.tsx`):
  the form code is set in the data face, not as a chip, and `earningsnerd/no-form-code-badge` now
  flags a hand-rolled eyebrow chip around a form as well as a `Badge`, alone or leading a meta line
  such as Notable filings' "{form} · filed {date}" (its form code moved to the data face
  with it). The form toggles, "Clear dates" and "Try again" (a `RetryButton`) carry the brand ring, the
  result rows an inset one inside the clipped list. The rows and the unselected form toggles brighten
  on hover to the row tint (`brand-weak`), never darken. The field stops at the length the backend
  accepts, and `tests/unit/searchQueryLimitParity.spec.tsx` reads that bound from the router; an
  error shows the backend's own detail, or the surface's sentence ("Search did not load. Try again
  in a minute.") when the body carried none, a bodiless 503 or 413 included. The description no
  longer promises every filing, and the title is in sentence case. At 200% text a row's company
  name wraps under its ticker in the primary ink (in both themes), each date and form code stays
  whole, and a middot keeps to the fact before it, so no line starts with one; each fact, its label,
  its value and its middot, is one run, so a line breaks between facts, and inside one only when it
  alone is wider than the line; the error alert's
  glyph keeps its size, its message takes its column's whole width and breaks a long token, and
  "Try again" ("Trying again…" while busy) sits on its own row under it, inside the alert
  (`full-text-search.spec.tsx`). The two date fields take the Input primitive's 14px text and shrink to their
  row: in the forms plugin's 1rem, with the blank room Chrome keeps in a date field for a six-digit year, each was
  312px in a 256px row at 320px under 200% text and the page scrolled to 344px (E81,
  `tests/e2e/reflow-200.spec.ts`).
- **Multi-Period Analysis** (`frontend/features/analysis/*`, `frontend/app/analysis/page.tsx`): the
  fair-use cap is stated once, in the narrative card, with no plan link; "See plans" stays only beside
  the 403 "Pro feature" gate, and the page's three inline links (Log in, See plans, Terms) carry the
  brand ring. The Cached badge says what it knows in a visible line beside it, in muted ink, never
  a title tooltip: "Served from an earlier run · regenerates if these figures change". A stale export reads "This report is out of
  date. Run analysis again before exporting."; a report whose evidence will not decode gives the one
  recovery sentence ("The analysis evidence could not be read consistently. Run analysis again to
  reload the report."), and a refused run with no detail says "The analysis did not start. Run it
  again." The chart axis captions are "Fiscal year" and "Fiscal quarter". The chart PNG's footer is
  the logo's lockup: the bare mark at 25px tall (about 32px wide, its minimum), then "Earnings"
  upright and "Nerd" italic 600 in the accent, drawn opaque in the bottom-right corner (D-039). The "up to 10 fiscal years or 12 quarters" caps, and
  the /pricing Pro card's "10-year trends", are written from `lib/planLimits.ts`, which mirrors
  `ANALYSIS_MAX_ANNUAL_PERIODS` and `ANALYSIS_MAX_QUARTERLY_PERIODS` in `backend/app/config.py`
  (`planLimitsLockstep.spec.ts`: no copy types a count of years or quarters, in digits or in words up to
  twelve, spaced, hyphenated or split across markup, outside the privacy policy's retention periods; its
  header names the forms it leaves to review, each planted in its fixture).

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
PDF cover (A4, with the fields the backend fills named), the email header (a fluid column up to
600 px, inline styles) and the A5 notebook cover (SVG with its preview). Every figure in the folder is
from the verified FY2025 set; every colour is a token; the mark's paths are byte-identical to
`earningsnerd-mark-mono.svg`. Two decisions were taken while checking them: the notebook's margin
carries no printed bracket marks, because a cover has no text for them to twin (D-016), and the
email footer uses the app's own sentence form of the disclaimer (D-017). The mail's line now names
filing data alone, "Filing data sourced from SEC EDGAR. Not investment advice.", since an
earnings-day alert carries a provider's report dates (D-043), and its page is fluid up to 600 px
(D-042). Each mail opens with a hidden preheader of its own, the line most inboxes list beside the
subject, so none is listed by the header's words (D-047). Under a phone's text zoom the header's wordmark
wraps between its two words and the tagline's mark inside itself, so the header fits a 320 px screen at
200% (D-048).

## 6. The founder slot

The dormant slot has been retired: its empty configuration, component and hero mount are
removed. It rendered nothing under the committed configuration, so the landing page's visible
content is unchanged. The brief's reader-quote slot stays unrendered
([01-interview.md](01-interview.md) A5).

## 7. Notable filings

The section left `app/page.tsx` on 2026-10-11, because the week's list read as microcap 8-Ks under
a "high-signal" heading (audit T7), and returned under the curation rule the founder decided
(D-046, §8) in two halves (E90). The backend's query serves the rule (#1437): the past week's 10-K
and 10-Q filings, from companies whose stored issuer holds a summary the filing page shows (D-052
reads "a full summary" so), newest first, one per company, at most six, and an empty list while its
flag is off, in a week with fewer than three such companies, or on a failed read. The landing
mounts the section after Reporting this week as a ruled row (D-045, §1). Its line says what the
query serves, "The past week's 10-K and 10-Q filings from companies with a summary to read, newest
first.", where the section once said "High-signal SEC filings from the past week, across the whole
market."; its filings are hairline lines in Reporting this week's anatomy, two across from 40rem
at the reader's text size, each opening its company page as before: the mark at 32, the ticker in
the data face with "10-Q · filed Oct 20, 2026" where Reporting this week has its day (sharing the
line while both fit, dropping beneath the ticker when they do not), and the company's name beneath,
truncating, through `formatCompanyName` as Reporting this week and the Filing identity line print it. The form code is one unbroken run
that the middot after it keeps to, and the date states the filing's day as the Filing identity line
does, through the same helper (`formatLocalDate`): a day with no time, the same in every time zone
and never stale on the cached page. The date moves under the code whole before it breaks, holding
the month and day as one run as the hero's identity line does, so under 200% text no line breaks
the code, starts with the dot or reads "filed Oct" over "20, 2026". There is no reason chip: under
D-046 it could only gloss the code the row's line already names (chief design's review of #1461).
With an empty list or a failed read it renders nothing, so it takes no number among the rows. The
mount gate (`tests/unit/landing-sections-mounted.spec.ts`) holds its place and the slot it is fed,
and `tests/unit/NotableFilings.spec.tsx` holds it to the lines it is served and to Reporting this
week's anatomy.

## 8. Decided by the founder

- The Multi-Period demo (`frontend/features/analysis/demo/demo-analysis.json`, the analysis
  teaser's sample and the landing's samples) ends at FY2024, and its own comment calls its figures
  approximate; it is to be regenerated through the pipeline to FY2025, not edited (D-046, E93).
- §7's curation rule: 10-K and 10-Q filings only, from companies that hold a full summary, newest
  first, at most six (D-046, E90). It landed in two halves: the backend's query (#1437, under
  D-052's reading of "a full summary") and the ruled row after Reporting this week.

The landing composition (tell T4) is decided too, and landed: ruled rows after the hero (D-045, #1398).

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

Seven gates added or widened by the copy and signal gates PR (D-031), each with a mutation proof in
that PR:

- `no-em-dash-copy.spec.ts`: a literal is exempt only when it is exactly the bare missing-value
  token (a lone em-dash) and stands alone: as a JSX child, written as text or as an expression (a
  conditional's branch or a fallback included), only as the sole child of its element, and never as
  an operand of `+`, a template's substitution or a part of a template; a token held in a `const` is
  followed to each reference of the name in its file and fails where one is joined into copy (a
  reference in another file is review-checked); the summary's quote attribution loses its dash: on the page
  the cite sits on its own line under the quotation, with the evidence chip (a control, not
  attribution) beside it when the quote carries evidence, and in the PDF the speaker stands alone,
  the one device D-031 names for both (the CSV keeps a speaker column).
- `brandCopyRules.spec.ts`: the public scope is walked from the public routes through the import
  graph (`tests/unit/importWalk.ts`), not listed, so a product component a public page renders
  (SourceTrace, FinancialMetricsTable, CompanySearch) is held to rule 1c, the one rule read on the
  public scope alone (rule 2 reads the whole app under D-030).
- `brandVoiceRules.spec.ts` (new): sentence case (a capital first word, no capitalised word after it
  but a proper noun, never an all-caps label) on headings h1 to h6, dialog and card titles
  (`ModalHeader`, `CardTitle`, `CardHeader`), the title prop of `GuidanceCard`, `Notice`, `Modal`,
  `SecondaryHeader` and `UpgradeModal`, button labels (a `<Link>` or `<a>` whose className reaches
  `buttonVariants()` included), every aria-label and meta titles, plus the components found across
  the tree to render their children or title into one of those; a label passed through a renamed
  variable, a spread or a helper function, or a className styled through a variable, is
  review-checked (`lessons/test-gates-must-be-as-wide-as-their-rule.md`); no exclamation mark, emoji or banned
  buzzword in copy, a placeholder included; no icon inside a heading (an icon imported from `lib/icons` or
  the Phosphor package under any name or through a namespace, or a tag named for one); no developer wording
  ("backend", an API path, "reader", an HTTP status) in `lib/` and `hooks/`.
- `reservedGlyphs.spec.ts` (new): the quotes glyph marks a filing passage and the braces an XBRL
  fact, nowhere else; the sparkle belongs to an AI-summary chip, which does not exist yet, so it has
  no sanctioned site: the two heading sparkles in `StreamingSummaryDisplay.tsx` stay listed only until
  brand-filing-page removes them and drops their entry in the same merge; a hand-drawn stand-in or
  the ✨ emoji counts.
- `backendMessageMatches.spec.ts` (new): every phrase the frontend routes the paywall, the no-retry
  path, the verification event or the dashboard's sign-in redirect on is written by the code that
  raises the message (docstrings do not count), or is listed as unsourced with its reason (the contact
  form, once matched on "429", reads the status since #1303). No other literal match exists in the
  api modules (`lib/api`, `features/<domain>/api`), nor anywhere under `app`, `components`,
  `features`, `hooks` and `lib` on a receiver named for an error or a message (err, error, message,
  msg, detail or reason, read through camelCase such as `errorMessage`); a message held under another
  name outside the api modules is the scan's limit.
- ESLint: the raw-colour rule reads `rgb()`, `rgba()`, `hsl()` and `hsla()` in either case as well as
  hex (a 3- or 4-digit hex inside an arbitrary utility or as a whole literal, where it can only be a
  colour), in an arbitrary utility too; `earningsnerd/locale-pinned-numbers` (new) bans an unpinned
  `toLocaleString()`, `toLocaleTimeString()` or `Intl.NumberFormat`, and one pinning any locale but
  `'en-US'` (another locale, or a variable), everywhere, `lib/format.ts`
  included, since its formatter cache pins en-US (`fmtCount`, `fmtDecimal`, or a date helper for a date); `toLocaleDateString()` was already banned
  outright by the date rule in `eslint.config.mjs`, which names `formatLocalDate`.
- `siteChromeFocusRing.spec.ts`: the page scan discovers every route's page and the feature
  modules it reaches, in place of the named routes (`PAGE_CONTROL_ROOTS`).

Four of them carry a shrink-only residue: `VOICE_RESIDUE`, the glyphs' `RESIDUE`, `RING_RESIDUE`
and the matchers' `UNSOURCED`. Each holds what the audit found when its gate landed, counted per
file, with the PR or the reason that clears each entry; a fixed entry fails until its count is lowered, and each
list's size must equal its cap, so a PR that shrinks a list lowers the cap in the same commit and no
slack is left. `UNSOURCED`'s cap moved once with the scan's reach, the day the scan reached the
dashboard boundary and the contact form. A PR that adds an entry raises the cap and gives its reason
in its body.

The design gates
(`designSnapshotParity.spec.ts`, the ESLint design rules, `no-em-dash-copy.spec.ts`,
`wordmarkSingleSource.spec.ts`) run unchanged against the new surfaces; their tails are in the
handoff ([README.md](README.md)).
