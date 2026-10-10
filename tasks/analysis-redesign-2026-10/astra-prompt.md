# Prompt for the Astra agent — Multi-Period Analysis data-notes redesign

> **What this is.** A ready-to-paste first message for a GPT-6 Astra / Codex session on this repository,
> continuing the design proposal in `docs/design/analysis-data-notes-redesign-2026-10.md`. It hands over
> everything the proposing session knew, states what is decided and what is open, and names the gates.
> Paste everything below the cut line. The founder's decisions are recorded in the
> "Founder decisions" block, so both tracks apply.

---8<--- copy everything below this line ---8<---

<role>
You are the engineering owner for the Multi-Period Analysis data-notes redesign on EarningsNerd. Read
`AGENTS.md` first (it is your entry point), then `CLAUDE.md`, then `lessons/README.md` sections
"Operations & workflow" and "Frontend & design system". UI work means rule 11: read `DESIGN.md` from
"Overview" on and `frontend/DESIGN_SYSTEM.md` §1–§6, §10 and §12 before touching a component.
</role>

<context>
The founder found the analysis page's source-check presentation unacceptable: repeated amber "Source check
needed" labels, a KPI badge that leaves its card on phones, table columns that triple in width where a
label sits, a narrative whose Red flags print twenty operands inline, and a "26 source checks needed"
count that measures labels rather than issues. A design review (2026-10-10, Claude Code session) produced:

- The proposal and implementation brief: `docs/design/analysis-data-notes-redesign-2026-10.md`. Read it
  whole. Its §2 is observed evidence (code, screenshots, measurements on the repository's own build), §4
  the proposal, §7 the phased brief with files and gates, §8 where it departs from the founder's brief, §9
  the founder's open decisions.
- A runnable prototype: `tasks/analysis-redesign-2026-10/prototype/index.html` (open it in a browser; the bar
  at the top switches data state, proposed vs today's markup, table window, theme, 200% text). It renders
  the real Meta Platforms 12-quarter dataset in three states produced by the repository's own engine from the
  SEC companyfacts payload, with no AI call: 1 clean, 2 incomplete history (ten lineage-less calculations
  plus ten real gaps; this is the production-like state), 3 genuine discrepancy (a simulated source
  conflict). `tasks/analysis-redesign-2026-10/README.md` explains how the data was produced and how to
  regenerate it.
- Two Playwright harnesses and their recorded runs: `harness/measure-current.mjs` (the current components on
  `next build` + `next start`, API mocked in the browser) and `harness/measure-proto.mjs` (the prototype),
  with `measurements/current.json` and `measurements/prototype.json`. Both measure page overflow, KPI
  card-child containment and value alignment, table and column widths, far-right sticky-column occlusion and
  label counts at 1480 / 1054 / 1024 / 768 / 390 / 320 CSS px, light and dark, 200% zoom and 200% text.

Key numbers (state 2). Current build: 33 repeated labels; table 2,076 px at every width with warned columns
234–240 px against 77–105 px clean; the net-margin growth label 54 px past its card at 390 (89 at 320, 126
at 200% text); document 429 px wide on a 390 phone. Prototype: 0 labels (41 one-letter affixes and one
strip), 0 page or card overflow at every configuration, twelve 77 px columns fitting at 1480 with no scroll,
no column ever half-hidden under the sticky metric column.

What the backend already provides and the design relies on: `fact_provenance.provenance_for_fact` gives a
row without stored provenance `validation: needs_review` with reason `legacy_calculation`;
`trend_analysis/dataset_quality.add_comparisons` computes every QoQ/YoY comparison with
`calculated_provenance`, which inherits the operands' validation; the narrative is code-rendered from
`build_observation_catalogue` with a "Source operands:" tail on each red flag; the fidelity scan
(`trend_analysis/fidelity.py`) licenses compact-scale tokens such as $60.8B.

The Track A verification of 2026-10-10 (PR #1197) found a phone overflow in the first prototype build
(chart panels sized by their min-content width; harnesses comparing with `window.innerWidth`) and a
list of brief corrections; all are folded into the proposal's §11 and the sections it names. Read §11
before building.

The quarterly data repair (`docs/quarterly-data-repair.md`, #1191) is a separate operational action. The UI
must look right before it (state 2) and after it (state 1). Never mark a legacy record validated from the
frontend, never hide a note, never show the word "verified".
</context>

<founder_decisions>
Taken on 2026-10-10 (the founder: "regarding decisions for founder - i'm aligned with your
recommendations"), so Track B is unblocked:
1. Note mark: letters a, b, c.
2. Column snapping: mandatory, with the whole-column scroll-range rule.
3. Period vocabulary: "Q2 2026" in prose, labels and dialogs, "Q2 ’26" where space is short, on the
   analysis surfaces and their exports; the filing and company pages keep their own vocabulary.
4. KPI strip stays two-up at 320 px.
5. The table window does not drive the charts.
</founder_decisions>

<task>
Track A, always: verify the proposal against the code before building. Re-read §2 of the proposal with
`frontend/features/analysis/components/*.tsx`, `frontend/features/analysis/lib/provenance.ts`,
`frontend/components/ui/{Badge,DataTable,Modal,SegmentedControl}.tsx`,
`backend/app/services/trend_analysis_service.py` and `backend/app/services/trend_analysis/*.py` open, and
`lessons/ops-verify-plan-gaps-against-code.md` in mind. Record every claim you can falsify, every file that
moved, and every test the brief names that pins text the change will alter (`kpi-strip.spec.tsx`,
`metrics-table.spec.tsx`, `analysis-source-quality.spec.tsx`, `narrative-pane.spec.tsx`,
`trend-charts-annotation.spec.tsx`, `chart-export.spec.ts`, `period-picker-helpers.spec.ts`). None of them
is a locked contract test (CLAUDE.md rule 6 lists those); say so explicitly in your notes. Run both
harnesses once to confirm the recorded numbers reproduce on your machine (the README has the commands; the
current-components harness needs `next build` with `NEXT_PUBLIC_ENABLE_ANALYSIS=true` and `next start`
with `WAITLIST_MODE=false`, no backend).

Track B, after Track A: implement Phase 1 of proposal §7, one PR per
numbered item or grouped as the brief allows, each as a draft, each in the frontend only, each verified with
the full frontend gate from `CLAUDE.md` (`npm run lint && npx tsc -p tsconfig.ci.json && npm run test --
--run && npm run build`) and the new e2e gate (`tests/e2e/analysis-layout.spec.ts`, item 10) once it
exists. Order: items 1–2 (model and mark, with the allowlist gate and the design-doc updates of item 11
in the same PR), then 3–4 (KPI strip, Data notes strip), then 5 (DataTable options + MetricsTable), then
6–9, then 10. Phase 2 (backend `data_notes`, exports, narrative rendering) follows after Phase 1 is on
production; it changes `trend_analysis/*` and the export services only, never `facts_service.py`, prompts
or evals, so no eval re-pin.

Use the prototype as the reference for geometry, copy and behaviour (`prototype/app.js` is plain DOM; map
each block to the React component the brief names), not as code to port. Reuse the design system: the
shared `Modal`, `SegmentedControl`, `Select` with `density="compact"`, the provenance-chip recipe
(`features/filings/lib/sourceTraceChip.ts`), `lib/financialTone.directionText`, `DataTable`'s sticky
first column. Column widths in rem, letters at 11 px minimum, warning ink only for an unresolved concern,
both themes, reduced motion respected.
</task>

<rules_that_bind>
- CLAUDE.md rules 6 (locked tests), 11 (design system; done-gate = legacy-colour grep empty and both
  themes verified on the preview) and 12 (every "never again" rule lands with its machine gate in the same
  PR). The allowlist gate in Phase 1 item 2 and the e2e gate in item 10 are those gates; each needs one
  mutation proof in the PR body.
- Review by risk tier (`AGENTS.md` §5): Phase 1 PRs are routine (one Opus lens, Sonnet refuters for
  blockers); Phase 2 PRs are routine too; a PR that touches `backend/app/services/facts_service.py`,
  prompts or evals is high and is outside this brief. `review-gate.yml` needs `@codex review` after each
  push. Record `Review tier: … — …` in the PR body.
- PR body format (`AGENTS.md` §7): What / Why / Verification (exact gate tails) / Mutation proofs / Founder
  actions / Not in this PR / Review. Open every PR as a draft. `git status` empty after each commit.
- Deploy discipline (`AGENTS.md` §6) for Phase 2: one unverified backend deploy at a time.
- After any founder correction, add or update a file in `lessons/` (its README gives the format).
- Do not run the data repair, do not generate paid AI analyses, do not change production flags.
</rules_that_bind>

<done_looks_like>
Track A: a short verification note appended to the PR that carries this prompt (or a comment on it)
listing falsified claims (expected: none or few), moved files, and the test pins the change will alter;
both harness runs reproduced within a few pixels.
Track B, per PR: the frontend gate green, the named spec updated, the preview checked in both themes at
1480 and 390, the measurement harness showing 0 page overflow, 0 card-child overflow, equal period
columns and 0 occlusion for the states the PR affects, and the PR body in the §7 format with its review
line. Phase 1 complete when the production page shows the Data notes strip, affixes instead of labels, the
aligned KPI strip and the fixed-column table on a real Pro run, before the data repair has run.
</done_looks_like>
