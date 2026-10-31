VERDICT: NEEDS CHANGES. The prompt diff and the test choice hold up. The gating and custody mechanics have gaps that could cost money or stop the lane early.

Scope: read-only, worktree `/home/user/wt/prompt-research` at `153cfc46`, still clean. I made no provider call and no GitHub write; my only GitHub calls were reads of #1029 and #1065. I re-ran `compose.py` with a dummy offline key. It reproduces main `a88b6fb1`, arm B `16457055`, candidate A `cd7a6208` (5367 characters), the five pins present, and `_build_messages[0]` equal to candidate A.

## Confirmed correct
- **Prompt-byte pins.** The only test that pins prompt text is `backend/tests/unit/test_copilot_live_regressions.py:59-66`. Its five substrings survive A, B and C, so no edit is needed.
  - It is not a locked test. Rule 6 is at `CLAUDE.md:79-82`, the T1–T10 inventory at `tasks/architecture-refactor-plan.md:668-677,775`, and `lessons/test-contract-tests-are-locked.md:5-9,41-42`. `tasks/review-evidence/citation-alignment-2026-10-02/README.md:21` records it as "not a locked test".
  - No full-prompt hash is pinned anywhere:
    - `test_copilot.py:811-832` checks message roles only;
    - `acquisition_period_cases.py:200-203` compares the prompt with itself;
    - `copilot_runner.py:129,144,296` pins sources, database and golden set, not the prompt;
    - `test_acceptance_source_review_delivery.py:459` pins a different prompt (`ROUTE_SYSTEM_PROMPT`).
- **f-string and lint safety.** The added text has no braces and no non-ASCII characters (compose output). Ruff ignores E501 (`backend/ruff.toml:15`).
- **CI triggers.**
  - `ci.yml:6` has `pull_request:` with no `types`, so only opened, synchronize and reopened fire it. Draft↔ready toggles do not re-run eval-baseline.
  - eval-baseline has no draft guard (`ci.yml:255`), so opening the draft costs one run.
  - copilot-eval fires on `ready_for_review` and is skipped while draft (`copilot-eval.yml:5,20`). It cancels an in-progress run (`:13-15`).
  - Pushing a branch with no PR is free (`ci.yml:4-5`).
- **RUNBOOK docs.** No RUNBOOK contradiction is created: `RUNBOOK.md:697-698` and `:758-766` stay true. A RUNBOOK sentence about the new rule belongs under "Not in this PR", since there is no merge.
- **Density-forcing rule.** Three runs of `--runs 3` give 9 draws per question. That meets `RUNBOOK.md:888-890` and exceeds the `--runs 5` bar for density-forcing prompts (`:891-896`) even if a reviewer counts rule A as density-forcing.

## Issues

**1. (Should fix, lane-ending) The full gate cannot run before the first paid trigger as planned. A fix-push after opening ends the lane.**
- **The order the rules require.** `AGENTS.md:99` requires `ruff && bandit && pytest` before every backend push, which includes step 0. Codex's step 3-4 order is: full pinned gate and exact-head review, then freeze, then any paid trigger.
- **There is no free hosted gate.** Opening the PR runs eval-baseline (`ci.yml:255,303`). A `workflow_dispatch` also runs it (`:277-278`).
- **Why a fix-push is fatal.** A second eval-baseline makes the spend rule (`design.md:294-295`) evaluate to 0.36 + 3×0.1725 = 0.8775 > 0.75. That stops the lane before Q1.
- **Disk.** `df` shows `/` with 78 MB available, but `/dev/shm` has 16 GB free on tmpfs.
- **Artifacts are affected too.** One retained artifact zip is 78.7 MB, and the unpacked folder is 213 MB (`scratchpad/copilot-37029964566/a.zip`). So even downloading Q1 to inspect it would hit ENOSPC on `/`. The brief raises disk only for pytest (`design.md:176`).
- **Fix:**
  - Run the gate from `git worktree add /dev/shm/cand <head>` with `TMPDIR=/dev/shm/tmp`, `PYTHONPYCACHEPREFIX=/dev/shm/pyc` and `pytest --basetemp=/dev/shm/pt`.
  - Use the pinned `ruff==0.16.9` and `bandit==1.9.4`; the venv matches.
  - Download and unpack every artifact under `/dev/shm`, and record its sha256 in comments, because tmpfs is lost on restart.
  - Make "full gate green on the exact frozen head" a hard stop before step 0.

**2. (Should fix) The pre-registration inside the frozen head refers to values it cannot contain.**
- **The placeholders.** The template puts `<HEAD_SHA>`, `PR #<N>`, the "Exact-head review" verdict and comment id, and "Offline gate: <counts>" inside the in-head file (`design.md:234,237`). A commit cannot contain its own SHA. The review and gate must cover the final head, including the `tasks/` files.
- **Review requirements.** Codex step 3 requires the review "before freezing". `RUNBOOK.md:813-815` requires three lenses before ready. `AGENTS.md:65-73` requires the review recorded in the PR body under "Review" before un-drafting.
- **Fix:**
  - The in-head file carries the base SHA, the prompt hashes, the BLOCK repr, the `prompt_identity.py` sha256, the rules and the spend.
  - The step-0 #1029 comment carries the head SHA, the file's sha256 and the gate tails.
  - The PR body carries Review, Mutation proofs (`AGENTS.md:53-54,93`) and a `Review override: <reason>` line.
  - Without that line, each ready toggle starts `review-gate` (`review-gate.yml:18-19,36`), which waits 20 minutes and then fails red. The reason Codex reviews are unavailable is the quota-exhausted notice in comment 5952713541. The override line passes the gate (`backend/scripts/review_gate.py:47,88-90`), with precedent in the #1029 body and comment 5960133326.
  - Gate step 2 explicitly on: all required CI checks green on the head, eval-baseline completed with its verdict recorded, and the PR-body Review present.

**3. (Should fix) Main moving mid-window can silently block or invalidate Q2 and Q3.**
- **Conflicts block runs.** GitHub does not run `pull_request` workflows while a PR has a merge conflict. A ready toggle would then trigger nothing, and the fix (rebase or push) is forbidden.
  - The optional `tasks/todo.md` edit (`design.md:205`) is an obvious conflict source, since other lanes edit it.
  - So is any other lane's edit to `copilot_service.py`.
- **Merges this lane cannot hold.** "Hold other backend merges" (`design.md:312`) is not in this lane's power.
  - The Codex implementation owner runs the merge queue (comments 5960271054, 5960461244).
  - The #1050 successors change the OpenAI, PyJWT, Sentry and Anthropic dependencies, so `backend/requirements.txt` (comments 5960133326, 5960418625). That changes the copilot-eval runtime.
- **`source_sha` will move.** It is the PR merge commit (`copilot_runner.py:297`), so any merge to main changes it. The identity table requires it to be identical (`design.md:220`), while the pre-registration allows a `git diff --quiet … -- backend .github` fallback (`:253`). These disagree.
- **Fix:**
  - Drop the `tasks/todo.md` edit and add new files only.
  - Before step 1, post a #1029 claim of the backend slot and of `copilot_service.py` for the window, and get the Codex owner's acknowledgement.
  - Before every ready toggle, check that the PR is mergeable and that `git diff --quiet <previous merge ref> origin/main -- backend .github` holds. Spend only if it does.
  - Use one validity rule, the diff-quiet one.

**4. (Should fix) The eval-baseline verdict has no role.**
- `RUNBOOK.md:817-818` says "Acceptance still requires its separate full summary artifact against the sole unchanged baseline". The brief treats eval-baseline only as a cost (`design.md:243-244,299`).
- **Fix:**
  - Pre-declare that its verdict (scored /70 and regression gate) is reported as a "normal gate". It is never re-run, is outside checks 1–5, and does not block Q1. Precedent: D18 and D23 in `tasks/pr-disposition-2026-09-30.md:48,53`, "the Copilot prompt does not reach it".
  - Name the cost method (precedent D7/D9: report tokens × `llm_pricing`).
  - Download its report promptly, because `retention-days: 14` (`ci.yml:397`).

**5. (Should fix) Mutation proof M2 is misdescribed.**
- `design.md:167` says M2 deletes the rule block, hashes to `26ec5d74`, and fails "rule count == 1 and the following assertions".
- `compose.py:105` actually builds M2 as `cand_a.replace("\n- " + RULE_HEAD, "\n- XX", 1)`, which corrupts only the rule's opening. Its own output fails only `rule_once` and the placement check; `table_fig` and `absent_metric` still pass.
- Deleting the whole block gives arm B `16457055`.
- **Fix:**
  - Define M2 as deleting BLOCK (expect `16457055`), or describe M2 accurately.
  - Keep one mutation per gate and put both tails in the PR body (`AGENTS.md:53-54`).
  - Never commit or push a mutation, unlike #808's committed mutation and revert (`f0a81fff`); here a push costs an eval-baseline.

**6. (Nit) Test footprint is wider than `AGENTS.md:60-61` asks.**
- Recommended assertions:
  - clause absent (gates the G-stage-2 cause);
  - `If there are no filing-text markers, output []` present (backs `RUNBOOK.md:758-761`);
  - the full rule text present exactly once.
- The separate `table_fig` and `absent_metric` substrings and the placement assertion are then redundant.
- The claim that "Rule 12 is already enforced by F" (`design.md:159`) overclaims. Rule A is stricter than F: `"Net income 7,571.6"` passes F, and cells under 8 characters are exempt (`design.md:115-116`). Say instead that rule 12 targets engineering rules and that the stricter clauses are measured only as context.

**7. (Nit) The locked-test byte-identity list is incomplete (`design.md:198`).**
- It omits these locked anchors:
  - T5 `test_expired_trial_gating.py`, which exercises the Copilot ask route (`tasks/architecture-refactor-plan.md:672`; file `:29,256`);
  - `test_generation_requires_account.py`;
  - `test_filing_scan.py` (T7), `test_refresh_replay.py` (T8), `test_companyfacts_fixture.py` (T9);
  - the frontend `summaryStream.contract.spec.ts` (T10, `:677`);
  - the serializer pins listed at `docs/summary-quality-improvement-plan.md:130`.
- The allowed-diff check (`design.md:201-205`) already proves these unchanged. Cite that inventory, or complete the list.

**8. (Nit) The measurement-tool identity is incomplete, and the prompt check is weaker than stated.**
- Only `f_attribution.py` and `prose_quote_audit.py` are hashed (`design.md:199`). Also hash and freeze:
  - `g_decide.py` and `g_precheck.py` (`tasks/review-evidence/g-stage1-2026-10-02/`);
  - `copilot_cost_runnerlog.py` (`g-stage2-2026-10-02/`);
  - the new cross-check script.
- `g_precheck.py:14` checks only the 8-hex prompt prefix and never the length, and `:20-21` yields `{}` for fingerprints. So "sha256 … 5367 characters, checked by g_precheck.py" (`design.md:215`) overstates it. Add a full-hash and length check per row, or label it prefix-only as in precedent.

**9. (Missing from the offline plan)**
- **Codex's named owner controls, as exact tests:**
  - MSFT identities: `test_copilot.py:484-498`, the `identity_*` cases including `identity_string`, plus `empty_array` and `mixed_fact_valid`.
  - Legitimate quotations: `test_copilot_prose_quotations.py:110` and the `prose_quote_valid` case.
  - Table fragments: `test_copilot_live_regressions.py:69-86`.
  - Not-disclosed cost: `test_copilot_prose_quotations.py:1094-1109` and `test_copilot.py:597-611`.
- **The edited owner test.** `test_copilot_live_regressions.py` is not in the RUNBOOK five-file set (`RUNBOOK.md:808`), so run it explicitly.
- **Tests that read `tasks/`.** Run them, or simulate them, on the final head: the five named in the #1029 body, including `test_review_evidence_links.py:29-49` (links must point to tracked files; `*.log` is git-ignored), and `testHomesAllowlist.spec.ts:48,105-110` (no `test_*.py` or `*_test.py` under `tasks/`).
- **Evidence custody after the window.** Durable evidence needs a separate tasks-only PR, which triggers no paid job. Never push to, close or reopen the candidate PR, even after Q3; a push re-runs eval-baseline.
- **Off-peak scope.** The off-peak rule must cover step 1 explicitly: peak-priced eval-baselines cost 0.347–0.352 (ledger D3/D5), and 0.35 + 3×0.1725 already fails the pre-Q1 check. The worst-case 0.1725 per run is the maximum observed with no cache (about 1.13M input tokens, 36 calls; `g-stage2-2026-10-02/copilot_cost_runnerlog.txt`), not a hard cap.

Files: `/tmp/claude-0/-home-user-EarningsNerd/4aaef390-9924-5295-aa90-251d71b700b2/scratchpad/prompt-research/design.md`, `/tmp/claude-0/-home-user-EarningsNerd/4aaef390-9924-5295-aa90-251d71b700b2/scratchpad/prompt-research/compose.py`, `/home/user/wt/prompt-research/backend/tests/unit/test_copilot_live_regressions.py`, `/home/user/wt/prompt-research/.github/workflows/ci.yml`, `/home/user/wt/prompt-research/.github/workflows/copilot-eval.yml`, `/home/user/wt/prompt-research/.github/workflows/review-gate.yml`, `/home/user/wt/prompt-research/backend/evals/RUNBOOK.md`