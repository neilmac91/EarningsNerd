# Exact-head review, round 1 (head `cd8199f1`): findings as received

Three independent lenses (scope and correctness, model behaviour, rules/gates/custody) reviewed head
`cd8199f1dcd4d7d93f0c34e3de2dca69b9d03c39` (code commit `81f85248` on base `efdc33f4`). The findings below are
the reviewers' text as handed to the implementer, kept verbatim. The README section "Review round 1" records how
each one was resolved.

## Blocking and should-fix

### R1-1. scope-and-correctness, SHOULD-FIX

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/PREREGISTRATION.md: acceptance rows 3 and 4, and the
paragraph "Known audit difference, decided before the runs" (same text in README.md, "Known audit difference")

**Finding:** Checks 3 and 4 are both measured with prose_quote_audit.py, and that tool flags real, product-verified
quotations as "composed". So a run can fail checks 3 and 4, with no retry allowed, when the candidate quotes exactly
the shapes the README says the wording keeps. I confirmed two separate false-positive cases on retained runs.
(1) Run 37029964566, ASML d1: the audit exits 1 and lists "Net income for 2025 amounted to €9,609.4 million,
representing 29.4% …" as composed. The product's provenance_service.normalize_for_match finds that span contiguous
in the row's source_text (the source reads `million\n, \nrepresenting`).
(2) Run 37004589548, AAPL d0: the answer says `labels this line "Gross margin,"`. The audit flags "Gross margin," as
composed because it does not strip edge punctuation. Decision F strips it, and quote_inventory reports the span as
in_source=True.
The pre-registration only covers case (1), and only for check 4. Check 3 ("prose_quote_audit.py: 0 composed on ASML
rows") also fails on the same ASML row, and no label is described for it. The new rule encourages quoting labels,
with the figures kept outside the quotes. A label written with the comma inside the closing quote is ordinary
English, so the risk of a false not-qualified result is not hypothetical. The implementer already marked deviation
1 as "needs a decision before freeze". The head should not be frozen until that decision is recorded.

**Fix:** Before freeze, get the decision owner (Codex, under #1029) to decide how checks 3 and 4 are measured, and
write that decision into PREREGISTRATION.md.
- Recommended option: define "composed or absent" by decision F's own per-span test, meaning normalize_for_match,
  citation markers blanked and edge characters stripped (quote_inventory.py's in_source). prose_quote_audit's raw
  composed_quote_rows would still be reported next to it. This matches the check text ("0 composed or absent
  quotations") and the audit's own definition of composed (not in the source).
- If the strict measurement stays: extend the "audit normalization difference" label paragraph to check 3 as well
  as check 4, and name both known classes (punctuation spacing and edge punctuation such as the trailing comma in
  "Gross margin,"). The report should then show why a check-3 or check-4 failure occurred, and that the failure
  still stands.
Update the matching README paragraph either way.

### R1-2. model-behaviour, SHOULD-FIX

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/PREREGISTRATION.md (checks 3 and 4 measurement; 'Known
audit difference'); README.md 'Known audit difference';
tasks/review-evidence/pr1021-qualification-2026-10-01/prose_quote_audit.py:45-46

**Finding:** The strict audit leg of checks 3 and 4 has a large chance of failing the candidate on genuine
quotations, and the risk is documented as narrower than it is. prose_quote_audit only reads published answers, and
every 8-or-more-character double-quoted span in a published answer has already passed decision F. So, with F live, a
'composed' hit can only be an audit artifact or an F bug. A truly composed quotation is withheld, and the F-withheld
and error legs of checks 3, 4 and 5 already fail it.

The audit lacks four of F's steps: edge-punctuation stripping, citation-marker blanking, the punctuation-spacing
fold, and the folds for low/curly marks, non-breaking hyphen, minus sign and invisible characters. The
pre-registration and README name only the punctuation-spacing fold and only the B2 case.

I re-ran the audit on all 23 retained runs:
- In the 12 G and later-main runs (F live), it reports exactly two composed hits.
- Both are published quotations that F verified: B2 37029964566 ASML d1 (MD&A sentence; the source reads
  `million\n, \nrepresenting`) and C1 37004589548 AAPL d0 (`The statement labels this line "Gross margin,"`, with the
  comma inside the marks). quote_inventory gives in_source=True for both.
- So 2 of 12 F-live runs, and 1 of the 2 arm-B runs (the candidate's parent arm), would fail checks 3/4 on the audit
  alone.

The ASML shape is not rare. 32,667.3 appears in the ASML source only as a table cell. The only prose sentence
carrying 9,609.4 has the spacing quirk right after the figure. The model quoted it in 1 of 25 tool-using ASML draws.
At arm B's 3 tool-using ASML draws per run, that gives about 1-0.96^9, roughly 30%, chance of at least one artifact
failure across Q1-Q3, before any displacement.

The candidate's wording then shuts the dominant ASML quote shape: table cells, which were most of the quoting ASML
tool draws. That plausibly pushes quoting toward the two shapes that trigger the artifact: MD&A sentences, and quoted
labels with the figure outside, where American style puts a comma inside the marks. AAPL has a standing motive for
the label aside, because the question says 'gross profit' and the filing says 'Gross margin'.

Offline, with the product's unsupported_prose_quotations on the retained ASML source:
- `the MD&A states "Net income for 2025 amounted to €9,609.4 million, representing 29.4% of total net sales" [3]`: F
  publishes; the audit says composed.
- The same quote stopping at 'million', quoted labels, and a full-row quote: clean in both.

Under 'the label never converts a failure', the predeclared set could therefore end 'not qualified' with no real
composed quotation, and the no-retry rule would burn the candidate. The implementer flagged this as needing a
decision before freeze; the evidence above says the exposure is material.

**Fix:** Before freeze:
(1) Correct 'Known audit difference' in PREREGISTRATION.md and README.md. List every normalization gap and both
retained F-verified false positives: 37029964566 ASML d1, and 37004589548 AAPL d0 "Gross margin,".
(2) Make and record an explicit decision on the audit leg of checks 3 and 4 before step 0, by one of these routes:
  (a) Define a composed quotation as a span the audit flags AND F's per-span test cannot find. That test is
  quote_inventory.classify in_source, which already copies the marker blanking, edge stripping and
  normalize_for_match. State that true composed quotations remain covered by the F-withheld, error and 18/18 legs.
  Codex must acknowledge this, since it changes a measurement method.
  (b) Keep the strict policy, with the quantified false-fail risk (2 of 12 F-live runs; 1 of 2 arm-B runs; about 30%
  per set from the ASML MD&A shape alone) written into PREREGISTRATION.md and explicitly accepted by Codex before
  step 1.
Either way, the choice must be in the frozen file.

### R1-3. rules-gates-custody, BLOCKER

**Where:** PREREGISTRATION.md:19-20 (Base), :62-67 (Preconditions 1 and 3); README.md:5; branch base efdc33f4

**Finding:** Main has moved past this head with a backend change, so cd8199f1 is no longer the exact integrated
candidate head that Codex step 3 says must be reviewed before freezing, and Codex step 1 (no parallel backend release)
is not met as written. GitHub shows main at 432fa5df = #1066 (merged 22:11:09Z), which changes backend/requirements.in
and backend/requirements.txt (OpenAI, PyJWT and Sentry runtime bumps). It sits on top of b9061ef = #1058 (frontend).
On #1029, comment 5962269409 (22:10Z) claims the backend slot for #1066's deploy and says #1067 will follow serially.
Consequences: (a) Every Q run measures the PR merge ref, which is the candidate plus 432fa5df. The local full gate
(5565) ran in a venv with openai 3.19.2, the efdc33f4 pin. All retained runs also record runtime.versions.openai
3.19.2. So the gated tree and the measured tree differ in the provider SDK. (b) The PREREG names the base as efdc33f4.
Precondition 1 lists deploy receipts only for #1036, #1056, #1060 and #1065, so nothing in the frozen file requires
#1066's (or #1067's) deploy to be verified before step 1. (c) Finding a red CI result only after opening the draft is
fatal under the PREREG's own spend rule, because a fix-push re-runs eval-baseline. The implementer's 'main has not
moved' was true when they committed (21:35Z and 21:51Z) but is no longer true.

**Fix:** Before step 0, while nothing is pushed: 1. Merge current origin/main into the branch. 2. Install the updated
backend/requirements.txt in the gate venv. 3. Re-run the full gate, the RUNBOOK five files plus
test_copilot_live_regressions.py, and the 13 tests that read tasks/. 4. Regenerate prompt_identity.txt and
scope_hashes.txt against the new base. 5. Update the PREREG and README base line. 6. Rewrite precondition 1 as a
general rule: every backend-touching merge on main up to the step-1 merge ref (now including #1066) has a verified
deploy receipt, and no backend deploy is in flight. 7. Add preparation.runtime.versions to the reported context.
8. Re-run the exact-head three-lens review on the integrated head.

### R1-4. rules-gates-custody, SHOULD-FIX

**Where:** PREREGISTRATION.md:81-86 (steps 2-3 pre-trigger check)

**Finding:** As written, the pre-trigger check `git diff --quiet <previous merge ref> origin/main -- backend .github`
can never pass. The merge ref (source_sha = GITHUB_SHA, the PR merge commit; copilot_runner.py:297) contains the
candidate's own backend diff, and origin/main does not. I simulated it with `git merge-tree --write-tree efdc33f4
HEAD`: the diff against efdc33f4 exits 1 and lists copilot_service.py and test_copilot_live_regressions.py, even
though main had not moved. Applied literally, it stops the lane before Q1. Otherwise the operator has to reinterpret
it after seeing it fail, which is the post-hoc choice the one-rule validity design was meant to remove. The post-run
rule (identity table :54, consecutive source_sha against each other) is correct, because both sides contain the
candidate.

**Fix:** Restate the pre-trigger check as `git diff --quiet <previous merge ref>^1 origin/main -- backend .github`,
meaning main's backend and .github are unchanged since the previous run. State that for Q1 the 'previous merge ref'
is the eval-baseline run's merge commit, so R(i) and Q1 share one backend tree.

### R1-5. rules-gates-custody, SHOULD-FIX

**Where:** PREREGISTRATION.md:121-122 (checks 3 and 4 measurement), :130-135 (Known audit difference); README.md:93-95

**Finding:** The implementer's deviation 1 (marked 'needs a decision before freeze') is still open, and it is
understated. prose_quote_audit.py flags published, F-verified, passing quotations as composed in 2 of the 8 retained
G runs, not just one. The two cases are: B2 37029964566, ASML d1, the MD&A sentence, and C1 37004589548, AAPL d0
`"Gross margin,"` (comma inside the closing quote). quote_inventory.py reports in_source=True for both. Both runs are
tool-using arms (B and C), which is the regime this candidate is meant to restore. Under the strict policy, each such
run fails check 4. The ASML case also fails check 3, whose measurement uses the same audit, but the label paragraph
names only check 4. At about one artifact run in four, a measurement-caused 'Not qualified' across Q1-Q3 is more
likely than not. No retry is allowed, and the flagged shape is exactly the genuine contiguous quotation Codex step 2
says to preserve.

**Fix:** Close the decision before freeze and record it in the PREREG, choosing either (a) or (b). (a) Keep the
strict policy, with the authorizing owner (Codex/founder) explicitly acknowledging the measured false-positive rate.
(b) Declare now that a composed_quote_rows span counts as composed only when F's own per-span test (quote_inventory
in_source) also fails, and report audit-only hits as 'audit normalization difference'. Whichever is chosen: cite both
retained cases, and apply the paragraph to check 3's ASML measurement as well as check 4.

## Nits

### R1-N1. model-behaviour

**Where:** PREREGISTRATION.md 'Reported as context' (20-F tool use label)

**Finding:** The 'deletion effect not preserved' label adds up all three 20-F questions, so it can miss a regression
that hits ASML alone. If only ASML goes tool-less (for example ASML ---, both BABA questions TTT, so 2/3), no label
applies. Check 3 then passes vacuously, because 0 of 20 tool-less ASML draws were ever withheld. And ASML is the
question the rule targets. g_decide's per-question draw strings are printed, so the data is reported, but nothing
flags that the targeted shape was never exercised. The same applies to BABA-viewed and the ellipsis shape.

**Fix:** Add to the context list, and to the handback, the exposure denominator per run and across Q1-Q3: tool-using
ASML draws and tool-using BABA-viewed draws. State that a check-3 pass on tool-less ASML draws is not evidence that
the rule stops the label-plus-cell shape.

### R1-N2. model-behaviour

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/README.md, 'Failure-shape coverage' last paragraph

**Finding:** The README says the wording keeps 'edge ellipses'. The rule says 'never put an ellipsis inside a
quotation', and an edge ellipsis inside the marks (`"by 3% to RMB1,023,670 million …"`, 36800236360 d1) is literally
inside the quotation. So the wording is stricter than F here too. This is harmless: the model can truncate without an
ellipsis and F still verifies the span. But the claim overstates what the wording preserves.

**Fix:** Drop 'edge ellipses' from the kept-shapes list, or add it to 'Disclosed deliberately' as another way the
wording is stricter than F.

### R1-N3. model-behaviour

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/crosscheck_count.py:72-75

**Finding:** Published and withheld rows are counted on different bases. On published rows the counter counts only
placed final citations; on withheld rows it counts every declared object. Declared-but-unplaced redundant text
citations on published rows are invisible. Under arm C, for example, every MSFT draw declared 'Total revenue 281,724
245,122 211,915' and 'Diluted $ 13.64 …', but the counter reports MSFT 0 for C1 and C2. A plausible displacement
under the candidate is to keep the cross-check excerpt in the JSON while dropping the [n] from prose, and the counter
would not see it. It is context only; check 1's use (non-integer n) is unaffected and correctly finds C1 BABA d2 'F1'.

**Fix:** Count declared objects with a positive integer n on every tool-using row, from candidate_deltas as the
withheld branch already does. Report placed and unplaced separately.

### R1-N4. model-behaviour

**Where:** tasks/review-evidence/prompt-candidate-2026-10-02/quote_inventory.py:94 and :73-74

**Finding:** (a) On a withheld row, only the text before the first sentinel is scanned. For a withheld not-disclosed
candidate, the reason after ===NOT_DISCLOSED=== is never scanned, which is exactly the surface template (c) targets;
only the chips are scanned. (b) The 'table-figure' class (a figure plus at most 4 words) also catches prose figure
phrases such as "€9,609.4 million" (from MD&A, F-verified), so the displacement report could overstate table-cell
quoting. in_source is printed, which mitigates this. (c) A straight single-quoted span that contains an apostrophe
('ASML's net sales') is not captured. All three are within the declared-heuristic caveat. Both scripts ran cleanly on
all 23 retained runs. They reproduce the README's four-run numbers and failure_shapes' 30 quoting rows, and every one
of the 19 F-failing spans is classed table-figure with in_source=False.

**Fix:** Scan the text after ===NOT_DISCLOSED=== (up to ===FOLLOWUPS===) as a 'withheld-reason' surface. Optionally,
note in the docstring that table-figure can include prose figure phrases, and read in_source alongside the class.

### R1-N5. rules-gates-custody

**Where:** PREREGISTRATION.md:62

**Finding:** 'Recorded in the step-0 comment on #1029' cannot hold for every precondition. Precondition 3's
acknowledgement comes from another owner after the claim is posted. Deploy receipts for later backend merges (for
example #1066) may also land after step 0.

**Fix:** Say 'recorded on #1029 before step 1'.

### R1-N6. rules-gates-custody

**Where:** PREREGISTRATION.md:76-77, :173

**Finding:** The step-1 spend rule '0.19 + 3 x 0.1725 = 0.7075 <= remaining reservation' is a constant and always
true. The condition Codex step 5 actually needs (the shared remainder after other owners' later costs and
reservations, such as the #1050 successors' 1.00 in 5960418625, and the DeepSeek balance each cover 0.75) is not
stated as an explicit stop. It is covered only by 'Budget risk stops the lane'.

**Fix:** Add an explicit step-1 stop: shared-ledger remainder minus known later charges and reservations >= 0.75, and
DeepSeek balance >= 0.75.

### R1-N7. rules-gates-custody

**Where:** PREREGISTRATION.md:127

**Finding:** The parenthetical 'MSFT uncited figures' mislabels the exit-2 category. prose_quote_audit's
uncited_figure_rows covers every ticker (arm B B1 had 4 uncited figures), so a non-MSFT uncited-figure row could be
read as an undeclared threshold.

**Fix:** Write 'uncited_figure_rows (any ticker) and tool_less_rows are reported, not thresholds'.

### R1-N8. rules-gates-custody

**Where:** PREREGISTRATION.md:144 (R iii)

**Finding:** R(iii) cites only the --runs 3 aggregate rule. It does not address RUNBOOK.md:891-896, the --runs 5
requirement for density-forcing prompts that critique0 #1(iii) asked to be stated.

**Fix:** Add one sentence: the rule makes no marker or density demand, and 9 draws per question exceeds --runs 5 in
any case.

### R1-N9. rules-gates-custody

**Where:** PREREGISTRATION.md:182-185 (Custody)

**Finding:** sha256 recording is required only for the copilot-eval zip, copilot-eval.json and runner.log. The
eval-baseline artifact is R(i)'s evidence and has 14-day retention, but it is only 'downloaded promptly', with no
hash recorded.

**Fix:** Also record the sha256 of the eval-baseline artifact zip and its report JSON in the same comment.

### R1-N10. rules-gates-custody

**Where:** run_validity.py:69-72 together with PREREGISTRATION.md:95-97, :162-167

**Finding:** run_validity marks any row with no tool_trace.initial_messages as INVALID. The runner records
initial_messages only once the service reaches stream_chat_with_tools (copilot_runner.py:219-222). So a row that
errors before the first provider call becomes a validity stop ('Incomplete') rather than a check-5 failure ('Not
qualified'), which classifies a quality failure more leniently.

**Fix:** State that a row with an error and no recorded request is also reported as a check-5 failure; invalidity
never erases a failure.

### R1-N11. rules-gates-custody

**Where:** scratchpad gate_*.log (gate_pytest_full.log and others)

**Finding:** The gate logs do not record the HEAD they ran on. The full gate started at about 21:51Z, the same minute
as the evidence commit, so the 5565 count cannot be tied to a SHA from the log alone. The count itself is right:
5565 passed, 39 skipped, 2 deselected.

**Fix:** Prefix each gate log with `git rev-parse HEAD` and `git status --short` on the frozen head that the step-0
comment will cite.

### R1-N12. rules-gates-custody

**Where:** backend/tests/unit/test_copilot_live_regressions.py:69; mutations.txt

**Finding:** The test has four new assertions but only three mutation proofs. The kept-sentence assertion ('If there
are no filing-text markers, output []') has no kill shown, against AGENTS.md section 4's one-mutation-proof-per-gate
rule.

**Fix:** Add an M4 that deletes that sentence and record its failing tail, or note why the assertion needs none.
