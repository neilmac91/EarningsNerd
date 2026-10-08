# Decision record 16 — the founder's two instructions of 2026-10-08: the custody question investigated and decided (R1 held under record 05's gate; the governed set and its manifest not determinable from committed evidence; one metadata-only custody step and its outcomes fixed in advance); the D3 SEC-budget patch to be applied, staged by the founder's choice (jobs and task worker first, the API service after the insider panel fits the budget); PR #1128 review record; eighth deploy-skip proof; closures 166–167 (chief, 2026-10-08)

Recorded 2026-10-08T17:57:53Z by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`). Context: record 15 merged to main
as `a3bc888beafd38f33ce7ba456561edaa8f593acf` (PR #1128, merged 2026-10-08T04:19:26Z); this branch was restarted from it, carries
closure 166 (`e295791e`, pushed 06:02Z before any context was launched for these instructions) and merges main `2aa0ddd6` (PRs
#1108, #1113 and #1120 merged meanwhile, none touching these records). Records only: no code, workflow, migration, cloud, IAM or
production change; no provider call; no reservation; no source material opened.

## What arrived

1. **The founder's reply to the chief's record-15 report** (2026-10-08, before 06:01Z), to its two founder items ("pass on the custody
   question from record 14 … Record 16 starts when your answer arrives" and "the D3 policy numbers stay on hold until you apply that
   patch"): "1. Figure this out yourself and proceed with the path forward that makes the most sense following your investigation.
   use lots of tokens. 2. apply the patch yourself."
2. **The founder's answer to one question the chief put after the D3 investigation** (2026-10-08, about 17:50Z): asked how to activate
   D3 given that 1 + 1 req/s on the API service breaks the insider panel's first view (below), the founder chose **"Stage it"** — pin
   the eight jobs and the task worker now; pin the API service in a follow-up PR once the insider panel is made budget-aware; same
   numbers, staged.

## Part A — the custody question (record 14's two-part clarification)

**How it was investigated.** Closure 166 pre-registered the label before launch. Workflow `wf_283b58bb-e1f` (13 read-only agents,
06:04–07:21Z): five readers, each a different angle over the committed records (the predicate's definition; every input set the
records name; every candidate manifest; the rules and the other blockers; a repository cross-check by `git grep` over all tracked
files except the acceptance evidence directory and `tasks/review-evidence/`); three independent path-forward designs
(integrity-first, progress-first, governance-first); three judges (a records auditor, a custody-risk officer, a CEO lens), who
split one vote each; two adversarial refuters of the leading design. No source material, custody input, custodian mapping or excluded
path was opened; nothing was sent anywhere. Two disclosed deviations: some readers grepped code lines beyond the label's stated scope
(H20 acceptance modules and test fixtures under `backend/evals/` and `backend/tests/`, for identities and wording only, no values
read); one judge wrote and deleted a temporary scratchpad file to recompute a digest. Closure 167 registers all 13 identities and
annotates both.

**The answers (the chief's bounded reading of committed evidence, not a custodian designation).**

| Return field (record 14) | Chief's answer | Basis |
|---|---|---|
| `governed_set` | **Not determinable from committed evidence.** Record 05's predicate, read as written, governs the clean approved inputs that the retained custody and control chain selects for the registered planner, with the governing controls released alongside ("restore the custody/control chain first, then the inputs it selects"; "every selected original and governing control"; record 03: "whatever the custody process releases as clean approved inputs"). No record names that set by count or category. Candidate populations, by category only: (i) the 69 recovered planning-folder files (21 bootstrap + 48 predecessor) or a control-selected subset of them; (ii) H20's frozen source packets or source units under PR1084's offline custody, whose packet-contract and unit-manifest identities were pinned externally before recovery; (iii) the predecessor planner's private clean inputs named in `R1-STATUS.md`. The "69" is a two-folder file count (the custody tool counts every regular file), and those folders also hold controls | Records 03, 05, 11, 14; `R1-STATUS.md`; `tools/h20-custody-check.sh` |
| `authoritative_manifest_exists` | **Not established in committed or relayed evidence; non-existence not proven** (bounded to Astra's searches for records 10, 12 and 14 and to tracked files outside the two excluded directories). The committed evidence shows pre-recovery per-member references (SHA-256 and byte length) for at most about 17 of the 69 (record 05's table: 11 verified; record 08: two control anchors and 15 predecessor pairs). The selection controls the records name — the allowlist successor `4987539c…` (2,020 B), the controls package's `01-INPUT-SELECTION.md` `b1cf7fd6…` (3,793 B), the receipt template `b06cf6a0…` (898 B) — were checked by hash only and never read by the chief; by size none can carry 69 SHA-256 digests, but each may designate the set | Records 04, 05, 08, 10, 12, 14; `git grep` |
| `authoritative_manifest_sha256` / `_bytes` / `provenance` | null | — |
| `minutes_used` | 0 against the R1 allowance (the chief's investigation is not allowance time) | Record 12 |

**Disposition: R1 stays NOT_RELEASED under record 05's gate as written; the predicate is not superseded.** The hold stands by
default (record 14) and under founder decision 3 ("No substitute … keep release held", record 11). The chief reads the founder's
reply — given to exactly this item — as delegating the investigation, the answers and the choice of path. The chief uses it to hold
and to fix in advance the one step and the test that can end the hold. The chief does not use it to supersede the predicate:
no identity in evidence gives equivalent assurance (the 69 of 69 equality is to recovery archives made on 2026-10-05, after
recovery, so it proves stability since then, not equality to the freeze; the E7 triple matches 0 of 69; ZIP, scope, allowlist and
reconstructed identities are barred by name), and records 12, 13 and 14 reserve a supersession to the founder's own words, never
inferred. Holding is reversible; a release under a wrong control is not.

**The one step that can end the hold (step A — the founder relays it once; metadata only; no deadline).** Asked of the custody side
(the founder's existing custody process; Astra relays as the registered adviser), answered from retained custody controls as they
are:

1. `designating_control`: which retained control designates the set released to the registered planner — its SHA-256, byte count,
   retention time (UTC) and one line of provenance (no path); and that set's count by category (bootstrap-side / predecessor-side /
   other; selected inputs / governing controls). If the designated set lies outside the 69 (categories ii or iii above), say so by
   category. If no retained control designates it, say so in one sentence.
2. `reference_controls`: each retained control that carries, per member of that set, both SHA-256 and byte length — identity, bytes,
   retention time (UTC), one line of provenance (no path), and how many members it covers with both values. Consider at least: the
   receipt template, the 2026-10-04T08:09:23Z custody receipt (beyond the triple), handback v2 `b3ef723d…`, and PR1084's pinned
   packet-contract and unit-manifest identities.
3. `coverage`: members covered by at least one qualifying reference control; uncovered; covered by references that disagree.
4. `single_manifest`: whether one retained control alone enumerates every member with both values.
5. `minutes_used`, and whether the founder consolidates them as preparation against the 136 remaining.

Rules for step A: no hashing or comparison of any member file; no new manifest; no file names, paths, per-file hashes or contents to
the chief; no input to any planner; stop at the first concrete discrepancy and still return the counts.

**Outcomes, fixed now (before any answer is seen).** A qualifying control is one retained by the custody process before the
2026-10-05 recovery packaging and not among the excluded identities: either recovery ZIP; any custody-tool output (the 2026-10-05
custody report `7caab414…` included); the controls package `ceed7244…` as a manifest; the scope decision `b7f0510c…`; the allowlist
successor's hash used as a manifest identity; the E7 triple; any list or manifest computed from current bytes.

- **A — a single qualifying control enumerates every member with both values.** Record 05 holds as written: its SHA-256 is
  `clean_frozen_h20_input_manifest_sha256`. The chief records step A in record 17 and briefs Astra's comparison under the existing
  gate (each member streamed into SHA-256 while counting bytes; matched / mismatched / partial counts). Release only on 0 mismatches
  and 0 partials and every other predicate.
- **B — no single control, but qualifying controls jointly cover every member of the designated set with both values, all agreeing.**
  Form (b) becomes available: `clean_frozen_h20_input_manifest_sha256` is the SHA-256 of a binding statement that lists only the
  designating control's identity and each reference control's identity (SHA-256 and bytes, in a fixed order) — a binding over
  controls that already existed, never a manifest computed from current bytes; the allowlist successor may serve as the designating
  control but never as a reference or as the field value. **Form (b) takes effect only on one written line from the founder — "I adopt
  record 16's form (b) for R1" — which can travel with the step-A answer**, so it costs no extra round trip and is the founder's own
  word, not an inference. The comparison then runs under the existing gate as in A.
- **C — no designating control, or incomplete coverage, or disagreeing references.** R1 stays NOT_RELEASED; the chief records the
  counts. What remains is founder-only, each in the founder's own words in its own record: (W1) releasing only the covered subset (an
  omission, record 05's scope decision); (W2) re-baselining from recovered bytes; (W3) binding to the E7 triple; (W4) accepting
  references retained after recovery; (W5) closing the allowance (TIMEBOX_EXHAUSTED would be false while 136 of 180 minutes remain).
- **No answer.** The hold stands; the step-A relay is the one standing founder item for R1.

Not triggers, ever: elapsed time; the 69 of 69 archive equality; any new hash of current bytes; any custody-tool run; the chief's own
reading; an adviser's concurrence alone; a general instruction that names no control.

**Unchanged:** `R1-STATUS.md` (BLOCKED_SOURCE_OWNED_PACKING); the receipt template (`template_only=true`); the allowance (180 / 44
charged / 136 remaining; nothing reset); the planner, undispatched and source-only; closure 146's fallback label, conditional; every
standing hold. Founder decision 1 authorised one acknowledgment attempt (made and answered on 2026-10-06); any further attempt before
a release, or any fallback bootstrap, needs a fresh written founder authorisation of the same shape. Record 14's open two-part brief is
replaced by step A; record 15's founder action 1 is replaced by the step-A relay.

## Part B — the D3 SEC-budget patch (record 08, `sec-process-budgets.patch`, `21322a05…`, 20,062 bytes)

**Authority.** The founder's "apply the patch yourself" is recorded as the founder's D3 decision — option (a) of record 08, `1 + 1`
per process — and as authority for the production deploy its merge performs. The chief's own 2026-10-04 commit of this patch was
classifier-denied and was not re-attempted then; under this explicit instruction the chief commits it. If the classifier denies the
commit again, the chief reports the denial and does not route around it.

**Investigation before applying** (closure 166's label; workflow `wf_6eb86498-eec`, six read-only agents, 06:04–07:11Z; resolved
with the PR's review contexts in a later closure). Findings the chief verified:

1. The patch no longer applies whole: its service hunk fails since PR #1117 (Docker layer caching) and PR #1122 (private task
   worker) rewrote the deploy job; the job, docs and test hunks apply.
2. **PR #1122's private task worker is a new SEC-calling process** (each task runs in a child process that inherits the worker's env
   and reaches SEC); the original gate passes with it unpinned. The port pins it and extends the gate to every Cloud Run update step.
   The worker's deploy step runs only with `GCP_DURABLE_TASKS_ENABLED=true` (off on the last deploy), so its pin takes effect when it
   is enabled.
3. **Since PR #1101, a merge confined to `.github/workflows/ci.yml`, `backend/tests/` and `docs/` deploys nothing** (the detector
   skips; `test_backend_deploy_scope.py` locks it). Record 08's "merge deploys the new env" is stale. The port adds one accurate
   paragraph under `backend/docs/` so its own merge deploys and is verified in its own deploy log.
4. **Jobs at 1 + 1 have ample headroom:** notable-filings at most ~100 s of SEC time against a 900 s timeout; earnings-calendar
   refresh at most ~40 s against 1,800 s; pregenerate under a minute; backfill-facts about 0 requests; digest, alerts and retention 0;
   filing-scan ~1.05 s per watched company against 1,800 s (fails only above ~1,700 watched companies).
5. **The API service at 1 + 1 breaks the insider panel's first view:** a cold fetch makes one submissions request and up to 60 Form 4
   downloads through edgartools — at least ~63 s at 1 req/s, past the 60 s server and 30 s client timeouts — and the abandoned
   thread keeps the instance's whole edgartools budget and one of its four pool threads; summary grounding then falls back under
   concurrency, and timeouts count toward the SEC circuit breaker (5 consecutive failures; 30 s recovery).
6. Rollback is not a revert: `--update-env-vars` only sets keys, so a rollback must set or remove both keys explicitly.
7. Configured sums: with the worker enabled, the Monday 07:00 UTC overlap is 12 req/s (10 counting only the bucket each job uses).

**The founder's choice: staged.** Stage 1 (the D3 PR, next): pin both SEC buckets to 1 on the eight jobs and the task worker; extend
the gate; docs state the staged arithmetic; one `backend/docs/` paragraph makes the merge deploy. Stage 2 (a later PR): make the
insider panel fit the budget and pin the API service, which completes the fleet bound. Until stage 2 the two service instances stay at
the defaults (10 + 9 each), the dominant unbounded term; the fleet does not meet SEC's 10 req/s per-user cap by configuration until
stage 2 lands. Stage 2 touches `backend/app/`, so it also arms `eval-baseline`.

**Execution rules.** Stage 1 is code-bearing: the lean three-lens review and one delta reviewer (closure 166's label); a ledger
reservation of USD 0.060000 written before the PR leaves draft and before each push while it is ready (`copilot-eval` runs on
`backend/**`); Codex reviews it; merge only with every check green; the deploy log verified (eight jobs updated with maps ending in
both pins; the worker step skipped while disabled; the service unchanged). Stage 2's contexts are pre-registered in closure 167; its
reservation is sized for `copilot-eval` and `eval-baseline` together before it leaves draft.

## PR #1128 review record closed (decision record 15)

- Head `b8667624` reviewed by the single pre-registered reviewer (closure 165, `record-15-reviewer-01`, launched 03:53Z): **NO
  BLOCKER**; 98 hash rows / 0 mismatched / 0 missing; closure chain 164 → 165 12 / 12; about 230 facts checked against GitHub; ledger
  arithmetic exact; 5 should-fix and 9 nits (the review-override history, a stale ledger line, the founder's ready time, the model
  change recorded as an event, the registration disclosure; nits), all applied in `8fe4ca4a` or the PR description.
- Delta `b8667624..8fe4ca4a` by the same reviewer: **NO BLOCKER bound to `8fe4ca4a8f7d512f9f04160b9f23b748751ab3b1`**; one residual
  nit carried (the chief's model field in `APPOINTMENTS.json`), applied by closure 166's commit `e295791e`.
- Codex reviewed the PR when it left draft: summary comment 6052055769, Completed 04:15:19Z on `8fe4ca4`, no findings; `review-gate`
  run 37726424050 passed; no override.
- Merged `a3bc888b` 2026-10-08T04:19:26Z. Main CI run 37726936950 green (04:19:29–04:27:27Z); its `deploy-backend` job 113149069699
  logged `No deployable backend changes - skipping deploy.` and **skipped all twelve deploy steps** — the eighth live proof of the
  PR #1101 correction.

## Registration (closures 166 and 167)

- `control/source-context-exclusion-166.json` (488 → 492; committed and pushed in `e295791e` before any launch): resolves
  `record-15-reviewer-01` to `launched-2026-10-08T0353Z`; pre-registers `custody-question-investigation-01`, `d3-sec-budget-pr-01` and
  `record-16-reviewer-01`.
- `control/source-context-exclusion-167.json` (492 → 506): resolves `custody-question-investigation-01` to the 13
  launch-time identities of workflow `wf_283b58bb-e1f` (registered as `claude-code-workflow:<workflow>:<agent>:<label>`), annotated with
  the two disclosed deviations; pre-registers `d3-stage-2-pr-01` (the stage-2 PR's investigation, three-lens review with refuters and
  delta reviewer). `d3-sec-budget-pr-01` stays provisional until its review contexts have run; its six investigation agents
  (`wf_6eb86498-eec`) are resolved with them. Disclosed for that workflow: one agent ran `git fetch origin main` in the main checkout
  (it moved the remote-tracking ref only); the cross-checker wrote two candidate patch files into the chief's scratchpad, outside the
  repository; candidate ports were tried only in isolated copies. No context gains source A/B, reconciliation or blind financial judging
  eligibility; all earlier identities and adverse histories retained.

## Spend

Since record 15: **0 DeepSeek calls; USD 0; 0 ledger events; 0 reservations** (headroom unchanged at 22.369715; holds 1.881713).
External mutations by the chief: PR #1128 marked ready and squash-merged `a3bc888b`; this branch restarted and pushed; closure 166
committed and pushed; draft PR #1129 opened (this record); main merged into it; no ledger write.

## Founder actions this record needs

1. **Custody step A (optional, no deadline):** relay the five-field metadata request above once to the custody side. If the answer is
   outcome B and you agree, add the one line "I adopt record 16's form (b) for R1".
2. **D3:** nothing — staged as you chose; stage 1 is the next PR.

Nothing in this record releases input, dispatches the planner, runs an export or operator leg, admits capacity, invites anyone,
changes a flag, adds load, implements E09 beyond D3 as instructed, redefines record 05's gate or changes the accepted reporting
contract.
