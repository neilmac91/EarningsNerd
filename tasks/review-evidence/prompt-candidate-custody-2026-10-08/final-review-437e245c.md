# Final exact-head review of `437e245c` (three lenses), verbatim
The last review round before the freeze, on the frozen head `437e245c824516ec8a552c2fd6dced0e0bc0091f`. Its verdicts and the operator's dispositions of its nits were posted in #1029 comment 5964670480; the full text existed only in the session's scratch space (`fix-r5-result.json`), so it is copied here verbatim (headings added). Rounds 1–5 are in [`../prompt-candidate-2026-10-02/design-history/`](../prompt-candidate-2026-10-02/design-history/design-v2.md).

## Lens: correctness-scope — APPROVE (reviewed head `437e245c824516ec8a552c2fd6dced0e0bc0091f`)

### F1 (NIT)

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/PREREGISTRATION.md:358 (Spend, Rule: "USD 0.1725 is the off-peak cost of one run with no cache hits"), also used at :114 and :125

**Finding:** 0.1725 is arm-B run B1 (37029156902) re-priced with no cache hits, rounded down: 1,131,023 prompt and 4,766 completion tokens over 36 calls give 0.172513. It is not the largest retained figure. Arm-C run 37005546506, also 36 calls, re-prices to 0.172635 by the same method (copilot_cost_runnerlog.py rates 0.15 and 0.60 per 1M). It is also not a cap on a run's cost: max_rounds=4 per row plus one transient retry allow more calls than 36. This does not change the arithmetic: 0.19 + 3 × 0.172635 = 0.7079 ≤ 0.75. The actual-spend rule and the observed run costs (0.005–0.035) keep the ceiling safe. The sentence just reads as more general than its basis.

**Fix:** No change needed before freeze. If you want, add a line to the step-0 comment on #1029: 0.1725 is B1's no-cache re-pricing (0.172513); the largest retained no-cache re-pricing is 0.172635 (37005546506); it is a projection, not a per-run cap.

### What the reviewer ran

I reviewed 437e245c824516ec8a552c2fd6dced0e0bc0091f, which is HEAD of /home/user/wt/prompt-candidate. I made a detached worktree at scratchpad/prompt-candidate/rev-final-cs, then removed it with `git worktree remove --force`. The original worktree still has HEAD at 437e245c and an empty status. Provider keys were unset and I used a mock key. Python was scratchpad/venv. For the pytest runs I installed the pinned packages openai 3.20.0, PyJWT 2.15.1 and sentry-sdk 2.71.0 into a separate overlay folder in the scratchpad, because the venv has 3.19.2.

One side effect to report: I ran `git fetch -q origin main` once. That moved the shared remote-tracking ref origin/main from e969e4ab to 82556d6e (#1072, frontend-only). For information only, since this does not replace the step-1 check: `git diff --quiet b40fa703 origin/main -- backend .github` exits 0 at 82556d6e. I made three read-only `gh api` GETs:
- comment 5958742492: the committed copy matches it after whitespace normalization; only the trailing newline differs;
- comment 5961781714: it carries the 7.346893 start point (7.712591 − 0.181528 − 0.184170);
- the jobs of runs 37063120532, 37029156902, 37072989252 and 37052760996: each copilot-eval job took 2–3 minutes, so the 20-minute pre-peak margin is enough.

(a) Scope and prompt:
- `git diff b40fa703 437e245c -- backend .github` touches only copilot_service.py (+3/−0 and two 1-line edits) and test_copilot_live_regressions.py (+8).
- An AST comparison of all 121 top-level nodes of copilot_service.py, in order, finds only SYSTEM_PROMPT different.
- The edits match the Codex decision and PREREGISTRATION (a)/(b)/(c) exactly: the 51-character clause is deleted, the RULES bullet is added after the [F#] bullet and before OUTPUT FORMAT, and the not-disclosed template gains its extension.
- prompt_identity.py exits 0. Its output matches prompt_identity.txt except the checkout HEAD line.
- Importing SYSTEM_PROMPT myself gives a22fb4cd…09f5, 5289 characters and 5313 bytes, with the rule and the extension once each.
- Removing both insertions gives 16457055… (5006 characters). Adding the clause back gives a88b6fb1… (5057), which equals base b40fa703's own SYSTEM_PROMPT when I import base's file as a separate module.

(b) Tests and mutations:
- The owner test plus the five RUNBOOK offline files plus test_copilot_prose_quotations.py: 1050 passed. The owner test alone: 7 passed.
- I re-ran M0–M4 with an exact-replace script on the reviewed head, restoring the file after each; status was 0 paths every time. M0: 7 passed. The others each give "1 failed, 6 passed" at the recorded line: M1 at :68, M2 at :70, M3 at :74, M4 at :69. The hunks match mutations.txt.

(c) Delta, scope proof and history:
- 998aff32..437e245c touches only the 8 files in the folder. The total diff names only the 2 backend files and new files in the folder; tasks/todo.md is untouched.
- scope_hashes.py passes on A (f4121429), on B and on HEAD.
- The committed scope_hashes.txt equals the run on A plus its annotation line and a trailing "exit 0". The run on B differs from the run on A only in the head line.
- A is B's parent and an ancestor of the head.
- 955c3098 appears only in design-history/exact-head-review-r5.md, the verbatim reviewer text. Every other commit SHA in the folder is on HEAD or main, except #1067's documented head and merge ref (b7bd5d19 and bc0a96c3).
- PREREGISTRATION sha256 is fc42c5fd…8f, the same at A and B.

(d) Lint, test homes and evidence reproduction:
- `ruff check .` in backend, ruff on the 2 changed files, and ruff on the folder's *.py with backend/ruff.toml are all clean. `bandit -r app -ll`: no issues, exit 0.
- `git ls-files`, run through the test-homes regexes, finds only the sealed tasks/fable-e8-repin-2026-09-22/tests/test_e8_addon.py; its sha256 d79de757…7456 equals code-sha256.json, and the fable folder is unchanged since base. No JS test is outside the homes.
- The 14 backend tests that read tasks/: 386 passed.
- These reproduce their committed outputs byte for byte, apart from header and exit lines:
  - composed_quotes.py on the 23 runs (exit 1); run 37072989252 gives exit 0 with all counts 0;
  - composed_quotes_probe.py (40 cases, 5 disclosed false failures, untagged 0, exit 0);
  - run_validity.py, raw and both controls; the committed file omits the d1/d2 lines and says so;
  - the post-1066 control (VALID);
  - crosscheck_count.py and quote_inventory.py.
- Recounted independently:
  - 402 published answers in the 23 runs, and 420 published plus 12 withheld (432 rows) in the 24;
  - 0 of `*`/`_`/`~`, backslashes, character references, backticks, default-ignorable or Cf characters, the three marks, odd mark counts, or quotations across a line break; answers with marks: 27 in the 23 runs and 40 in the 24;
  - the three backslash rows (37005114216, 37029156902 and 37029964566) hold 5, 4 and 4 backslashes, all after ===CITATIONS===;
  - the audit checks 15 spans and all 15 are in-order pairs; 722 Copilot calls with a 37,115-token maximum, so the charge is 0.0070;
  - 631 eval-baseline calls; 71,040 tokens and max_tokens 12000 confirmed.
- max_retries=0 is confirmed at openai_service.py:120-121 and provider_requests.py:171, and the check at :252-253. copilot_chat records an ai_call for every attempt in its finally block.
- ci.yml pull_request uses the default types, so ready_for_review does not re-run eval-baseline. copilot-eval runs on ready_for_review only when the PR is not a draft.

(e) All 10 commits in b40fa703..437e245c, including the two merges, end with exactly the two required trailer lines.

Not run: the full backend pytest, which the operator runs.

## Lens: model-behaviour — APPROVE (reviewed head `437e245c824516ec8a552c2fd6dced0e0bc0091f`)

No findings.

### What the reviewer ran

I confirmed that `git -C /home/user/wt/prompt-candidate rev-parse HEAD` is 437e245c824516ec8a552c2fd6dced0e0bc0091f with 0 status lines. I made one detached scratch worktree at that SHA (scratchpad/prompt-candidate/review-final-mb) and removed it afterwards with `git worktree remove --force` plus a prune. The implementer tree is still at 437e245c and clean. I did not edit it, commit or push. The scratch venv python ran with OPENAI_API_KEY, DEEPSEEK_API_KEY and OPENAI_BASE_URL unset, using the mock key for backend imports. No provider calls, no gh api calls and no full backend pytest. My scratch scripts are in scratchpad/prompt-candidate/out-mb/.

Scope: the backend diff against b40fa703 is the SYSTEM_PROMPT edit (a, b, c) and four owner-test assertions. `git diff --quiet 998aff32 HEAD -- backend .github` exits 0. f4121429..HEAD touches only scope_hashes.txt. PREREGISTRATION sha256 is fc42c5fd…1fc8f, as reported. prompt_identity.py exits 0 and matches the committed txt apart from the checkout HEAD line. test_copilot_live_regressions.py plus test_copilot_prose_quotations.py: 771 passed. The check text in PREREGISTRATION matches tasks/copilot-tool-nonexecution-2026-09-30.md:264-271 word for word.

(a) Prompt as the model sees it. I read the composed RULES and OUTPUT FORMAT in full and found nothing material that is not disclosed.
- The new bullet only governs formatting and is scoped to "answer prose". It does not contradict "never announce that a figure was omitted": the absence clause sits only in the not-disclosed template, a separate branch. It does not contradict the no-tool fallback sentence either, where "quoted from" means where the number comes from, and the bullet only keeps table figures out of quotation marks.
- Residual risks, each measured or disclosed:
  - 10-K tool skipping is caught by check 2.
  - 20-F re-suppression gets the "deletion effect not preserved" label and the exposure denominators.
  - Displacement into other quote forms shows in the inventory and is listed in the handback limitations.
  - Quoted labels that are not in the filing (e.g. AAPL "gross profit") are withheld by F and fail through the F-withheld, error and 18/18 legs.
  - The not-disclosed path is unmeasured live, which is disclosed.
- The tension between "never quote a table row with cells left out" and "Keep table figures outside quotation marks" (critique1 #4) remains, but the row-cells wording is Codex's own. ASML and BABA full-row quotations verify under F. Retained runs contain 0 full-row quotations.
- The only live markers and the tool-result payloads carry no human labels to quote.

(b) Composed-quotation reading.
- composed_quotes.py on the same 23 runs exits 1. With the 5-line header and "exit 1" added, `cmp` shows it is byte-identical to composed_quotes.txt. Run 37072989252 alone exits 0 with every count 0.
- composed_quotes_probe.py (backend, 37063120532 sources) exits 0, and header + output + "exit 0" is byte-identical to the committed txt: "40 cases: F-withheld leg 2, FALSE FAILURE 5, agree 33; untagged FALSE FAILURE 0". Cases 29 and 37–40 are the disclosed false failures; 30 and 35 are the F-withheld legs.
- My own adversarial probes: 54 answers against the real unsupported_prose_quotations, in two batches.
  - Shapes covered: comma, period and colon inside label quotes; several labels; markers inside quotations; full and partial table rows; MD&A sentences with spacing quirks; markdown tables and lists of quoted labels; sub-floor "Revenue"/"Diluted" followed by more quotations; quotations crossing soft breaks, hard breaks (two spaces or a backslash), paragraph breaks and list or blockquote continuations; curly and straight marks and apostrophes; en and em dashes; headings; emphasis outside the marks; `&amp;` outside the quotation and `&nbsp;` inside it; a quotation spanning a table cell; and true compositions.
  - Results: 50 agree (two of them true F withholds that the reading also reads as composed) and 4 false failures.
  - All 4 false failures are stricter than F and covered by the disclosure: a hard-break backslash and `&nbsp;` (backslashes and character references), an ordered-list continuation (block markers), and a pipe inside a quotation that spans a table cell (the catch-all "any span whose text differs from F's display of it").
  - No reading result is laxer than F on a published answer.
- Code read: verdict(), read_row(), PAIR/PAIRING_FOLD, and the INVENTORY folds (byte-equal to provenance _TYPOGRAPHY_FOLDS and the space/punctuation regexes), checked against F's _displayed_quotation_reasons, _quotation_reading and _rendered_text. F runs on the final resolved full_answer, which is what the runner records as row.answer.

(c) Measured counts, from my own script using F's _DEFAULT_IGNORABLE_RE.
- 402 published answers in the 23 runs, and 420 published answers plus 12 withheld candidates in the 24 runs (432 rows, 0 empty): 0 backticks, 0 default-ignorables, 0 backslashes, 0 character references (in fact 0 '&'), 0 `*_~`, 0 ＂„‟, 0 odd mark counts, 0 quotations crossing a line break, 0 block-marker continuations and 0 empty pairs.
- Answers with marks: 27 in the 23 runs, and 28 + 12 = 40 in the 24.
- The backslashes are only in the candidate_deltas of three published rows, all after ===CITATIONS===, none in the answer: 37005114216 ASML d1 (5), 37029156902 BABA native d1 (4) and 37029964566 BABA native d1 (4).
- Using F's own _rendered_text and _quotation_reading on the 27 answers with marks: the in-order pairs equal F's spans on all 27, all 15 audit-checked spans are pairs, 0 nested, and 0 sub-floor labels followed by another quotation.
- Other claims re-verified:
  - 51 quoted spans in the 23 runs, all double, 0 edge ellipses.
  - BABA-viewed "Revenue" in 13 of 69 draws across 9 runs.
  - ASML: 25 tool-using and 44 tool-less draws, with 0 tool-less withheld or errored. The MD&A shape occurs once (37029964566 d1).
  - Six source texts, identical in all 24 runs.
  - 722 Copilot calls, largest prompt 37,115 tokens, 0 unknown.
  - Probability arithmetic: 1−0.96^9 = 30.7% and 1−(17/18)^9 = 40.2%.

(d) Reproductions.
- quote_inventory.py on the 4 header runs: exit 0, body identical (lines 4–23).
- crosscheck_count.py on the 5 header runs: exit 0, body identical (lines 6–56).
- run_validity.py on the 4 runs: exit 1. The output is identical once the d1/d2 system-prompt MISMATCH lines that the txt says it omits are dropped; all 72 MISMATCH lines are system-prompt lines only.
- run_validity.py with the a88b6fb1 control on the 3 main runs, and with the 16457055 control on arm B: exit 0, identical.
- run_validity.py on copilot-37072989252 with the main-prompt control: exit 0, identical (VALID, openai 3.20.0, aeb56401 x28).
- The same run without the control: exit 1, with 18 MISMATCH lines, all 'system prompt a88b6fb1de5b7f31 / 5057 chars' (0 other), matching the committed summary line.

## Lens: rules-gates-custody — APPROVE (reviewed head `437e245c824516ec8a552c2fd6dced0e0bc0091f`)

### F1 (NIT)

**Where:** PREREGISTRATION.md:155-169 (Validity: 'stop, record, apply no rule, run no replacement' and 'Invalidity never erases a failure') against :342-350 (Outcome: 'Incomplete: a validity stop or a spend stop with no failed check')

**Finding:** Two rules can give different labels for one case. Example: a backend merge lands after a ready transition, so Q2 is invalid under the head-anchored rule, and Q2's rows also show an ASML F-withheld row. 'Apply no rule' says checks are not evaluated on Q2, so the outcome is Incomplete if Q1 passed. 'Invalidity never erases a failure' is written as a general principle, which supports Not qualified. The text only settles the error-row-without-request case (check 5 fails, Not qualified). This does not threaten measurement validity or spend, and the handback reports everything, but two operators could label the same stop differently.

**Fix:** No file edit needed. Before step 1, add one sentence to the step-0 comment fixing the label. For example: on an invalid run, checks are not applied except that an error row with no recorded request fails check 5; any other check failure seen on an invalid run is reported in the handback and does not set the outcome. Codex may choose the opposite label instead, as long as it is fixed before any paid trigger.

### F2 (NIT)

**Where:** PREREGISTRATION.md:376-387 (balance case: 'it fell by at least the run's known cost but by less than the known cost plus these charges … A smaller delta means the balance has not settled')

**Finding:** The DeepSeek balance is reported to the cent; every recorded reading in tasks/ has two decimals (for example 76.68, 85.56, 55.65 → 54.59). A Copilot run's known cost is USD 0.005–0.008 (baseline_context.txt), below that resolution. So for a Q run the delta is usually 0.00, which the text calls 'not settled', and the charge stands. That conclusion is correct and conservative, but the stated reason is not the usual one. For a run with unknown-cost calls, rounding can also add up to 0.01 to the delta and trigger the budget-risk stop when the lane did not overspend. The ceiling is never at risk: every error goes toward stopping. Exposure is low because the 24 retained runs and 9 eval-baseline reports have 0 unknown calls.

**Fix:** Optional, no file edit. In the step-0 comment, note that balance readings have cent resolution, so for a Copilot run the balance case seldom replaces the charge, and a stop it triggers may come from rounding. The conservative rule stays unchanged.

### F3 (NIT)

**Where:** PREREGISTRATION.md:131-134 (step 2 third check `git diff --quiet <previous source_sha>^1 origin/main -- backend .github`, reused by step 3) against precondition 2 (:86-88, 'The `origin/main` SHA checked is recorded with the result')

**Finding:** Precondition 2 records the origin/main SHA it checked. The pre-ready check in steps 2 and 3 neither says to fetch main first nor to record the SHA. A stale local origin/main makes that guard pass without checking anything. The head-anchored Validity rule still catches a changed backend after the run, so measurement validity holds. At worst one invalid run (about USD 0.006) is paid for, and that run is still covered by the spend rule.

**Fix:** Optional, no file edit. Before each ready transition, run `git fetch origin main` and record the fetched origin/main SHA with the result of the third check, as precondition 2 does; this can be stated in the step-0 comment.

### What the reviewer ran

Head: `git -C /home/user/wt/prompt-candidate rev-parse HEAD` printed 437e245c824516ec8a552c2fd6dced0e0bc0091f, as expected. The worktree was clean. I made a detached worktree at that SHA under scratchpad/prompt-candidate/rv-final-r6. At the end I removed it with `git worktree remove --force`. The branch is still at 437e245c with 0 status entries. I made no edits, commits or pushes, and called no model provider.

Whole-file read of PREREGISTRATION.md (sha256 fc42c5fd…f8f, as reported) against the Codex decision items 1–7:
- Ceiling 0.75, hard stop, including the automatic and ready jobs. No merge or production release.
- Absolute qualification with three fresh 18-attempt runs, checks 1–5 per run, and row R.
- No retry, replacement or candidate edit. The early stop is reported.
- The not-disclosed path stays unmeasured. The handback list matches item 7: head, outcomes or stop, telemetry and unknowns, review and gates, limitations.

Trigger costs, from the workflows at the head:
- Pushing the branch is free: ci.yml triggers on push only for main, and no other workflow has a push trigger.
- ci.yml's `pull_request` uses the default types (opened/synchronize/reopened), so eval-baseline runs once, when the draft opens. Its scope step returns RUN=true because backend/app changed.
- copilot-eval triggers on opened/synchronize/reopened/ready_for_review and skips drafts. Its concurrency group has cancel-in-progress.
- converted_to_draft triggers nothing. ready_for_review runs only copilot-eval (paid) and review-gate (free).
- So the paid set is 1 eval-baseline plus 3 copilot-eval. Reopen and push are correctly banned.

Spend arithmetic and wording:
- 0.19 + 3×0.1725 = 0.7075 ≤ 0.75. Eval-baseline costs about 0.179 at the pinned rates (llm_pricing 0.003/0.15/0.60, peak ×2 on Mon–Fri 01–04 and 06–10 UTC, the same as step 1).
- 0.0071 = 37,115×0.15/1M + 2,400×0.60/1M. I recounted 722 ai_call lines in the 24 retained runner logs: largest prompt 37,115, 0 unknown.
- 0.0179 = 71,040×0.15/1M + 12,000×0.60/1M. I recounted 631 calls in the 9 retained eval_*.json reports: largest one-call prompt 71,040. 12,000 is the largest max_tokens in extraction.py, with thinking off in CI.
- The telemetry path summary.baseline.incurred_provider_usage (calls, unknown_calls) is present in all 9 retained reports.
- Spend wording: 'Budget risk stops the lane', the unknown-cost sentence and the balance case are now consistent.
- Balance readings: step 1 reads before the trigger, steps 2 and 3 read after each download and before each ready transition, and step 4 reads after Q3's download. The paragraph on UTC times names the two readings compared for each run.
- max_retries=0 confirmed at openai_service.py:120-121 and provider_requests.py:171, with the refusal at :252-253. Copilot app-level retries are logged per attempt through record_ai_call.
- The start point 7.346893 matches #1029 comment 5961781714 (7.712591 − 0.181528 − 0.184170). No later #1029 comment posts a different remainder.

Rules and custody:
- The mergeable wording is accurate (`mergeable` field, re-read while null; `unstable` for non-required checks).
- The validity rule is anchored to the frozen head.
- Custody covers the local zip sha256 beside the API digest, and the merge ref fetched by SHA with ^1/^2, with the compare API as fallback (merge-base = head).
- Outcome definitions read correctly, apart from NIT 1.
- Off-peak margin is adequate: eval-baseline jobs took about 10–10.5 min (37061778841, 37051282050) and copilot-eval runs about 2–3 min.

Round-5 record: a script of my own checked design-history/exact-head-review-r5.md against fix-r4-result.json. With whitespace normalized, all 24 where/finding/fix/ran texts are present, both APPROVE verdicts are present, and the head is present. Severity is carried by the '## Nits' heading. README R5-N1 to R5-N6 are complete and accurate. I recounted R5-N2: rows 37005114216 ASML r1 and 37029156902 / 37029964566 BABA native r1 hold 5, 4 and 4 backslashes, all after ===CITATIONS===, and 0 in the answer. Stale-wording grep for 'is budget risk.', '955c3098', 'reads `draft`', 'no row holds', 'markdown reading', 'is exact', '38 cases' and 'this file': the only hits are historical resolution rows, the round-4 closing paragraph and one round-4 probe comment; none in the active text.

Gates run here (not the full suite):
- scope_hashes.py b40fa703 HEAD on 437e245c: exit 0, RESULT: PASS. It differs from the committed txt only in the head line and the annotation lines.
- prompt_identity.py backend b40fa703, with a mock key: exit 0. It differs from the committed txt only in the checkout HEAD line.
- Targeted pytest (test_review_evidence_links, test_copilot_live_regressions, test_copilot_prose_quotations, test_e8_repin_package_is_sealed, test_retired_model_ids): 788 passed.
- Test homes: the only test-named file outside the allowed roots is the sealed fable fixture.
- `git diff --quiet 998aff32 437e245c -- backend .github` exits 0. Commit B changes only scope_hashes.txt. Both commits end with the two trailer lines.

Live state, read-only:
- After `git fetch origin main`, origin/main is 82556d6e. `git diff --quiet b40fa703 origin/main -- backend .github` exits 0: main moved by frontend, lessons, tasks and CLAUDE.md only, with no overlap with the branch's files.
- Open PRs touching backend/ or .github are exactly #1035 (draft: backend/evals, backend/scripts, 1 test), #1069 (draft: ci.yml, ops.yml, routers, services, migration, tests; mergeable false/dirty) and #1070 (requirements.txt, requirements.in). #1009 touches neither.
- No workflow run is queued or in progress anywhere. Main CI 37086152008 on 82556d6e succeeded, so no backend deploy is in flight.
- The #1066 and #1067 deploy receipts (00438-v8g, 00439-llg) match precondition 1.
