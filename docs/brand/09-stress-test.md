# Phase 9: the stress test

The applied work ([08-applications.md](08-applications.md)) under the checks the brief names, on
the production build served locally (`next build` then `next start`, no backend, so the hero
example shows its fallback and the pricing page its "could not check your account" notice). The
captures and boards are under [stress/](stress/). The `/impeccable` critique was not available in
this session, so the second review is the same fourteen-tell table scored by hand on the rebuilt
pages, with the evidence beside each score.

## 1. What was checked

| Check | Evidence | Finding |
|---|---|---|
| Phone size, both themes | [light 390](stress/home-light-390-fold.jpg), [dark 390](stress/home-dark-390-fold.jpg), [waitlist 390 after the fixes](stress/after-waitlist-light-390-fold.jpg) | The headline sets at 36px over three lines. In the first pass the mark broke across "Keep the source in / view.", against 06-system.md §6 (no mark across more than one line of a headline at phone width); after the review it sits under "the source" alone and stays on one line at both widths. The evidence table stacks into one card per metric with its own current, prior and change. The margin narrows to 36px on a phone but stays, with its 11px twins `aria-hidden`; the in-text marker they repeat is 12px, the provenance chip's size, since the review. The consent bar covers the hero example on a first visit at 390, as it did before (T12's wording is fixed; its placement is the consent layer's, unchanged). |
| Colour-blind simulation (Machado 2009, severity 1.0: protan, deutan, tritan) and grayscale, on every surface with gain or loss beside sage | [evidence section, light](stress/cvd-evidence-light.jpg), [dark](stress/cvd-evidence-dark.jpg), [Multi-Period demo](stress/cvd-multi-period.jpg) | Under protan and deutan the gain green and the loss red both become ochre, so colour alone would not separate them; it never has to. Every change carries its sign and glyph ("↗ +6.4%", "−0.3pp", "▲"), the struck-through "$391.0B" carries its meaning in the strike, and the sage mark is a tint under a phrase, never a signal on a figure. In grayscale the deltas read as mid-grey text with the glyph. The Separate Signals Rule is what makes the simulation pass. |
| Grayscale print of the landing page | [landing, 1440, grayscale](stress/home-light-1440-grayscale.jpg) | The mark's tint fades to almost nothing in grayscale and the 2px hairline carries the device; the catch card's strike-through and the chips survive; nothing on the page depends on sage being green. |
| Grayscale print of the business card | [front, back, colour and grayscale](stress/business-card-print.jpg) | The front's highlight becomes a hairline underline under "shows its work", still legible; the navy back prints as near-black with the stacked lockup in two greys. Nothing under 7pt (templates README, Print). |
| Misuse board | [twelve cases](stress/misuse-board.jpg) | Built from the real tokens, fonts and the mark's own paths: a mark on a figure, on a price, on a claim we did not check, on another company's name; the margin as decoration; two highlights on one surface; sage on a number; our words in the filing's face; the filing's words in our face; the mark stretched, recoloured, and on a busy ground. Each panel states the rule and what to do instead. |
| Lineup against the competitors' heroes | [eight folds at 480px](stress/hero-lineup.jpg) | The new fold beside BamSEC, Fiscal.ai, Koyfin, Public, Quartr, Stock Analysis and TIKR, from the Phase 2 captures (Simply Wall St still answers the headless browser with a bot challenge, D-007 and D-019). At thumbnail size ours is the quietest of the eight and the only one whose headline carries a mark; it is also the only one with a filing's figures and a filed date in the fold. |

## 2. The sameness test, rerun

Same fourteen tells and 0 to 3 scale ([00-audit.md](00-audit.md) §2). The current pass is
2026-10-23 on main `5897d602`, after #1457 merged as `ab6962ec`, with E120 (#1495) included.
The previous column is the recorded 11 of 42, which already moved T4 from 3 to 1 after D-045.
The new [capture set](stress/closeout-2026-10-23/README.md) records eight routes at 390 and
1440px, in light and dark, at default and 200% browser text. The homepage's default-size full
pages show the lower rows; enlarged-text captures use the viewport, so capture does not reset
the text setting. These are current-state captures, not a new visible code change.

| # | Tell | Before | Previous | Main | Current evidence |
|---|---|---|---|---|---|
| T1 | Default palette and type, no device; nothing recognisable without the logo | 3 | 1 | 1 | The palette and faces stay by decision. C5's solid sage phrase and genuine italic recur on the [hero](stress/closeout-2026-10-23/home-light-1440-100-fold.jpg), [auth pane](stress/closeout-2026-10-23/login-dark-1440-100-fold.jpg) and waitlist. Located passages retain the separate annotation paint on the [Risks rows](stress/closeout-2026-10-23/filing-light-1440-100-risks.jpg). The familiar palette is the trace. |
| T2 | Copy scoped into neutrality | 3 | 1 | 1 | The [claims row](stress/closeout-2026-10-23/home-light-1440-100-rows.jpg) names Figures, Risks, Nine parts and SEC EDGAR, in the product's words. Matching claims still name what the server can check, deliberately; the trust strip retains the scope and investment-advice line. |
| T3 | The Nerd missing: no point of view, wit, human | 3 | 1 | 1 | The catch card remains in the [full page](stress/closeout-2026-10-23/home-light-1440-100-page.jpg); the [404](stress/closeout-2026-10-23/not-found-dark-390-100-fold.jpg) says "We looked. The link is mistyped or out of date." No founder sentence, by A5. |
| T4 | Template composition | 3 | 1 | 1 | D-045's two-column hero stays. The [desktop rows](stress/closeout-2026-10-23/home-light-1440-100-rows.jpg) have a rule, numbered 14rem label column and content; the [phone](stress/closeout-2026-10-23/home-dark-390-100-rows.jpg) and [1440px at 200% text](stress/closeout-2026-10-23/home-dark-1440-200-rows.jpg) stack that label above its content. The full pages show the plan table and closing line. T4's move from 3 to 1 holds on current main; it is not a second reduction. `landing-sections-mounted.spec.ts` and `earningsnerd/no-four-up-grid` retain the rule. |
| T5 | Sample-data drift | 3 | 1 | 0 | The [homepage](stress/closeout-2026-10-23/home-light-1440-100-page.jpg) and [auth sample](stress/closeout-2026-10-23/login-light-1440-100-fold.jpg) show FY2025, revenue $416.2B and diluted EPS $7.46. The [analysis teaser](stress/closeout-2026-10-23/analysis-light-1440-100-teaser.jpg) names its saved FY2020 to FY2025 run (#1457). Its different window is explicit, not stale sample data. The saved run and the static set are held together by `landingSamplesVerified.spec.ts`. The waitlist example is unavailable in this local run, so its successful data state is not newly observed. |
| T6 | No human, no reason, no "aha" | 3 | 1 | 1 | "The number you remember" still sets last year's total, as a reader remembers it ($391.0B, FY2024), beside the filing's ($416.2B, FY2025) with its XBRL chip in the [homepage](stress/closeout-2026-10-23/home-dark-1440-100-page.jpg); no wrong number is invented (D-012). The founder slot remains retired, rather than left empty for a sentence the founder has not supplied. |
| T7 | Notable filings | 3 | 0 | 0 | Previous score retained. This build has no backend, so Reporting this week and Notable filings omit themselves. It does not newly establish a populated or production feed. #1437 and #1461's rule remains: 10-K/10-Q, companies holding a summary the filing page shows, newest first, six at most, with the line describing that query (D-052). |
| T8 | A second homepage in a second voice | 3 | 0 | 0 | The [waitlist](stress/closeout-2026-10-23/waitlist-light-1440-100-fold.jpg) shares the subhead and C5 emphasis: "The 10-K, read for you, with receipts." No urgency or zero counter. |
| T9 | Pricing off-voice and off-fact | 2 | 1 | 1 | [Pricing](stress/closeout-2026-10-23/pricing-light-1440-100-fold.jpg) says "For reading a few filings a month" and "For deeper filing research", with "Request an invite". The annual plan now shows $20/month, billed at $240, saving $60. The former $32.50 trace is gone; the current values derive from the pricing module. The local account-check failure is a disclosed state, not a promise that registration is open. The trace left is "Unlimited": the Pro plan offers "Unlimited Multi-Period Analysis" and the homepage's plan table "Unlimited" (`ANALYSIS_LINES.pricingPro` and `landingPro` in `frontend/lib/planLimits.ts`), while analysis runs are capped at 100 a month (`ANALYSIS_MONTHLY_CAP` in `backend/app/config.py`) and no page states that cap until a reader reaches it, when the 429 names it; the one fair-use line (`PRO_FAIR_USE_LINE`, E58) covers summaries, at 300 a month. The point stays until E122 states both ceilings where "Unlimited" is read (D-050). |
| T10 | Placeholder as decoration | 2 | 0 | 0 | The [auth pane](stress/closeout-2026-10-23/login-light-1440-100-fold.jpg) has a real sample paragraph and figure. The waitlist count is absent when its request fails, never "0+"; `waitlistCounter.spec.tsx` retains its floor when a count is served. Loading bones elsewhere represent actual pending reads, not decoration. |
| T11 | The disclaimer forgot to be a product | 2 | 1 | 1 | The trust strip and data notes retain the product's scope. The [homepage](stress/closeout-2026-10-23/home-light-1440-100-page.jpg) labels the analysis "sample data (one saved run)"; #1457 removed "illustrative" and the sample's unresolvable Report reference. Scope remains the intentional trace. |
| T12 | A boilerplate consent bar | 3 | 0 | 0 | The [first visit](stress/closeout-2026-10-23/consent-light-1440-100-fold.jpg) opens with "Cookies on this site" and explains the choices. [390px at 200% text](stress/closeout-2026-10-23/consent-dark-390-200-fold.jpg) is captured separately, with no consent choice submitted. |
| T13 | The mark fails at the sizes it is used most | 2 | 2 | 2 | Previous score retained under D-015: the drawing is protected. This pass does not repeat the small-icon board or redraw the mark. |
| T14 | A ticker-tape element on the company page | 1 | 1 | 0 | The [company lead](stress/closeout-2026-10-23/company-light-1440-100-fold.jpg) has exchange, CIK, the SEC link and latest filing; no market quote. The quote was removed under D-046. This is the current fixture-rendered page, not a production account. |

**Current sameness score: 9 of 42**, from 36 initially and 11 previously. T4's earlier move
is confirmed; T5 and T14 each lose one stale trace, and T9 trades its old one for "Unlimited",
which E122 clears. The nine remaining points are the six single traces in T1, T2, T3, T4, T6
and T11, T9's pricing trace, and the protected mark's two in T13.
T7 and T13 explicitly carry their previous scores where this pass does not repeat their evidence.

2026-10-23, after this pass: D-058 retires the catch card that T3 and T6 cite, for "Follow one figure to the filing"
(#1530). Their scores stand as recorded, from captures that predate it; the next stress test rescores T3 and T6.
The captures establish neither production behaviour nor full accessibility compliance.

## 3. The three weakest points, fixed

Chosen from the first pass over the captures as the places where the new system was contradicted
by something still on the page.

1. **The waitlist headline broke two rules at once.** "Read a 10-K in 5 minutes, not 5 hours."
   set "5 minutes" in sage (sage on a number) and claimed a speed nobody measured (S5). It is now
   the fourth brand headline, "The 10-K, read for you, with receipts.", with the mark under "with
   receipts"; the page `<title>` follows (`frontend/app/waitlist/page.tsx`).
2. **The consent bar still opened with the sentence two competitors also say.** "We value your
   privacy" is now "Cookies on this site", and the body states what the cookies do: essential
   keeps you logged in; analytics cookies and session recording stay off until allowed. That is
   what `app/posthog-provider.tsx` enforces for PostHog, the one analytics tool that sets cookies;
   the first wording said "analytics" without "cookies", which the review caught, because Vercel
   Web Analytics (cookieless) ran for every visitor (since D-046 it waits for the same consent).
   The dialog's intro, which promised "personalized content" the site does not offer, names the
   three categories it actually has (`components/CookieConsent.tsx`,
   `tests/unit/CookieConsent.spec.tsx`).
3. **The Financial Highlights table rounded the figure it was demonstrating.** `fmtCurrency`
   defaults to one decimal for values of a dollar or more, so a served "$7.46" displayed as "$7.5"
   while the Change Report showed "$7.46". The table now keeps the precision a currency row was
   served with (compact figures such as "$416.2B" keep their rounding), and the parity spec pins
   it in both layouts (`features/summaries/components/FinancialMetricsTable.tsx`,
   `tests/unit/FinancialMetricsCards.spec.tsx`). This one is a product fix: live summaries round
   per-share figures the same way.

The first pass left two findings: the hero mark spanning two lines, and the header's "Request
invite" at phone width against "Request an invite" on desktop. The second is a deliberate
shortening and stays. The first broke the device's own misuse rule, so the review round moved
the mark onto "the source", the words the device stands for, without changing a word of the
served headline.

The October 2026 audit found two more on the hero (pub/F08, pub/F09): the evidence row set the
filing's words without quotation marks, and a live figure's hover and link said its figures came
from the XBRL filing, which the hero cannot vouch for. The excerpt now wears quotation marks, and a
live example's link reads "Source filing · check the figures on SEC EDGAR" with no XBRL hover; the
XBRL wording stays on the checked fallback (08-applications.md §1). The current-main rescore in
§2 includes these corrections; the earlier captures remain historical evidence.

## 4. The second review

The routine-tier review of the whole branch (one Opus lens, a Sonnet refuter for each blocker)
found three blockers, all upheld by their refuters and all fixed: matching claims that had lost
the server's scope ("each figure ..." in nine places), a search-coverage claim widened to "any
company that files with the SEC" (search reads SEC's ticker file only), and the consent clause
above. Its should-fix items are fixed or recorded in the PR: the sample's per-share row now reads
Cited as a real payload's would, sage is off the remaining public numbers, the marked block's
corners are square, and four gates held the rules this work wrote down at that review
(`brandCopyRules.spec.ts`, `markSingleSource.spec.ts`, `founderNote.spec.tsx`,
`waitlistCounter.spec.tsx`). The dedicated `founderNote.spec.tsx` was subsequently retired with
the unused Founder slot; the other three gates remain.

After the fixes the production build was rebuilt and recaptured: [home, both
themes](stress/after-home-1440-both-themes.jpg), [waitlist, both
themes](stress/after-waitlist-1440-both-themes.jpg), [waitlist at
390](stress/after-waitlist-light-390-fold.jpg), [home at 390](stress/after-home-light-390-fold.jpg),
[the evidence section](stress/after-home-evidence-light.jpg); the images were captured again after
the review round, from a build made with CI's environment (so the header shows the Multi-Period
link). The Previous column in §2 was scored on these; its Main column is scored on the closeout
set. The ESLint
design rules, the CI TypeScript check, the unit suites touched and the three Playwright specs
that run without a backend (`home-page-unauthenticated`, `not-found-page`, `text-floors`) were run
against the same build; their results are in the handoff ([README.md](README.md)).

## 5. The founder's review

The founder's review of `ab3f8f0` (an AI-assisted principal-engineer pass, review 5484603342 on
PR #1226) found two P2s and two P3s, none in the mark's drawing, and all four are fixed (D-028):

- **The quote promise.** "Quotes … or withheld" covered Forward Signals quotes, which stay on the
  page, labelled Cited, while `AI_FORWARD_QUOTE_GATE` is off. The claims strip now names risk
  excerpts, the trust strip likewise, and the evidence lead says a quote reads Verified in filing
  only when its words were found; `brandCopyRules.spec.ts` rule 1c fails on the three old sites.
- **The catch card at 200% text.** At 390px under a 32px root font the two amounts overlapped by
  59.6px, and in the desktop column too. The pair now wraps on its own content width, and a
  Playwright spec measures the painted text in both themes at 390px, 320px and 1280px.
- **The margin twin.** It assumed a 16px height and sat 8px low at 200%; it now centres on its
  marker's measured midpoint (`markedCopy.spec.tsx`).
- **The geometry gate.** A translation on only the stacked logo's arrowhead passed every check;
  `markSingleSource.spec.ts` now reads the transform hierarchy, and five planted moves fail it.

## 6. Not done, and said so

- The colour-blind pass is a simulation, not a session with a colour-blind reader.
- The print checks are grayscale conversions of screen renders, not proofs from a printer.
- The phone checks are an emulated 390px viewport, not a device.
- Simply Wall St's hero is still missing from the lineup (D-019).
- The original stress captures retain the old FY2019 to FY2024 demo. The current capture set in
  §2 shows the saved FY2020 to FY2025 run after #1457. The mark's small-size drawing stays closed
  by decision.
