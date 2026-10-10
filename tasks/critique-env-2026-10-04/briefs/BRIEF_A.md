# Assessment A — Design review (design director). Isolated from Assessment B.

Read BRIEF_COMMON.md first (same directory). You are the unanchored design judgment: do NOT run the
Impeccable detector (`impeccable detect`), do not inject detect.js, and do not read any detector output
or anything named `B-*` in the evidence directory. Think like a design director reviewing a research
product for investors. The chat deliverable is assembled by the orchestrator; you return structured
findings only.

## What to do, in order
1. Read the current docs named in the common brief (DESIGN.md, frontend/DESIGN_SYSTEM.md, relevant
   lessons) and the primary-target source: `frontend/app/filing/[id]/page.tsx`, `page-client.tsx`,
   `StreamingSummaryDisplay.tsx`, `features/summaries/components/{SummaryDisplay,SummaryBlocks,
   FinancialMetricsTable,SummaryActionsBar,GenerateSignupGate,SummaryRisks}.tsx`,
   `features/filings/components/{SourceTrace,MetricSourceLink,WhatChanged,SupersededFilingNotice}.tsx`,
   `features/filings/components/copilot/{FilingWorkspace,AskCopilotRail,CopilotMessage,CitationChip,
   FilingViewer,SecondaryPaneTabs,CopilotTeaser,CopilotCoachmark,CopilotComposer,AskFilingCallout,
   AskAboutSelection,PaneResizer}.tsx`, `components/Header.tsx`, `components/ui/*.tsx`,
   `app/globals.css`, `tailwind.config.js`. Skim the supporting surfaces: `app/page.tsx` +
   `features/marketing/components/{LandingHero,HeroExample,TraceToSourceDemo,AskFilingDemo,
   PricingSection}.tsx`, `features/companies/components/CompanySearch.tsx`,
   `features/search/components/FullTextSearch.tsx`, `app/company/[ticker]/page-client.tsx`,
   `features/analysis/components/{AnalysisPageClient,PeriodPicker,KpiStrip,MetricsTable,TrendCharts,
   NarrativePane,AnalysisTeaser}.tsx`. Record file:line for every claim you make from source.
2. Inspect the batched evidence: view EVERY baseline screenshot for the filing page (names starting
   `filing-`) and at least the desktop+mobile, light+dark shots of `home-`, `search-`, `company-`,
   `analysis-` with the Read tool, and read the matching .json records (console, overflow, focus trail,
   styles, aria). Note the exact viewport sizes from the records.
3. Make the DESIGN SPECIFICITY verdict before anything else: is the composition, interaction and
   visual language grounded in THIS product (an investor's research desk reading SEC filings), or
   could an unrelated SaaS use it unchanged? Judge coherence, structural sameness, category-
   interchangeable choices, missed opportunities for product character. Then holistic design:
   hierarchy, IA, emotional fit, discoverability, composition, typography, color, accessibility,
   states, copy, edge cases; cognitive load (the 8-item checklist: single focus, chunking <=4,
   grouping, visual hierarchy, one thing at a time, minimal choices <=4 per decision point, working
   memory, progressive disclosure; count failures; list every decision point with >4 visible
   options); emotional journey (peak-end, valleys, reassurance at high-stakes moments such as
   starting a generation, hitting a paywall, an error, verifying a number).
4. Simulated persona walkthroughs of the research task (hypotheses to investigate, NOT user research):
   Jordan (confused first-timer, never used a filing product), Alex (experienced equity researcher,
   impatient power user who wants keyboard paths and density), Sam (keyboard-dependent / screen-reader
   user, cannot see hover states, needs visible focus and announced state). Walk each through:
   homepage → find Apple → pick the FY2025 10-K → read the summary → verify "Total net sales
   $416,161M" and a risk claim against the source → come back and continue. Use the evidence files
   `filing-light-desktop-anon-tabtrail`, `filing-light-desktop-pro-ask-keyboard`,
   `filing-*-sourcetrace-*`, `filing-light-desktop-pro-trace-nocontent` (production reality: no
   in-app text), `filing-light-desktop-pro-trace-content` (fixture), the `home-*-search-typed`,
   `company-light-desktop-*`, `analysis-*-pro*` records. Report specific red flags: the exact
   element and interaction that fails each persona.
5. Score the ten Nielsen heuristics 0–4 for the PRIMARY workspace (the filing page as Read+Operate),
   with a one-line reason and evidence file for each; n/a is allowed only where a heuristic genuinely
   cannot apply (state the reason) and the applicable maximum then shrinks by 4. Keep supporting
   marketing observations (homepage, Persuade) separate from the primary score: give the homepage a
   short separate note (not a second full table). Be honest: 4 means genuinely excellent; most real
   interfaces land 20–32/40.
6. Produce 3–5 priority issues (ordered), 2–3 strengths to preserve (specific about why they work),
   persona red flags, minor observations, and 3–5 provocative questions. Separate shared-system
   causes (tokens/components/global CSS) from local route problems and from documentation drift
   (docs say X, code does Y). Tie each proposed change to the research task and to observed evidence.
   For each issue state whether it would change an established decision listed in the common brief.
7. Targeted verification: for any finding you are not sure reproduces, run at most a handful of
   targeted captures with the harness (prefix --out with `A-`). Do not start an open-ended polish
   loop. Record coverage limitations honestly (e.g. no real screen reader; hover on touch; headless).

## Return (StructuredOutput schema is enforced; fill every field)
design_specificity: {verdict: 'authored'|'mixed'|'interchangeable', rationale, missed_opportunities[]}
heuristics: [{n, name, score (0-4 or 'n/a'), reason, evidence}] x10, applicable_max, total, band
homepage_note (string), cognitive_load: {failures: [...], decision_points_over_4: [...], rating}
emotional_journey: {peaks: [...], valleys: [...], high_stakes_moments: [...]}
strengths: [{title, why_it_works, evidence}] (2-3)
priority_issues: [ {id, severity, confidence, classification, surface, mode, title, task_impact,
  reproduction, evidence_screenshots[], source_refs[], observed, desired, smallest_change,
  affected_components[], changes_established_decision (string or ''), impeccable_command, effort,
  dependencies, acceptance_criteria[], fixture_dependent (bool), notes} ] (3-5)
personas: [{name, archetype, walkthrough_summary, red_flags: [{element, failure, evidence}]}] (3)
minor_observations: [{title, detail, evidence, classification}]
documentation_drift: [{doc, claim, code_reality, evidence}]
questions: [string] (3-5)
coverage: {views_inspected[], themes[], viewports[], states[], not_inspected: [{what, why}],
  targeted_captures_run[]}
