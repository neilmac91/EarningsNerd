# Task: Site-wide copy voice pass (2026-07-07, branch claude/earningsnerd-copy-voice-rr0pvy)

Rewrite user-facing English copy into a shorter, plainer, human voice (harvey.ai reference).
Remove em-dashes from copy (keep hyphens in compounds, en-dashes in ranges, and the bare `—`
null-value table token). Preserve every factual claim exactly. Copy only: no logic, structure,
styling, or data changes. Approved decisions: coverage claim = "every SEC-registered company"
(align HowItWorks); whimsy loaders trimmed to the sharp ones; emoji dropped from headings and
banners (feedback chips stay); em-dash CI gate added (CLAUDE.md rule 12).

- [x] 1. `docs/voice-and-style.md` (reusable voice spec)
- [x] 2. Chrome + metadata (layout, manifest, home meta/hero/JSON-LD, Footer, AiDisclaimer,
      error pages, search/calendar/analysis/company meta; CookieConsent left as-is)
- [x] 3. Marketing components (QuickAccessBar, HowItWorks, FeatureShowcase, AccuracySection,
      CtaBanner, HeroExample, NotableFilings, ReportingThisWeek) + specs in lockstep
- [x] 4. Waitlist page + form
- [x] 5. Pricing + auth surfaces (register, AuthShell, verification banner/modal,
      delete-account retention note, de-exclaimed auth success states)
- [x] 6. App surfaces (dashboard, settings, watchlist, calendar, analysis, search, company,
      filing/streaming, summaries, copilot, subscriptions, feedback) + specs in lockstep
      (+ alerts-cap 403 detail synced in backend watchlist router + fixture)
- [x] 7. Admin (em-dashes only) + invite-message twin in backend email_service.py
- [x] 8. New gate: `frontend/tests/unit/no-em-dash-copy.spec.ts` (caught 2 misses: terms
      meta, Chart.tsx dev warn — fixed)
- [x] 9. Verify: eslint 0 / tsc 0 / vitest 331 passed (70 files) / next build OK /
      playwright 17 passed 3 skipped 0 failed (CI-shaped: WAITLIST_MODE=false) /
      backend ruff + bandit + pytest 1368 passed / diff read-aloud review
- [x] 10. `docs/copy-change-summary.md` (before→after highlights + flagged claims)
- [x] 11. Commit, push, draft PR (no merge, no deploy)

# Task: Design-system v2 adoption pass (post-migration; PR-per-surface)

## Task #35 — live-eval findings: guard window bypass (CONFIRMED + fixed) + N-run gating
**Origin:** first-ever live run of the copilot eval (sandbox: local PG + real SEC ingestion +
DeepSeek). Baseline main held Fact adj 1.00 across all draws (guard stripped 6-8 attempts/draw —
the round-4 fix does real work). But the approved coverage-prompt experiment was NEGATIVE and
surfaced a real bug:
- [x] **Negative result (nothing shipped from it):** identical prompts scored 62%↔81% pass
      run-to-run; the "cite every figure / compute_metric for derived numbers" clause made
      placement WORSE (model fetched growth metrics then reused their chips across other
      metrics' growth figures). Prompt reverted; coverage stays WARN-level telemetry.
- [x] **CONFIRMED GUARD BYPASS (deterministic repro, exists on main):** in a dense marker run
      ("surged 19.4% [F3] to $15.00B [F2] in 2023 [F3]"), stripped markers bounded the next
      marker's adjacency window → the survivor got a year-only, unfalsifiable window and shipped
      on the wrong metric's figure while its neighbors vanished. FIX: stripped markers no longer
      advance `prev_marker_end` — windows are judged against the FINAL text (kept-literal [n]
      still bounds). Replay regression test + production/scorer parity test added (68 green).
- [x] **`copilot_runner --runs N`:** per-run reports + cross-run aggregate (mean/min/max pass
      rate; TRUST line = rows with Fact adj < 1.0 in any run; total guard catches).
- [x] **Scorer polish:** figure-coverage skipped on refusals (explanation sentences aren't
      uncited-figure noise).
- [x] **RUNBOOK:** two-standard gating rule (resolver = deterministic offline; prompt/model =
      --runs 3+ aggregates) + the negative result recorded so it isn't re-attempted blind.
**Review:** the eval harness caught a trust regression before it shipped and converted a live
flake into a deterministic, unit-tested fix — exactly the audit loop the round-4 plan promised.

## Task #34 — citation-trust hardening plan (post-round-4 review; Neil-approved, two PRs)
**Origin:** principal-engineer review of the round-4 fix surfaced three residual concerns:
(1) stripped chips leave figures UNCITED (trust downgraded silently), (2) value-match ≠
concept-match (right value, wrong label keeps its chip), (3) no alerting — Neil is the alerting
system. Approved decisions: concept guard STRIPS; GCP email alerting; golden set AAPL+TSLA; both PRs.
**PR 1 — measure + close the blind spot (no model-behavior change):**
- [x] Coverage telemetry: `count_uncited_figures` on the final answer (financial-looking tokens
      vs citation claim spans); `figure_count`/`uncited_figures` on the complete event, in the
      PostHog `copilot_inference_cost` event, and as a warning log.
- [x] Concept-adjacency guard: `_CONCEPT_SYNONYMS` (11 curated concepts) +
      `_fact_matches_adjacent_concept` — falsification-only (strip only when the span names a
      DIFFERENT metric and never the fact's own); unknown concepts always keep.
- [x] Eval harness: `score_figure_coverage` (WARN) + concept check folded into the ADJACENCY hard
      gate; `concept` shipped on fact citations; runner gains Coverage column.
- [x] Alerting: `scripts/setup_citation_alerts.sh` (2 log-based metrics, email channel, 2 policies;
      idempotent) + **root-cause find:** the JSON log formatter emitted `level` but not `severity`,
      so ALL prod JSON logs land as DEFAULT severity and any severity filter would never match —
      added `severity` to `logging_service.py`. RUNBOOK + tasks/archive/beta-monitoring.md updated.
**PR 2 — selection pressure on the model (eval-gated):**
- [x] Prompt clause: multi-metric questions must fetch EACH metric and period via tools — one
      lookup per figure; unfetched figures need a text excerpt or must be omitted.
- [x] Golden set: 2 cases / 16 questions (8 AAPL + 8 TSLA) from live XBRL via SEC companyconcept
      API — round-4 bait verbatim (TSLA revenue trio 81.462/96.773/97.690B), four-metric variant,
      the FY2024 op-income $7,076M vs net-income $7,091M near-collision wrong-label bait (both
      render $7.1B — only the concept-adjacency gate can catch a swap), margin/percent cases,
      revenue-default-fetch catcher, 5 refusals. Both cases verified:false pending operator
      confirmation of ingestion. (Scratchpad staging was lost to a container rollback; re-authored
      from the research agent's reported values.)
- [ ] Gate (operator, Neil): ingest AAPL/TSLA filings + facts, then
      `cd backend && python -m evals.copilot_runner` — require Fact adj = 1.00 and Cite
      faithful = 1.00 on all answered rows; watch Coverage and `(−N stripped)` as the
      placement-discipline signal for the new prompt clause.

## Task #33 — field report round 4: fact citations on the WRONG figures (trust)
**Neil sanity-checked citations: revenue fact chips ([1] $81.46B FY2022, [2] $96.77B FY2023,
[3] $97.69B FY2024) attached to gross-profit/operating-income/net-income figures — the chip
opened provenance for a different metric than the claim.**
- [x] **Root cause:** nothing verified fact-marker PLACEMENT. Text citations verify by excerpt
      matching; fact citations were provenance-verified (value real, from financial_fact) but the
      model reuses legit markers as year labels ("net income fell to $20.85B in 2022 [F1]" where
      [F1] = revenue FY2022). Round-1's "never invent F-markers" hardening likely pushed it
      toward reusing existing ones.
- [x] **Value-adjacency guard** in `_resolve_citations` (falsification-only, EVERY occurrence
      incl. reuse): a figure matching the fact's value (display-rounding tolerance; money at
      raw/K/M/B scalings; margin/growth fractions vs percent; bare years ignored) must appear in
      the claim span before the marker — bounded by the PREVIOUS marker (a marker vouches for the
      claim since the last citation; window cap 64 chars). Mismatch -> occurrence stripped +
      `misplaced_fact_markers` counted on the complete event + warning log.
- [x] **Prompt:** one-marker-one-figure rule (never reuse a marker on a different number/metric/
      year; markers are not year labels).
- [x] **Quality-audit harness (the "how do we trust citations" ask):**
      `fact_to_citation` now ships machine-readable `value`/`value_kind`;
      `score_fact_marker_adjacency` in copilot_scorers re-runs the SAME production matcher +
      window rule (imported, single source of truth) over the final answer — new ADJACENCY hard
      gate in `score_copilot_answer`; runner reports `Fact adj` + `(−N stripped)` attempts;
      RUNBOOK gained a "Copilot citation-fidelity audit" section (4 protection layers, live eval
      procedure, Cloud Run log watch, quarterly manual spot-check protocol).
- [x] **Tests:** +4 resolver adjacency tests (strip wrong-figure reuse, keep matching, percent
      facts, qualitative placements) + 6 eval-scorer tests (39 + 23 = 62 green).
**Review:** trust enforced at the resolver (guard), discouraged at the prompt, audited in the
eval harness and in prod telemetry — the same figure-adjacency definition in all layers.

## Task #32 — filing/210 field report, round 3 (copilot conversation quality)
- [x] **Inter-tool narration streams as the answer** ("Let me gather the key financial
      figures…Now let me get the margin computations…"): stream_chat_with_tools yielded every
      round's delta.content, and narration rounds end in tool calls the user never needed to
      see. The wrapper now HOLDS BACK each round's prose until its nature is known: first
      tool-call delta -> tool round, held prose dropped from the stream (still rides the
      assistant message for model context); prose crossing the 240-char hold-back cap -> real
      answer, flushed + streamed live; short final answers flush at round end. Wrapper-level
      regression test added.
- [x] **Follow-ups suggest unanswerable questions** ("…by quarter?" on a 10-K -> not
      disclosed): prompt now constrains suggestions to questions THIS filing's content can
      answer (with the annual/quarterly example).
- [x] **Dead end offers no next step**: the NOT_DISCLOSED output contract now carries a
      followups block (questions the filing CAN answer); service parses it out of the verdict
      buffer and ships it on complete; the not-disclosed card renders the Ask-next chips.
      Backend + frontend tests added (35/35 · 237/237).
**Review:** root causes in the streaming wrapper + output contract, not the UI; the narration
fix benefits every tool round, and dead ends now redirect productively.

## Task #31 — Tesla-filing field report, round 2 (three findings)
- [x] **Summary right-side whitespace (again):** the 88ch left-anchored measure still left a
      gutter Neil reads as dead space. `.markdown-body` now FILLS its pane (max-width none;
      the pane/card is the measure); `.filing-reader` keeps the editorial measure. Docs updated
      (second field iteration on this rule — recorded so it doesn't regress toward a cap).
- [x] **Copilot rail bottom-follows the stream:** `[messages]` effect pinned scrollTop to
      scrollHeight per token, parking readers at the sources when answers complete. Now anchors
      ONCE at ask time (last assistant status === 'reading') + one initial scroll when restored
      history hydrates; the reader scrolls at their own pace.
- [x] **No follow-up questions on long answers:** COPILOT_MAX_TOKENS default 1200 truncated
      long multi-citation completions BEFORE the ===FOLLOWUPS=== block (8 verbatim excerpts in
      the citations JSON ate the budget). Default bumped to 2400 (+ config comment); prompt now
      caps excerpts at ~30 words, forbids padded citation lists, and declares an answer without
      the followups block incomplete. NOTE for prod: if COPILOT_MAX_TOKENS is pinned in Secret
      Manager env, raise/unset it or the default bump is inert.
**Review:** backend 33/33, frontend 236/236, build green; compiled CSS verified.

## Task #30 — filing/118 field report: copilot F-citation noise + summary whitespace
**Two production findings from Neil (earningsnerd.io/filing/118):**
- [x] **Copilot [F#] noise:** the model fabricated [F1]..[F12] markers for figures it read from
      filing text (or after failed tool lookups); the server resolver correctly refused to invent
      sources but left the dead markers as literal prose noise. ROOT-CAUSE FIX, two layers:
      (1) `_resolve_citations` now STRIPS unresolvable F-markers from the answer (an unmatched
      F-marker can only be a tool artifact; spacing tidied, plain unmatched [n] stays literal per
      the quoted-content contract); (2) SYSTEM_PROMPT hardened — never write an [F#] not returned
      in a tool `cite` field this conversation; on tool error, cite filing text with plain [n].
      +3 regression tests (33/33 green).
- [x] **Summary whitespace:** `.markdown-body`'s reader layout (centered 88ch rail + centered
      68ch children) floats as a dead-space island inside the wide summary pane. Per Neil's call
      (option: left-anchor at 88ch): `.markdown-body` now left-anchors ONE 88ch measure
      (margin-inline 0, children fill the rail); `.filing-reader` keeps the centered editorial
      measure. DESIGN_SYSTEM.md + CLAUDE.md reader-layout clauses updated; fixture screenshot
      verified. Upstream ledger: reader-layout doc should note the card-context variant.
**Review:** both fixes verified (backend 33/33 incl. new tests; frontend 236/236 + build +
fixture screenshot). Root causes, not band-aids: fabrication prevented at the prompt, guaranteed
harmless at the resolver; layout fixed at the CSS source with docs aligned.

## Task #29 — DS v2.2 sync + adoption + brand refresh (four PRs; approved plan)
**Plan approved by Neil** (full spec: session plan file). Pack = ds-v2.2 upload; new brand = 9
sage monogram SVGs. Scope decisions: copilot surface upgrades to AskFilingAnswer's DESIGN with a
ZERO-functionality-loss mandate (CopilotMessage machinery stays); hero search standardizes onto
inputClasses({leadingIcon}); FULL email retheme to the cream brand.
- [x] **PR A — pack sync (guarded):** take Badge(+solid/info/warning)/Card(as)/Chart(barCursor)/
      Notice(new)/index/AskFilingAnswer(rewrite)/DESIGN_SYSTEM wholesale; Input = pack + re-apply
      boolean-error guard x4; tailwind = info.text hunk ONLY (no brand.light); globals = .tnum
      comment only; CLAUDE.md spliced + augmented to v2.2; Button/DataTable KEPT (pack regressions).
      Grep gates: guard x4, type-default, no brand.light, info.text present.
- [x] **PR B — adoption:** StateCard->Notice x12 + delete (+ drop PricingPage.test mock);
      UnverifiedBadge->Badge warning + delete ("Unverified" literal kept); filing-type chips ->
      Badge brand/info/neutral; Recommended -> Badge solid x2; leading-icon fields (watchlist +
      HERO CompanySearch, glow/kbd kept); CopilotComposer -> Textarea composer (handle kept);
      Card as="section" x6; barCursorProps x2.
- [x] **PR C — rebrand:** logo components -> new monogram (currentColor; two-tone wordmark at
      Header/AuthShell; delete theme file + EinsteinLogo); 9 SVGs + LOGO_README; generate-brand-
      assets.mjs (sharp+png-to-ico devDeps; Playwright OG w/ committed Inter) -> favicon.ico,
      apple-touch 180 full-bleed, 192/512 + maskable(0.62), og-image; manifest.ts + icons/
      themeColor/JSON-LD + ?v=2; FULL email retheme (email_service.py) + rendered screenshots.
- [x] **PR D — copilot design upgrade (zero loss):** restyle CopilotMessage/CitationChip to the
      AskFilingAnswer design (evidence-block chrome, footnote list + TrustBadge, counts footer);
      popovers/deep-links/analytics/StreamingText perf/ticker/not_disclosed/followups preserved
      1:1; 9 suites stay the spec (layout-text-only assertion updates); NO deletions.
**Review:**
- *PR A (pack sync):* per-file strategy byte-verified (KEEP files == HEAD; TAKE files == pack;
  Input == pack + exactly the 4 guards). NEW pack regression found by the build and fixed:
  Input.tsx v2.2 gained client-only hooks (useRef/useLayoutEffect for composer auto-grow) but the
  pack dropped `'use client'` — next build fails when a server component reaches it via ui/index.
  Docs given a repo-reality note (DESIGN_SYSTEM.md + CLAUDE.md): AskFilingAnswer = DS reference
  implementation, 0 importers; production renderer = CopilotMessage.tsx. 3-agent adversarial
  verify: primitives-delta CLEAN (no existing-variant/export regressions); guard semantics
  confirmed correct across Input/Textarea/Select incl. boolean-error+hint interplay.
  Gates green: typecheck / eslint 0 / vitest 236 / build / all 6 greps.
  **Upstream ledger (report to Claude Design):** (1) Button type='button' default dropped AGAIN;
  (2) Input boolean-error guard dropped x4; (3) brand.light re-added; (4) NEW — Input.tsx missing
  'use client' with client-only hooks (build-breaking downstream); (5) MIGRATION.md not
  regenerated (still v2.1); (6) AskFilingAnswer re-parses markdown per streaming token (perf —
  do not adopt for streaming); (7) minor, now FIXED in-repo (verify + Gemini agreed; pack still
  has them): Select px/pr conflict-order gamble its own header forbids -> explicit per-side
  padding; Notice description lacks break-words (unbroken URL/accession overflows);
  AskFilingAnswer citation-list React keys collide on duplicate `n` -> index-suffixed.
  - *PR B (adoption):* all 8 items landed via 5 file-disjoint agents; implemented TWICE — a
  container rollback mid-task wiped the first (uncommitted) implementation while the remote
  stayed intact, so the branch was re-reset to origin/main and the workflow re-run with the
  first run's port notes baked in. Results identical: 12 StateCard->Notice + delete (+ test
  mock dropped); UnverifiedBadge->Badge warning x2 + delete ("Unverified" literal + tooltip
  kept, peer/fundamentals specs pass unmodified); filing-type chips -> Badge brand/info/neutral
  via getFilingTypeStyles badgeVariant (row tints untouched); Recommended -> Badge solid x2;
  leading-icon fields x3 (watchlist + HERO + FullTextSearch — glow moved to wrapper,
  placeholder unchanged, hero drops to standard field sizing per Neil's decision);
  CopilotComposer -> Textarea composer (controlled value, style maxHeight cap, min-w-0 flex-1,
  shell = documented DS pattern; 15 copilot suites green UNMODIFIED); Card as="section" x6;
  barCursorProps x2. Gates: typecheck / eslint 0 / vitest 236 / build / retirement greps == 0.
  Both-theme fixture screenshots (flag-enabled build): login Notice, company page, peers
  Unverified, watchlist, hero.
- *PR C (rebrand):* landed after the rollback recovery — the 9 sage SVGs were reconstructed
  from Bash outputs in the surviving /root/.claude session transcripts, then byte-verified
  against Neil's re-uploaded zip (all 9 identical). Logo components rewritten (currentColor
  monogram, hook-free mode, server-renderable; theme file + EinsteinLogo deleted); two-tone
  wordmark at Header/AuthShell/full lockup; generate-brand-assets.mjs (sharp + png-to-ico
  devDeps, committed Inter variable woff2 + OFL) -> favicon.ico, apple-touch 180 full-bleed,
  icons 192/512 + maskable(0.62), og-image 1200x630; manifest.ts + icons/themeColor pair +
  JSON-LD raster logo + ?v=2 OG cache-bust; FULL email retheme (9 templates, not 8 — agent
  found send_invite too) with rendered screenshots, legacy palette greps clean, email render
  tests 3/3. Gates: typecheck / eslint 0 / vitest 236 / build; favicon/manifest/head tags
  verified live on the prod server; both-theme home + auth screenshots.
- *PR D (copilot design, zero loss):* CopilotMessage + CitationChip restyled to the v2.2
  evidence-block language — panel card chrome (lift, not tint), mono answer register
  (.copilot-answer/font-data per the DS type roles) with v2.2 GFM manners (mb-3 rhythm,
  hairline tnum tables), brand-tint bordered marker chips, footnote evidence rows (brand-rail
  excerpts w/ pseudo-element curly quotes so exact-text queries keep passing, XBRL tag rows,
  TrustBadge Verified/Cited), compliance row = grounded copy + "{n} citations · {m} verified".
  ALL machinery preserved 1:1: chips/popovers/deep-links/analytics/StreamingText fast path/
  ticker/not_disclosed/followups/paywall — 236/236 green with ZERO test edits (incl. every
  copilot suite). BONUS BUG the visual pass caught: composer auto-grow measured scrollHeight 0
  in a hidden pane and pinned height:0px (invisible composer once opened) — ui/Input.tsx grow()
  now skips unmeasurable elements (upstream ledger item for the pack Textarea). Verified with a
  full filing-page fixture (scripted SSE answer): reading/answer/popover states, both themes.
**PR B port notes (from verify):** composer must stay CONTROLLED (value prop) so prefill
  triggers the layout-effect grow — imperative el.value alone fires nothing; cap height via
  style={{maxHeight:120, overflowY:'auto'}} (className styles the Shell, not the textarea);
  pass className="min-w-0 flex-1" so the Shell flex item fills the composer row.

## Task #28 — Adoption PR 5: Ask-this-Filing (copilot) + final stragglers
**Scope change vs the original plan (recon finding):** AskFilingAnswer is DEAD pack code — never
imported, and its data model is incompatible with the shipped copilot API (id vs n, no `verified`,
no [F#] XBRL grammar, no markdown, different status enum); CopilotMessage's behavior is pinned
verbatim by 6 test files. Swapping it in = a behavior-REGRESSING rewrite (loses verified badges,
XBRL chips, GFM). Decision: KEEP CopilotMessage as the renderer, adopt v2 primitives inside the
copilot surface, keep AskFilingAnswer as the DS-documented artifact, and put its rework/retirement
at the TOP of the upstream ledger.
### Copilot surface (primitives only; renderer/parsers/tests untouched)
- [x] CopilotComposer: textarea KEPT raw (chat-input pattern — v2 Textarea's shell would double
      the composer chrome; upstream candidate: composer variant); send -> icon-only Button
      (name "Send" kept); disclaimer 11px -> xs
- [x] CopilotMessage: error-bubble upgrade/retry -> Button; [n]/XBRL markers + Verified/Cited
      badges + excerpt lines -> text-data-xs; Ask next/Sources labels -> text-xs
- [x] AskCopilotRail: free-taste-exhausted CTA -> Button; "Scoped to this filing" pill -> Badge
      brand; quota lines -> text-xs; sheet shells shadow-2xl -> shadow-e5 dark:none; launcher kbd
      chip raw slate-950 -> black-alpha + text-data-xs (launcher FAB itself kept — deliberate)
- [x] CopilotTeaser/AskFilingCallout/CopilotCoachmark CTAs -> Button (test-pinned copy intact)
- [x] FilingViewer: loading spinner -> SkeletonText mono (role=status); error actions -> Button
      secondary ("Try again" name kept) + buttonVariants primary SEC.gov link; error layout kept
      inline (inside the viewer pane — no nested panel)
- [x] LEFT: dark slate sheet fills (sanctioned navy convention), CitationChip popover,
      FilingWorkspace tabs/resizer, ALL citation/marker logic — 52/52 copilot tests pass unmodified
### Stragglers
- [x] pricing: CTA ternary -> Button primary/secondary with loading (hover:opacity-90 dead);
      StateCard retry buttons -> Button; usage bar -> transition-[width]; plan cards KEPT
      (already tokenized; border-2 emphasis is the deliberate plan treatment); $390/$290, switch,
      CTA names, checkout flow untouched (spec green)
- [x] transition-all now EXTINCT repo-wide: safe sites -> transition; width bars ->
      transition-[width]; the SVG progress ring -> transition-[stroke-dashoffset]
- [x] hover:opacity now EXTINCT: RevokeConfirmModal -> error-emphasis press; contact/ContactForm
      links -> underline hover; UserMenu avatar -> brand-border ring hover
- [x] ThemeToggle + app/error.tsx raw gray -> tokens; UserMenu dot -> warning tokens; DEFERRED
      (documented): CookieConsent + delete-account slate sweeps, crash boundaries
- [x] type-floor one-liners: NotificationBell/Footer/SummaryRisks/notification-prefs/
      EmailChipsInput -> text-data-xs / text-xs
- [x] Gates: typecheck 0 / full eslint clean / vitest 236/236 / build OK; pricing verified both
      themes with fixtures; copilot verified by its 9 unmodified suites (52 tests)
**Review:** The load-bearing recon finding reframed this PR: AskFilingAnswer (the pack's copilot
renderer) is dead code with a data model incompatible with the shipped API — adopting it would
regress verified badges, XBRL chips, and markdown. Kept CopilotMessage; adopted primitives around
it; AskFilingAnswer's rework/retirement is now the TOP upstream ledger item. With the stragglers
sweep, transition-all and hover:opacity are extinct repo-wide and the sub-floor type in app
surfaces rides text-data-xs/text-xs. The five-PR adoption pass is complete.

## Task #27 — Adoption PR 4: marketing home + consolidation
**Scope (approved pass, PR 4 of 5):** home surface fixes + the deferred consolidation. Deliberate
marketing chrome (glass-card, mockup-frame, hero-search glow, lift pills, CTA pill shape) STAYS.
### Home surface (drift + states only)
- [x] app/page.tsx: both page-level skeletons -> Skeleton family (brand-weak bone fill killed;
      role=status wrappers kept, sr-only added)
- [x] HotFilings: bones -> Skeleton (+role=status); error/empty -> GuidanceCard (+loading Button
      retry); source chips -> Badge (new = warning tint for earnings-soon, neutral otherwise);
      View-AI-Summary -> buttonVariants secondary sm; Refresh -> Button ghost; 10px -> xs;
      transition-all -> transition
- [x] TrendingTickers: flame orange -> warning tokens; bones -> Skeleton; error/empty ->
      GuidanceCard; stale/unavailable notice kept inline (status notice accompanying content);
      Refresh -> Button ghost w/ leftIcon; ticker-card transition-all -> transition (lift stays)
- [x] CompanySearch dropdowns shadow-lg -> e3 dark:none (hero glow/input + slate-900 hero fills
      stay — deliberate pattern); SocialProofStrip + FilingPulse slate -> white-alpha tokens;
      FilingPulse 10/11px -> xs, meter -> transition-[width]
- [x] HeroExample: second ambient glow REMOVED (DS §7); mockup chrome + traffic lights stay
- [x] QuickAccessBar/HowItWorks/FeatureShowcase/ReportingThisWeek/CtaBanner: transition-all ->
      transition; ReportingThisWeek 10px -> xs (pill kept — day/time chip, Badge shape unneeded);
      testids/aria untouched (QuickAccessBar spec + e2e green)
### Consolidation
- [x] 3 admin ShimmeringLoader sites -> Skeleton (role=status + sr-only); ShimmeringLoader DELETED
- [x] EmptyState shim DELETED: 7 Summary* sites -> new feature-scoped SectionEmpty (composes
      GuidanceCard; section copy lives with the filings feature, ui layer stays pure); 2 admin
      sites inline GuidanceCard with their filter-aware copy
- [x] Orphans DELETED: DashboardPreview, FinancialCharts (+ spec's chart half — table assertions
      kept), StatCard (transitively orphaned), charts/DeltaBar, charts/Sparkline (-622 lines)
- [x] KEPT: useCountUp (+spec, DS §11 primitive), TrendSparkline (v2 barrel API), StateCard
      (remaining 12 usages = compact form notices on auth/pricing/compare — wrong ergonomics for
      GuidanceCard's panel; upstream candidate: ui/Notice). Compare-page empty-prompt left with
      StateCard for the same reason (single consistent notice component per surface)
- [x] Gates: typecheck 0 / eslint clean / vitest 236/236 (was 237; one FinancialCharts test
      deleted with its component) / build OK; greps clean in scope (remaining transition-all
      sites are filing-page/auth chrome — PR 5 note); both-theme home screenshots
**Review:** Two-part PR. Consolidation: six dead files deleted (-622 lines), ShimmeringLoader and
the EmptyState shim retired with their importers migrated onto Skeleton/GuidanceCard, and the
PR-1-era orphan chain (DashboardPreview -> StatCard -> charts/*) fully removed. Home: marketing
chrome untouched, but every loading/error/empty state now rides the v2 system, source chips are
Badges, the off-palette orange and second glow are gone, and banned utilities (transition-all,
sub-floor type, raw slate, shadow-lg) are cleared from the home surface.

## Task #26 — Adoption PR 3: company page onto the v2 component layer
**Scope (approved pass, PR 3 of 5):** app/company/[ticker]/page-client.tsx + PeerComparisonPanel +
InsiderActivityPanel, ZERO behavior change. Out of scope (recon): CompanyLogo + UnverifiedBadge
(shared leaves, high blast radius — UnverifiedBadge's raw amber flagged upstream: Badge needs a
warning variant), financialTone wiring (already correct), accordion year-toggles + filter chips +
panel toggles (token-compliant segmented controls; tests pin button roles/names like "1Y").
- [x] page-client: filings section -> Card recipe on semantic <section>; year-groups + filing rows
      rounded-lg->xl; per-type tinted row fills KEPT (tint insets on panel, not card fills — same
      call as the watchlist wells); recommended banner: gradient KILLED -> flat brand-weak tint box
      (trial-box precedent); header shadow-sm -> e1
- [x] page-client: 3 full-page states -> GuidanceCard (unsupported-foreign = empty w/ FileTextIcon;
      other two = error) + buttonVariants home actions; filings error -> inline pattern w/ role=alert
      + Button retry; filings empty kept inline + role=status; filings spinner -> Skeleton rows;
      full-page company spinner kept (route gate) + role=status/sr-only
- [x] page-client: Summarize/Generate/SEC-EDGAR/back-home -> buttonVariants; Retry -> Button;
      watchlist star kept raw (token-clean; aria-pressed/label load-bearing)
- [x] page-client: Recommended pills KEPT as solid emphasis chips (tint Badge vanishes on the
      brand-weak banner/row grounds; upstream: Badge solid variant); filing-type badges KEPT
      (tonal map includes info, which Badge lacks; upstream: Badge info/warning variants)
- [x] PeerComparisonPanel: Card recipe; SUBJECT_FILL + 6 local hexes deleted -> seriesColor(0)/
      chartTheme(dark).flat/xAxisProps/yAxisProps; hand-built tooltip -> ChartTooltip (Bar gains
      name={label}); spinner -> Skeleton; testid/h2/rank sentence/Unverified preserved
- [x] InsiderActivityPanel: both sections -> Card recipe; <table> -> DataTable (module-level
      TRANSACTION_COLUMNS; Type tone gain/loss + Badge neutral "10b5-1"; Shares/Value/Date numeric
      right); InsiderTransaction interface -> type alias (DataTable Record constraint);
      spinner -> Skeleton; "1Y" toggles + null-when-empty untouched
- [x] Gates: typecheck 0 / eslint clean / vitest 237/237 (peer+insider+peers-api specs green) /
      build with both panel flags compiled in; both themes verified on the real public
      /company/AAPL route in Playwright with pathname-matched fixtures (bare-array filings,
      {peers}/{transactions} envelopes) — chart chrome, DataTable tones, star, banner all correct
**Review:** Zero-behavior recomposition of the company page (3 files + 1 type alias). The banned
gradient banner and all local chart hexes are gone; the filings surface, both panels, and every
CTA now ride the v2 layer. Three documented keep-decisions: per-type tinted filing rows (insets,
not card fills), solid Recommended chips (tint Badge invisible on tinted grounds -> upstream Badge
solid variant), and hand-rolled filing-type badges (Badge lacks an info tone -> upstream candidate,
same family as UnverifiedBadge's missing warning variant).

## Task #25 — Adoption PR 2: dashboard surface onto the v2 component layer
**Scope (approved pass, PR 2 of 5):** recompose /dashboard, /dashboard/settings, /dashboard/watchlist
+ components/dashboard/* + components/settings/* + components/watchlist/* onto components/ui/* with
ZERO behavior change. Recon: container layer is 0% adopted (atoms partially in settings); no Recharts,
no ShimmeringLoader, no orphans in scope; only BillingPanel has a unit test (preserve its
link /subscribe|upgrade/ + button /manage billing/ roles).
- [x] settings/* (5 comps, 8 identical hand-rolled cards) -> Card (kept inline icon+h2 headers —
      CardHeader/Title would restyle headings, out of zero-change scope); spinner-cards/rows ->
      Skeleton/SkeletonText bones; delete + export buttons -> Button destructive/loading
      (kills 2 of 3 banned hover:opacity sites; ConnectedAccounts unlink became an
      underline-on-hover text action — Button destructive is too heavy for an inline row)
- [x] dashboard/page.tsx: all hand-rolled cards -> Card (quick actions = Link-wrapped
      Card interactive, focus ring on the Link); full-page/saved/watchlist StateCards ->
      GuidanceCard + Button retry; the two IN-CARD errors (subscription/usage) became the
      inline icon+message+retry pattern instead — GuidanceCard-in-Card stacks panel chrome;
      Pro/Free pill -> Badge; section spinners -> Skeleton bones (route-gate spinner stays);
      transition-all -> transition-[width] duration-base. Header Logout text-button kept
      (nav-link pattern, not a button)
- [x] dashboard/error.tsx: both bespoke panels + hand-drawn SVGs + raw buttons -> GuidanceCard
      error + Button (lock icon for the auth variant)
- [x] watchlist/page.tsx: insight cards -> Card (dropped hover affordance — not clickable);
      getStatusBadge -> Badge tonal variants (icon={null} strips beat/miss/new glyphs);
      ticker chip -> Badge neutral; StateCards -> GuidanceCard; 3 Links -> buttonVariants;
      inset metric wells (page-color inside panel) kept — a recess, not a card fill
- [x] WatchlistAddSearch: KEPT hand-rolled (already token-compliant) — search-with-icon matches
      the hero CompanySearch pattern and inputClasses' px-3.5 PAD fights the pl-11 icon inset;
      aligned stray shadows (shadow-sm dropped; dropdowns shadow-lg -> shadow-e3 dark:none).
      Upstream candidate: a leading-icon field variant
- [x] FilingFeed: animate-pulse cards -> Skeleton (+ role=status/sr-only per the PR-1 a11y rule);
      StateCard error/empty -> GuidanceCard + secondary Button retry
- [x] EarningsCalendar: cream-as-card-fill bug fixed -> panel Card recipe on the semantic
      <section> (ul list stays; weak DataTable fit — no numeric/tone columns)
- [x] WhatChangedCard: container -> Link-wrapped Card interactive; DIRECTION chips KEPT —
      financialTone.directionChip is gain/loss (green/red), and the card's calm brand/muted
      treatment is a deliberate, now-documented exception (icons still carry direction)
- [x] Gates: typecheck 0 / eslint clean / vitest 237/237 (BillingPanel roles intact) / build OK;
      both themes verified by rendering the REAL /dashboard, /settings, /watchlist routes in
      Playwright with en_session cookie + pathname-matched API fixtures (uncommitted script)
**Review:** Zero-behavior recomposition of the dashboard surface (12 files): container layer went
from 0% to full adoption (Card/GuidanceCard/Skeleton/Badge/buttonVariants); all three banned
hover:opacity sites are gone. Two mapping judgment calls vs the recon: in-card errors use the
inline pattern (no panel-in-panel), and WhatChangedCard's calm chips stay (deliberate exception
to directionChip, now documented in-code). Screenshot-verified in both themes on live routes with
fixture-fed APIs — feed/calendar fixtures needed the backend's {items}/{events} envelopes
(bare arrays make React Query treat the query as errored via undefined data).

## Task #24 — Adoption PR 1: filing summary surface onto the v2 component layer
**Scope (approved):** recompose the filing page's building blocks on components/ui/* with ZERO
behavior change — same data, same handlers, new composition. DESIGN_SYSTEM.md is canonical.
- [x] StatCard: container onto Card recipe (keep count-up + sparkline + chip API) — value/label
      onto type tokens, sparkline -> ui/TrendSparkline (deleted charts/StatCardSparkline.tsx),
      skeleton -> SkeletonStat inside the Card recipe
- [x] StatCard.Skeleton + filing-page ShimmeringLoader sites -> Skeleton/SkeletonText/SkeletonStat
      (page-client: pre-hydration bones, streaming bones, SummarySectionsSkeleton, filings-list bones;
      also fixed the underscore-cloaked `animate-[shimmer_2s_infinite]` -> `animate-shimmer` token)
- [x] FinancialCharts: **recon found it ORPHANED** — no page imports it (only its unit spec).
      Left untouched per surgical-changes; delete component + spec in PR 4 (consolidation).
      The filing page's real chart is FundamentalsTrendChart (below).
- [x] FinancialMetricsTable -> DataTable (numeric right-align, gain/loss cell tones, icon carries
      direction so it never rides on color alone; caption now reflects actual columns)
- [x] Summary* empty states (ui/EmptyState) -> GuidanceCard variant="empty" via a transitional shim
      inside EmptyState itself (upgrades all 10 call sites incl. admin at once; shim deleted in PR 4)
- [x] page-client error/retry cards -> GuidanceCard variant="error" (+ secondary Button retry;
      warning-toned fallback-summary card intentionally left — it is a warning, not an error)
- [x] FundamentalsTrendChart chrome -> Chart factories (gridProps/xAxisProps/yAxisProps/ChartTooltip,
      seriesColor(0) bar fill, Skeleton loading state, Card recipe on semantic <section>)
- [x] Gates: tsc=0, eslint --max-warnings 0 clean, vitest 237/237 (51 files), production build OK;
      every touched surface is backend-gated (filing page) or orphaned (StatCard's only importers
      are the orphaned DashboardPreview + FinancialCharts — noted for PR 4), so visual verification
      = a throwaway uncommitted harness route rendering each recomposition with fixture data,
      screenshotted in both themes + preview checklist in the PR body
**Review:** Zero-behavior-change recomposition of the filing summary surface onto components/ui/*.
Five files recomposed (FundamentalsTrendChart, FinancialMetricsTable, ui/EmptyState shim,
filing/[id]/page-client skeletons+error card, StatCard) + one deletion (charts/StatCardSparkline).
One real finding: the DataTable caption was static and named columns that conditionally don't render —
the existing no-prior-period spec caught it; fixed with a conditional caption (a11y accuracy win).
FinancialCharts confirmed orphaned; its deletion and the EmptyState-shim inlining are queued for PR 4.

# Task: Sharpen the AI reports via eval-gated prompt-prose waves (post-council activation)

## Task #23 — Revive YoY amplifier (guarded) — TESTED, DROPPED (no ship)
Revived the Wave-4a YoY% amplifier under the now-merged guardrail and re-judged (cli:sonnet, 3×3).
The guardrail prevents the old 4→2 crash (faithfulness held ~3.78), but YoY gives NO measurable gain
and still tempts causal fabrication on salient deltas (full-YoY: capex; Option-B-minus-cashflow: geo).
Neutral-with-downside ⇒ reverted, not shipped (reputation-first). Full analysis in lessons.md.

## Task #22 — Redistribution guardrail — TESTED, DROPPED (no ship; see lessons.md / PR #493)

## Task #21 — Faithfulness guardrail (driver/outlook groundedness), eval-gated — guardrail-first
**Why:** the #487 judge-view fix revealed the *baseline* model fabricates causal/outlook claims the
source doesn't support (invents forward guidance a 10-K never gives; attributes a cash-flow change to a
cause the statement contradicts). numeric_precision stays 1.0 → invisible to deterministic scorers; only
the (now-trustworthy) judge sees it. Highest-value faithfulness lever.
**Change (surgical, 10k/10q/20f-analyst-agent.md):** tighten the Wave-2 driver directive + the
outlook/key_changes directive so the model attributes a cause / states an outlook ONLY when the filing
explicitly does (cite it); otherwise report the change without inventing a driver, and don't manufacture
an outlook a 10-K/10-Q doesn't give. Keep lean — over-correction → timid/generic prose (council concern),
so pressure-test the wording (design panel) for over-refusal/insight-loss before shipping.
**Gate (CLAUDE.md — ship only behind a pass):** judged before/after on a multi-run sample with the
SUBSCRIPTION judge (`--judge cli:sonnet`, NOT the API key), counting causal/outlook G3 fabrication flags;
faithfulness up, deterministic recall/precision/coverage no-regression (regression_gate). Then Wave 4b.

**RESULTS (3 filings × 3 runs, cli:sonnet):** V1 (append caveats) = no effect (faith 3.00→3.11 flat,
causal 6→8). V2 (reword lead directive conditional + DO-NOT prohibition) = causal ~6→~1, but mean flat
(3.11) — fabrication REDISTRIBUTES. **V3 (V2 + a concrete no-cause EXAMPLE — reviewer suggestion) is the
ship:** mean faithfulness **3.00→3.78**, OUTLOOK fabrications **→0**, runs-with-any-fabrication 8/9→4/9,
deterministic PASS. The worked example unlocked the headline gain (see lessons.md). **Shipped V3.**
**Next target (queued):** a "don't present a derived/aggregated figure as reported; don't infer tone"
guardrail — the redistributed modes — which would also let the Wave-4a YoY amplifier return.

## Task #19 — Wave 4 (Copilot prose + golden set + XBRL amplifiers), eval-gated
Judge is now wired (Task #18, merged in #486), so Wave 4 can be judged cheaply. Sequenced as two
reviewable, separately-gated slices:

### Wave 4a — XBRL grounding: amplifiers + a judge-view fix — DONE, shipping
- [x] **FCF relabel** → "Free Cash Flow (OCF - CapEx)" (names the derivation for the model).
- [x] **Working-capital fallback**: when `working_capital` is untagged, derive it from
      Current Assets - Current Liabilities per period (labeled as derived).
- [x] **Judge-view fix** (`evals/runner._xbrl_to_text` 8k→40k): the judge saw `json.dumps(metrics)[:8000]`
      and false-flagged the ~1/3 of metrics past the cut (FCF/ROE/ROA/WC/current ratio) as G3
      hallucinations. Same class as the 60k-excerpt bug. Pulled forward from Wave 5 because it blocks
      trustworthy judging of ANY XBRL-grounded summary. +offline test.
- [x] **YoY% amplifier — DROPPED.** A judged before/after (fixed judge) showed it induced *fabricated*
      cash-flow causal drivers (faithfulness 4→2). Kept the raw prior-period figures (pre-existing),
      dropped the pre-computed delta. See lessons.md; the driver-groundedness guardrail (which would
      let YoY return) is queued as a prose-wave item.
- [x] Gate: 45 offline unit tests; deterministic regression_gate PASS (3-filing live run: precision
      1.0, coverage/depth/specificity 1.0, gate_fail 0, no regression); judged spot-check confirms
      faithfulness holds without the YoY-induced fabrication.

### Wave 4b — Copilot prose + golden-set expansion (copilot_service.py + copilot_golden_set.json)
- [ ] Surgical prompt additions ONLY (prompt is already tool-first + refusal + verbatim + Item cites):
      currency directive (render non-USD in reporting currency, never bare $); sharpen the
      NOT_DISCLOSED explainer to name *where the figure would normally appear*; tool-fallback clarity
      (if a tool returns not_disclosed, cite the filing's own stated figure verbatim or refuse — never
      substitute memory/arithmetic); Wave-2 driver directive (state the cited primary driver).
- [ ] Expand copilot_golden_set.json 1→~5: add a 20-F currency case + an 8-K guidance-refusal case
      (verified against EDGAR). Note: live copilot_runner needs ingested filings; the deterministic
      unit gates (test_copilot_evals.py) run offline in CI regardless.

## Task #18 — Two-tier judge wiring (measure Wave 4 cheaply) — DONE, merged (#486)
- [x] `evals/judge.py`: dispatch `judge_summary` on the model id via `judge_backend()` →
      three backends, existing Opus path refactored (behaviour unchanged):
      - `claude-*` → **anthropic SDK** (`ANTHROPIC_API_KEY`, API credits) — DEFAULT, authoritative.
      - `cli:sonnet`/`cli:opus` → **subscription CLI** (`claude -p --output-format json`), with
        `ANTHROPIC_API_KEY` stripped from the child env so it uses the logged-in Claude
        subscription (OAuth), not API credits. Manual/local only (no OAuth in CI).
      - `glm-5.2`/`openai:<model>` → **OpenAI-compatible** (z.ai), `JUDGE_OPENAI_BASE_URL/API_KEY`
        (fall back to `OPENAI_*`). Cheap CI/fallback judge.
- [x] Shared `_judge_with_retry` (2 attempts, parse, never raises) factored out of the old loop.
- [x] `--judge` help + `evals/RUNBOOK.md` document the backends + the **agreement-check** gate
      (default stays Opus so a cheaper judge can't *silently* weaken the bar).
- [x] Tests: `judge_backend` routing (10 cases), dispatch, missing-cred graceful-fail for each
      backend, retry-then-parse, CLI subprocess mock asserting `ANTHROPIC_API_KEY` stripped + JSON
      parsed from the `result` wrapper. 24 judge tests; full suite **864 passed**; ruff + bandit green.
- [x] **Live wiring smoke** (synthetic G3-hallucination case): all three backends caught the
      fabricated outlook and returned FAIL — `cli:sonnet` matched Opus exactly `{2,2,4,3}`,
      `glm-5.2` within 1 pt. Wiring proven; fuller golden-set agreement check runs with Wave 4.


## Wave 3 — ADR go-live (in PR #484) — RESULTS
- [x] **20-F ADR prose** (3 groundable items: filing-stated risk-change, convenience-translation
      date/rate, restatement/basis flag). Judged before/after on 7 20-F golden filings (fixed judge):
      recall +0.012, no deterministic regression, judge dims flat-within-noise, G3 fabrication flags
      down on most ADRs. **Ship.**
- [x] **`--forms` eval filter** (cheap per-form judged runs; e.g. `--forms 20-F` = 7 vs 22 entries).
- [x] **`USE_STRUCTURED_OUTPUT` evaluation → DON'T FLIP.** Full-set analyst vs structured: structured
      **loses 5.6 pts recall** (0.796 vs 0.851), less consistent, no offsetting gain. Keep OFF; the
      `*-structured-agent.md` prompts stay dormant; no case to invest in structured-agent prose.
- [x] **Currency-consistency guard** (`score_currency_consistency`) — deterministic scorers are
      currency-AGNOSTIC (numeric_precision matched value not unit), so a foreign filer's figures
      rendered as bare `$` (e.g. DKK→`$`, a ~7x distortion) was invisible. New scorer flags bare-`$`
      on non-USD filers (US$/NT$/HK$ excluded via lookbehind; currency-alias native counting).
      WARN-gated (not hard — the slip is intermittent, would flake CI). Validated on real NVO/BABA/ASML.
- [~] **FPI adoption gate / `ENABLE_FPI_FILINGS` flip** — Step A (offline tests) green; B/C eyeball:
      currency correct on **6/7 ADRs all runs**; **NVO (DKK) has an intermittent ~1/3 `$`-slip**
      (the prompt already says "never render non-USD as `$`" yet the model occasionally ignores it).
      GO-LIVE DECISION for founder: (a) flip now, accept the rare DKK slip with the guard monitoring,
      or (b) hold until a runtime currency-enforcement (post-gen: regenerate/flag if reporting_currency
      != USD and bare-`$` present) reduces it. Recommend (b) if DKK-class quality matters at launch.

## Context
The report **is** the product. Highest-leverage, lowest-risk lever right now is improving the AI
prompt prose (content + presentation), each change gated on the eval (deterministic scorers always;
LLM judge for qualitative dims). Full plan: `~/.claude/plans/act-as-an-expert-adaptive-rivest.md`.

## Shipped (merged to main)
- [x] **Wave 0a** — re-verified ASML in the golden set after #478 (drift-free; 26/27 verified). (#479)
- [x] **Wave 1** — figure-citing directives (working capital, full operating/investing/financing
      cash flow, EPS nuance) in 10-K/10-Q/20-F analyst prompts. (#479)
- [x] **Wave V** — visual appeal: bold key figures (prompt prose + deterministic `_build_structured_markdown`);
      editorial-writer path is disabled (decision 3a), so the renderer is the real lever. (#479)
      Eval-gated: recall 0.778→0.816, precision/coverage/gate held, latency flat. Baseline re-pinned.
- [x] **Reset-all endpoint** — `POST /api/admin/summaries/reset-all` (FK-safe, dry-run, keeps
      XBRL/content, `include_saved` opt-in) to refresh summaries after a prompt change. (#480)
- [x] **Phase-2 readiness** — deterministic `score_specificity` scorer (anti-boilerplate + change-language,
      CI WARN-gated) + made the LLM judge reliable (no temperature, max_tokens 4096, json_repair, retry)
      + re-pinned baseline with `mean_specificity=0.9857`. (#481)

## Wave 2 (narrative quality), judge-gated — COMPLETE, shipping
- [x] Add to 10-K/10-Q/20-F analyst prompts: "What changed & why" driver directive, anti-boilerplate
      specificity, risk-factor materiality filter. Verified all forms load (6-K unchanged).
- [x] Judge before/after (DeepSeek, `--runs 3 --judge`) + GLM bake-off, all 78 runs each, 0 errors.
- [x] **Result:** regression gate GREEN — recall +0.009, precision/coverage/gate_fail held,
      specificity flat (−0.0012; deterministic scorer saturated ~0.99). Judge specificity +0.074,
      insight +0.058 (before/after delta valid; both old-cap). No regression anywhere; small positive.
- [x] Deterministic specificity target didn't move (scorer near-ceiling) → Wave 2 is a
      **no-regression prose refinement**, NOT re-pinning baseline (re-pin only on a locked gain).
- [x] Full pytest (818 unit) + ruff + bandit GREEN. Push + draft PR.
- [ ] (Optional, ~$50, founder call) Fixed-cap authoritative judged run on the Wave-2 config for
      trustworthy faithfulness/insight numbers now that the judge sees the full excerpt (528827a).

## MAJOR finding this session — judge truncation artifact (FIXED, 528827a)
- Judge saw `excerpt[:60000]` while the model grounds on the full ~124–165k excerpt → real
  deep-filing facts (buybacks/dividends/segment revenue, late in a 10-K) were false-flagged as G3
  hallucinations, driving faithfulness to 1.96 / judge_pass 0 across all 78 runs — despite
  deterministic numeric_precision 1.0. Proved on AAPL FY25 ($100B buyback at char 73,895, past 60k).
  Raised cap to 200k; verified faithfulness 2→4, insight 3→4 on the same summary. **The pipeline was
  never hallucinating; the judge was under-contexted.**

## GLM-5.2 vs DeepSeek bake-off — COMPLETE (see tasks/archive/glm-5.2-bakeoff.md)
- [x] Full-pipeline env-swap, judge-on, identical Wave-2 prompts. **Quality dead-heat** (deltas within
      noise; both perfect on precision/coverage/gates; 0/78 errors). DeepSeek ~48% faster, ~3.5×
      cheaper. **Decision: stay on DeepSeek; keep GLM-5.2 as a validated env-swap failover.**
- [x] Generalized reasoning-model thinking-disable to GLM/z.ai (264eb65; DeepSeek/Gemini unchanged).

## Method / guardrails (CLAUDE.md)
- Eval-gate every wave (deterministic no-regression + judge hold-or-improve). Re-pin baseline on a locked gain.
- Run the FULL pytest AND `ruff check .` before pushing (lessons.md).
- Surgical edits; keep directives lean (over-prescription → formulaic prose risk).

## False-"reported" earnings dates fix (BIIB 7/1 → real 7/29) — 2026-07-04
Root cause: unguarded ingest treated ANY 8-K Item 2.02 as an earnings release (BIIB pre-announcement
7/1 flipped the 7/29 estimate; TSLA delivery 8-K; MVO distribution notices inserted fresh rows).
Plan approved (plans/please-see-the-attached-magical-rain.md); decisions locked: flip-only sweep,
facts-only past days.
- [x] `is_probable_earnings_release` guard (gap 10–90d OR delta ≤7d) on BOTH flip paths; unified
      single flip site; insert path deleted (`skipped_no_prior`); new RefreshStats counters.
- [x] Past-date hygiene: AV ingest skips past-dated rows; `downgrade_stale_estimates` in refresh;
      `events_in_range` + reporting-this-week serve facts-only past days; dashboard calendar on ET day.
- [x] `scripts/repair_false_reported_earnings.py` (keep/restore/delete, dry-run default, shares the
      engine guard) + `earnings_calendar_job.py --sweep-from/--sweep-to` guarded re-sweep.
- [x] Tests: guard thresholds + BIIB/TSLA shapes, flip-only, AV past-skip, facts-only serving,
      stale downgrade, sweep-window override, repair classification/mutation; time-bombs defused
      (fixed `today=` injection).
- [x] Docs: strategy §3.5 implemented-rules block, DEPLOYMENT one-shot `--args` runbook, lessons.md.
- [ ] Verify: targeted pytest → full unit suite → ruff; push; draft PR.
- [ ] Prod (user, after merge+deploy): repair dry-run → --execute → guarded re-sweep → probe
      /api/calendar (BIIB on 7/29 estimated, not 7/1 reported).

---

# Task: Homepage sections keep/fix/kill — Trending Filings & Market Movers (2026-07-06)

**Status: APPROVED 2026-07-06 (Market Movers: HIDE; Trending Filings: option B = hide +
immediate EDGAR rebuild) — IMPLEMENTED on this branch (PR #571).** Full evidence:
`tasks/homepage-sections-review-findings.md`. What shipped: `NEXT_PUBLIC_ENABLE_MARKET_MOVERS`
default-off flag (section + prefetch gated); HotFilings/FilingPulse removed from the homepage and
replaced by the EDGAR-native "Notable filings" section (`notable_filings_service` scan/score/serve,
`GET /api/notable_filings`, `scripts/notable_filings_job.py` Cloud Run job + `/internal` seed
trigger, `notable_filings` table + migration); impression instrumentation
(`homepage_section_viewed` via SectionImpression on the new section + ReportingThisWeek) +
`notable_filing_clicked`; dead-integration allowlist gate + lesson; docs updated
(DEPLOYMENT §12, ARCHITECTURE, CONFIGURATION). Ships dark — rollout steps in DEPLOYMENT.md §12.
REMAINING (separate teardown PR, ~1 deploy later): B2 + B3 below.

## Phase A — zero-risk prep (any verdict)
- [ ] A1 (S, 2–3h): `homepage_section_viewed` impression event (IntersectionObserver hook) on both
      sections + ReportingThisWeek baseline; fix hardcoded `source:'stocktwits'` in
      `market_mover_clicked`. Files: new `frontend/lib/useSectionImpression.ts`, `HotFilings.tsx`,
      `TrendingTickers.tsx`, frontend unit tests.
- [ ] A2 (S, 1–2h): stop rendering `Last error: …` internals to users —
      `backend/app/services/trending_service.py:74,110-113,119-121,141-142` + assertion in
      `tests/unit/test_stocktwits_fmp.py`. (Moot if B1 ships in the same deploy.)
- [ ] A3 (30 min, Neil, no code): run PostHog queries P1–P6 from findings §3.

## Phase B-MM — Market Movers: HIDE now via flag; permanence ratified at day 30 (amended per adversarial pass)
- [ ] B1 (S, 1–2h): flag-gate `NEXT_PUBLIC_ENABLE_MARKET_MOVERS` default-off in `featureFlags.ts`;
      conditional render at `frontend/app/page.tsx:224-230` + skip `fetchTrendingInitial`
      prefetch (`frontend/lib/serverApi.ts:143` + call site) when off. Verify build + e2e +
      both themes on preview.
- [ ] B2 (M, 4–6h, follow-up PR ≥1 deploy later — NOT data-gated; the pipeline is unlicensable
      per findings §4.2.1, only the slot's future replacement is a day-30 question): delete
      `routers/trending.py` (+ mount), `services/trending_service.py`,
      `tests/unit/test_stocktwits_fmp.py`, `TrendingTickers.tsx` + companies-api fns +
      `queryKeys.trendingTickers`, and the flag. `integrations/stocktwits.py` may stay
      (roadmap A3/B4 names the signal) with the caveat that future use needs a license
      (Stocktwits ToS Apr 2026 §5).
- [ ] B3 (S, 2h, pairs with B4): retire `integrations/fmp.py` + `FMP_*` settings + doc rows;
      update `docs/ARCHITECTURE.md:156-157` + stale docstrings; add `lessons/` entry
      (dead-integration sweep + machine gate).

## Phase B-TF — Trending Filings: minimal honest fix (recommended, amended per adversarial pass)
- [ ] B4 (M, 4–6h): `services/hot_filings.py` — dedupe one-per-company, 7-day freshness floor
      (matches the "this week" title; tunable — self-omission is the safety valve),
      **empty result below 3 qualifying companies**, `recency` in sources only when >0, delete
      dead FMP/Finnhub calls+components; `pulse_service.py` — **suppress component breakdown
      when only velocity/type are active** (tier only); `routers/hot_filings.py` — remove
      zero-score fallback, drop public `force_refresh`.
      New `tests/unit/test_hot_filings_ranking.py`; update tz/pulse tests.
- [ ] B5 (S, 2–3h): self-omit when empty incl. header (ReportingThisWeek precedent), retitle to
      **"New filings this week"** + honest coverage subtitle (`page.tsx:191`), fix false
      "last 24 hours" empty-state copy (`HotFilings.tsx:101`); frontend render test.
- [ ] B6 (L, 2–3 days optimistic — decision at 30-day checkpoint ~2026-08-05, or immediately if
      Neil picks the runner-up): EDGAR-wide `notable_filings` service (edgartools/Atom poll via
      edgar layer, 8-K item materiality, recognizability filter vs microcap junk,
      one-per-company, cron via `/internal/jobs/*`; link cards to `/company/{ticker}` to avoid
      cold-ingest latency). Frontend mostly unchanged.

Sequencing: PR 1 = A1+B1+B4+B5 (~1.5 days; A2 moot once B1 ships in the same deploy — include
only if the hide is deferred); PR 2 = B2+B3 one deploy later; B6 gated on the checkpoint.
