# Copilot prompt fix candidate: qualification pre-registration

This file is committed in the frozen head before any paid trigger. It names that head as "the commit containing this
file". The head SHA, this file's sha256, the gate tails (from a gate run on that head) and the exact-head review
verdicts go in the step-0 comment on #1029, never in this file. The PR number is posted after step 1 as a note
outside the registration.

## Authorization and ceiling

- **Authority:** Codex's decision on #1029, comment 5958742492 (2026-10-02 18:27Z), under the founder's delegation.
  The text is preserved verbatim in `design-history/codex-decision-5958742492.md`.
- **Ceiling:** USD 0.75 in total, including the automatic `eval-baseline` and ready jobs. Hard stop.
- **No merge and no production prompt release** follow from this measurement. Codex decides from the complete
  handback; no passing run erases a failure.
- **Absolute qualification, not comparative.** These are three fresh qualification runs of one candidate.
  Historical results (G stages 1 and 2, earlier main runs) are context only. No comparative effect is claimed.

## Candidate identity

- **Base:** main `b40fa70382c5d45239817f012c2b0e9d6a5a5532` (post-#1067). The candidate commit `81f85248` was cut
  from main `efdc33f4` (post-#1065). Main then gained two backend merges and three frontend-only merges (#1042,
  #1043, #1044):
  - #1066 changes the backend runtime pins (`openai` 3.20.0, `PyJWT` 2.15.1, `sentry-sdk` 2.71.0).
  - #1067 changes `backend/requirements-eval.txt` (`anthropic` 1.9.0), which neither CI nor the Copilot runner
    installs.
  Merge commits `5e5e80a5` (main `11681b9c`) and `3264cdcc` (main `b40fa703`) bring that main into the branch, so
  the gated `backend/` and `.github` tree is the one the runs measure. A run's merge ref also carries any later main
  merge outside `backend/` and `.github`. Precondition 2 and the validity rule check the backend tree mechanically.
  Deploy verification of every backend merge is a precondition below.
- **Head:** the commit containing this file, on branch `claude/copilot-prompt-candidate`.
- **Diff against base:** `backend/app/services/copilot_service.py` (the `SYSTEM_PROMPT` assignment only),
  `backend/tests/unit/test_copilot_live_regressions.py` (four assertions in one existing test), and new files in
  this folder. `scope_hashes.py` proves it, including byte identity to base of `backend/requirements.txt`,
  `requirements.in`, `requirements-dev.txt` and `requirements-eval.txt`.
- **The prompt edit,** exactly two insertions plus arm B's deletion:
  - (a) **Arm B deletion.** `, including when all cited figures use tool markers` (51 characters) is removed from
    output-format step 3. "If there are no filing-text markers, output []" stays.
  - (b) **RULES bullet,** after the `[F#]` bullet and before `OUTPUT FORMAT`. Composed text: "- Each quotation in
    your answer prose must be one contiguous span copied verbatim from the filing. Keep table figures outside
    quotation marks, never quote a table row with cells left out, and never put an ellipsis inside a quotation."
  - (c) **Not-disclosed template:** `<one sentence stating what is missing and why this filing would not contain
    it; name the missing metric without quotation marks>`.
- **Composed `SYSTEM_PROMPT`:** sha256 `a22fb4cd5472512f5867bad039feaef7400487869487fa94ae5d7a94073309f5`,
  5289 characters (5313 UTF-8 bytes). It equals `_build_messages(...)[0]['content']`.
  - Removing (b) and (c) gives arm B, `164570555f40de62e102c5b24e6fc6a80361aeb5767e37f80019faebc7c90087`
    (5006 characters).
  - Re-inserting the clause gives main, `a88b6fb1de5b7f3103088f0795b04bea9b3216627e59dcb8bb9ebfd98ecd88cd`
    (5057 characters), which equals the base commit's own `SYSTEM_PROMPT`.
  - `_MIN_QUOTED_LEN` is 8 and `_MIN_VERIFIABLE_LEN` is 24, both unchanged.
  - Proof: `prompt_identity.py`, output in `prompt_identity.txt`.
- **Disclosed deliberately:** the wording is stricter than decision F in two places. Neither is enforced by F, and
  neither is a check.
  - "Keep table figures outside quotation marks": F lets a verified label-plus-cell quotation such as
    `"Net income 7,571.6"`, and any cell under 8 characters, publish. That shape is reported as context (the quote
    inventory).
  - "never put an ellipsis inside a quotation": F strips an edge ellipsis and verifies the rest, so an edge
    ellipsis such as `"by 3% to RMB1,023,670 million …"` passes F's per-span test. The example is illustrative: the
    retained BABA quotation it is cut from has no ellipsis, and none of the 51 quoted spans in the 23 retained runs
    (every form, published and withheld, per `quote_inventory.py`) starts or ends with one. The rule bans the edge
    ellipsis too; the model can truncate without one.

## Identity table (every row of every run)

| Item | Required value | Checked by |
| --- | --- | --- |
| System prompt (`initial_messages[0].content`) | full sha256 `a22fb4cd5472512f5867bad039feaef7400487869487fa94ae5d7a94073309f5` and 5289 characters, on every row | `run_validity.py` |
| Contexts (`json.dumps(initial_messages[1:], sort_keys=True)`, full sha256) | AAPL `db033e5a13d4f0e5…`, TSLA `3babd16a34cf8c3d…`, MSFT `b552352b2af3c70f…`, BABA native-2026 `6db10712e7803711…`, BABA viewed-2025 `be263a712053cf36…`, ASML `09e857dbd1b95645…` (full values pinned in `run_validity.py`) | `run_validity.py` |
| Tool schema (full sha256) | `b69589739c353f6c2e6ec884028ebbfd3b130582f48200c8e821ca960dd6e638` | `run_validity.py` |
| Generation options | `{"max_tokens": 2400, "model": "deepseek-flash", "temperature": 0.2}` | `run_validity.py` |
| Report fields | `golden_sha256` `15f8e7f92f934a5b040d905e8f684896cb11b2309d41737bbb58d59d0127b3c0`; `requested_model` deepseek-flash; `requested_flags` `{"COPILOT_MAX_TOKENS": 2400, "USE_STATEMENT_FINANCIALS": true}`; `runs` 3; `planned_attempts` 18 (six questions × draws 0–2), one result row per planned identity | `run_validity.py` |
| Backend tree of each run | `git diff --quiet <head> <source_sha> -- backend .github` exits 0 for each of `eval-baseline` (its `ci-execution.txt` `source_sha`), Q1, Q2 and Q3, where `<head>` is the frozen head. Both sides contain the candidate, so this binds every run to the gated tree and implies that consecutive merge refs agree | git, by the operator |
| Fingerprint | expected `aeb56401…`; any other value is **reported, not invalid**; a stable fingerprint does not prove unchanged provider state | `run_validity.py` (counts from `runner.log`) |

`run_validity.txt` shows the checker on retained runs: main and arm B runs fail only on the system prompt, and
pass when the control option swaps in their own prompt. `run_validity_post1066.txt` shows the same on #1067's
post-#1066 run (precondition 2). The control option is never used on a qualification run.

## Preconditions before step 1

Each is recorded on #1029 before step 1:
1. **Deploys.** Every backend-touching merge on main, up to `origin/main` at the moment of step 1, has a verified
   deploy receipt, and no backend deploy is in flight. When this file was written the list included #1036 (revision
   00433-vcp), #1056 (00434-nbg), #1041 (`5525a91d`, covered by #1060's 00436-pkk), #1060 (00436-pkk), #1065
   (00437-xsf), #1066 (`432fa5df`, 00438-v8g, #1029 comment 5962491931) and #1067 (`b40fa703`, 00439-llg, #1029
   comment 5962762092). Any later backend merge joins the list.
2. **Same backend as the gated tree.** `git diff --quiet b40fa70382c5d45239817f012c2b0e9d6a5a5532 origin/main --
   backend .github` exits 0 at step 1. The `origin/main` SHA checked is recorded with the result. Otherwise stop
   before any paid trigger: main must be merged into the branch, re-gated and re-reviewed, which is a new freeze.
   The runtime this tree installs was checked offline before freeze (`run_validity_post1066.txt`): #1067's own
   `copilot-eval` run 37072989252 ran on merge ref `bc0a96c3` (main `3084c024`, after #1066, plus #1067's head
   `b7bd5d19`), whose `backend/` and `.github` equal `b40fa703`'s. It recorded `openai` 3.20.0, and every row
   matched the identity table's contexts, tool schema, generation options and report fields under the main-prompt
   control (`--control-prompt a88b6fb1…:5057`).
3. No other active prompt-candidate PR.
4. **Backend slot.** The serial #1066/#1067 backend slot claimed in comment 5962269409 has been released (comment
   5962762092 records it free). Then a backend-slot and `copilot_service.py` claim for the window is posted on #1029.
   It names every open PR that touches `backend/` or `.github` at step 1. When this file was written those were
   #1035 (draft: `backend/evals`, `backend/scripts` and one backend test), #1069 (draft security hardening:
   workflows, routers, services and a migration) and #1070 (Dependabot: `backend/requirements.txt` and
   `requirements.in`). The claim is acknowledged by the merge-queue owner, or by the owner of each named PR. An
   explicit "no backend merges planned" from them also satisfies this. The draft is not opened without one of them.
5. **Measurement.** Codex acknowledges the registered composed-quotation measurement for checks 3 and 4 (below), or
   directs its one predeclared alternative, the strict reading. Step 1 does not start without one of the two.
6. **Gates and review.** The full backend gate is green on the exact frozen head, and the exact-head independent
   review (three lenses: correctness and scope, model behaviour, rules/gates/custody) has run on the head that
   contains this file, with any findings fixed and re-reviewed before freeze. A gate run on an earlier head does not
   satisfy this, even when that head's `backend/` and `.github` are identical.

## Trigger sequence

0. *(free)* Push the branch with no PR. Post the #1029 comment: head SHA, this file's sha256, the tails of the gate
   run on that head (precondition 6), review verdicts and the spend start point.
1. *(about USD 0.18)* Read the DeepSeek balance and the shared ledger. The planned set fits the reservation
   (0.19 + 3 × 0.1725 = 0.7075 ≤ 0.75). **Stop** unless both hold: the shared-ledger remainder, minus every other
   owner's later known charges and reservations (for example the #1050 successors' 1.00 in comment 5960418625),
   is at least 0.75; and the DeepSeek balance is at least 0.75. Trigger off-peak only: not Monday–Friday
   01:00–04:00 or 06:00–10:00 UTC, and at least 20 minutes before the next peak start (`eval-baseline` takes about
   10–11 minutes). Open the PR as a **draft**. Its body carries the Review section, the M0–M4 tails from
   `mutations.txt` (the mutation proofs), and a `Review override:` line whose reason is limited to the measurement
   window: no merge under this disposition, and the line is removed before any merge decision.
   This runs `eval-baseline` once; `copilot-eval` is skipped while the PR is a draft.
2. After `eval-baseline` completes: download its artifact and record the sha256 of the zip beside the artifact's
   API `digest` (Custody), and the sha256 of its report JSON (`eval_*.json`); record its verdict and telemetry
   (`summary.baseline.incurred_provider_usage`, with `calls` and `unknown_calls`) and its `source_sha` (the merge
   ref, in `ci-execution.txt`). Apply the spend rule: spent + 3 × 0.1725 ≤ 0.75. Before marking ready, run three
   checks:
   - the REST pull-request `mergeable` field is true (re-read while it is null). `mergeable_state` is not the
     check: it reads `draft`, `blocked` or `unstable` on a draft PR or with failing non-required checks;
   - the Validity backend-tree check on the previous run's `source_sha`:
     `git diff --quiet <head> <previous source_sha> -- backend .github` exits 0, where `<head>` is the frozen head;
   - `git diff --quiet <previous source_sha>^1 origin/main -- backend .github` exits 0, i.e. main's `backend/` and
     `.github` are unchanged since the previous run's merge ref was made. (The merge ref contains the candidate's
     backend diff and `origin/main` does not, so this compares main with the merge ref's first parent, which is
     main.)

   For Q1 the previous run is `eval-baseline`, so row R(i) and Q1 measure one backend tree. A failed check means no
   ready transition: the lane is a **validity stop**, reported, and the outcome is Incomplete unless a check has
   already failed (see Outcome). Otherwise mark the PR ready: this starts **Q1**.
3. After Q1 completes: download the artifact; record the sha256 of the zip beside the artifact's API `digest`
   (Custody), and the sha256 of `copilot-eval.json` and `runner.log`.
   Inspect validity, cost and checks 1–5 **before continuing**. Convert to draft. Apply the same spend rule and the
   same three checks, with Q1 as the previous run; a failed check is a validity stop, as in step 2. Mark ready: this
   starts **Q2**.
4. Repeat step 3 for **Q3**. Then convert the PR back to draft.

Every paid trigger in steps 1–4 is off-peak under the step-1 rule. Never push, rebase, close or reopen the PR
during or after the window. Never toggle it while a run is in progress (`copilot-eval` cancels an in-progress run).
Results go in PR or #1029 comments, never in commits to this branch.

## Validity (one rule)

A run is valid only when every row matches the identity table above (`run_validity.py` exits 0) and
`git diff --quiet <head> <source_sha> -- backend .github` exits 0, where `<head>` is the frozen head and `source_sha`
is the run's merge ref (for `eval-baseline`, from `ci-execution.txt`). This binds `eval-baseline`, Q1, Q2 and Q3 to
the gated tree, so `backend/` and `.github` also agree between consecutive merge refs. The step-2 and step-3
pre-trigger checks stop the lane before paying for a run that follows an invalid one, or one whose merge ref would
be built on a changed main; a backend merge that lands after a ready transition is caught only by this rule, after
the run. A mismatch, a cancelled run or a missing artifact makes the run **invalid**: stop, record, apply no rule,
run no replacement. Fingerprints are reported; a value other than `aeb56401` does not make a run invalid.

**Invalidity never erases a failure.** `run_validity.py` marks a row without `tool_trace.initial_messages` as a
mismatch, and the runner records those messages only once the service reaches the provider call. A row with an
`error` and no recorded request therefore makes the run invalid **and** fails check 5 (0 errors). The outcome is
Not qualified, with the stop reported.

## Acceptance: checks 1–5 on each run

Verbatim from `tasks/copilot-tool-nonexecution-2026-09-30.md` ("Acceptance checks for any fix candidate"):

> **Acceptance checks for any fix candidate** (every run, both runs):
>
> 1. MSFT string-ID rejections: 0 (no withheld MSFT row; no string or `F#` identity in the citation array).
> 2. AAPL/TSLA/MSFT tool use: every draw (18/18 across both runs).
> 3. ASML: no stitched or unverified citation excerpt, no withheld ASML row, and no composed prose
>    quotation; redundant cross-check citations are counted and reported.
> 4. Composed-quote audit clean: 0 composed or absent quotations across all rows.
> 5. Formal acceptance 18/18 with 0 errors, and 0 answers without any citation; uncited figures reported.

**Applied per run.** "18/18 across both runs" and "every run, both runs" were written for two runs. Codex's decision
applies the checks to **each** qualification run, so check 2 means 9/9 AAPL/TSLA/MSFT draws in each run, and every
check is evaluated separately on Q1, Q2 and Q3.

| # | Measured by |
| --- | --- |
| 1 | No MSFT row has an `error`. `crosscheck_count.py` lists 0 declared objects without a positive JSON integer `n` on MSFT rows. No MSFT row carries an `Invalid citation declaration` withheld reason. |
| 2 | `g_decide.py`: every AAPL, TSLA and MSFT draw is `T` (9/9 per run). |
| 3 | 3/3 ASML rows completed and scored, each with `unverified_excerpts == []` and `citation_faithfulness == 1.0`; no ASML row has an `error`; `f_attribution.py`: 0 ASML F-withheld; `composed_quotes.py`: 0 composed spans on ASML rows (registered measurement below; the raw `prose_quote_audit.py` ASML hits are reported beside it). Redundant cross-checks are counted with `crosscheck_count.py` (declared method in its docstring) and reported. |
| 4 | `f_attribution.py` exits 0 with 0 UNEXPLAINED and 0 F-withheld rows on any surface (answer, reason, chip). `composed_quotes.py` exits 0: 0 composed spans and 0 rows without source text (`prose_quote_audit.py`'s `rows_without_source_text == []`). The raw `composed_quote_rows` of `prose_quote_audit.py` are reported beside it, with each flagged span's verdict. |
| 5 | `summary` expected/completed/scored 18/18/18, `errors` 0, `accepted` true, `failures` []. `prose_quote_audit.py` `uncited_answer_rows` = 0. Uncited figures are reported as the sum of `score.uncited_figures` per run and per question. |

**Audit policy for checks 4 and 5.** `prose_quote_audit.py` exits 2 whenever an escalation category is non-empty.
Following the D14/D17 precedent (`tasks/pr-disposition-2026-09-30.md`): composed 0 and uncited answers 0 is a pass.
`uncited_figure_rows` (any ticker) and `tool_less_rows` are reported, not thresholds. The existing MSFT advisory
(one uncited figure per draw) is reported and is not made a threshold.

**Composed-quotation measurement for checks 3 and 4, decided before the runs.**

*Why the raw audit cannot be the measurement on this build.* `prose_quote_audit.py` reads quotations more simply than
decision F. It lacks F's citation-marker blanking (`[n]`, `[F#]`), its edge-character stripping (spaces, `.,;:!?…`),
`normalize_for_match`'s punctuation-spacing fold, and its folds for low and curly marks, the non-breaking hyphen, the
minus sign and invisible characters. Its floor counts the raw characters between the marks, while F applies its floor
(8) after blanking markers and stripping edges, so the audit checks a label such as `"EBITDA [1]"` that F exempts. It
also lacks F's markdown reading (emphasis delimiters `*`, `_`, `~`, backslash escapes and character references) and
F's quote pairing. Its regex `"([^"]{8,})"` cannot match a quotation under 8 characters, so after a sub-floor quoted
label it restarts at the label's closing mark and pairs that mark with the next quotation's opening mark: the text
between the two quotations becomes an audit span, though F never reads it as a quotation. The audit reads only
published answers. With F live, every published double-quoted span has already passed F's per-span test (found in the
source, or exempt under the floor), so on this build a raw audit hit is a normalization, floor, pairing or rendering
difference, or an F defect. A truly composed quotation is withheld by F, and it fails through the F-withheld legs of
checks 3 and 4 and the 0-errors leg of check 5. Across the 23 retained runs, the raw audit flags five runs
(`composed_quotes.txt`):
- Three runs from before decision F, whose composed quotations were published: 36777581481 (BABA
  `"Revenue ... 996,347"`), 36800236360 (ASML `"Total net sales 32,667.3"`, `"Net income 9,609.4"`) and 36870677818
  (AAPL `"Total net sales 416,161"`, `"Gross margin 195,201"`). F's per-span test also fails on every one of these
  spans; they are genuine compositions.
- Two F-live runs, where the flagged quotation was published and F-verified:
  - B2 37029964566, ASML d1: the MD&A sentence that begins "Net income for 2025 amounted to €9,609.4 million,
    representing" (full span in `composed_quotes.txt`). The source reads `million\n, \nrepresenting`.
  - C1 37004589548, AAPL d0: `labels this line "Gross margin,"`, with the comma inside the closing mark.
  F's per-span test finds both.
Under a strict reading, 2 of the 12 G and later-main runs and 1 of the 2 arm-B runs (the candidate's parent arm)
would fail check 4 with no composed quotation; B2 would also fail check 3. The ASML MD&A shape appeared in 1 of the
25 tool-using ASML draws across the retained runs (1 of 18 in the G and later-main runs). At arm B's rate of three
tool-using ASML draws per run, that shape alone gives about a 31–40% chance of at least one false failure across
Q1–Q3. The candidate's wording may also move quoting toward the two shapes that trigger it: MD&A sentences, and quoted
labels with the figure outside, where a comma often sits inside the closing mark.

The pairing shape is a sub-floor quoted label followed by another quotation in the same answer: for example BABA's
7-character label `"Revenue"`, then a quoted MD&A sentence, or the same label quoted twice with figures between
(`composed_quotes_probe.txt`, cases 1–3). F publishes such an answer, the raw audit flags the text between the two
quotations, and both the strict reading and a reading that re-tests each audit span as the audit pairs it read that
text as composed. BABA-viewed answers quote `"Revenue"` in 13 of the 69 retained BABA-viewed draws (9 of the 23
runs), and the candidate's "Keep table figures outside quotation marks" may move quoting toward quoted labels. No
retained published answer (0 of 402) quotes a sub-floor label followed by another quotation, so the retained runs
do not exercise this shape.

*Registered measurement.* The quotations read are those of each row `prose_quote_audit.py` flags. On such a row the
published answer is folded with the audit's own FOLD. For the pairing only, F's other three marks (`＂`, `„`, `‟`) are
also made straight, one character for one, so positions still match the audit's spans. The double quotes are then
paired in order: the matches of `"([^"]*)"`, with no floor. A pair may cross a line break, as F's pairs may, and an
empty pair is read as a sub-floor label. A quotation is **composed** when F's per-span test, as copied in
`composed_quotes.verdict`, neither exempts it nor finds it in the row's `inputs.source_text`. Every pair on the row
is tested, whether or not the audit flagged it. The copy blanks markers, strips edge characters, applies F's floor (a
normalized needle under 8 characters with no interior ellipsis is a label) and matches with a copy of
`normalize_for_match` (`quote_inventory.classify`, `in_source`). The other classes are reported, with the raw audit
count beside them, and none is composed:
- **audit pairing difference:** an audit span that is not one of the row's pairs, i.e. the text between two
  quotations (the pairing shape above: a sub-floor quoted label such as BABA's `"Revenue"` followed by another
  quotation);
- **sub-floor label:** a pair the per-span test exempts;
- **audit normalization difference:** a flagged pair the per-span test finds. An unflagged pair it finds is counted
  as verified.

The two folds make all six of F's marks straight, so the in-order pairing leaves a mark unpaired only when their
count on the row is odd. The row's pairs are then not trusted: its audit spans are tested as the audit pairs them,
none is an audit pairing difference, its other pairs are not read, and the row is reported as having unpaired marks.
Such a row can still fail on the pairing shape. F pairs every mark it reads, so an answer F publishes has an even
count as displayed; an odd count needs a mark that the answer's text and its display count differently, such as a
character reference (`&quot;`, probe case 37). With an even count, the in-order pairs are F's pairs unless F reads
a nested quotation or the display differs from the text, the two readings below. A row without source text remains
an absent quotation and fails. Two parts of F's reading are not copied:
- its markdown reading (emphasis delimiters, backslash escapes and character references): a published quotation
  that contains markdown emphasis, such as `"**Net income**"`, is still read as composed and is reported with its
  span; an escaped mark (`\"Revenue\"`) leaves its backslash in the pair, which can then reach the floor and read as
  composed (probe case 38); and a character reference is read as written;
- its nested reading: `"x "y" z"`, which F tests whole and inner, is read in order as two pairs, with the inner text
  as the gap between them.

None of the 402 published answers in the 23 retained runs contains `*`, `_` or `~`, a backslash or a character
reference (`&name;` or `&#…;`), holds a `＂`, `„` or `‟` mark or an odd number of marks, nests a quotation (by F's own
reading), or quotes a sub-floor label followed by another quotation. Across all 432 rows of the 24 retained runs
(including run 37072989252 and the 12 withheld candidates), no row holds a backslash, a character reference, one of
those three marks or an odd number of marks. Each of the 15 spans the audit checks in the 23 runs is one of its
row's pairs and matches a span of F's own reading. `composed_quotes.py` applies this mechanically. On the retained
runs it keeps all three genuine compositions and clears both F-verified spans; no flagged span there is under the
floor or a pairing difference. `composed_quotes_probe.py` compares the reading with the product's
`unsupported_prose_quotations` on 38 synthetic answers built on retained source texts (`composed_quotes_probe.txt`).
No answer F publishes is read as composed, apart from three disclosed cases: markdown emphasis, a backslash-escaped
mark and a one-sided character reference (the odd count above). Every answer F withholds is read as composed, apart
from two the audit does not flag: the disclosed nested case, and a `„…‟` quotation, which F withholds as ambiguous
(`‟` opens in F). A run fails both through the F-withheld leg.
The check text is unchanged. Only the reading of the audit leg is defined here, and the F-withheld, error and 18/18
legs are untouched.

*Decision owner.* This defines how a check's measurement is read, so Codex acknowledges it on #1029 before step 1
(precondition 5). Codex may instead direct the one predeclared alternative before step 1: the **strict reading**.
Under it, any raw `composed_quote_rows` entry fails check 4, and fails check 3 when it is on an ASML row. That
direction accepts the false-failure exposure described above, including the pairing shape. The "audit normalization
difference", "sub-floor label" and "audit pairing difference" verdicts are then reported, but they never convert a
failure. No other reading is available, and the reading in force is fixed before step 1.

## R. RUNBOOK aggregate evidence

A separate row, after checks 1–5, which stay unchanged:
- (i) The `eval-baseline` run on the frozen head (step 1) passes against the unchanged baseline. It is reported as a
  normal gate. A red result means not qualified; it is never re-run.
- (ii) `score.fact_adjacency == 1.0` on every scored row of each run: the TRUST veto (`backend/evals/RUNBOOK.md`,
  "Gating rule": "The aggregate's TRUST line … is the hard veto").
- (iii) Three runs × `--runs 3` give 9 draws per question, meeting the RUNBOOK's aggregate rule for prompt changes.
  The RUNBOOK's `--runs 5` requirement covers density-forcing prompts. This rule makes no marker or density demand,
  and 9 draws per question exceeds 5 in any case.

## Reported as context, outside the rules

- **20-F tool use** per run, from `g_decide.py`: question-runs and draws. A run with 20-F tool-using question-runs
  ≤ 1/3 is labelled **"deletion effect not preserved"** (a question-run is tool-using when at least 2 of its 3
  draws have non-empty `tool_trace.tool_results`, as `g_decide.py` counts). This is a label, not a check.
- **Exposure denominators,** per run and across Q1–Q3, from `g_decide.py`'s per-question draw strings: tool-using
  ASML draws and tool-using BABA-viewed draws. The label above sums the three 20-F questions, so it can miss ASML
  alone going tool-less. A check-3 pass on tool-less ASML draws is reported as such. It is not evidence that the
  rule stops the label-plus-cell shape, because none of the 44 tool-less ASML draws in the 23 retained runs was
  withheld or errored.
- **Quote inventory** across all forms (double, single, backtick, guillemet, blockquote), from `quote_inventory.py`:
  where table figures go (displacement report).
- **Non-F withholds,** with their captured reasons.
- **Redundant cross-check counts,** from `crosscheck_count.py`.
- **Not-disclosed rows:** expected 0. The not-disclosed path is unmeasured live.
- **Uncited figures,** per run and per question. The MSFT advisory is not a threshold.
- **Per-run cost,** including cache-miss tokens, and **fingerprints**.
- **Runtime versions,** `preparation.runtime.versions` per run (printed by `run_validity.py`). The base pins
  `openai` 3.20.0, `edgartools` 5.58.0 and `sqlalchemy` 2.0.54. Every retained run before #1066 recorded `openai`
  3.19.2; #1067's post-#1066 run 37072989252 recorded 3.20.0 (`run_validity_post1066.txt`). A different value is
  reported; the backend-tree rule above is the validity condition.

Baseline values of these measures on retained main and arm B runs are in this folder's README.

## Outcome

- **Qualified:** all three runs are valid, and each passes checks 1–5 and R.
- **Not qualified:** any check fails in any run. The predeclared set continues while validity and spend permit,
  but the failure stands. No retry, selective rerun, replacement run or candidate edit. Diagnostic withhold reasons
  never turn withheld rows into passes. The #1056 triage rule (`RUNBOOK.md`, "Triage rule for a red copilot-eval
  run") does not apply, because this candidate changes model-facing bytes.
- **Incomplete:** a validity stop or a spend stop with no failed check. The early stop is reported. A row with an
  `error` and no recorded request is a check-5 failure even though it also stops the run (see Validity).

## Spend

- **Start point:** the last posted shared-ledger remainder, USD 7.346893 (#1029 comment 5961781714), before other
  owners' later costs. The 0.75 reservation is debited from it.
- **Rule:** before step 1, 0.19 + 3 × 0.1725 ≤ 0.75, and the two step-1 stops (shared remainder after other
  owners' later known charges and reservations ≥ 0.75; DeepSeek balance ≥ 0.75). Before each ready transition,
  spent so far + remaining runs × 0.1725 ≤ 0.75. USD 0.1725 is the off-peak cost of one run with no cache hits;
  0.19 is the conservative off-peak `eval-baseline`. Budget risk stops the lane: a failed spend rule, or the
  balance case for a run with unknown-cost calls (below).
- **Accounting:** every physical provider call, including withheld and error rows and unknown charges.
  `copilot_cost_runnerlog.py` over each run's `runner.log` for the Copilot runs;
  `summary.baseline.incurred_provider_usage` (with `unknown_calls`) for `eval-baseline`. Unknown cost is not free.
- **Unknown-cost calls.** Each provider call without usage is charged to "spent so far", and it stops the lane only
  when the charged total fails the spend rule. The charge is the off-peak, no-cache, worst-case cost of one call of
  its kind, doubled for a call the log marks `"peak": true`:
  - a Copilot call (a `runner.log` `ai_call` line without usage, counted as `unknown` by
    `copilot_cost_runnerlog.py`): **USD 0.0071**. That is the largest prompt among the 722 Copilot calls logged
    in the 24 retained runs (37,115 tokens) at the cache-miss rate of 0.15 per 1M, plus the pinned 2,400-token
    completion cap at 0.60 per 1M;
  - an `eval-baseline` call (`summary.baseline.incurred_provider_usage.unknown_calls`): **USD 0.0179**. That is the
    largest one-call prompt among the 631 calls in the 9 retained `eval-baseline` reports (71,040 tokens) at the
    cache-miss rate, plus a 12,000-token completion (the largest `max_tokens` the summary extraction requests) at
    0.60 per 1M.

  The prompt sizes are the largest observed, not hard caps. One case replaces the charge: the DeepSeek balance is
  read before the run's trigger and again after its artifact is downloaded, and it fell by at least the run's
  known cost but by less than the known cost plus these charges. The run's spend is then that balance delta. A
  smaller delta means the balance has not settled, and the charge stands. The delta also counts any other owner's
  concurrent calls, so it can overstate this lane's spend. A delta above the known cost plus the charges is decided
  by whether the run has unknown-cost calls:
  - with unknown-cost calls, the charge may understate this lane's spend. That is budget risk: the lane stops, and
    the stop is reported;
  - with none, the run's known cost is exact. The excess is reported as other owners' concurrent spend, and the lane
    does not stop.

## Custody

After each run: download the artifact, then record in a PR or #1029 comment the sha256 of the zip computed locally,
beside the artifact's `digest` from the Actions artifacts API (`gh api
repos/neilmac91/EarningsNerd/actions/runs/<run_id>/artifacts`, read only), and the sha256 of `copilot-eval.json` and
`runner.log`. The two zip values are expected to be equal; a difference is reported with both. In the same comment,
record the run's merge ref: `git fetch origin <source_sha>` fetches the object by its SHA (GitHub regenerates
`refs/pull/N/merge` as main moves), and `git rev-parse <source_sha>^1 <source_sha>^2` gives its parents. If that
fetch is refused, the compare API (`repos/{owner}/{repo}/compare/<head>...<source_sha>`) is the fallback for the
Validity diff and the parents. The `eval-baseline` artifact is row R(i)'s evidence and has 14-day retention. It is
downloaded promptly, and the sha256 of its zip, beside the API `digest`, and of its report JSON go in the same kind
of comment. A durable private copy is requested from the founder-side Codex custody owner, as for G; this lane cannot
write founder storage.

## Handback (#1029)

- the frozen head;
- all three outcomes, or the explicit stop;
- actual telemetry and unknowns;
- the exact-head review and the gates;
- remaining limitations:
  - small denominators, including the exposure denominators above (tool-using ASML and BABA-viewed draws);
  - the not-disclosed path is unmeasured live;
  - decision F and the audit see only double quotes, so other quote forms are visible only through the inventory;
  - the composed-quotation reading in force for checks 3 and 4; every audit normalization difference, sub-floor
    label and audit pairing difference (the text between two quotations, as when a sub-floor quoted label such as
    BABA's `"Revenue"` is followed by another quotation); every row with unpaired marks (an odd mark count, read
    as the audit pairs it, so the pairing shape can still fail there); and any span holding markdown emphasis, a
    backslash escape or a character reference, or read from a nested quotation (F's markdown reading, with its
    emphasis delimiters, backslash escapes and character references, and its nested reading are not copied);
  - offline coverage of the G failure shapes is argued, not replayed (a prompt change alters model output).

This design's earlier versions and the review findings are preserved in `design-history/`.
