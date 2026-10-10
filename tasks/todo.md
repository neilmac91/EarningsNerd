# Open items — EarningsNerd

One page, newest first, one line per open item with its owner and next step. Holds are pointers,
never restated here. This file replaced the ledger on 2026-10-07; the ledger is
`archive/todo-ledger-through-2026-10-07.md` (6,693 lines, June 2026 → closure 171 of 9 October 2026;
ledger-format entries merged to `main` after the ledger closed were moved there unchanged) and its
unchecked rows are history unless an item below carries them. Format: `AGENTS.md` §7. Close an item by
deleting its line in the PR that closes it; a handover is a refresh of "Where things stand".

## Where things stand — 2026-10-10

- Production: the last recorded state is the ledger's "2026-10-04 — CODE RED chief takeover"
  section and its records under `code-red-20261004/runtime/` (record 21, `DECISIONS-21.md`, is the
  latest merged; record 22 is open as #1184 and read production back live through 13:05Z: #1176's
  images, every SEC pin at 1, durable tasks delivering); verify the latest `deploy-backend` run on
  `main` and `/health/detailed` before relying on it. Record 19 notes for the CPO that `eval-baseline`'s
  `mean_citation_fidelity` read 0.83–0.86 against its 0.9648 baseline on all six runs of
  2026-10-09 (advisory).
- Holds: everything under "Held until the founder says otherwise" in
  `handover-astra-2026-09-19.md` §5 and the September 28 checkpoint in
  `continuation-plan-2026-09-26.md` stays held. The E7/R1/H20 acceptance programme and the CODE RED
  records are a separate task; nothing here redesigns, lifts or restates them.
- Open PRs on 2026-10-10: #1121 (founder role contacts, held), #1035 (native delivery) and #1009
  (Pro pricing, held) drafts, and #1184 (CODE RED record 22, the CODE RED chief's). The
  chief-engineer merge train of 2026-10-09/10 landed them one verified backend deploy at a time:
  #1142 and #1143 (EN-05 parts a and c, EN-04), #1166 (the design-critique decisions A–E), #1170,
  #1134 (the Lane B gates), #1171, #1123 (copilot-eval paths), #1135 (the parallel backend suite),
  Lane B's seven router PRs (#1137–#1141, #1163, #1164: each router at ORM ceiling 0) and this
  page's PR (#1118, with #1126 folded in). Earlier on 2026-10-09: #1144 (the summary pipeline's
  named stages), #1153 (risk headings), #1156 (W0.G), #1167 (record 20), #1168 and #1169 (CI
  images through `mirror.gcr.io`). The CODE RED chief's #1172 (record 21) and #1181 (the read-back
  PR) merged on 2026-10-10, deploying nothing.
- Review and models: PRs are reviewed by risk tier (`AGENTS.md` §5); `review-gate.yml` needs a Codex
  review or a `Review override:` line; Codex reviews again since 2026-10-07, so the override
  exception rests while it does (CODE RED record 15). Marking a PR ready for review triggers the
  paid `copilot-eval` run only when it touches that workflow's `paths:` filter (the eval's own
  inputs since #1123), once per head commit (#1166's draw gate): reserve first (`DECISIONS-09.md`;
  `AGENTS.md` §6). `python -m pytest` runs under pytest-xdist (`-n auto`) since #1135, so every
  venv needs `pip install -r backend/requirements-dev.txt`.

## Open items

Founder:
- [ ] The dead OUTPUT REFERENCE prompt branch Wave 0 found (`prompt_loader.py:50-54`'s markers never match, so each prompt loads whole): reviving or deleting it changes prompt bytes, a RUNBOOK event that is yours (ledger, "2026-10-09 — Hot-module refactor").
- [ ] Optional; recommended now (record 20): relay record 16's custody step A (five metadata fields) once — the text is in `DECISIONS-20.md`'s appendix — and, if you agree, tell the chief in your own words "If the answer is outcome B, I adopt record 16's form (b) for R1" (`code-red-20261004/runtime/control/DECISIONS-16.md`).
- [ ] Optional; recommended (record 20): set the repository's squash default to "Pull request title and description" (Settings → General → Pull Requests → "Allow squash merging" → "Default commit message"), so a squash merge without an explicit message carries the reviewed PR text; the chief's attempt was refused by the auto-mode classifier (`DECISIONS-18.md`, chief defect 7; `DECISIONS-20.md`).
- [ ] CI image pulls (#1169's Codex P2, answered on the PR): `mirror.gcr.io` serves only Docker Hub images it has cached, so a cache miss fails the pull; choose an Artifact Registry remote repository for Docker Hub (durable) or a Docker Hub token in CI.
- [ ] With Astra: the H20-only packing/closure refinement by the registered source-only planner (`DECISIONS-04.md`, `DECISIONS-05.md`; ledger, CODE RED section, which records the implementation hold).
- [ ] Console actions from the private security remediation plan: credential rotation and push protection, removing the old revision tags, scoping the WIF trust to `main` (PR #1069 follow-up; not code).
- [ ] #1118's open founder decisions: 3 (repository visibility and public records), 4 (`tasks/` retention) and the optional 8 (register the engineering briefs as subagents); its other decisions were approved with the PR on 2026-10-09.
- [ ] Upstream DS-source sync (DS-01, P0), external work in the DS source project: apply the upstream-sync notes §1–15 (the ledger cites `tasks/upstream-sync.md`, which is not in the repository), regenerate `_ds_bundle.js`, republish and link the package rather than re-vendoring (ledger, "2026-10-02 — design-v3 remediation series").
- [ ] Publish an archive repository or release asset for the removed `frontend/design/landing-redesign` export (a public-account action); until then its 34 files are preserved at commit `02628e5`.
- [ ] After #1176 (account deletion cancels every live Stripe subscription): in the Stripe Dashboard, cancel any `trialing`, `past_due`, `unpaid` or `paused` subscription orphaned before the fix (its customer has no account; the `user_deleted` audit rows list the deleted addresses), and decide whether a Stripe failure should block the deletion, retry or alert (today the account is deleted and only `error: …` in the response and audit row records it).
- [ ] Lane B's pre-existing behaviours, each listed in its PR as your decision: async handlers doing synchronous DB work (#1140, #1141); duplicate saved summaries without a UNIQUE key, which needs a migration (#1140); a success audit row committed before an account delete that then fails, and the export's isoformat timestamps (#1141).
- [ ] Authorize or drop the Copilot prompt fix candidate, which is not pre-authorized engineering work (arm B's deletion plus an answer-text quotation rule), judged against the diagnosis's acceptance checks 1–5 with aggregates of at least three runs; needs its own authorization and ceiling (ledger, "2026-09-30 — Copilot tool nonexecution diagnosis").
- [ ] Authorize or drop the native-evidence delivery adapter, which is not pre-authorized engineering work: Codex binds the base, runs the probe `plan` on the releasing machine, then `run` once; opening a PR runs the paid `eval-baseline` job and merging deploys, neither yet authorised (ledger, "2026-09-30 — native-evidence delivery adapter candidate").

Engineering:
- [ ] Field-class follow-ups from #1180's and #1188's bodies ("Not in this PR"; the one pin left is in `frontend/tests/unit/inputClassesNoOverrides.spec.tsx`): the delete-account confirm field's error focus shows the brand border and ring in dark, pinned until the dark `shadow-ring-error` token in the focus-ring line below exists; the chat composer's shell border turns grey on hover while it is focused (`focus-within:border-brand` loses to the field's `hover:border-flat-light` on variant order; add `hover:focus-within:` twins in both themes or a focus-within shell option); the company, full-text and watchlist search fields draw a 20px spinner (`right-4`/`right-3`) over their 14px trailing inset, covering the last 17–21px of typed text while it shows: set `trailingIcon` to each field's own spinner condition (`isLoading`, `isFetching`, `isLoading || addMutation.isPending`) and take the Input spinner's 16px at `right-3`; `INVALID`'s error border and ring override the field's own in one variant chain inside `Input.tsx`, winning by palette order (`error` after `border` and `brand`), not by an explicit state: split the border and focus-ring tones out of `FIELD_BASE` so `invalid` (and the Input component's `error`) picks the error tone instead of layering it, and hold every `invalid` combination to one class per property per variant chain in `inputClassesNoOverrides.spec.tsx`.
- [ ] Focus-ring follow-ups, recorded on the founder's instruction of 2026-10-10 (#1178's body, "Not in this PR"): the DS ring recipe on every Tab stop of the pages whose controls still draw the browser's outline (check-email, the settings cards, admin invites, and the watchlist add field's result rows, which need an inset ring; the hand-rolled notification switch becomes the DS `Switch`), with a gate that reaches page controls (`siteChromeFocusRing.spec.ts` covers the chrome only); `shadow-ring-error` has no dark token and reads 1.27:1 on panel in dark, part of the ring-token decision in the UI and a11y line below.
- [ ] Hot-module refactor, lane D, under the founder's standing authorization (`refactor-plan-2026-10.md`; ledger, "2026-10-09 — Hot-module refactor", which states what it does not cover and lists Wave 0's PRs): Wave 0 closed ([evidence](refactor-wave0-closeout-2026-10.md)); founder authorized Dead cleanup on 2026-10-10 and confirmed the USD 5 floor for this programme (USD 18 ceiling unchanged); Dead then I1, one verified deploy at a time; outside the plan, the Rule-7 follow-up and Wave 0's three behaviour bugs, each with its anchor updated in the same PR.
- [ ] CODE RED chief: after Monday 2026-10-12, read the 06:00–08:00 UTC window, the first with the whole fleet pinned and `backfill-facts` at 07:30, with the read-only `capacity-readout`: SEC errors, breaker opens, job outcomes (`DECISIONS-19.md`).
- [ ] CODE RED chief: the read-back follow-ups #1181's review left (`DECISIONS-22.md`): the describe-service shell read still inherits gcloud's stderr (behind the privacy test's byte-exact lock), the capacity receipt's `error_detail.message` is bounded but not address-redacted, the logs-probe step echoes raw stderr on its denied branch, and both heredoc bodies wait to be extracted to committed modules under `ops/`; and, from #1184's review, no test pins the classifier's `error (gcloud not executable)` class; none deploys.
- [ ] Design critique 2026-10, what remains after its four PRs (#1146, #1147, #1148, #1150): outside the repo, P-01 republish the design-system package in Claude Design; in it, the three allowlisted full-page spinner screens wait for their pages' next rework (ledger, "2026-10-09 — Design critique 2026-10" sections).
- [ ] Workflow owner: `review-gate.yml:61` re-runs the gate on any comment containing "@codex review", Codex's own summary boilerplate included, which cancelled a required run on PR #1131 (`DECISIONS-17.md`); exclude the Codex connector's comments.
- [ ] Lane B follow-ups: `docs/ARCHITECTURE.md`'s service catalog rows for the new services, in one PR; prune the ceilings table's zero rows once no branch edits it; the routers still above 0 (analysis, contact, feedback, internal, sitemap, subscriptions, summaries, webhooks); the read-only GET gate's three open follow-ups, none with a live instance (tests only): a call through an unaliased `import app.x`, the last of #1134's named gaps (#1175 closed the other two); and two from #1175's review that the gate's docstring does not list yet, Connection-level `execute`/`begin` (`db.connection().execute`, `engine.begin() as conn`) and a Query bound through a tuple or a `for` target. The other limits that docstring states stay review concerns.
- [ ] Test-isolation leaks #1135 lists under "Not in this PR" (items 1–6 and 8): module state reset only on setup, a probe route left on `main.app`, root logging reconfigured by an import, a bound temporary `SessionLocal`, the shared `SUMMARY_LIMITER`, unscoped backfill passes, and the temp DB left behind on Windows; none fails today; tests only.
- [ ] Security review packages WP-07 onward, each in its own PR (PR #1069 series).
- [ ] Frontend deferred, named (EN-04, EN-05 parts a–c and the risk headings are done: #1143, #1142, #1120, #1153 and #1171): focus after a generation that succeeds, the desktop pane's unscrolled overhang for a chip-opened Filing tab, detector and doc cleanups, the harness `verify_probe.mjs` / `verify_trace.mjs` consent seed (ledger, "2026-10-06 — EN-02"); from the EN-01 follow-up and EN-03 sections (merged 2026-10-08): memoizing CopilotMessage's
  `ReactMarkdown` components (safe with `isReturnTarget`), `GenericTable` at phone width and a server-side
  "—" for a missing prior value; #1120's founder confirmations (`RetryButton` with the stream's failure, focus moves only when nobody holds it and lands on the card's heading, the monthly-limit card follows the same rule) are recorded in its ledger section.
- [ ] UI and a11y follow-ups recorded in the ledger's 2026-10-03/04 sections (lines 76, 104–110, 168–172): dark-mode hover tint on natively disabled secondary/ghost Buttons, DS focus-ring tokens under 3:1, EmailVerificationModal's double user invalidation, the "Free" badge when the subscription call fails, the saved-summaries error card without Retry, Modal Escape `preventDefault`, the stale popover rectangle, sr-only ticker context; and the optional zero-spend class-7 snapshot check (line 140).
- [ ] Rule (h) Retry-gate residue: FilingViewer "Try again" stays a plain Button; Analysis Run keeps native `disabled` because `analysis-api.spec.ts` pins it (needs a PR-body-documented contract change, rule 6); EmailVerificationModal's post-success `disabled={resent}`; InsiderActivityPanel's 600-level gain/loss text (ledger, 2026-10-03/04 sections).

## What to doubt first

- An item above may already be closed by a PR merged after 2026-10-10: check `git log` before starting it.
- The ledger's older unchecked rows and the dated handovers are not a queue (`AGENTS.md` §1).