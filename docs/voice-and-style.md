# Voice and style

How EarningsNerd copy is written. This applies to every user-facing English string: page
copy, headings, buttons and CTAs, empty/error/loading states, tooltips, form helper text,
toasts, meta titles and descriptions, email subjects, export mastheads. The product is openly
AI-powered; say so plainly. The copy sounds like the person who read the filing and checked
the numbers: a careful, dry, numerate colleague, pleased to have checked, never in a hurry.

The brand strategy this serves is `docs/brand/03-strategy.md` (positioning S1, the values as
behaviours S2, the personality spectrum S3, the promise "I can check it" S4, the never list S5).

## Reference texture

Three kinds of real writing, and what each lends:

- **A good footnote.** It states the fact, the basis and the exception in one breath, and it
  never apologises for being specific: "Services net sales include amortization of the deferred
  value of services bundled in the sales price of certain products." Lend: precision as
  warmth; the exception stated, not hedged.
- **A plain shareholder letter.** First person, short declaratives, a reason behind every
  number, no adjectives doing the work of evidence: "We paid $15.4 billion in dividends. We
  bought back more than that." Lend: the reason, the "because", the willingness to say "we".
- **A deadpan finance newsletter.** The joke is in the understatement and the aside, never in
  the punchline, and the numbers are always right: "Operating cash flow fell while net income
  rose. Worth a look." Lend: the dry aside, rationed.

Together: short, specific, confident, plain, with a pulse. Headlines of a few words, subheads
of one plain sentence, claims backed by a figure with its source, no throat-clearing.

## The four rules

1. **Short.** Headlines a few words. One idea per sentence. If you wouldn't say it aloud,
   cut it.
2. **Specific over abstract.** Name what the product does and who it's for. Prefer a real
   detail or number ("10-K and 10-Q summaries", "5 summaries a month") to a vague benefit
   ("actionable insights"). Say what was checked and against what: a figure the server
   matched reads "SEC XBRL", a risk excerpt it could not locate is "withheld".
3. **Confident and plain.** Lead with the user's outcome. State the AI plainly without
   over-explaining it. Drop the hype. No exclamation marks.
4. **Restraint over decoration.** Cut adjectives that don't earn their place and any
   sentence that only exists to set up the next one. No emoji in headings or banners.

## Tone rules and the humour floor

- **Scope once, as a behaviour.** Say what the product does with what it could not check,
  once per surface, in the product's own words ("where we could not match it, we say so";
  "N withheld"). Never repeat the scope as a hedge in every sentence. The audit counted sixteen
  hedge sites on one page (`docs/brand/00-audit.md` T2); the ceiling is one.
- **Colleague, not oracle.** "Here is where it says so", never "trust us". The product shows its
  work; the copy points at it.
- **Patient.** Filings arrive on a schedule and the reader is not late. Never "markets move
  fast", never a countdown, never "before the next call".
- **The humour floor.** Dry, and only dry. One wry line per surface at most, carried by
  understatement or an aside ("Worth a look.", "Reading the size-8 fine print…"). Never a joke
  about money, a company, a loss or the reader. Never where the moment costs the reader
  something: the monthly-limit card, a failed generation, a billing or security email. Never
  inside a summary, a chip, a tally, an export or anything that quotes the filing. The loading
  quips are the one sanctioned playful surface.
- **First person is allowed and rationed.** "We" for what the product does ("we say so");
  the founder stays absent from website copy ([A5](brand/01-interview.md#3-the-answers-in-force)).
- **The filing's words are the filing's.** Quote them exactly, in quotation marks, in the
  filing's face; never paraphrase inside quotation marks; never recase a quoted heading.

## Do and don't, from the live site

| Don't (as it was on 2026-10-11) | Do |
|---|---|
| "Nine-part summaries use selected filing text and available XBRL data, with source labels where a match is found." (hero subhead) | "Figures are checked against the company's XBRL where they can be, and quotes against the filing's own text." |
| "Where the numbers come from" (section heading) | "Figures with their receipts." |
| "Source labels show when financial metrics match filed XBRL data. Where supporting evidence is available, citations connect excerpts to the filing. The summary is built from selected filing text and available structured data." | "Each row in the highlights carries a label: SEC XBRL when its value matched the company's XBRL fact, Cited when it points to the filing without that match. A quote reads Verified in filing only when its words were found there." |
| "Speed matters. Markets move fast. You need clarity before the next earnings call." (waitlist) | "Filings are long. The signal is spread across a hundred pages, and checking a number takes an afternoon. We read it with you and point at the passage." |
| "Join 0+ others on the waitlist" | (nothing, until the count is worth saying) |
| "Choose the plan that fits your workflow" (pricing subtitle) | "Summaries are generated once per filing and shared. That is what makes unlimited reading possible at this price." |
| "You're on the EarningsNerd waitlist! 🎉" (email subject) | "You're on the EarningsNerd waitlist" |
| "Please verify your email address to unlock AI-powered SEC filing summaries." | "Verify your email address and you can start reading." |
| "We couldn't find this page. The link may be mistyped or out of date." (404) | "We looked. The link is mistyped or out of date. Start from the homepage search, or open your dashboard." |
| "Scanning 400 pages of footnotes so you don't have to…" (loading quip) | "Reading the footnotes so you can go straight to the ones that matter…" |
| "Explore SEC filings with AI-assisted summaries." (footer) | "The summary that shows its work." |
| "Generated by EarningsNerd — AI-Powered SEC Filing Analysis" (export masthead) | "Generated by EarningsNerd · AI summaries of SEC filings" |

## Headlines

The hero headline is a PostHog copy test (`frontend/features/marketing/lib/headline.ts`).
Variant A ships in the HTML and survives the brand work; the five below are the lines that may
replace or extend B and C. Each is under eight words and a claim the product keeps:

1. "The summary that shows its work." (the tagline; also variant C)
2. "Read it faster. Check it anyway." (variant B)
3. "The summary, with the filing beside it."
4. "The 10-K, read for you, with receipts."
5. "Numbers you can check, not trust."

**Tagline:** "The summary that shows its work." It goes under the wordmark on the social card,
the business card, the footer and the merch; it is the positioning in six words.

## Dashes

- **No em-dashes (—) in copy.** Restructure the sentence instead of swapping in another
  dash: split it into two sentences, use a colon, or just cut the aside.
- **Hyphens stay** in compound terms: 10-K, real-time, cold-start, day-of.
- **En-dashes (–) stay** in genuine numeric or date ranges: Q1–Q4, 30–60s, FY2019–FY2024.
- **The bare `—` null-value token stays.** Tables and detail rows render `—` for missing
  data (see `MISSING_TOKENS` in `frontend/lib/format.ts`). That is a data convention, not
  prose. It is the only sanctioned em-dash, and it stands alone, in a cell or an element of
  its own: never with a unit after it, a sign before it or a middot joining it to a label. It
  renders through one element, `MissingValue` (`frontend/components/ui`), which hides the
  token from assistive tech and gives it words: "unavailable" by default, the word the
  analysis evidence uses for a missing figure, or the site's own where that would claim more
  than its data says ("no cohort", "no role listed", "Not included"). A figure that sits in a
  line of copy and can be missing gets words, or the element. Two CI gates hold it:
  `frontend/tests/unit/missingValueToken.spec.ts` fails the token rendered anywhere but the
  element, and `frontend/tests/unit/no-em-dash-copy.spec.ts` exempts the bare `'—'` only where
  it stands alone, reads a same-file formatter's fallback where the formatter is called, and
  reads a fragment as its contents. An element is one value to the em-dash gate, so the
  element set beside a unit (`{count ?? <MissingValue />} sh`, which still reads "— sh")
  passes it and is review-checked, as are the other forms each gate's header lists out of
  reach.

## House conventions

- Meta titles: `Page name | EarningsNerd`.
- Compact label separators use the middot: `AAPL · 10-K`, `Free for beta members · no card
  required`. Never an em-dash.
- Card and section titles are sentence case (also a DESIGN_SYSTEM.md rule).
  One exception: a risk row's heading is quoted filing text (a verbatim prefix of its excerpt,
  `excerptHeadings` in `features/summaries/lib/riskTitle.ts`, cut by `riskHeadline.ts`), so it
  keeps the filing's own casing and is never recased in a copy pass.
- The summary's section titles are the schema's (`backend/app/services/summary_schema.py`:
  "The Print", "Results That Matter", "Forward Signals", "Notable Footnotes" …) and keep their
  casing everywhere they are named, including on the sales page.
- "AI-powered", lowercase p, except at the start of a sentence or in title-case page titles.
- Ellipsis character `…` on loading states ("Logging in…") is fine.
- One retry verb ([D-032](brand/decisions-log.md)): "Try again", and "Trying again…" while it runs, on every
  retry control and in the copy beside it ("Try again in a moment."); never "Retry" or "please retry".
  `frontend/tests/unit/busyControlsStayFocusable.spec.ts` fails another label, busy text or "retry" in copy.
- Buzzwords to avoid: unlock, seamless(ly), empower, effortless(ly), supercharge, transform,
  actionable insights, decision-ready, game-changing, "in today's fast-paced world". Say what
  the thing does instead. Add: "signal" as a noun for the product's output, "edge", "clarity"
  as a promise, and any sentence whose subject is the market.
- Vocabulary the product owns, use it as the product does: "located in the filing",
  "matched the company's XBRL", "withheld", "checkable", "cited", "the filing's own words",
  "Full summary". Never "verified" without a match behind it.
- The account verb is "Log in": "Log out", "logged in", "logging in" (D-046). "Login" is the noun
  ("the login page", "Login failed"), and "sign up" is registering, so it stays. Never "sign in" or
  "sign out" in any form, "Signing you in…" and "Sign back in" included.
  `frontend/tests/unit/brandVoiceRules.spec.ts` fails it in copy, a lowercase message, a character
  reference and the copy attributes of markup a module builds (an aria-label, an alt, a title, a
  placeholder) included, except eight forms its header names as gaps: the two words split around an
  expression, across literals joined with `+` or around an element; a noun between them ("Sign other
  devices out"); a letter from another script; and, in a lowercase string shaped like a class list,
  the verb joined into a longer word by a hyphen, a slash or a colon ("sign-in-related",
  "sign-in/sign-up", "auth:sign-in"), as a class joins its parts. Copy in a JSON module stays
  review-checked. On the backend, `backend/tests/unit/test_user_facing_copy_voice.py` fails it in every
  literal of the files it reads, `app/routers`, `app/services`, `app/dependencies.py` and `main.py` (a
  module of text for the model is read for its copy alone, and markup by its text and its attributes
  that are not code), with the forms its header names as gaps and false positives; the messages
  `app/schemas`' validators raise are outside it. Its exempt list holds the two sites that still say
  it: the unlink detail's "only sign-in method", which the locked `test_auth_flow.py` pins (F56), and
  the OAuth-linked mail, which takes the verb in E46.

## Claims

- Preserve every factual and product claim exactly: prices, plan limits, coverage, retention
  periods, response times, security certifications. Never invent features, capabilities,
  metrics, pricing, or testimonials.
- If a claim can't be confirmed, leave it unchanged and flag it. Never restate an unverified
  claim more confidently.
- Cut hedges, keep scope. "Where a match is found" is a hedge when it repeats; "where they can
  be checked", "checkable", "up to nine parts" and "with a ticker on SEC EDGAR" are scope, because
  the code checks only some figures (`backend/app/services/provenance_service.py`,
  `build_metric_source`), drops a summary part the filing has nothing for, and searches only SEC's
  ticker file. A rewrite may move scope into plainer words; it never deletes it.
  `frontend/tests/unit/brandCopyRules.spec.ts` fails on "each figure" or "every figure" without
  the scope beside it, and on a promise of nine parts for every filing.
- Of a summary's quotes, only risk excerpts are withheld when the filing's text does not match
  them. A Forward Signals quote stays on the page, labelled Cited, while `AI_FORWARD_QUOTE_GATE`
  is off (`backend/app/services/ai/forward_quote_gate.py`). So a public surface promises "located
  or withheld", or "the filing's own words", of risk excerpts only; the same spec fails on that
  promise made of quotes in general. Arming the gate is what would widen the claim.
- A sample figure on a sales surface is verified against the filing's XBRL and carries its
  filing identity; a quoted passage is verbatim from that filing (`docs/brand/00-audit.md` §4
  records the current set).
- Legal body text (privacy, terms) is not restyled in copy passes. Legal wording changes go
  through their own review and bump `lib/legalDates.ts`.

## Copy that is also code

Before editing a string, check what it's wired to:

- Strings compared in logic (the `delete my account` confirm phrase, the pricing
  `Current Plan` CTA) change only with their comparison site, in the same edit.
- Object keys (OAuth error codes), analytics event names, storage keys, and backend status
  values are not copy.
- Shared constants (`AiDisclaimer.SEC_EDGAR_NOT_ADVICE`) are edited in place, never forked.
- Copy duplicated across frontend and backend must be changed on both sides in the same PR.
  The beta invite is not such a pair: the message an admin copies (`DEFAULT_INVITE_MESSAGE` in
  `features/admin/lib/shareLinks.ts`) and the invite email (`send_invite_email` in
  `backend/app/services/email_service.py`) open with the same two sentences and differ after
  them on purpose, the message carrying its link inline and asking not to be forwarded, the email
  carrying a button and "No credit card required." Keep their intent aligned, not their wording.
- Component and e2e tests assert exact copy (headings such as "Generation interrupted" and
  "Page not found" are pinned by name). Any copy change runs `npx vitest run` before push and
  updates the coupled assertion in the same PR (see `lessons/test-vitest-for-copy-changes.md`).
