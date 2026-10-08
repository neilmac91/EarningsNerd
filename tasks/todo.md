# Open items — EarningsNerd

One page, newest first, one line per open item with its owner and next step. Holds are pointers,
never restated here. This file replaced the ledger on 2026-10-07; the ledger is
`archive/todo-ledger-through-2026-10-07.md` (6,469 lines, June 2026 → closure 165 of 8 October 2026;
ledger-format entries merged to `main` after the ledger closed were moved there unchanged) and its
unchecked rows are history unless an item below carries them. Format: `AGENTS.md` §7. Close an item by
deleting its line in the PR that closes it; a handover is a refresh of "Where things stand".

## Where things stand — 2026-10-08

- Production: the last recorded state is the ledger's "2026-10-04 — CODE RED chief takeover"
  section and its records under `code-red-20261004/runtime/`; verify the latest `deploy-backend`
  run on `main` and `/health/detailed` before relying on it.
- Holds: everything under "Held until the founder says otherwise" in
  `handover-astra-2026-09-19.md` §5 and the September 28 checkpoint in
  `continuation-plan-2026-09-26.md` stays held. The E7/R1/H20 acceptance programme and the CODE RED
  records are a separate task; nothing here redesigns, lifts or restates them.
- Open PRs on 2026-10-08: #1121 (founder role contacts), #1035 (native delivery), #1009 (Pro
  pricing, held), #1129 and #1130 (opened by other sessions) drafts; from the agent-workflow-cost
  task: #1123 (copilot-eval paths, changes CI behaviour) and #1126 (process gates, stacked on #1118)
  drafts. #1108 (EN-03), #1110 (CODE RED records gate), #1112 (PR disposition sweep), #1113 (EN-01
  follow-up) and #1120 (EN-05 part b) merged on 2026-10-08; record 15
  (`code-red-20261004/runtime/control/DECISIONS-15.md`) is the latest CODE RED record.
- Review and models: PRs are reviewed by risk tier (`AGENTS.md` §5); `review-gate.yml` needs a Codex
  review or a `Review override:` line; Codex reviews again since 2026-10-07, so the override
  exception rests while it does (CODE RED record 15). Marking a PR that
  touches `backend/**` ready for review triggers the paid `copilot-eval` run: reserve first
  (`DECISIONS-09.md`, reservation rule; `AGENTS.md` §6).

## Open items

Founder:
- [ ] Apply (or change the numbers in) the handed-over patch pinning `SEC_RATE_LIMIT_PER_SECOND=1` and `EDGAR_RATE_LIMIT_PER_SEC=1` on the service and all eight jobs, with its rule-12 gate; patch, fleet assumptions and decision in `code-red-20261004/runtime/control/DECISIONS-08.md`; reserve before any PR carrying it is marked ready.
- [ ] Relay the record-14 custody clarification (which retained input set record 05's predicate governs; whether an authoritative manifest exists for it) with its six return fields (`DECISIONS-14.md`; D3 as recorded there).
- [ ] With Astra: the H20-only packing/closure refinement by the registered source-only planner (`DECISIONS-04.md`, `DECISIONS-05.md`; ledger, CODE RED section, which records the implementation hold).
- [ ] Console actions from the private security remediation plan: credential rotation and push protection, removing the old revision tags, scoping the WIF trust to `main` (PR #1069 follow-up; not code).
- [ ] Decide the founder decisions listed in the agent-workflow-cost PR (review tiers, repository visibility, the review-gate override, `tasks/` retention).
- [ ] Cloud Tasks delivery (PR #1122): provision and verify delivery before switching CPU billing; keep minimum one instance and 1 GiB. Activation needs your specific IAM exception and a successful authenticated empty delivery probe (ledger, "2026-10-07 — Google Cloud cost optimisation").
- [ ] Upstream DS-source sync (DS-01, P0), external work in the DS source project: apply the upstream-sync notes §1–15 (the ledger cites `tasks/upstream-sync.md`, which is not in the repository), regenerate `_ds_bundle.js`, republish and link the package rather than re-vendoring (ledger, "2026-10-02 — design-v3 remediation series").
- [ ] Publish an archive repository or release asset for the removed `frontend/design/landing-redesign` export (a public-account action); until then its 34 files are preserved at commit `02628e5`.

Engineering:
- [ ] Docs-vs-config: `docs/OPERATIONS.md` alert threshold `database.checked_out > 8` is unreachable with the deployed pool 4 / overflow 0 (handback B33); fix the doc.
- [ ] Security review packages WP-07 onward, each in its own PR (PR #1069 series).
- [ ] Frontend deferred, named: EN-04, EN-05 (a) the desktop close path for a launcher-, ⌘K-, "/"-, CTA- or coachmark-opened pane and (c) the logo, theme toggle and "← Back" focus rings (part (b), a failed generation's focus, merged in #1120), focus after a generation that succeeds, the desktop pane's unscrolled overhang for a chip-opened Filing tab, risk-card headlines, detector and doc cleanups, the harness `verify_probe.mjs` / `verify_trace.mjs` consent seed (ledger, "2026-10-06 — EN-02"); from the EN-01 follow-up and EN-03 sections (merged 2026-10-08): memoizing CopilotMessage's
  `ReactMarkdown` components (safe with `isReturnTarget`), `GenericTable` at phone width and a server-side
  "—" for a missing prior value; #1120's founder confirmations (`RetryButton` with the stream's failure, focus moves only when nobody holds it and lands on the card's heading, the monthly-limit card follows the same rule) are recorded in its ledger section.
- [ ] UI and a11y follow-ups recorded in the ledger's 2026-10-03/04 sections (lines 76, 104–110, 168–172): dark-mode hover tint on natively disabled secondary/ghost Buttons, opacity fading the focus ring on aria-disabled controls, DS focus-ring tokens under 3:1, EmailVerificationModal's double user invalidation, the "Free" badge when the subscription call fails, the saved-summaries error card without Retry, Modal Escape `preventDefault`, the stale popover rectangle, sr-only ticker context; and the optional zero-spend class-7 snapshot check (line 140).
- [ ] Rule (h) Retry-gate residue: FilingViewer "Try again" stays a plain Button; Analysis Run keeps native `disabled` because `analysis-api.spec.ts` pins it (needs a PR-body-documented contract change, rule 6); EmailVerificationModal's post-success `disabled={resent}`; InsiderActivityPanel's 600-level gain/loss text (ledger, 2026-10-03/04 sections).
- [ ] Copilot prompt fix candidate (arm B's deletion plus an answer-text quotation rule), judged against the diagnosis's acceptance checks 1–5 with aggregates of at least three runs; needs its own authorization and ceiling (ledger, "2026-09-30 — Copilot tool nonexecution diagnosis").
- [ ] Native-evidence delivery adapter: Codex binds the base, runs the probe `plan` on the releasing machine, then `run` once; opening a PR runs the paid `eval-baseline` job and merging deploys, neither yet authorised (ledger, "2026-09-30 — native-evidence delivery adapter candidate").

## What to doubt first

- An item above may already be closed by a PR merged after 2026-10-08: check `git log` before starting it.
- The ledger's older unchecked rows and the dated handovers are not a queue (`AGENTS.md` §1).
