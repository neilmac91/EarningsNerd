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

Same fourteen tells, same 0 to 3 scale ([00-audit.md](00-audit.md) §2). Scored on the rebuilt
pages after the three fixes in §3. These scores and captures precede the retirement of the empty
Founder slot; [A5](01-interview.md#3-the-answers-in-force) records its current absence.

| # | Tell | Before | After | Evidence |
|---|---|---|---|---|
| T1 | Default palette and type, no device; nothing recognisable without the logo | 3 | 1 | The palette and faces stay by decision (06-system.md §1 to §2). The device is now on the hero headline, the evidence row, the auth pane, the waitlist headline, the social card, the templates: cover the lockup on the [fold](stress/after-home-1440-both-themes.jpg) and the marked phrase and the bracket twins still name the house. |
| T2 | Copy scoped into neutrality | 3 | 1 | The sixteen hedge sites are gone (07-voice.md, table). The trust strip still carries one scope statement and "Not investment advice"; both are kept on purpose, and that is the trace. |
| T3 | The Nerd missing: no point of view, wit, human | 3 | 1 | The catch card, the quips signed "Reading the filing", the 404, the stalled line. The Founder sentence was still absent in these captures; the empty slot has since been retired under A5. |
| T4 | Template composition | 3 | 2 | The skeleton is intact: two-column hero, four-up strip, heading + lead + card, alternating rows, four-up grid, two pricing cards, banner ([grayscale full page](stress/home-light-1440-grayscale.jpg)). What changed inside it: the strip says four behaviours instead of four pseudo-statistics, the evidence section has the marked copy and the catch. A layout pass is its own PR (`tasks/todo.md`). |
| T5 | Sample-data drift | 3 | 1 | Every surface is FY2025 against FY2024 from one verified set, and the Financial Highlights table now shows "$7.46 / $6.08" like the Change Report two screens later ([after](stress/after-home-evidence-light.jpg)). The Multi-Period demo alone ends at FY2024: a pipeline snapshot, labelled, regenerated by the founder, not edited. |
| T6 | No human, no reason, no "aha" | 3 | 1 | "The number you remember" is on the page with two real figures. The Founder slot rendered nothing in these captures and has since been retired (08-applications.md §6). |
| T7 | Notable filings | 3 | 0 | Unmounted; DORMANT until E90 remounts it under D-046's curation rule ([08-applications.md](08-applications.md) §7). |
| T8 | A second homepage in a second voice | 3 | 0 | The waitlist page shares the subhead, the voice and the fourth brand headline ([after, both themes](stress/after-waitlist-1440-both-themes.jpg)); no urgency, no counter at zero. |
| T9 | Pricing off-voice and off-fact | 2 | 1 | The call to action reads the registration mode ("Request an invite" under the gate); the plan copy says what each is for. The yearly toggle still shows the derived "$32.50 /month"; it is arithmetic on the stated price and is left. |
| T10 | Placeholder as decoration | 2 | 0 | The grey bars are gone; the counter has a floor of 25. |
| T11 | The disclaimer forgot to be a product | 2 | 1 | The trust strip's fourth line and the Multi-Period data notes remain, both true, both the product's own scope. |
| T12 | A boilerplate consent bar | 3 | 0 | "Cookies on this site", then what the cookies do, checked against the analytics gate ([after](stress/after-home-1440-both-themes.jpg)). |
| T13 | The mark fails at the sizes it is used most | 2 | 2 | Unchanged by the founder's decision (D-015). The Safari pinned-tab icon is the one new small rendition. |
| T14 | A ticker-tape element on the company page | 1 | 1 | Outside this brief's surfaces; correct and sourced. |

**Second sameness score: 12 of 42** (from 36). Of the twelve points left, five sit in T4 and T13
(a layout pass and a protected mark), one in T14 (scope), and the rest are single traces that
are each a decision rather than an oversight.

## 3. The three weakest points, fixed

Chosen from the first pass over the captures as the places where the new system was contradicted
by something still on the page.

1. **The waitlist headline broke two rules at once.** "Read a 10-K in 5 minutes, not 5 hours."
   set "5 minutes" in sage (sage on a number) and claimed a speed nobody measured (S5). It is now
   the fourth brand headline, "The 10-K, read for you, with receipts.", with the mark under "with
   receipts"; the page `<title>` follows (`frontend/app/waitlist/page.tsx`).
2. **The consent bar still opened with the sentence two competitors also say.** "We value your
   privacy" is now "Cookies on this site", and the body states what the cookies do: essential
   keeps you signed in; analytics cookies and session recording stay off until allowed. That is
   what `app/posthog-provider.tsx` enforces for PostHog, the one analytics tool that sets cookies;
   the first wording said "analytics" without "cookies", which the review caught, because Vercel
   Web Analytics (cookieless) runs for every visitor. The dialog's intro, which promised "personalized content" the
   site does not offer, names the three categories it actually has (`components/CookieConsent.tsx`,
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
XBRL wording stays on the checked fallback (08-applications.md §1). The sameness scores above are
not rescored here; that waits for the records PR.

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
link). The table in §2 is scored on these. The ESLint
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
- The Multi-Period demo's years are the founder's to regenerate; the composition (T4) is its
  own PR; the mark's small-size drawing is closed by decision.
