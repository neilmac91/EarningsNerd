# Exact-head review, round 3 (head `198d0e78`): findings as received

Three independent lenses (scope and correctness, model behaviour, rules/gates/custody) reviewed head
`198d0e789e48ef28fd24baebbc7a5f37c79b956a` (the round-2 fix commit on merge `3264cdcc`, base `b40fa703`). Verdicts:
scope-and-correctness APPROVE, model-behaviour CHANGES NEEDED, rules-gates-custody APPROVE. The findings below are
the reviewers' text as handed to the implementer, kept verbatim (line-wrapped only), followed by what each lens ran.
The README section "Review round 3" records how each finding was resolved.

## Should-fix

### R3-1. model-behaviour, SHOULD-FIX

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/composed_quotes.py:53-65 (classify takes the audit's
paired spans as given) and :45-50 (verdict); PREREGISTRATION.md 'Why the raw audit cannot be the measurement' and
'Registered measurement' paragraphs, and the handback limitations; README.md measurement paragraph and Limitations

**Finding:** The registered reading of checks 3 and 4 can still fail a run that holds no composed quotation, because
it re-tests the spans exactly as the #1021 audit pairs them. The audit regex `"([^"]{8,})"` cannot match a quotation
shorter than 8 characters. When an answer quotes a short label and then quotes something else, the regex starts again
at the label's closing mark and pairs it with the next quotation's opening mark. The text between the two quotations
becomes a 'span'. `verdict` strips its edges, finds it is 8 or more characters and not in the source, and classes it
composed. Decision F pairs the marks correctly and publishes the answer.

I reproduced this offline. The product's `unsupported_prose_quotations` returned [] and `composed_quotes.verdict`
returned 'composed' on three synthetic answers built on retained source texts:
- BABA native: `The "Revenue" line agrees, and MD&A says revenue "further increased by 3% to RMB1,023,670 million
  (US$148,401 million) in fiscal year 2026" [1]`. Flagged span: ` line agrees, and MD&A says revenue `.
- BABA viewed: `The "Revenue" line shows RMB996,347 million [F1], up from RMB941,168 million on the same "Revenue"
  line a year earlier [F2]`.
- The same BABA viewed answer with curly quotes, which the audit folds to straight ones.

The other 12 synthetic spans agreed with F:
- `"EBITDA [1]"` and `"... 996,347"` were classed sub-floor.
- Interior ellipses, both `...` and `. . .`, were classed composed, and F gave elided_quotation.
- An edge ellipsis, B2's MD&A sentence and `"Gross margin,"` were classed as normalization differences.
- Label-plus-cell spans, including one with a marker inside, were classed composed, and F gave
  quotation_not_in_source.

Why this is plausible on the qualification runs:
- The setup is already the most common quote in the retained runs. BABA-viewed answers quote the 7-character label
  "Revenue" in 13 of 69 draws, spread over 9 of the 23 runs. That is 13 of the 27 published answers that quote at
  all.
- The candidate's 'Keep table figures outside quotation marks' moves quoting toward quoted labels with the figure
  outside, and the PREREG says so itself.
- No retained answer has a short quote followed by another quote, so '15 of 15 spans match F's reading' says nothing
  about this shape under the new wording.
- The strict reading fails it too. A false failure is permanent: no retry, rerun or replacement.

The PREREG names quote pairing as a gap but describes its exposure only through markdown emphasis. It also says a raw
hit on this build is 'a normalization, floor or rendering difference, or an F defect'. A pairing failure fits none of
these, and the frozen file gives the reader no way to tell it from a real composition.

**Fix:** Before freeze, and so before Codex's precondition-5 acknowledgement, change the reading in
composed_quotes.py. On each row the audit flags, pair the published answer's double quotes in order: apply the
audit's FOLD, then use the inventory's `"([^"\n]+)"` with no floor. F publishes only answers whose quotation marks
pair unambiguously, so this matches F's pairing apart from the markdown case already disclosed. Apply `verdict` to
every one of those pairs. A raw audit span that is not one of those pairs becomes a new reported class, 'audit
pairing difference', which is not composed. Then:
- Re-run composed_quotes.txt on the 23 retained runs; it should come out unchanged.
- Add the three synthetic answers above to the round-3 probe record.
- State the new class in 'Why the raw audit…', 'Registered measurement', the handback limitations and the README.

If the measurement is to stay as it is, disclose this exposure explicitly instead. Name the shape: a sub-floor quoted
label such as BABA's "Revenue" (13 of 69 BABA-viewed draws) followed by another quotation in the same answer. State
that both readings would fail it.

## Nits

### R3-N1. scope-and-correctness

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/PREREGISTRATION.md:110-119 (trigger step 2, and step 3's
'same ... diff-quiet checks') with Validity :128-133

**Finding:** After R2-N4, validity is anchored to the frozen head, but the step-2 pre-trigger guard still compares
`<previous merge ref>^1` with `origin/main`. Step 2 also never says to apply the new head-anchored check (`git diff
--quiet <head> <eval-baseline source_sha> -- backend .github`) to eval-baseline before Q1 is marked ready. Suppose a
backend merge lands between the precondition-2 check at step 1 and the opening of the draft. Then eval-baseline's
`^1` and `origin/main` both contain it, the guard passes, and Q1 is paid for (~0.17). The invalidity only shows when
Q1's validity is inspected at step 3. So the sentence 'The step-2 pre-trigger check only avoids spending on a run
this rule would invalidate' overstates what the guard does. Precondition 4 (the backend-slot acknowledgement) and the
minutes-long window make this unlikely, and the validity rule still catches it after the fact. No invalid run could
be counted.

**Fix:** Optionally, before freeze: in step 2, and in step 3 by reference, add 'apply the Validity backend-tree check
to the previous run's source_sha' before marking ready. Alternatively, anchor the guard as `git diff --quiet
b40fa70382c5d45239817f012c2b0e9d6a5a5532 origin/main -- backend .github`. Otherwise, the operator should run the
head-anchored diff on eval-baseline at step 2.

### R3-N2. scope-and-correctness

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/run_validity.py:8 (module docstring)

**Finding:** The docstring still says source_sha is printed 'for the `git diff --quiet <s1> <s2> -- backend .github`
rule between runs'. That is the consecutive-pair chain R2-N4 replaced. The registered rule is now `git diff --quiet
<head> <source_sha>` for each run. This is documentation drift only; the PREREG text is correct.

**Fix:** Change it to '(for the head-anchored `git diff --quiet <frozen head> <source_sha> -- backend .github`
validity rule)'. Or leave it, since the PREREG governs.

### R3-N3. model-behaviour

**Where:** PREREGISTRATION.md 'Reported as context' first bullet (20-F tool use label)

**Finding:** 'Deletion effect not preserved' is defined precisely, but only through the pinned g_decide.py. A
question-run counts as tool-using when at least 2 of its 3 draws have non-empty tool_results, and the label applies
when g_decide prints '20-F question-runs tool-using N/3' with N ≤ 1. g_decide.py is byte-identical to base in
scope_hashes.txt, so the definition cannot drift. The hashed PREREG text itself does not state the 2-of-3 rule, so a
reader of the frozen file alone could read 'tool-using question-run' as 'any tool draw'.

**Fix:** Optionally, add one clause: '(a question-run is tool-using when at least 2 of its 3 draws have non-empty
tool_trace.tool_results, as g_decide.py counts)'.

### R3-N4. rules-gates-custody

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/PREREGISTRATION.md:88-91 (precondition 4)

**Finding:** The acknowledgement is tied to "the active Codex implementation owner (the #1050 successors)". Both
successors, #1066 and #1067, are now merged. Two other open PRs touch backend/ or .github: #1069 is a draft
security-hardening PR (ci.yml, ops.yml, summary_pipeline, routers, a migration and test_copilot.py), and #1070 is a
Dependabot bump of backend/requirements.txt that is not a draft. A merge of either inside the window would trigger
the head-anchored validity stop. The measurement would stay correct, but spend would be wasted and the result
Incomplete. The frozen wording still allows the claim to cover these PRs.

**Fix:** No edit to the frozen file is needed. In the precondition-4 claim on #1029, name #1069 and #1070 (and any
backend or .github PR open at step 1). Get the acknowledgement from the merge-queue owner, or from each of their
owners, so it covers them.

### R3-N5. rules-gates-custody

**Where:** PREREGISTRATION.md:109-116 (step 2), :119 (step 3)

**Finding:** Before each ready transition the steps check that the PR is mergeable and that the diff is quiet. They
do not say what happens when either check fails. Validity says the check only exists to avoid spending on an invalid
run, and pushing or rebasing is forbidden. So the only possible action is to stop, but the file never says so.

**Fix:** In the step-0 or step-1 note, state that a failed mergeable or diff-quiet check means no ready transition,
and that the lane is a validity stop (Incomplete, reported). If the file is ever re-frozen, add one sentence saying
so.

### R3-N6. rules-gates-custody

**Where:** PREREGISTRATION.md:70, :128-131 (validity diff against each source_sha)

**Finding:** Each run's source_sha is a transient refs/pull/N/merge commit. Frontend merges such as #1059 are landing
on main now, so the merge ref is likely to be regenerated before a later diff is run. The diff then needs the old
merge object, fetched by its SHA.

**Fix:** After each run, fetch the source_sha object by SHA (`git fetch origin <source_sha>`) and record `git
rev-parse <source_sha>^1 <source_sha>^2` in the custody comment. If that fetch is refused, the compare API is the
fallback.

### R3-N7. rules-gates-custody

**Where:** PREREGISTRATION.md:264-274 (Spend)

**Finding:** It says "Unknown cost is not free", but the spend rule never says how unknown calls (`unknown_calls`, or
runner.log calls without usage) count toward "spent so far".

**Fix:** In the step-0 comment, state the treatment. One option: each unknown call counts as budget risk unless the
DeepSeek balance delta bounds it.

### R3-N8. rules-gates-custody

**Where:** PREREGISTRATION.md:107 (PR body) and AGENTS.md section 4 and section 7

**Finding:** The body requirement lists only the Review section and a `Review override:` line. AGENTS.md also expects
the Mutation proofs tails in the body. The override line is not tied to a head, so it would also let review-gate pass
on any later merge attempt of this PR.

**Fix:** Put the M0–M4 tails from mutations.txt in the PR body. Word the override reason as limited to the
measurement window, with no merge under this disposition and removal before any merge decision.

### R3-N9. rules-gates-custody

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/run_validity.py:8 (docstring)

**Finding:** The docstring still describes source_sha as input to the "`git diff --quiet <s1> <s2>` rule between
runs". That is the consecutive-pair chain that R2-N4 replaced with the head-anchored rule. The pre-registration
governs, so this is documentation drift only.

**Fix:** Optional before freeze: change it to "for the `git diff --quiet <frozen head> <source_sha> -- backend
.github` validity rule". Otherwise leave it, since the frozen pre-registration is authoritative.

### R3-N10. rules-gates-custody

**Where:** run_validity.py CONTEXTS and TOOL_SCHEMA_SHA256; run_validity.txt

**Finding:** Every retained run used to pin the context, tool-schema and option hashes predates #1066 (openai
3.20.0). No validity control has been run on the post-#1066 runtime that Q1–Q3 will use. These inputs are built by
the app, so drift is very unlikely, but a mismatch would only show up after paid spend.

**Fix:** Before step 1, download the #1067 copilot-eval artifact (run 37072989252, merge ref built on post-#1066
main) and run `run_validity.py --control-prompt
a88b6fb1de5b7f3103088f0795b04bea9b3216627e59dcb8bb9ebfd98ecd88cd:5057` on it. This reviewer could not download it:
the gh proxy refuses the artifact blob redirect. Record the result with precondition 2.

## What each lens ran (as received)

### scope-and-correctness (APPROVE)

I worked in a scratch worktree at 198d0e789e48ef28fd24baebbc7a5f37c79b956a, since removed with `git worktree remove
--force`. /home/user/wt/prompt-candidate was not touched and is still clean at 198d0e78. All Python runs had
OPENAI_API_KEY, DEEPSEEK_API_KEY and OPENAI_BASE_URL unset, and app imports used the dummy key
sk-test-key-for-mocking.

Scope:
- `git diff 61cce875 198d0e78 --stat` touches 5 files, all under tasks/review-evidence/prompt-candidate-2026-10-02/:
  PREREGISTRATION.md, README.md, composed_quotes.py, composed_quotes.txt and design-history/exact-head-review-r2.md.
- By `--name-status`, cd8199f1, 61cce875 and 198d0e78 each touch only that folder.
- 81f85248 touches only copilot_service.py and the owner test. Merges 5e5e80a5 and 3264cdcc add nothing beyond `git
  diff b40fa703 3264cdcc`, which shows only those two files.
- `git diff origin/main...HEAD` (origin/main fa6c5c87, merge-base b40fa703): 26 files. They are copilot_service.py
  (SYSTEM_PROMPT only: the clause deletion, the RULES bullet, the template extension), the owner test (+8 lines, four
  assertions) and 24 new files in the folder.
- `git diff --name-only b40fa703 origin/main` has no backend/ or .github paths. Main's 5 later commits (#1064, #1071,
  #1045, #1046, #1047) are frontend, docs or tasks only.
- `git merge-tree --write-tree origin/main HEAD` is clean, and the merged backend/.github tree equals HEAD's.
- Main's backend merges since efdc33f4 are #1066 and #1067. #1041 (5525a91d) touches only index_membership.json, as
  the PREREG says.

Prompt identity:
- I re-ran prompt_identity.py: exit 0. The output equals the committed prompt_identity.txt except for the checkout
  HEAD line.
- I also checked independently, without the script, by loading the base module via importlib and diffing with
  difflib:
  - The candidate prompt is sha256 a22fb4cd5472512f5867bad039feaef7400487869487fa94ae5d7a94073309f5, 5289 characters,
    5313 bytes. This matches prompt_identity.txt, the PREREG identity table and run_validity.py.
  - Base and origin/main have the same copilot_service.py; its prompt is a88b6fb1…, 5057 characters.
  - The diff is exactly 2 insertions and 1 deletion.
  - Removing the two insertions gives 16457055 (5006 characters), which equals base minus the clause. Adding the
    clause back gives a88b6fb1, which equals base.
  - `_build_messages(...)[0] == {'role': 'system', 'content': SYSTEM_PROMPT}` holds for 10-K, 20-F and 10-Q stubs,
    with history. The floors are 8 and 24.
  - No other backend or .github file pins the prompt hash or the clause.

Other re-runs:
- scope_hashes.py b40fa703: PASS. It is identical to the committed txt apart from the head line and the 4 newly added
  folder files in the allowed-diff list, as the README states.
- Owner test file: 7 passed.
- Mutation runner (r3/run_mutations.sh pointed at my worktree): M0 passes. M1, M2, M3 and M4 fail at :68, :70, :74
  and :69, matching the README table and mutations.txt. The file was restored after each.
- Also run: test_copilot, test_copilot_prose_quotations and test_review_evidence_links (924 passed); `ruff check .`
  and `bandit -r app -ll` in backend/ (both clean).
- I checked the implementer's r3 logs (all stamped HEAD 198d0e78, clean status): full pytest 5565 passed, 39 skipped;
  ruff and bandit exit 0; RUNBOOK and owner 1050 passed; tasks readers 386 passed.

Round-2 findings at 198d0e78, all resolved as the README claims:
- R2-1: the run attribution is gone and the example is marked illustrative. I re-ran quote_inventory.py over all 23
  retained runs that have a copilot-eval.json: 51 spans, all in double quotes, and 0 start or end with an ellipsis (7
  have an interior ellipsis). A wider scan of every answer, candidate_delta and service_event for an ellipsis next to
  any quote mark also found 0. The B2 MD&A span is no longer cut with an ellipsis.
- R2-N1 and R2-N7: `composed_quotes.verdict` applies F's floor first, matching copilot_service.py:894-897. My own
  probe of 24 spans against the product's unsupported_prose_quotations found 0 disagreements. Re-running
  composed_quotes.py on the 23 runs reproduced composed_quotes.txt byte for byte (exit 1, sub-floor count 0
  everywhere).
- R2-N3: the disclosure is in the PREREG, README and docstring. I confirmed 414 rows and 402 published answers, 0 of
  them containing `*`, `_` or `~`. The audit checks 15 spans across 7 runs, and all 15 equal a span of F's own
  reading (_rendered_text plus _quotation_reading).
- R2-N2, N4, N5 and N6: the text changes are present as described.

The other committed outputs also reproduce: quote_inventory.txt and crosscheck_count.txt are identical.
run_validity.txt matches apart from the d1/d2 lines, whose omission the file discloses, and the controls give VALID
with exit 0.

PREREGISTRATION.md sha256 at this head, for the step-0 comment:
9bdaa60bd08cf18c447a544401fc555eec8ea8101ba971eea060d71e0e476fcd.

### model-behaviour (CHANGES NEEDED)

I reviewed head 198d0e789e48ef28fd24baebbc7a5f37c79b956a read-only, in my own scratch worktree, which I have since
removed. I made no pushes, edits or GitHub writes and called no AI provider. For the probe I stubbed the app's
AI-client module out of the import and left all provider keys unset.

**Main moved, nothing reaches the backend.** `git diff --stat b40fa703 origin/main -- backend .github` (main at
fa6c5c87) is empty. The branch diff against b40fa703 touches only `copilot_service.py` (SYSTEM_PROMPT), the owner
test, and the evidence folder.

**The prompt reads as intended.** I read the composed SYSTEM_PROMPT in full.
- The clause is deleted, and "output [] after the citations line" stays. The JSON identity sentences are untouched,
  so MSFT citation identities are unaffected, consistent with arm B's 6/6 MSFT empty arrays.
- The RULES bullet is formatting-only and scoped to "answer prose". It names all three retained F-withheld shapes:
  label plus cell, interior ellipsis, and label and value glued together.
- It does not touch the tool directives. 20-F tool-use risk remains only as an unmeasurable residual. The pinned
  g_decide label and the exposure denominators can detect it, but it cannot be gated under Codex's checks 1–5.
- Genuine contiguous quotations are still allowed. The template edit stays on the not-disclosed path.

**composed_quotes against the product.** I probed `composed_quotes.verdict` against the product's
`unsupported_prose_quotations` on 15 synthetic answers built on retained BABA and ASML sources.
- 12 agree: F's floor is applied first, markers are blanked, edges are stripped, and interior ellipses are detected,
  including the spaced `. . .` form.
- 3 disagree. These are the out-of-phase pairing cases in the should-fix finding.
- Re-running composed_quotes.py on all 23 retained runs gives output identical to the committed composed_quotes.txt.

**quote_inventory.py.**
- It reproduces 51 spans, none with an edge ellipsis.
- Synthetic probes confirm it catches table-figure displacement into straight and curly single quotes, backticks,
  guillemets, blockquotes and „…“ quotes, including on the withheld-reason and withheld-chip surfaces.
- It does not see emphasis (bold or italic), which is not a quotation form.

**Other checks.**
- crosscheck_count.py: identity checks (positive int, bool excluded), placed/unplaced counting and restates are
  correct. A fenced declaration would print as unparseable. Check 1 still catches it, because the product's
  `_parse_citations` turns any non-int n into an error row.
- Counts on the 23 retained runs: 402 published answers, 0 unparseable declarations, and "Revenue" quoted in 13 of 69
  BABA-viewed draws.
- Owner test plus test_copilot_prose_quotations.py: 771 passed.
- The implementer's r3 logs are stamped with HEAD 198d0e78: 5565 passed, ruff and bandit clean, M0 passes, M1–M4 fail
  as designed, identity and scope pass.

### rules-gates-custody (APPROVE)

I reviewed head 198d0e789e48ef28fd24baebbc7a5f37c79b956a in a scratch worktree (rr-rules-gates-custody), with
provider keys unset and the #1066 pin overlay; the worktree has been removed and /home/user/wt/prompt-candidate is
untouched (HEAD 198d0e78, clean). I made no pushes, edits, GitHub comments or provider calls. All GitHub reads went
through gh api.

Codex decision (comment 5958742492): the design-history copy is byte-identical to the live comment apart from the
trailing newline, and the comment has not been edited. I checked the pre-registration (sha256
9bdaa60bd08cf18c447a544401fc555eec8ea8101ba971eea060d71e0e476fcd) against each point of the decision:
- three fresh 18-attempt runs, absolute qualification, no comparative claim;
- checks 1–5 match tasks/copilot-tool-nonexecution-2026-09-30.md:264-271 verbatim (that file is unchanged on base and
  on origin/main), with a per-run note (9/9 per run);
- row R covers eval-baseline, the TRUST veto (fact_adjacency) and 9 draws per question;
- uncited figures are reported separately and the MSFT advisory is not a threshold; the D14/D17 audit precedent is
  confirmed in tasks/pr-disposition-2026-09-30.md;
- the not-disclosed path is unmeasured live;
- stop rules, no retries, no merge or release, inspect Q1 before continuing, handback items;
- 0.75 total including the automatic jobs. ci.yml uses default pull_request types, so eval-baseline runs once and is
  not re-triggered by ready_for_review; copilot-eval is skipped on drafts.

Self-reference and validity:
- The frozen file contains no head SHA, PR number or review verdict.
- Validity is anchored to the frozen head through `git diff --quiet <head> <source_sha> -- backend .github`.
  source_sha comes from copilot_runner (GITHUB_SHA) and from ci-execution.txt.

#1029 comments:
- Deploy receipts confirmed: #1036 00433-vcp (main ledger), #1056 00434-nbg, #1060 00436-pkk (covers #1041), #1065
  00437-xsf (comment 5961932127), #1066 00438-v8g (5962491931), #1067 00439-llg (5962762092, slot free).
- Spend: the 7.346893 start point is in 5961781714 and is reaffirmed in 5961932127, with no later ledger posted. The
  #1050 1.00 reservation is in 5960418625.
- Off-peak windows match llm_pricing.is_peak_hour.

origin/main and merge state:
- I fetched origin/main; it is now 7efccf2b (#1048), past fa6c5c87. The six commits since b40fa703 touch nothing
  under backend/ or .github; precondition 2's diff exits 0.
- A trial no-commit merge of origin/main was clean and was then aborted.
- Open backend PRs found: #1069 (draft) and #1070 (Dependabot).

Repository rules:
- Rule 6: the backend diff against base is only copilot_service.py SYSTEM_PROMPT and four assertions in
  test_copilot_live_regressions.py; scope_hashes.py passes, including every locked test.
- Test homes: no test_*.py or *_test.py file under tasks/ is added by the branch.
- Every tasks/ change is a new file in the evidence folder, and fix rounds 61cce875 and 198d0e78 touch only that
  folder.
- Merges 5e5e80a5 and 3264cdcc have the same trees as their automatic merges, so they carry no extra edits.
- All six branch commits carry both trailers as parsed trailers.
- The deleted clause is 51 characters.

Commands re-run in scratch:
- the 14 tasks-reading tests (the implementer's list, a superset of the 13 found by grep): 386 passed at head, and
  386 passed on the trial merge with origin/main;
- the five RUNBOOK copilot suites plus the owner test and test_review_gate: 1068 passed;
- ruff on backend: clean;
- scope_hashes.py on b40fa703 against HEAD: exit 0, identical apart from the folder's new files;
- prompt_identity.py: exit 0, identical.

Implementer's r3 logs: all are stamped with HEAD 198d0e78 and a clean status. Full pytest 5565 passed, 39 skipped;
ruff and bandit exit 0; runbook/owner 1050 passed; mutations M0–M4 as recorded.

Limitation: the #1067 copilot-eval artifact could not be downloaded, because the gh proxy refuses the blob redirect.
