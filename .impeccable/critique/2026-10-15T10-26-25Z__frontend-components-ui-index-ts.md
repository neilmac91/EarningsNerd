---
target: EarningsNerd shared design system
total_score: 28
max_score: 40
na_heuristics:
p0_count: 1
p1_count: 4
target_identity: "file:/workspace/earningsnerd-design-review/frontend/components/ui/index.ts"
target_fingerprint: "sha256:1a68bbbec0ebad07084b263758a6fa2e94439cfd644f68fd6c29b97fa9221dba"
target_path: /workspace/earningsnerd-design-review/frontend/components/ui/index.ts
timestamp: 2026-10-15T10-26-25Z
slug: frontend-components-ui-index-ts
---
Method: dual-agent (A: /root/instruments/type_layout_lens · B: /root/instruments)

# EarningsNerd shared design-system critique, 15 October 2026

The product already has a specific, coherent visual identity. Filing identities, scoped verification counts, the margin and the mark, and distinct data and original-document type roles make the interface recognizable as an investor's research desk. The highest-value work is to make this system reliable at enlarged text sizes and at the boundaries between shared chrome, reading surfaces and existing primitives.

Target: `frontend/components/ui/index.ts`, representing the shared UI layer with `frontend/components`, `frontend/app/globals.css` and `frontend/tailwind.config.js`. Surfaces: home, filing, company, pricing, dashboard and sign-in. Source: `1f12fc835fcbf525042473ab0e988b4827734f38`. Public production captures establish what was visible on 15 October; signed-in local captures use route fixtures and do not establish authenticated production behavior. The independently written design assessment finished before detector findings entered the combined synthesis.

## Design health score

Health runs from 0, worst, to 4, excellent. All ten heuristics apply to this shared system. Assessment A's independently recorded scores are retained.

| Heuristic | Score | Evidence |
|---|---:|---|
| Visibility of system status | 3 | Filing identity and verification tally state the document and scope; shared loading/error patterns exist. The sticky page identity becomes hidden on scroll. |
| Match with the real world | 3 | Form, reporting period, filed date and EDGAR source are distinct. The financial vocabulary still assumes audience knowledge. |
| User control and freedom | 3 | Back links, originals and source actions provide clear exits. The secondary back link is obscured after scrolling; Source sheet modality needs repair. |
| Consistency and standards | 3 | Company and filing identities share a vocabulary; primitive contracts are substantial. Feedback still copies the field and choice-group recipes. |
| Error prevention | 3 | Pricing waits for identity/subscription truth and filing entries distinguish their actual states. No checkout or production mutation was tested. |
| Recognition rather than recall | 3 | A numbered summary contents list and repeated document identity reduce recall. Long dashboard company names truncate in the fixture view. |
| Flexibility and efficiency | 3 | Search shortcut, form/period filtering and source-pane shortcut support direct paths. |
| Aesthetic and minimalist design | 2 | Ordinary-size composition is calm; at enlarged text the hero prints overlapping financial values, and sticky chrome retains space while hiding its purpose. |
| Error recovery | 3 | FilingIndex and pricing provide named Notice/Retry paths; related company/dashboard state improvements already have open PR ownership. |
| Help and documentation | 2 | Source explanations and pricing FAQ help at point of use. A discoverable glossary/help path is a research lead for newer investors, not a proven missing feature. |
| Total | 28/40 | A coherent system with specific shared defects. |

The October 4 filing-page critique scored 27/40. The present target is the shared system, so these values are not a like-for-like trend.

## Design specificity and deterministic evidence

The design review found strong product specificity before seeing the detector. A company-to-filing transition keeps the same identity grammar, figures have a recognizable data face, the summary reads as a document, and its original source has a different reading register. A new palette or font family would not address the observed failures. The landing page's repeated section construction remains the known composition item F6.

The CLI scan returned 18 records across five files: 16 warnings and two advisories. Every record was checked against source. There are zero verified defects from this scan, one semantic pattern kept, four approved exceptions and thirteen out-of-scope test fixtures. The kept pattern is the admin navigation's active underline. The approved exceptions are the success-check pop curve and the social-card template's Inter, Geist Mono and cream ground. The fixtures deliberately contain examples that the repository's own rules must reject. No ignore file was created.

Mutable browser injection succeeded on four fresh local tabs: home, pricing, login and filing/3. Its console reported 18, 2, 1 and 2 finding groups respectively. These are browser groups, not the CLI's 18 source records. Browser warnings included nested marketing surfaces, eyebrow/icon composition, line length and the approved font/palette/easing. The summary's full-width measure is explicitly settled; it is not a new defect because a generic detector prefers shorter lines. The broad home composition warnings support a known review lead, not eight separately proven nested-card defects. These were headless diagnostic overlays, not a user-visible Human tab.

## What is working

The system makes source evidence part of the interface. CompanyIdentity reuses FilingIdentity's fact line and separators, and the verification tally scopes its claims. This continuity is more valuable than cosmetic variation between routes.

Semantic hierarchy is separated from display size. Filing sections use h2/h3 structure, pricing uses section and question levels, and the footer supplies a hidden section heading. An 18px page title in compact chrome is not itself a hierarchy defect.

Shared interaction contracts are unusually well developed: Modal owns the top focus trap and body lock; busy controls remain focusable; RetryButton retains a failed query during retry; field recipes reset the forms plugin; reduced-motion behavior is intentional. Recipe consolidation must preserve these behaviors.

## Priority issues

### P0: Hero financial values overlap at 200% text

At production home, the hero example fixes three metric tracks and makes values nowrap (`HeroExample.tsx:81-85`, `:161`). At 390px and a 32px root, painted amounts overlap by about 44.9px and 69.9px between adjacent groups. At 1440px, the second pair still overlaps by about 8.1px. Both themes reproduce it. The figures themselves are supplied correctly; their presentation is unreadable under this explicit trigger.

Let complete metric groups wrap or stack according to the available width, retaining all labels and complete amounts. Do not shrink the data role or remove precision merely to fit. Inspect the real long forms as well as the compact fallback. #1278 does not touch HeroExample and #1311 retains the metric geometry, so this is separate follow-up work. Evidence: `home-200-390`, `home-dark-200-390`, and their 1440 twins with Range measurements. Suggested lenses: adapt, then polish.

### P1: The shared secondary header hides behind global chrome

`SecondaryHeader.tsx:27` and `Header.tsx:82` both stick to top-0; z-40 sits behind z-50. On production pricing at scrollY 500, its H1 is at y20-48 beneath a 65px global header. Hit testing over the title returns global chrome, while a blank remnant of the secondary row remains below. The same component serves dashboard and watchlist.

Make the row nonsticky or place it below the measured global header. Reusing #1278's header-height mechanism is the smallest dependency if it merges first; that branch leaves this top-0 consumer untouched. Verify back/title/logout controls after scroll in both themes and at phone/desktop widths. Evidence: `pricing-header-light` and `pricing-header-dark`. Suggested lenses: layout, then polish.

### P1: Reading overlays and global chrome have conflicting ownership

The Source sheet declares aria-modal below lg while the site header remains above its scrim. The local fixture walk activated the header's theme control with the sheet still open. Today's local scroll probe also reproduces the floating Source launcher over a reading line. Both are known follow-ups, now reproduced rather than rediscovered.

Resolve the shared chrome contract so the open sheet owns pointer interaction and the closed launcher reserves readable space. Preserve the established sheet/popover layering and focus return; no second dialog primitive is needed. Evidence: `tasks/design-system-review-2026-10/data/local-source-proof.json` and its linked source-sheet/launcher captures; `FilingWorkspace.tsx:378`, `:423`, and `Header.tsx:82`. Suggested lenses: harden and layout, then polish.

### P1: The auth placeholder changes the geometry of every normal page header

The pending branch of `Header.tsx:129-136` reserves a round 36px skeleton; the eventual guest branch has two controls. A fresh local seven-second PerformanceObserver run records CLS 0.145394 on home and pricing, with the auth cluster, navigation and main offset among the shift sources. Login, which uses AuthShell, records zero in the same observation window. This confirms the known follow-up with today's evidence; it is not a production Core Web Vitals result.

Reserve the eventual header cluster's footprint while retaining the current truthful pending semantics. Check anonymous, signed-in and failed account lookup states. Evidence: `performance.json`. Suggested command: polish.

### P1: The shared feedback modal restyles primitives it already has

`FeedbackWidget.tsx:90-116` creates a raw pressed-choice row and textarea. The latter uses white/70 with black/10 rather than Input's bright white and token border; the choice row lacks the shared SegmentedControl's named group. #1289 replaces raw colour residue but leaves these duplicate structures.

Compose Textarea and SegmentedControl, preserving the current ref, min-length guard, state and focus behavior. Keep the field and group migration together because they share one modal and one acceptance path. Evidence: source census and the local feedback captures in both themes. Suggested lenses: distill, then polish.

## Cognitive load and emotional journey

The entry path has one clear first action, a real example, and a secondary company search. The filing then keeps identity, contents and source context visible. Those choices support a reader trying to check a claim. The eight popular-company shortcuts exceed the playbook's four-choice heuristic, but they are recognizable alternatives to search, not evidence that four should be deleted. Group size and choice count are two checklist flags; the hierarchy and task path remain intelligible. State labels and disclosure reduce memory demand inside the filing.

The most damaging emotional break is precision turning into overlapping numbers when the reader enlarges text. Hidden page identity during scroll and clipped long company names add smaller orientation costs. The original-source reading role, explicit EDGAR links and scoped tally otherwise provide reassurance at the moments where a reader checks trust.

## Persona red flags

A reader using enlarged text cannot reliably separate the hero's financial amounts. This was measured on production in both themes.

A newer investor sees dashboard fixture names such as "Taiwan S..." and "Internatio..." while tickers remain available. The complete names remain in accessible text, so this is a recognition lead rather than missing content. Do not generalize the fixture to authenticated production without evidence.

A returning researcher loses the sticky secondary title/back action on scroll. Breadcrumbs and the filing identity help elsewhere, but the shared row currently works against location awareness.

## Minor observations and excluded candidates

The main navigation has no current-route cue; adding a restrained `aria-current` state is orientation polish, not a new navigation architecture. A compact glossary/help path is a research question, not a proven blocker. Neither is required before repairing the five concrete issues above.

The old "Filing excerpt" sheet-title and production streaming-caret leads do not survive current-source verification. The SourceTrace title is "Source detail", while a separate backend-supplied risk-row label still reads "Filing excerpt" and needs a coordinated investigation. CopilotMessage explicitly describes whole answers with no caret. The disconnected reference has separate open-PR ownership.

Do not replace the approved cream/navy palette, Inter/system/Geist roles, full-width summary measure, justified summary paragraphs, margin-and-mark device, or success check. Do not label dark mode an inversion defect without a measured failure of its purpose. Source and observed contrast support preserving the palette.

Questions skipped: the review-only brief asks for ranked plans and a founder-decisions section, and none of these concrete repairs requires an interrupting product decision.

## Final synthesis corrections

The report adds the verified shared AuthShell/settings/fallback landmark and terminal-heading gaps from the wider route census. Source launcher overlap is a known arbitrary-scroll observation, not proof of an unreadable endpoint. Prefer inputClasses on Feedback's existing textarea to preserve its wrapper and resize behavior. The dark auth hover is an explicitly retained scoped recipe in current code and DESIGN.md; a proposed removal was refuted and became documentation clarification. Exact Card migration is limited to seven compatible shells. See [the complete review](../../tasks/design-system-review-2026-10/REPORT.md), [evidence index](../../tasks/design-system-review-2026-10/data/evidence-index.json) and [fresh refutation](../../tasks/design-system-review-2026-10/refutation.md).
