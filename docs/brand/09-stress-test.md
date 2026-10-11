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
| Phone size, both themes | [light 390](stress/home-light-390-fold.jpg), [dark 390](stress/home-dark-390-fold.jpg), [waitlist 390 after the fixes](stress/after-waitlist-light-390-fold.jpg) | The headline sets at 36px over three lines; the mark breaks across "Keep the source in / view." and `box-decoration-break: clone` closes each fragment, so the hairline reads on both lines. The evidence table stacks into one card per metric with its own current, prior and change. The 11px margin twins are hidden below `sm` with the gutter, so no sub-12px text reaches a phone. The consent bar covers the hero example on a first visit at 390, as it did before (T12's wording is fixed; its placement is the consent layer's, unchanged). |
| Colour-blind simulation (Machado 2009, severity 1.0: protan, deutan, tritan) and grayscale, on every surface with gain or loss beside sage | [evidence section, light](stress/cvd-evidence-light.jpg), [dark](stress/cvd-evidence-dark.jpg), [Multi-Period demo](stress/cvd-multi-period.jpg) | Under protan and deutan the gain green and the loss red both become ochre, so colour alone would not separate them; it never has to. Every change carries its sign and glyph ("↗ +6.4%", "−0.3pp", "▲"), the struck-through "$391.0B" carries its meaning in the strike, and the sage mark is a tint under a phrase, never a signal on a figure. In grayscale the deltas read as mid-grey text with the glyph. The Separate Signals Rule is what makes the simulation pass. |
| Grayscale print of the landing page | [landing, 1440, grayscale](stress/home-light-1440-grayscale.jpg) | The mark's tint fades to almost nothing in grayscale and the 2px hairline carries the device; the catch card's strike-through and the chips survive; nothing on the page depends on sage being green. |
| Grayscale print of the business card | [front, back, colour and grayscale](stress/business-card-print.jpg) | The front's highlight becomes a hairline underline under "shows its work", still legible; the navy back prints as near-black with the stacked lockup in two greys. Nothing under 7pt (templates README, Print). |
| Misuse board | [twelve cases](stress/misuse-board.jpg) | Built from the real tokens, fonts and the mark's own paths: a mark on a figure, on a price, on a claim we did not check, on another company's name; the margin as decoration; two highlights on one surface; sage on a number; our words in the filing's face; the filing's words in our face; the mark stretched, recoloured, and on a busy ground. Each panel states the rule and what to do instead. |
| Lineup against the competitors' heroes | [eight folds at 480px](stress/hero-lineup.jpg) | The new fold beside BamSEC, Fiscal.ai, Koyfin, Public, Quartr, Stock Analysis and TIKR, from the Phase 2 captures (Simply Wall St still answers the headless browser with a bot challenge, D-007 and D-019). At thumbnail size ours is the quietest of the eight and the only one whose headline carries a mark; it is also the only one with a filing's figures and a filed date in the fold. |

## 2. The sameness test, rerun

Same fourteen tells, same 0 to 3 scale ([00-audit.md](00-audit.md) §2). Scored on the rebuilt
pages after the three fixes in §3.

| # | Tell | Before | After | Evidence |
|---|---|---|---|---|
| T1 | Default palette and type, no device; nothing recognisable without the logo | 3 | 1 | The palette and faces stay by decision (06-system.md §1 to §2). The device is now on the hero headline, the evidence row, the auth pane, the waitlist headline, the social card, the templates: cover the lockup on the [fold](stress/after-home-1440-both-themes.jpg) and the marked phrase and the bracket twins still name the house. |
| T2 | Copy scoped into neutrality | 3 | 1 | The sixteen hedge sites are gone (07-voice.md, table). The trust strip still carries one scope statement and "Not investment advice"; both are kept on purpose, and that is the trace. |
| T3 | The Nerd missing: no point of view, wit, human | 3 | 1 | The catch card, the quips signed "Reading the filing", the 404, the stalled line. The human arrives with the founder sentence (08-applications.md §6), which is the founder's to write. |
| T4 | Template composition | 3 | 2 | The skeleton is intact: two-column hero, four-up strip, heading + lead + card, alternating rows, four-up grid, two pricing cards, banner ([grayscale full page](stress/home-light-1440-grayscale.jpg)). What changed inside it: the strip says four behaviours instead of four pseudo-statistics, the evidence section has the marked copy and the catch. A layout pass is its own PR (`tasks/todo.md`). |
| T5 | Sample-data drift | 3 | 1 | Every surface is FY2025 against FY2024 from one verified set, and the Financial Highlights table now shows "$7.46 / $6.08" like the Change Report two screens later ([after](stress/after-home-evidence-light.jpg)). The Multi-Period demo alone ends at FY2024: a pipeline snapshot, labelled, regenerated by the founder, not edited. |
| T6 | No human, no reason, no "aha" | 3 | 1 | "The number you remember" is on the page with two real figures. The founder slot renders nothing until written. |
| T7 | Notable filings | 3 | 0 | Unmounted; DORMANT until a curation rule exists. |
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
   keeps you signed in; analytics and session recording stay off until allowed, which is what
   `lib/analytics.ts` enforces. The dialog's intro, which promised "personalized content" the
   site does not offer, names the three categories it actually has (`components/CookieConsent.tsx`,
   `tests/unit/CookieConsent.spec.tsx`).
3. **The Financial Highlights table rounded the figure it was demonstrating.** `fmtCurrency`
   defaults to one decimal for values of a dollar or more, so a served "$7.46" displayed as "$7.5"
   while the Change Report showed "$7.46". The table now keeps the precision a currency row was
   served with (compact figures such as "$416.2B" keep their rounding), and the parity spec pins
   it in both layouts (`features/summaries/components/FinancialMetricsTable.tsx`,
   `tests/unit/FinancialMetricsCards.spec.tsx`). This one is a product fix: live summaries round
   per-share figures the same way.

Two further findings were weighed and left: the hero mark spanning two lines at 1440 and 390 is
correct under `box-decoration-break: clone` and would only change by marking a shorter phrase of
the served headline; and the header's "Request invite" at phone width against "Request an invite"
on desktop is a deliberate shortening.

## 4. The second review

After the fixes the production build was rebuilt and recaptured: [home, both
themes](stress/after-home-1440-both-themes.jpg), [waitlist, both
themes](stress/after-waitlist-1440-both-themes.jpg), [waitlist at
390](stress/after-waitlist-light-390-fold.jpg), [the evidence
section](stress/after-home-evidence-light.jpg). The table in §2 is scored on these. The ESLint
design rules, the CI TypeScript check, the unit suites touched and the three Playwright specs
that run without a backend (`home-page-unauthenticated`, `not-found-page`, `text-floors`) were run
against the same build; their results are in the handoff ([README.md](README.md)).

## 5. Not done, and said so

- The colour-blind pass is a simulation, not a session with a colour-blind reader.
- The print checks are grayscale conversions of screen renders, not proofs from a printer.
- The phone checks are an emulated 390px viewport, not a device.
- Simply Wall St's hero is still missing from the lineup (D-019).
- The Multi-Period demo's years are the founder's to regenerate; the composition (T4) is its
  own PR; the mark's small-size drawing is closed by decision.
