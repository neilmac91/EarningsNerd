# Independent refutation

Read-only review at `1f12fc835fcbf525042473ab0e988b4827734f38`. No application changes were present at review start. I read the packet, relevant implementation, design guidance, measurement JSON and supplied open PR diffs. I did not use the author's rationale. A bounded independent helper checked Distill D3-D6 and Clarify C1-C2. No application files, branches, tests or external systems were changed. This is a source and evidence review, not a fresh browser run.

The user's clarified P0 rubric includes an unreadable financial value on a primary production route at the required enlarged-text setting. Under that rubric DS-01 retains P0. The principal refutations are DS-09's claimed rule violation, DS-07's broad claim of exact compatibility, the alleged existing Card enforcement owner, and Clarify C2's actionable scope.

Proposal IDs below are frozen from the refutation packet: proposed DS-09 became final DS-14 documentation drift; proposed DS-10 became final DS-09 E58. E59 and E9 became final DS-10 and DS-11. Final ordered plans in REPORT.md incorporate these corrections.

## Findings

### DS-01: survives, P0 under the supplied rubric

`HeroExample.tsx:81-85,161` fixes three columns while the complete values and deltas refuse to wrap. The production measurements show actual adjacent value overlap, not merely a text node exceeding its own box. At 1440px/root32, net income ends at x1195.47 while EPS starts at x1187.33. At 390px/root32, revenue ends at x224.20 while net income starts at x179.33. Both themes have the same measured geometry. The live values are longer than the abbreviated fallback; testing only the fallback would miss the desktop case. The document's wider scrollWidth has other causes and must not be attributed entirely to this strip.

Smallest fix: let whole metric groups reflow based on available content width, preserving full labels, figures, deltas and their source semantics. Keep ordinary text geometry and financial formatting. M, routine, after [#1311](https://github.com/neilmac91/EarningsNerd/pull/1311)'s same-file changes; [#1278](https://github.com/neilmac91/EarningsNerd/pull/1278) does not change this strip. Extend an existing marketing/reflow browser gate with both live long values and fallback values at 390 and 1440, root16/root32, both themes. A no-document-overflow assertion alone will not detect overlap inside the card.

### DS-02: survives, P1

`SecondaryHeader.tsx:27` and `Header.tsx:82` both stick at top zero, with z40 beneath z50. Production pricing evidence at scrollY500 places the secondary title at y20-48 under the global header's y0-65 and hit-tests the global header at that point. The shared component predicts the same cause on dashboard and watchlist; label those as shared-code coverage unless separately captured.

Use [#1278](https://github.com/neilmac91/EarningsNerd/pull/1278)'s measured `--site-header-h`, preserving sticky behavior and stacking order. S, routine, after [#1278](https://github.com/neilmac91/EarningsNerd/pull/1278). Its proposed header-offset gate is the right owner to extend: it must recognize this top-zero secondary header as an offset consumer. Verify scrolling and keyboard-focused back/actions below the header, including wrapped enlarged-text header states. Raising z-index would conceal the other header and is not a fix.

### DS-03: survives, P1, known

`useSheetFocusTrap.ts` handles Tab, Escape and restoration but does not make the background inert. The Source sheet is aria-modal while its scrim sits below Header. `source-proof.json` shows a real header-theme activation changing the theme while modal remains true in both themes. This disproves any claim that the existing keyboard trap alone supplies modality.

The smallest complete scope is inertness for all outside interactive page/chrome subtrees for the modal lifetime, not just disabling the one observed theme control. Preserve desktop nonmodal panes, consent ownership, a nested modal's priority and the restored opener. Do not inert an ancestor that contains the sheet. M, routine, after [#1278](https://github.com/neilmac91/EarningsNerd/pull/1278)/#1289/#1295 reconciliation. Extend `pane-close-focus.spec.ts`, `consent-bar-yields.spec.ts` and the existing hook behavior as appropriate, without a duplicate universal modal gate. Include pointer, keyboard, close/unmount, responsive transition and stacked-modal cases.

### DS-04: survives, P1, with state-specific scope

`app/layout.tsx:121-124` explicitly leaves the main landmark to routes. AuthShell uses divs throughout (`15,34-35`); six auth pages compose it without a main of their own. Settings uses divs in both loading and ready frames (`dashboard/settings/page.tsx:101,140`). TickerFilingsView's loaded and fallback wrappers also use divs (`34-67`). Main-bearing ready states elsewhere do not prove their whole-page fallbacks contain a landmark.

Add one semantic main at the route/shared-shell owner and enumerate the affected fallback states. Do not turn the root `#main` div into a main, which would nest many existing route mains. AuthShell can solve its six routes together. M, routine, after the overlapping shell/auth/settings/filing heads. Extend `skip-link.spec.ts`: it currently proves one `#main` target on /terms, which is not proof of a semantic main. Assert one exposed landmark on the affected ready/loading/error states and preserve focus navigation.

### DS-05: survives, P1

`dashboard/page.tsx:220-238` omits its header in the user-failure branch and uses GuidanceCard's h3 default. The three company branches at `company/[ticker]/page-client.tsx:245-318` likewise use the default without a preceding h1. The invalid-ticker branch is source-supported; the packet should not imply it is as readily route-reachable as company missing or unsupported.

[#1289](https://github.com/neilmac91/EarningsNerd/pull/1289) fixes `dashboard/error.tsx`, app error boundaries and supplies h1 support; it does not fix dashboard/page's retained query failure. Reuse that API only in the whole-page branches. Calendar is correctly excluded because its toolbar establishes the preceding heading. S independently or M combined with DS-04, routine, after [#1289](https://github.com/neilmac91/EarningsNerd/pull/1289) and the company/dashboard heads. Extend `text-floors.spec.ts`'s state matrix; reusing [#1289](https://github.com/neilmac91/EarningsNerd/pull/1289)'s boundary-heading owner for matching boundaries is reasonable, but do not add parallel general outline scans.

### DS-06: survives, P1, known, with corrected measurement language

`Header.tsx:134-135` renders a 36x36 skeleton; the measured complete pending desktop cluster, including the theme control and gap, is 84x36. The resolved cluster is 306.046875x46 in the supplied local run. `header-shift.json` and `performance.json` record a local 0.145394 layout-shift sum. This is reproducible local evidence, not field CWV and not a promise of the same pixels on every machine. The measured navigation also shifts horizontally. Mobile measurement is much smaller, about 0.00532, so do not characterize every width with the desktop number.

Reserve responsive pending geometry that can accommodate the actual resolved states, without hardcoding 306px as a universal target or fighting [#1278](https://github.com/neilmac91/EarningsNerd/pull/1278)'s wrap rules. M, routine, after [#1278](https://github.com/neilmac91/EarningsNerd/pull/1278)/#1289. Extend existing Header/reflow ownership with delayed anonymous, signed-in and failed-auth transitions. Preserve pending-auth behavior rather than flashing anonymous CTAs before identity settles.

### DS-07: downgrade and narrow, valid duplication but not all exact twins

Exact canonical shells exist in `HeroExample.tsx:124-126`, `ContactForm.tsx:138,180`, and calendar `EarningsCalendarPage.tsx:212-215`, `MonthView.tsx:42`, `WeekView.tsx:125-127,198`. Card supports `as`, e1/e2/e3 and xl/2xl, so those can retain semantic elements, geometry, motion and padding through composition.

The contact intro at `contact/page.tsx:30` uses rounded-lg, which Card does not support. Waitlist's 2xl cards use `dark:border-border-dark`, whereas Card uses white/10. Its rounded-3xl banners differ further. These are near-twins, not appearance-preserving substitutions. Exclude them from exact-compatible Distill, or name the deliberate visual normalization separately. AlertBell e4, DayDetailDialog e5 and specialized clickable reporting tiles also require their own behavior review.

M, routine for the bounded compatible group, sequenced after each touched file's owner, including [#1121](https://github.com/neilmac91/EarningsNerd/pull/1121)/#1301/#1311 and any newer contact work. No current canonical Card-composition gate was found. Existing designRules tests guard stripes, form badges and motion, not a ban on raw panels. If introducing a new never-again rule, add one bounded guard for the complete canonical recipe with semantic exceptions and one mutation proof; do not claim an existing owner or ban every raw surface. Treat duplication as maintenance debt rather than demonstrated functional failure.

### DS-08: survives, P1 system drift; no demonstrated focus failure

`FeedbackWidget.tsx:107-116` implements a parallel text-field recipe: px3/py2, translucent light fill and white/15 dark border versus Input's px3.5/py2.5, white fill and border-dark. [#1289](https://github.com/neilmac91/EarningsNerd/pull/1289) only changes its light border. The existing field already resets forms-plugin rings and draws the brand focus treatment, so a missing focus indication claim would be false.

Prefer the existing raw textarea with `inputClasses()` to preserve `resize-none`, ref, aria-label, rows, maxLength, required semantics and modal autofocus. `<Textarea>` is also viable, but it adds Shell and its default resize-y behavior (`Input.tsx:394-409`), so is not a blind drop-in. S, routine, after [#1289](https://github.com/neilmac91/EarningsNerd/pull/1289). Existing `inputClassesNoOverrides.spec.tsx` and `siteChromeFocusRing.spec.ts` own recipe/state verification; check the actual modal in both themes. No new generic field scanner is necessary.

### DS-09: refuted as a rule violation; retain documentation-conflict finding only

The hover glow exists, but it is intentional in current source: `globals.css:247-250` describes a faint dark hover glow and `265-267` implements it. More decisively, `DESIGN.md:416` explicitly says the remaining authentication glass treatment follows its existing scoped CSS recipe. DESIGN_SYSTEM section 7's sole-hero-glow sentence conflicts with that specific retained exception.

Code-first precedence resolves this toward preserving the scoped treatment. A measured glow proves what is painted, not that it is unauthorized. Drop the glow-removal PR from Polish. A small documentation clarification can reconcile the broad sentence with the real exception, folded into Distill D6. Do not add sole-glow enforcement that would ban the current intended behavior. Removing the live hover declaration is a design change, not dead-code cleanup.

### DS-10: survives only as known E58

[tasks/todo.md:44](https://github.com/neilmac91/EarningsNerd/blob/1f12fc835fcbf525042473ab0e988b4827734f38/tasks/todo.md#L44) already directs one coordinated fair-use clarification after the brand series. Preserve the settled Unlimited plan presentation and entitlement authority. The supplied [#1290](https://github.com/neilmac91/EarningsNerd/pull/1290) diff changes the dashboard limit banner to account-specific used-limit copy, so do not sweep it back to generic Unlimited language. Analysis fair-use behavior is also already owned by its open work and is not an upgrade opportunity.

Read once app-wide as one copy/meaning owner, with the requested pricing FAQ and filing-limit contexts, unless a later explicit decision says otherwise. Do not silently reduce the task to FAQ-only or duplicate paragraphs everywhere. S/M to M, routine for a frontend copy owner and those contexts, after the series. Extend the current brand-copy/voice and entitlement-derived verification; no hardcoded numerical guardrail and no backend entitlement change.

## Additional highest known findings

**E59 survives as known maintenance debt.** `allowlistCapsAreEqualities.spec.ts:26-42` lists 21 named-constant ceiling sites in seven files: 19 list caps plus the two z-value ceilings. `bottomChromeLadder.spec.ts:602,604` really compares maximum z values, so those remain inequalities. The current comment claiming [#1301](https://github.com/neilmac91/EarningsNerd/pull/1301)/#1295 make retry-label caps equalities is not supported by the supplied diffs, which lower counts only. Recount after the series, convert the actual remaining list sites and shrink the existing meta-allowlist. M, routine. One stale-cap mutation proves the existing owning gate, without inventing another inventory gate.

**E9 survives only as explicitly deferred work.** `fullPageSpinnerGate.spec.ts:33-53` pins exactly three screens with reasons: company and filing when their server seed is missing, and legacy TickerFilingsView's client-only company load. Their source branches remain present. The first two do not establish a spinner on every production load. [tasks/todo.md:57](https://github.com/neilmac91/EarningsNerd/blob/1f12fc835fcbf525042473ab0e988b4827734f38/tasks/todo.md#L57) says to wait for each page's next rework. Keep that condition and page-owner sequencing; three separate replacements may exceed an M estimate for one generic cleanup. Reuse the existing spinner and loading/motion gates when each page changes, retaining loading, failure, seed and retry behavior.

## Corrected plans

**Distill**

- D1: retain only the exact compatible ContactForm, HeroExample and calendar shells listed above. Exclude contact intro, waitlist, dialogs, popovers and specialized interactive compositions from the automatic migration. M routine, after owning heads.
- D2: retain shared feedback input recipe composition, preferably `inputClasses()` on the existing textarea. S routine after [#1289](https://github.com/neilmac91/EarningsNerd/pull/1289).
- D3: retain removal of unused Button tertiary alias, its resolver and type exclusion, after [#1278](https://github.com/neilmac91/EarningsNerd/pull/1278). `Button.tsx:27-33,57` contains the definition and stale three-call-sites comment; no application consumer was found. S routine. Existing type and Button checks suffice; do not add a pure absence test.
- D4: retain only proven unused declarations and exports with their dependent gates/docs. Remove only `.filing-summary` from the combined selector at globals.css:102; keep live `.copilot-answer`. Remove dead animation exemptions and corresponding designRules fixtures together. Keep active font alias, chart mirrors, data helpers and live Card APIs. If retiring TrendSparkline, retire its exclusively used helper with it; do not remove `directionTone` while `Chart.tsx:390` still calls it. Update parity omissions, shadow/stagger documentation and sidecar where relevant. M routine after overlapping heads; parity and normal frontend gates.
- D5: retain known E59, current nineteen list sites, remeasured after the series; retain two z inequalities. M routine with the current meta-gate.
- D6: retain concrete active documentation/comment drift, including the scoped auth-glow exception and misleading future equality claim. Other examples: GuidanceCard's removed StateCard comment, skip-link's stale homepage autofocus comment, layout's absolute no-Inter-download claim, and theme-toggle guidance that omits AuthShell's intentional separate chrome. No historic rewrite. S routine because frontend source comments change; no prose-mirroring tests.

**Polish**

- P1-P5 survive with the corrected DS-01 through DS-06 scopes above. Combine route semantics and heading-level changes where that keeps one understandable fix; do not duplicate gates.
- P6 remains optional visual polish, not a demonstrated WCAG failure. CompanyLogo's company name is present beside decorative images, and logos have their own contrast exception. If dark transparent third-party marks need a backplate, scope the light backplate to the loaded image, preserve the existing initials fallback, fixed box, clipping, loading and error behavior, and check several marks in both themes. Do not recolor the marks or replace the shared fallback palette. S/M routine; use CompanyLogo tests and targeted visual verification.
- P7 glow removal drops. Preserve the intentional scoped AuthShell CSS; document its exception under D6.
- P8 remains known E9, deferred to each page's next rework. It is not a newly urgent cleanup PR and should not be represented as three guaranteed M-sized edits.

**Clarify**

- C1 retains known E58 with one shared qualification owner and the designated contexts after the copy series. Existing Unlimited and Analysis decisions stay settled.
- C2 drops from the actionable plan. `provenance_service.py:96-100,189-191` uses Filing excerpt only after retained-source matching; `summary_sections.py:362-364` preserves that export meaning. `riskTitle.ts:6-10` already derives useful headings from verbatim source. No concrete truthful replacement or authoritative section name was supplied. Basic-EPS casing differs between `services/ai/xbrl_narrative.py:106`, `copilot_tools.py:45` and `trend_analysis/periods.py:46`, but is a separate naming investigation. A combined AI/Copilot/source/export change is high tier, needs concrete scope and applicable paid-CI handling, and cannot yet be responsibly estimated M. Keep it as held investigation, without a speculative implementation PR.

For future application PRs, the normal frontend lint, CI TypeScript, unit and build checks still apply, plus affected browser flows and preview verification in both themes. One mutation proof belongs to a new or strengthened never-again rule. This review itself created no rule implementation and ran no modifying test or paid evaluation.
