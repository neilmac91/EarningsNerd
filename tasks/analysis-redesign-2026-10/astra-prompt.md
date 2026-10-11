# Prompt for the Astra agent — Multi-Period Analysis data-notes redesign

> **What this is.** A ready-to-paste first message for a GPT-6 Astra / Codex session on this repository,
> continuing the design proposal in `docs/design/analysis-data-notes-redesign-2026-10.md`. It hands over
> everything the proposing session knew, states what is decided and what is open, and names the gates.
> Paste everything below the cut line. This file is briefing material the founder asked for, not the
> hand-over of record: that is the Engineering row in `tasks/todo.md` (`AGENTS.md` §7), which carries the
> status and the next step, while the proposal's §7 and §9 carry the brief's status and the founder's
> decisions; this file restates none of them as authority.

---8<--- copy everything below this line ---8<---

<role>
You are the engineering owner for the Multi-Period Analysis data-notes redesign on EarningsNerd. Read
`AGENTS.md` first (it is your entry point), then `CLAUDE.md`, then `lessons/README.md` sections
"Operations & workflow" and "Frontend & design system". UI work means rule 11, with `AGENTS.md`'s reading list: read `DESIGN.md`
from "Overview" on and `frontend/DESIGN_SYSTEM.md` §1–§6 and §12 before touching a component, and
`DESIGN_SYSTEM.md` §7–§11 in full (marketing surfaces, theme mechanics, exemptions, charts, motion) for the
chart, theme, exemption or motion work this brief contains; both files in full for a token, theme or
typography change.
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
  card-child containment and value alignment, table and column widths, sticky-column occlusion at every
  column boundary and the far-right end, and label counts at 1480 / 1054 / 1024 / 768 / 390 / 320 CSS px, light and dark,
  200% zoom and 200% text at 1480, 390 and 320.

Key numbers (state 2). Current build: 33 repeated labels; table 2,076 px at every width with warned columns
234–240 px against 77–105 px clean; the net-margin growth label 54 px past its card at 390 (89 at 320, 126
at 1480 with 200% text, 303 / 338 on the phones with 200% text, where the figures themselves run 51 / 86 px
past their cards); document 429 px wide on a 390 phone (815 with 200% text). Prototype: 0 labels (40 one-letter affixes and one
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

Status: the Engineering row in `tasks/todo.md` and the proposal's §7 status block are the record of which
PRs landed which items and what is next; this file does not restate them. Track A is done (the
verification comment on #1197). Read `tasks/analysis-redesign-2026-10/review-2026-10-10.md` first: it names
what the landed items and the gate still owe, each with its evidence and fix; Phase 2 is rewritten in §7
after the review and landed in #1225 (its status note there says where it departs from the brief and what
stays open).

The quarterly data repair (`docs/quarterly-data-repair.md`, #1191) is a separate operational action. The UI
must look right before it (state 2) and after it (state 1). Never mark a legacy record validated from the
frontend, never hide a note, never show the word "verified".
</context>

<founder_decisions>
Proposal §9 is the record of the founder's decisions; this block only points at it. Five were taken on
2026-10-10 (the founder: "regarding decisions for founder - i'm aligned with your recommendations"):
letters as the note mark; mandatory column snapping with the whole-column range rule; the "Q2 2026" /
"Q2 ’26" vocabulary on the analysis surfaces and their exports; the KPI strip two-up at 320 px; the table
window not driving the charts. Track B is unblocked on them. Under "Amended and added by the
comprehensive review", the amendment to decision 4 and decisions 6–9 are NOT yet confirmed: decision 6
(the table's glyph budget) is on `main` (#1202) pending ratification, so overruling it is a rollback
follow-up; the amended 4 (one-up cards below 17 em), 7 (filled bars), 8 (presets as plain buttons) and 9
("Unavailable", "No figures need review") are not on `main` and are implemented in the prototype only:
treat each as a founder pause (`AGENTS.md` §3), do not implement it until the founder confirms it in
writing, and say in the PR body which of them a PR relies on.
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
is a locked contract test (CLAUDE.md rule 6 lists those); say so explicitly in your notes. Run the
prototype harness once to confirm `measurements/prototype.json` reproduces (the README has the commands; both
recordings are written only in the browser `harness/browser-pin.mjs` pins, Playwright 1.56.1's Chromium on linux
x64, so in another browser or on another platform pass `--out` and expect other widths). `measurements/current.json` is a recording of `main` at `97293e7`, before Phase 1 landed, so
it reproduces only against a build of that revision: `git worktree add ../en-97293e7 97293e7`, then the
README's commands (`harness/build-stamped.mjs` on that worktree with `NEXT_PUBLIC_ENABLE_ANALYSIS=true`, which
installs its packages with `npm ci`, runs `next build` itself, not through npm, with an allowlisted environment and
no Node flags but heap sizes, and stamps the build with its source tree, public variables, downloaded fonts and a
hash of its whole output) and this tree's harness with `--build ../en-97293e7`, which serves the build itself
(`next start` through Next's own CLI in the same controlled environment, with `WAITLIST_MODE=false`, no backend)
(`97293e7` has no harness; the harness verifies that the
server serves that worktree's build id, that the stamp names it, that checkout's `frontend/` tree, the build's
fonts, and its output and installed packages unchanged since the stamp, before the run and after it, and that
the build's variables, fonts and fixtures and the browser match its pins, and records them). Run `measure-current.mjs` on current `main` only as a fresh measurement of the shipped
components (its probes find that markup by data attribute), never as a comparison with the recording: the
counts and geometry differ by design, and the harness refuses to write `measurements/current.json` for any
other served build, so pass `--out` naming another file.

Track B, after Track A: implement what is open in proposal §7 (the P1 follow-ups of the review file, the
gate's leftovers and Phase 2's open parts among them; Phase 2 itself landed in #1225), one PR per numbered item or grouped as the brief allows, each as a draft, each verified with
the gates its files call for (`CLAUDE.md`, `AGENTS.md` §8): the frontend follow-ups with the full frontend
gate (`npm run lint && npx tsc -p tsconfig.ci.json && npm run test -- --run && npm run build`) and the e2e
gate (`tests/e2e/analysis-layout.spec.ts`, #1206); a PR that changes backend services (as Phase 2's #1225
did) with the full backend gate from `backend/` (`ruff check . && bandit -r app -ll && python -m pytest`) as
well, plus the frontend gate whenever it touches `frontend/`, and, should one ever change the catalogue or
prompt bytes, the observation-selector gate §7 Phase 2 names. Order: Phase 1's items 1–11 and Phase 2 are on
`main` (the todo row and §7 name the PRs; #1225 changed `trend_analysis/*`, the export services and the
analysis frontend, never the facts service (`facts_service.py` and the `facts/` package behind it since
#1210), prompts or evals, so no eval re-pin); what remains is the review file's follow-ups, the gate's
leftovers and Phase 2's open parts (§7's status note; review items 11 and 27) among them.

Use the prototype as the reference for geometry, copy and behaviour (`prototype/app.js` is plain DOM; map
each block to the React component the brief names), not as code to port. Do not port: its global
`:focus-visible` rule, its 13 px and 10 px type, its eyebrow dialog headings, the data face inside AI
prose, its tinted lineage box, its hand-drawn select chevron, its raw chart colours, or `buildNotes`
(`lib/dataNotes.ts` on `main` is the model; its `total` counts every slot, the prototype's counts
populated values). Where the prototype and `main` differ, the review file says which wins. Reuse the design system: the
shared `Modal`, `SegmentedControl`, `Select` with `density="compact"`, the provenance-chip recipe
(`features/filings/lib/sourceTraceChip.ts`), `lib/financialTone.directionText`, `DataTable`'s sticky
first column. Column widths in rem, letters at 11 px minimum, warning ink only for an unresolved concern,
both themes, reduced motion respected.
</task>

<rules_that_bind>
- CLAUDE.md rules 6 (locked tests), 11 (design system; done-gate = legacy-colour grep empty and both
  themes verified on the preview) and 12 (every "never again" rule lands with its machine gate in the same
  PR). The allowlist gate of item 2 (#1199) and the e2e gate of item 10 (#1206) are those gates; a PR that
  extends either carries one mutation proof in its body.
- Review by risk tier (`AGENTS.md` §5): Phase 1 PRs are routine (one Opus lens, Sonnet refuters for
  blockers); a backend PR on these surfaces is routine too (#1225 went high for its approved locked-anchor
  change); a PR that touches the facts service (`backend/app/services/facts_service.py` or
  `backend/app/services/facts/`), prompts or evals is high and is outside this brief. `review-gate.yml` needs `@codex review` after each
  push. Record `Review tier: … — …` in the PR body.
- PR body format (`AGENTS.md` §7): What / Why / Verification (exact gate tails) / Mutation proofs / Founder
  actions / Not in this PR / Review. Open every PR as a draft. `git status` empty after each commit.
- Deploy discipline (`AGENTS.md` §6) for any backend PR: one unverified backend deploy at a time.
- After any founder correction, add or update a file in `lessons/` (its README gives the format).
- Do not run the data repair and do not change production flags. Do not generate paid AI analyses. The one
  bounded exception this prompt carried, the RUNBOOK's "Multi-Period Analysis observation-selector gate"
  before a `PROMPT_VERSION` bump, lapsed with #1225, which left the prompt and catalogue bytes unchanged; a
  future change to them re-opens that gate (`backend/evals/RUNBOOK.md`: the offline gate, fresh analyses for
  three diverse real companies in both modes with its spot-check protocol, a cache re-serve of each) as
  bounded measurement spend under `AGENTS.md` §3, with the balance read first and the ceiling, the six
  generations plus their re-serves and the protocol's results in that PR's body under Founder actions,
  never as a standing permission: no other paid analysis is authorised by this hand-over.
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
