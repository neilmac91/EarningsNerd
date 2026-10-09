# Open items — EarningsNerd

One page, newest first, one line per open item with its owner and next step. Holds are pointers,
never restated here. This file replaced the ledger on 2026-10-07; the ledger is
`archive/todo-ledger-through-2026-10-07.md` (6,577 lines, June 2026 → closure 170 of 9 October 2026;
ledger-format entries merged to `main` after the ledger closed were moved there unchanged) and its
unchecked rows are history unless an item below carries them. Format: `AGENTS.md` §7. Close an item by
deleting its line in the PR that closes it; a handover is a refresh of "Where things stand".

## Where things stand — 2026-10-09

- Production: the last recorded state is the ledger's "2026-10-04 — CODE RED chief takeover"
  section and its records under `code-red-20261004/runtime/`; verify the latest `deploy-backend`
  run on `main` and `/health/detailed` before relying on it.
- Holds: everything under "Held until the founder says otherwise" in
  `handover-astra-2026-09-19.md` §5 and the September 28 checkpoint in
  `continuation-plan-2026-09-26.md` stays held. The E7/R1/H20 acceptance programme and the CODE RED
  records are a separate task; nothing here redesigns, lifts or restates them.
- Open PRs on 2026-10-08: #1121 (founder role contacts), #1035 (native delivery), #1009 (Pro
  pricing, held) drafts; from the agent-workflow-cost task: #1123 (copilot-eval paths, changes CI
  behaviour) and #1126 (process gates, stacked on #1118) drafts. #1108 (EN-03), #1110 (CODE RED
  records gate), #1112 (PR disposition sweep), #1113 (EN-01 follow-up), #1120 (EN-05 part b), #1128,
  #1129 and #1130 (CODE RED record 16 and the prompt-candidate custody kit) merged on 2026-10-08;
  #1131 (D3 stage 1, deployed), #1132 (record 17), #1145 (the backend suite made hermetic, with
  `tests/support/network_gate.py` as its gate) and #1149 (record 18) merged on 2026-10-08/09;
  #1151 (D3 stage 2, option A: the API service pinned, the insider endpoint off behind a
  server-side switch, the fuzzy-search fallback deleted) merged and deployed on 2026-10-09, after
  the founder moved `backfill-facts-weekly` to `30 7 * * 1`; #1146, #1147, #1148 and #1150 (design
  critique 2026-10, parts 1–4: the filing page, the company page, the homepage, loading and motion),
  #1154 (architecture docs), #1155 (record 19) and #1159 (Wave 0 test anchors for the facts
  refactor) merged on 2026-10-09; record 19
  (`code-red-20261004/runtime/control/DECISIONS-19.md`) is the latest CODE RED record, and it notes
  for the CPO that `eval-baseline`'s `mean_citation_fidelity` read 0.83–0.86 against its 0.9648
  baseline on all six runs of 2026-10-09 (advisory).
- Review and models: PRs are reviewed by risk tier (`AGENTS.md` §5); `review-gate.yml` needs a Codex
  review or a `Review override:` line; Codex reviews again since 2026-10-07, so the override
  exception rests while it does (CODE RED record 15). Marking a PR that
  touches `backend/**` ready for review triggers the paid `copilot-eval` run: reserve first
  (`DECISIONS-09.md`, reservation rule; `AGENTS.md` §6).

## Open items

Founder:
- [ ] Design critique 2026-10, your calls (ledger, its homepage and company-page sections): whether "Find filings" becomes the hero's one primary action, demoting "See a live example", today's tracked hero CTA; and whether any signed-in user may replace a stored failure row within their quota, a backend policy change to the Pro-gated regeneration.
- [ ] Optional, no deadline: relay record 16's custody step A (five metadata fields) once; on outcome B, the one line "I adopt record 16's form (b) for R1" (`code-red-20261004/runtime/control/DECISIONS-16.md`; the record-14 relay is replaced by it, and the D3 patch of `DECISIONS-08.md` is applied by your instruction, staged).
- [ ] Durable-tasks rollout owner (PR #1122's Cloud Tasks rollout, live with request-based CPU since D3 stage 1's deploy and confirmed intended): run the post-deploy checks in `docs/DEPLOYMENT.md` (authenticated task success, retries and errors, API latency, SQL connections) (`DECISIONS-17.md`).
- [ ] Optional: set the repository's squash default to "Default to pull request title and description", so a squash merge without an explicit message carries the reviewed PR text (`DECISIONS-18.md`, chief defect 7).
- [ ] With Astra: the H20-only packing/closure refinement by the registered source-only planner (`DECISIONS-04.md`, `DECISIONS-05.md`; ledger, CODE RED section, which records the implementation hold).
- [ ] Console actions from the private security remediation plan: credential rotation and push protection, removing the old revision tags, scoping the WIF trust to `main` (PR #1069 follow-up; not code).
- [ ] Decide the founder decisions listed in the agent-workflow-cost PR (review tiers, repository visibility, the review-gate override, `tasks/` retention).
- [ ] Upstream DS-source sync (DS-01, P0), external work in the DS source project: apply the upstream-sync notes §1–15 (the ledger cites `tasks/upstream-sync.md`, which is not in the repository), regenerate `_ds_bundle.js`, republish and link the package rather than re-vendoring (ledger, "2026-10-02 — design-v3 remediation series").
- [ ] Publish an archive repository or release asset for the removed `frontend/design/landing-redesign` export (a public-account action); until then its 34 files are preserved at commit `02628e5`.

Engineering:
- [ ] CODE RED chief: after Monday 2026-10-12, read the 06:00–08:00 UTC window, the first with the whole fleet pinned and `backfill-facts` at 07:30, with the read-only `capacity-readout`: SEC errors, breaker opens, job outcomes (`DECISIONS-19.md`).
- [ ] CODE RED chief (small): `ops.yml` `describe-jobs` and `describe-service` print the two SEC pin values for every job and the task worker, with the visibility test extended; no operation reads them back today (`DECISIONS-19.md`).
- [ ] Design critique 2026-10, what remains after its four PRs (#1146, #1147, #1148, #1150): outside the repo, P-01 republish the design-system package in Claude Design; in it, the three allowlisted full-page spinner screens wait for their pages' next rework (ledger, "2026-10-09 — Design critique 2026-10" sections).
- [ ] Workflow owner: `review-gate.yml:61` re-runs the gate on any comment containing "@codex review", Codex's own summary boilerplate included, which cancelled a required run on PR #1131 (`DECISIONS-17.md`); exclude the Codex connector's comments.
- [ ] Security review packages WP-07 onward, each in its own PR (PR #1069 series).
- [ ] Frontend deferred, named: EN-04, EN-05 (a) the desktop close path for a launcher-, ⌘K-, "/"-, CTA- or coachmark-opened pane and (c) the logo, theme toggle and "← Back" focus rings (part (b), a failed generation's focus, merged in #1120), focus after a generation that succeeds, the desktop pane's unscrolled overhang for a chip-opened Filing tab, risk-card headlines, detector and doc cleanups, the harness `verify_probe.mjs` / `verify_trace.mjs` consent seed (ledger, "2026-10-06 — EN-02"); from the EN-01 follow-up and EN-03 sections (merged 2026-10-08): memoizing CopilotMessage's
  `ReactMarkdown` components (safe with `isReturnTarget`), `GenericTable` at phone width and a server-side
  "—" for a missing prior value; #1120's founder confirmations (`RetryButton` with the stream's failure, focus moves only when nobody holds it and lands on the card's heading, the monthly-limit card follows the same rule) are recorded in its ledger section.
- [ ] UI and a11y follow-ups recorded in the ledger's 2026-10-03/04 sections (lines 76, 104–110, 168–172): dark-mode hover tint on natively disabled secondary/ghost Buttons, opacity fading the focus ring on aria-disabled controls, DS focus-ring tokens under 3:1, EmailVerificationModal's double user invalidation, the "Free" badge when the subscription call fails, the saved-summaries error card without Retry, Modal Escape `preventDefault`, the stale popover rectangle, sr-only ticker context; and the optional zero-spend class-7 snapshot check (line 140).
- [ ] Rule (h) Retry-gate residue: FilingViewer "Try again" stays a plain Button; Analysis Run keeps native `disabled` because `analysis-api.spec.ts` pins it (needs a PR-body-documented contract change, rule 6); EmailVerificationModal's post-success `disabled={resent}`; InsiderActivityPanel's 600-level gain/loss text (ledger, 2026-10-03/04 sections).
- [ ] Copilot prompt fix candidate (arm B's deletion plus an answer-text quotation rule), judged against the diagnosis's acceptance checks 1–5 with aggregates of at least three runs; needs its own authorization and ceiling (ledger, "2026-09-30 — Copilot tool nonexecution diagnosis").
- [ ] Native-evidence delivery adapter: Codex binds the base, runs the probe `plan` on the releasing machine, then `run` once; opening a PR runs the paid `eval-baseline` job and merging deploys, neither yet authorised (ledger, "2026-09-30 — native-evidence delivery adapter candidate").

## What to doubt first

- An item above may already be closed by a PR merged after 2026-10-09: check `git log` before starting it.
- The ledger's older unchecked rows and the dated handovers are not a queue (`AGENTS.md` §1).