# Multi-Period Analysis — Production Output Review Prompt (Claude Fable 5)

> **What this is.** A ready-to-run prompt for a Claude Code session on `claude-fable-5`, auditing
> the first production runs of Multi-Period Analysis (MSFT annual + quarterly) end-to-end:
> rendering vs. intent, data correctness vs. SEC XBRL, EdgarTools leverage, UX enhancements, and
> legal cover. It follows Anthropic's
> [Prompting Claude Fable 5 guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5)
> (goal-over-steps, grounded progress claims, explicit boundaries, parallel subagents,
> fresh-context verification) and the cross-model
> [prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
> (XML structure, role, context/motivation, investigate-before-answering).
>
> **How to run**
> 1. Start a fresh Claude Code session on this repo with model `claude-fable-5`
>    (effort `xhigh` recommended; `high` is fine).
> 2. Attach the nine screenshots — five from the MSFT **quarterly** run, four from the MSFT
>    **annual** run. The prompt degrades gracefully without them (key observations are
>    transcribed inside), but attach them for pixel-level verification.
> 3. Paste everything below the cut line as the first message.
> 4. Expect a long autonomous run. It ends with an Investigation Summary + Remediation Plan for
>    your approval. **No code changes are made in this session.**

---8<--- copy everything below this line ---8<---

<role>
You are a staff-level reviewer doing a production-readiness audit for EarningsNerd: part
full-stack engineer (FastAPI/SQLAlchemy backend, Next.js/TypeScript frontend), part financial
data-quality auditor who treats every displayed number as a claim to be verified against SEC
XBRL, part product-minded UX critic. You are rigorous about evidence and comfortable saying
"this is fine as designed" when it is.
</role>

<context>
EarningsNerd is an AI-powered SEC filing analysis platform. Its Pro flagship feature,
**Multi-Period Analysis** (`/analysis`), shipped in PR #552 (companyfacts ingestion,
deterministic trend engine, grounded streaming AI narrative with verified citations, PDF
export) with polish in PR #555 — both merged. The feature is now live at
https://www.earningsnerd.io/analysis behind `NEXT_PUBLIC_ENABLE_ANALYSIS`.

The owner ran the first real analyses — Microsoft (MSFT, CIK 0000789019), once in **quarterly**
mode (12 periods, 2023Q4†–2026Q3) and once in **annual** mode (10 fiscal years, FY2016–FY2025) —
and captured screenshots of both runs (attached). Pro clients pay for this feature; before
promoting it, the owner needs to know: is the output displaying as designed, are the numbers
right, what is broken, what should be improved, and is the legal exposure covered. Your report
is the basis for the fix/improve roadmap, so a wrong "all clear" is worse than a false alarm —
and an unverified alarm wastes a development cycle.

MSFT fiscal-calendar note so you don't trip on it: Microsoft's fiscal year ends June 30, so
"FY2025" ended 2025-06-30 and "2026Q3" is the quarter ended 2026-03-31. SEC registrants file no
Q4 10-Q; Q4 values are derived as FY minus Q1–Q3, which this feature does explicitly (the †
"computed Q4" convention).
</context>

<materials>
- **Screenshots (attached).** Quarterly run: period picker + KPI cards, narrative sections
  ("The trajectory" → "What to watch next"), Sources list [1]–[28], "Metrics by period" table
  (unscrolled + scrolled right). Annual run: picker/KPIs/charts, narrative, Sources list
  [1]–[29], full table with CAGR column. If the screenshots are missing, say so in the report
  and proceed — <triage_observations> transcribes the essentials.
- **Live page:** https://www.earningsnerd.io/analysis (running an analysis needs a Pro login you
  don't have; the public shell — copy, footer, disclaimers — is fetchable).
- **This repo** — see <codebase_map>. Read `CLAUDE.md`, `frontend/DESIGN_SYSTEM.md`, and
  `tasks/lessons.md` before forming opinions; the design system defines what "displaying as
  expected" means for theme, type, tone colors, and tables.
- **EdgarTools** (the library underpinning EDGAR access): https://github.com/dgunning/edgartools
  and https://edgartools.readthedocs.io/en/latest/ (latest release ~5.40.x, June 2026).
- **SEC ground truth:** `https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json`
  (send a proper `User-Agent` and stay well under 10 req/s per SEC policy — this repo has its
  own `sec_rate_limiter` conventions for a reason).
- **Merged PRs #552 and #555** for design intent, review history, and what was explicitly
  declined (e.g. a `rounded-xl` suggestion was rejected on evidence in #555).
</materials>

<codebase_map>
Pre-mapped by a scout pass. Line numbers may have drifted — re-locate before citing them as
evidence, and correct the report wherever reality differs.

Backend:
- `backend/app/services/trend_analysis_service.py` (~936 lines) — the engine.
  `DATASET_CONCEPT_ORDER` (~50-62) fixes the metric set; `_growth` (~199-203) computes deltas as
  `(current − prior) / abs(prior)`; `_cagr` (~206-210) with an **annual-mode-only** guard
  (~364-374) that also excludes `unit == "pure"` series (margins, current ratio). F# markers are
  assigned per valued point (~387-393); server-side F#→[n] resolution lives in
  `resolve_narrative_citations` (~692-721) driven by `_MARKER_RE` at ~669:
  `r"\[\s*F\s*(\d+)\s*\]"` — single markers only. Sources-list entries come from
  `_point_citation` (~672-689), which appends `" — derived Q4"` whenever `point["derived"]` is
  truthy (~677-678). The "verified citations" badge value is `grounded = len(citations)` —
  distinct *resolved* markers. Narrative is cached in `TrendAnalysis` keyed by dataset
  fingerprint + `PROMPT_VERSION`.
- `backend/app/services/facts_service.py` (~1635 lines) — companyfacts ingestion. The
  Multi-Period path fetches **raw SEC JSON via httpx** (`_fetch_companyfacts_async` ~1465-1492)
  — EdgarTools is NOT on this path. FY/Q labelling is derived from period windows, never
  trusted from `fp` (~1116-1156). Two distinct things stamp `source="derived"`:
  `derive_q4_facts` (~1282-1316, true FY−Q1−Q2−Q3 derivation, flows/USD only, never per-share)
  and `derive_same_period_metrics` → `_make` (~1334-1345), which marks computed metrics
  (margins, FCF, working capital, current ratio) as `derived` for **every** period.
- `backend/prompts/trends-analyst-agent.md` — the narrative prompt (loaded via
  `get_named_prompt`). Hard rule #2 (~14-17) demands single `[F#]` markers after every figure;
  it gives no guidance forbidding multi-reference forms.
- `backend/app/routers/analysis.py` — coverage (auth) / dataset + SSE stream + PDF (Pro,
  `can_analyze_trends`); monthly cap via `check_analysis_limit`; `ANALYSIS_*` caps in config.
- `backend/app/services/export_service.py` — `generate_analysis_pdf_html` (~250-354, WeasyPrint);
  reuses the derived † (~283-284); its footer (~348-351) has **no** "informational purposes /
  not investment advice" line, unlike the summary PDF (~120).
- `backend/app/services/edgar/` — EdgarTools wrapper for the *per-filing* extraction pipeline
  (separate from companyfacts). `backend/requirements.txt` pins `edgartools==5.40.1`.
- Tests: `tests/unit/test_trend_analysis_service.py` (CAGR-quarterly=None is asserted —
  annual-only is intended), `test_analysis_stream.py` (citation resolution: single markers
  only), `test_companyfacts_ingest.py` (Q4 derivation + computed metrics; nothing asserts the
  Sources-list excerpt text), `test_facts_service.py`.

Frontend (feature code under `frontend/features/analysis/`):
- `components/AnalysisPageClient.tsx` — orchestrator; renders KpiStrip / TrendCharts /
  NarrativePane / MetricsTable; PDF blob download; page footer line ("† = computed Q4",
  ~317-320) with no investment-advice language of its own (the global `components/Footer.tsx`
  ~64 carries "Data sourced from SEC EDGAR. Not investment advice.").
- `components/NarrativePane.tsx` — narrative body is plain
  `<ReactMarkdown remarkPlugins={[remarkGfm]}>` (~128) with **no components map**: resolved
  `[n]` citations render as literal text, and any unresolved `[F…]` text passes through
  verbatim. The Sources list (`CitationList`, ~19-48) is the only styled citation surface. The
  DS-blessed chip renderer exists in `features/filings/components/copilot/CopilotMessage.tsx`
  (DESIGN_SYSTEM.md documents the `[n]`/`[F1]` chip contract) and is NOT reused here.
- `components/MetricsTable.tsx` — wraps `components/ui/DataTable.tsx` in
  `<div className="overflow-x-auto">` (~114); DataTable supports a sticky *header* only — no
  sticky first-column capability exists anywhere in the repo. Delta text via
  `fmtPercent(growth * 100, …)` + `financialTone` (~59-62), no sign-flip guard. † dagger from
  `point.derived` (~49-57).
- `components/TrendCharts.tsx` — Recharts (^3.9); four fixed-height panels
  (`className="h-56"`, ~134); no legend/expand/data-label affordances; no expand pattern exists
  anywhere in the codebase.
- `components/KpiStrip.tsx` — four tiles; growth line = CAGR (annual) or latest YoY (quarterly).
- `components/PeriodPicker.tsx` — mode toggle, chips, † on derived-Q4 chips.
- `api/analysis-api.ts` — types + SSE reader; on `complete` the buffered raw tokens are replaced
  by the server-resolved narrative.
- `frontend/lib/financialTone.ts` — `directionOf` (~16-19) is purely sign-based
  (`n > 0 ? 'up' : 'down'`); no metric-aware inversion exists.
- `frontend/lib/featureFlags.ts` `ENABLE_ANALYSIS` + `app/analysis/layout.tsx` notFound() gate.
- No CSV/XLSX/PNG export utility exists anywhere in the frontend (`recharts` is the only chart
  dep; no `xlsx`/`papaparse`/`html2canvas`/`file-saver`) — owner item 2 is greenfield.
</codebase_map>

<owner_observations>
Verbatim asks from the product owner. Items 1–3 are enhancement requests to scope; 4–6 are
suspected defects to confirm and root-cause; 7 is a delegated review.

1. Charts should be expandable/collapsible so the user can focus more or less on them.
2. Pro users should be able to export a specific chart or table in multiple formats (image,
   CSV/Excel).
3. Users should be able to toggle data labels on charts.
4. The citations in the AI trend analysis do not look well formatted. Also check that the
   references cited in the body match the numbers in the "Sources — every figure verified
   against SEC XBRL" list.
5. No CAGR values are listed in the **quarterly** Metrics-by-period table.
6. The "Metric" (leftmost) column should stay visible when scrolling the Metrics-by-period
   table horizontally — the screenshots show it scrolled out of view.
7. Have a legal-review subagent check that we're covered for mistakes — "not investment
   advice", etc.
</owner_observations>

<triage_observations>
Findings from a first-pass read of the screenshots. **Treat every one as unverified**: confirm
or refute each with code and data evidence. A refutation with evidence ("by design because X,
here's the code") is as valuable as a confirmation. These double as a transcript if the
screenshots aren't attached.

T1 — "derived Q4" label appears on values that are not derived Q4s. Quarterly Sources list:
  `[20] Free cash flow = 15,803,000,000 (2026Q3) — derived Q4`, `[26] Current ratio = 1.28x
  (2026Q3) — derived Q4`, `[13] Net margin = 47.3% (2026Q2) — derived Q4`. Annual Sources list:
  `[9] Gross margin = 64.0% (FY2016) — derived Q4`, `[16] Net margin = 22.5% (FY2016) — derived
  Q4` — "derived Q4" on fiscal-year rows is nonsensical on its face. Suspected root cause: two
  meanings share one flag — `derive_same_period_metrics._make` (facts_service.py ~1343) stamps
  computed metrics `source="derived"` for **every** period, and `_point_citation`
  (trend_analysis_service.py ~677-678) renders any `derived` point as "— derived Q4". The
  frontend † dagger (MetricsTable, PeriodPicker) and the PDF † inherit the same conflation —
  which is why "† = computed Q4" appears in annual mode where it cannot mean Q4. Confirm the
  chain, check the annual inconsistency (annual `[28] Working capital (FY2024)` carries no tag
  while `[24]/[25]` FY2016/FY2025 do — explain why), and sweep for every other surface that
  reads this flag. Note: no test asserts the Sources-list excerpt text, so a fix needs one.

T2 — Raw F-markers leak into the rendered narrative. Quarterly body: `[F58, F59, F60]`,
  `[F222 vs F211]`, `[F72, F84]`, `[F125, F126]`. Annual body: `[F1..F10]`, `[F31..F40]`,
  `[F9,F10]`, `[F91..F100]`, `[F211..F220]`. Suspected root cause: `_MARKER_RE`
  (trend_analysis_service.py ~669) matches only a single bracket-adjacent `[F<digits>]`, so
  list/range/"vs" forms yield zero matches and ship verbatim; the narrative prompt
  (trends-analyst-agent.md, hard rule #2) demands single markers but never forbids multi-ref
  forms, so the model improvises them. Two knock-ons to confirm: (a) the "N verified citations"
  badge counts only resolved markers, so every leaked multi-ref is an *unverified numeric
  claim* standing next to a "verified" badge — assess against the feature's grounding promise;
  (b) fix layering — tighten the prompt contract, extend the resolver to expand multi-refs, or
  both (belt-and-braces recommended; resolver-side handles cached narratives and model drift).
  Separately: resolved `[n]` citations render as plain text because NarrativePane uses bare
  ReactMarkdown — no chip, no link to the Sources row — while the DS citation-chip contract and
  the CopilotMessage renderer already exist. Assess reuse.

T3 — Body↔Sources numeric mapping (owner item 4). Spot checks pass — quarterly: [1]=$56.2B
  2023Q4 revenue, [2]=$82.9B 2026Q3, [9]/[10] gross margins, [22]/[23] LT debt $42.0B→$31.4B;
  annual: [12]/[13] operating margin 28.6%→45.6%, [26]/[27] current ratio 2.35×→1.35×,
  [28] working-capital −57% FY2024. Verify the full mapping 1:1 (all 28 + all 29), including a
  subtle case: growth-rate claims citing *level* sources (quarterly: "YoY gains of +18.4% [3]"
  where [3] is a revenue level) — confirm that matches the intended contract ("the narrative
  only cites values from this dataset") and that repeated markers correctly reuse one number.

T4 — CAGR in quarterly mode is empty **by design**: the engine computes CAGR under an
  annual-only guard (trend_analysis_service.py ~364-374) and a test asserts quarterly
  `cagr is None`. So this is not a data bug — it is a product/UI question: a permanently empty
  CAGR column in quarterly mode is dead UI. Recommend either hiding the column in quarterly
  mode, or computing an annualized CAGR from quarterly endpoints (spec the guardrails — the
  annual version already nulls out on ≤0 endpoints and ratio units). State which you'd ship.

T5 — Sticky metric column (owner item 6), confirmed absent by the scout: MetricsTable wraps
  DataTable in `overflow-x-auto` (~114) and DataTable supports a sticky *header* only — no
  sticky-first-column capability or DS pattern exists in the repo. Spec the fix as a reusable
  DataTable capability (opaque bg in both themes, hairline edge, works with the sticky header),
  not a one-off hack.

T6 — Nonsense percent changes on sign-flipping/near-zero-base series. Quarterly investing cash
  flow: 2024Q1 +$503.0M → 2024Q2 −$71.9B renders "QoQ −14,399.2%" (the Activision quarter);
  also "+212.9%", "−140.5%", "−168.7%". Annual financing CF: "−499.5%", "+200.2%"; investing CF
  "−327.6%". Root cause to confirm: `_growth` = `(current − prior)/abs(prior)`
  (trend_analysis_service.py ~199-203) has no sign-change guard, and the frontend renders the
  raw value. Finance convention is "n/m" (not meaningful) across sign changes; decide where the
  guard belongs (server, so PDF and narrative inherit it) and what the display shows.

T7 — Direction/tone semantics: increases render green even where up isn't good — quarterly
  capex "+54.0%", annual capex "+45.1%", current liabilities "+12.7%" gain-colored, and annual
  long-term debt "−5.9%" loss-colored (a debt *reduction* shown red reads backwards to
  investors). Confirmed mechanism to verify: `directionOf` (financialTone.ts ~16-19) is purely
  sign-based and no per-metric inversion exists. Decide the register: metric-aware good/bad
  coloring (capex/debt/liabilities inverted), or a deliberately neutral "direction, not
  judgment" convention (in which case say so and consider neutral color for those rows). Check
  what the narrative and inflection signals imply the product's stance already is.

T8 — EPS in derived quarters: quarterly table leaves EPS (basic and diluted) blank ("—") in
  2023Q4/2024Q4/2025Q4. Confirmed intent: `derive_q4_facts` never derives per-share units
  (EPS is not additive — documented in the docstring). Remaining question is presentation:
  is silent "—" right, or should derived-Q4 EPS = NI ÷ diluted shares (marked †), or a hint
  explaining the blank? Recommend one.

T9 — Charts: (a) no visible series legends on any of the four charts — three unlabeled lines on
  Margins/Cash/Balance-sheet panels are unreadable without hover (verify whether tooltips are
  the only affordance); (b) mixed-magnitude series share one axis — annual Balance sheet plots
  equity (→$343.5B / $414.4B quarterly) against debt and cash (~$30–40B), flattening the latter
  into the baseline; (c) panels are fixed at `h-56` (TrendCharts.tsx ~134) with no expand
  affordance anywhere in the codebase. Fold fixes into the enhancement scoping (owner items 1–3
  touch the same component).

T10 — Margin deltas are relative-percent, not percentage points: quarterly net margin
  47.3%→38.3% renders "QoQ −19.0%" (arithmetically right, conventionally surprising — finance
  readers expect −9.0pp); KPI card "NET MARGIN YoY +4.0%" is 36.9%→38.3% relative. Decide and
  recommend a house convention (pp for margin-type metrics is standard).

T11 — Minor: annual narrative "an 1,700-basis-point expansion" (grammar); large vertical gaps
  between narrative sections in the quarterly run; annual net-margin KPI card shows no
  sub-metric where the other three show CAGR (if margins deliberately get no CAGR, consider pp
  change instead of blank); Sources list numbers rendered as plain monospace lines — check
  overflow behavior at mobile widths.

Numbers that already re-derive cleanly from public MSFT figures (use as anchors, not as a
substitute for Phase 4): FY2025 revenue $281.7B / net income $101.8B; FY2016 revenue $91.2B;
FY2018 net income $16.6B (TCJA charge — the narrative correctly calls it a one-time tax
effect); quarterly derived 2023Q4 revenue $56.19B matches MSFT's reported Apr–Jun 2023 quarter;
2026Q2 net-margin spike (47.3%, NI $38.5B) correctly flagged by the narrative as anomalous.
</triage_observations>

<mission>
Work in phases. Each phase states the outcome it must establish — how you get there is your
call. Phases 2, 4, and 6 are natural subagent fan-outs and can run in parallel with code
reading once Phase 1 gives you enough shape.

**Phase 0 — Orientation.** Read `CLAUDE.md`, `frontend/DESIGN_SYSTEM.md`, `tasks/lessons.md`,
and skim PRs #552/#555 (description + review threads). Outcome: you know the design intent and
the standards output is judged against.

**Phase 1 — Feature comprehension.** Read the analysis feature end to end: companyfacts
ingestion → `financial_fact` → dataset build (periods, derived Q4, YoY/QoQ/CAGR, signals) → F#
citation system → narrative generation (prompt + streaming + verification + caching) → API →
frontend rendering (charts, table, narrative, sources, PDF export). Outcome: you can explain
where any pixel in the screenshots came from.

**Phase 2 — EdgarTools capability study (required before any plan is written).** Study the
EdgarTools docs and repo, and this repo's actual usage of it (`backend/app/services/edgar/`,
`requirements.txt` pin vs. current release). Outcome: a capability matrix mapping each pipeline
stage (companyfacts retrieval, standardized metrics, fiscal-period labelling, quarterly
derivation, multi-period statement stitching, Form 4, full-text search) to: what we use today /
what we hand-rolled / what EdgarTools offers natively (e.g. `Company.get_facts()` +
`facts.query()`, standardized multi-period statements) / whether adopting it would simplify or
harden the pipeline, with migration risk. Note version-variance risk explicitly — this repo
already wraps EdgarTools defensively (`ownership_extractor`), and the pinned version likely
trails the current release. Any remediation step that touches data plumbing must cite this
matrix.

**Phase 3 — Rendering & correctness audit.** Verify every item in <owner_observations> (4–6)
and <triage_observations> against the code. Outcome: each item classified
confirmed-bug / by-design / enhancement, with root cause at file:line for bugs, user impact,
and severity per <severity_rubric>. Sweep for adjacent defects the seeds imply (e.g. if the
derived-Q4 flag is conflated in Sources, is the same flag misused anywhere else — PDF export,
table daggers, provenance checks?). Judge rendering against `DESIGN_SYSTEM.md` in both themes.

**Phase 4 — Independent data validation.** Re-derive the displayed numbers from SEC ground
truth, not from our own pipeline: fetch MSFT companyfacts (or use EdgarTools directly),
recompute every Sources entry (28 quarterly + 29 annual), all eight KPI-card values, derived-Q4
arithmetic (FY − Q1 − Q2 − Q3) for at least revenue/net income/OCF, and a sample of YoY/QoQ/
CAGR figures from the tables. Match XBRL levels exactly; allow rounding tolerance on displayed
percentages (state the tolerance you used). Also establish what "N verified citations" means in
code and whether the badge's claim holds for these runs. Outcome: a pass/fail table with any
mismatch traced to ingestion, derivation, or display — and an explicit list of anything you
could not validate and why. If outbound SEC access is blocked in the sandbox, fall back to the
repo's fixtures/tests and mark affected rows "not independently validated" rather than implying
they were.

**Phase 5 — Enhancement scoping.** For owner items 1–3 plus the chart issues from T9 (legends,
mixed-magnitude axes) and anything Phase 3 reclassified as enhancement: propose a DS-compliant
approach (which components, which tokens/primitives, both themes, reduced-motion), note reuse
(existing export/PDF utilities, chart library capabilities for labels/legends), estimate size
(S/M/L), and flag risks. Recommendations, not implementations.

**Phase 6 — Legal & compliance review (delegate to a subagent).** Brief: inventory every
disclaimer this feature's user sees (analysis page + footer line "All figures from SEC XBRL…",
PDF export output, pricing/marketing copy, Terms/Privacy/Security pages, AI-narrative preamble
if any); gap-check against standard practice for AI-generated financial content — no investment
advice / no recommendation, accuracy-and-completeness disclaimer, AI-generated-content
disclosure, SEC-data attribution, no advisor-client relationship, "past performance" caution
where relevant; then draft recommended disclaimer text and exact placements. Frame the output
as preparatory research for the owner to take to qualified counsel — it is not legal advice,
and the report must say so.

**Phase 7 — Verify, then synthesize.** Before writing the final report, spawn a fresh-context
verifier subagent and have it attack your highest-severity findings (is the evidence real? is
the root cause actually at that line? does the "fix" break something else?). Drop or downgrade
anything that doesn't survive. Then produce the deliverable per <deliverable> and end the
session. Do not begin remediation.
</mission>

<operating_rules>
- **Investigation only.** The deliverable is your assessment; do not apply fixes, do not
  refactor, do not commit code. Write the report to `tasks/analysis-review-findings.md`
  (uncommitted) and present it as your final message.
- **Investigate before claiming.** Never report a rendering or data bug without having read the
  code responsible for it; never speculate about code you haven't opened; never accept a seeded
  observation without verifying it yourself.
- **Ground every claim.** Before reporting, audit each claim against a tool result from this
  session — a file:line you read, a number you computed, a response you fetched, a screenshot
  region you inspected. If something is not verified, say so explicitly. If tests fail or a
  fetch is blocked, report that faithfully rather than working around it silently.
- **When you have enough information to act, act.** Don't re-derive settled facts or survey
  options you won't pursue; when weighing a choice in a recommendation, give the
  recommendation.
- **You are operating autonomously.** The owner is not watching and cannot answer mid-run;
  proceed without asking on anything reversible and in-scope. Collect genuine decisions
  (scope changes, product-taste calls you cannot settle from the DS or PRs) in the report's
  "Open questions" section instead of stopping. End your turn only when the report is complete.
- **Delegate deliberately.** EdgarTools study, legal review, SEC data validation, and the
  verifier pass are independent workstreams — run them as subagents and keep working while
  they run; intervene if one drifts. Read code directly yourself when a grep would do.
- **Respect external services.** SEC endpoints get a descriptive User-Agent and gentle request
  rates. Do not log in to, or probe, the production site beyond fetching public pages.
- **Severity honesty.** "Working as designed" and "could not verify" are first-class outcomes.
  Do not inflate findings to justify the audit, and do not soften a P0 because the feature just
  shipped.
</operating_rules>

<severity_rubric>
- **P0** — a displayed financial number is wrong, a label materially misrepresents the data
  (users could quote it), or a legal-exposure gap (e.g. no investment-advice disclaimer
  anywhere on a paid financial-analysis surface).
- **P1** — misleading-but-explainable labels, broken core interactions (unusable table scroll,
  unreadable charts), citation system failing its own "verified" promise.
- **P2** — conventions and polish that a finance-literate user would notice (pp vs %, n/m,
  tone semantics), dead UI (empty CAGR column).
- **P3** — nice-to-haves and the net-new enhancement requests.
</severity_rubric>

<deliverable>
Write `tasks/analysis-review-findings.md` and reproduce it as your final message, structured as:

1. **Verdict** — one paragraph: is the feature displaying as designed, and is the data trustworthy,
   overall? Lead with this.
2. **Findings register** — table: ID · severity · area (data/labeling/citations/table/charts/
   legal/other) · one-line finding · status (confirmed / by-design / refuted / unverified) ·
   evidence anchor (file:line, computation, or screenshot ref).
3. **Detailed findings** — for each confirmed item: what the user sees, root cause with
   file:line, impact, recommended fix, acceptance criterion, test to add.
4. **Data validation results** — methodology (source, tolerance), pass/fail per Sources entry
   and KPI card (57 sources + 8 KPI values), any mismatch traced to its pipeline stage, and the
   verdict on the "N verified citations" badge's claim.
5. **EdgarTools capability matrix & optimization opportunities** — per Phase 2, including the
   version-pin gap and any recommended adoptions with risk notes.
6. **Enhancement proposals** — owner items 1–3 + chart improvements: approach, components,
   size, risks.
7. **Legal review** — current-state inventory, gaps, recommended disclaimer text and
   placements, marked "for counsel review — not legal advice".
8. **Remediation plan (for approval)** — phased: A = correctness/label bugs, B = quick wins,
   C = enhancements. Each item: scope, acceptance criteria, tests, size, dependencies. State
   plainly that nothing proceeds until the owner approves.
9. **Open questions** — only decisions that genuinely block the plan.

Write the report for the owner, who did not watch you work: complete sentences, outcome first,
no invented shorthand or arrow chains; introduce every identifier (file, flag, metric) in plain
language the first time it appears. If you must choose between short and clear, choose clear.
</deliverable>
