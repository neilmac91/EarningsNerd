# Copilot prompt fix candidate (2026-10-02)

One prompt candidate, authorized by Codex's decision on #1029 (comment 5958742492, 2026-10-02 18:27Z, under the
founder's delegation; text in [design-history/codex-decision-5958742492.md](design-history/codex-decision-5958742492.md)).
The candidate commit `81f85248` was cut from main `efdc33f4` (post-#1065). Main then moved to
`b40fa70382c5d45239817f012c2b0e9d6a5a5532`:
- #1066 changes the backend runtime pins (`openai` 3.20.0, `PyJWT` 2.15.1, `sentry-sdk` 2.71.0).
- #1067 changes `backend/requirements-eval.txt` (`anthropic` 1.9.0), which neither CI nor the Copilot runner
  installs.
- #1042, #1043 and #1044 are frontend-only.
Merge commits `5e5e80a5` (main `11681b9c`) and `3264cdcc` (main `b40fa703`) bring that main into the branch, so the
gated tree is the tree the runs measure. `b40fa703` is the base for every comparison below. The candidate is
qualified by three fresh paid runs under [PREREGISTRATION.md](PREREGISTRATION.md). No merge and no production
prompt release follow from them.

## The candidate

`SYSTEM_PROMPT` in `backend/app/services/copilot_service.py` changes in three places. Nothing else in that file
changes ([scope_hashes.txt](scope_hashes.txt), AST check).
- **(a) Arm B's deletion.** `, including when all cited figures use tool markers` is removed. G stage 2 showed this
  clause suppressed 20-F tool use ([../g-stage2-2026-10-02/README.md](../g-stage2-2026-10-02/README.md)).
  "If there are no filing-text markers, output []" stays, so a tool-only answer still declares `[]`.
- **(b) A RULES bullet,** after the `[F#]` bullet and before `OUTPUT FORMAT`: "Each quotation in your answer prose
  must be one contiguous span copied verbatim from the filing. Keep table figures outside quotation marks, never
  quote a table row with cells left out, and never put an ellipsis inside a quotation."
- **(c) The not-disclosed template** gains "; name the missing metric without quotation marks".

Composed prompt: sha256 `a22fb4cd5472512f5867bad039feaef7400487869487fa94ae5d7a94073309f5`, 5289 characters.
Removing (b) and (c) gives arm B `16457055`; adding the clause back gives main `a88b6fb1`, byte-equal to the base's
own prompt ([prompt_identity.txt](prompt_identity.txt)).

**Why this wording** (design v2, [design-history/design-v2.md](design-history/design-v2.md)):
- "Keep table figures outside quotation marks" is formatting only. The earlier "state table figures" was an
  answer-shape imperative next to the no-tool fallback sentence, which risks the hypothesis-1 tool-skipping cue.
- "in your answer prose" matches Codex's scope and leaves the citation and follow-up JSON strings out of it.
- "a label joined to its value" was dropped. It is not in Codex's wording and could suppress genuine MD&A sentences.
- "only one … such as a sentence or phrase" was dropped. It read as a one-quotation limit and invited quoting.
  The per-quotation framing still allows genuine contiguous quotations.
- The absence clause sits in the not-disclosed template. In RULES it would sit on the disclosed path, next to
  "never announce that a figure was omitted or unavailable".

## Files

| File | What it shows |
| --- | --- |
| [PREREGISTRATION.md](PREREGISTRATION.md) | identity table, preconditions, trigger steps 0–4, validity, checks 1–5, row R, context, outcomes, spend, custody, handback |
| [prompt_identity.py](prompt_identity.py), [prompt_identity.txt](prompt_identity.txt) | full sha256 and length; `_build_messages(...)[0]` equals `SYSTEM_PROMPT`; minus (b) and (c) equals arm B; plus the clause equals main and the base's own prompt; floors 8 and 24 |
| [scope_hashes.py](scope_hashes.py), [scope_hashes.txt](scope_hashes.txt) | byte identity to base (`git diff --exit-code` and sha256 at both) of the scorer, runner, bootstrap, schema, golden set, sources, baselines, regression gate, RUNBOOK, runtime pins, flags and model, workflows, tool path, citation floor, decision F's owner test, every locked test and the measurement tools; allowed diff; AST scope |
| [run_validity.py](run_validity.py), [run_validity.txt](run_validity.txt) | the validity checker for each qualification run (full prompt hash and length per row), with negative and control results on retained runs |
| [composed_quotes.py](composed_quotes.py), [composed_quotes.txt](composed_quotes.txt) | the registered composed-quotation measurement for checks 3 and 4: the unchanged #1021 audit, with each flagged span re-tested by F's per-span test; output on all 23 retained runs |
| [crosscheck_count.py](crosscheck_count.py), [crosscheck_count.txt](crosscheck_count.txt) | declared redundant cross-check method (declared objects on every row, placed and unplaced); also lists declared citation identities (check 1) |
| [quote_inventory.py](quote_inventory.py), [quote_inventory.txt](quote_inventory.txt) | every quoted span in every quote form, classified as table-figure, sub-floor, verified or other |
| [baseline_context.txt](baseline_context.txt) | input sha256, `g_decide.py`, `copilot_cost_runnerlog.py`, `prose_quote_audit.py` summaries and uncited figures on the retained runs |
| [mutations.txt](mutations.txt) | owner-test mutations M1–M4 failing, and M0 passing |
| [design-history/](design-history/design-v2.md) | design v1, design v2, the three adversarial critiques, Codex's decision and the round-1 exact-head review findings ([exact-head-review-r1.md](design-history/exact-head-review-r1.md)), verbatim |

The scripts have no `test_` prefix or `_test` suffix, so the test-homes gate does not treat them as tests.
`scope_hashes.txt` and `prompt_identity.txt` were produced against merge commit `3264cdcc`, with base `b40fa703`.
The commits after it change only files in this folder. Re-running both scripts on the frozen head gives the same
results, with this folder's new files added to the allowed-diff list.

## Owner test and mutations

`backend/tests/unit/test_copilot_live_regressions.py::test_contiguous_citation_instruction_reaches_actual_service_messages`
reads `messages[0]['content']` from the real `_build_messages`. It gains four assertions and no new test case:
- the clause is absent (the G stage-2 cause);
- "If there are no filing-text markers, output []" is present;
- the RULES bullet's full composed text occurs exactly once;
- `name the missing metric without quotation marks>` occurs exactly once.

There is no full-prompt hash pin in tests; the pre-registration carries the hash. `test_copilot_prose_quotations.py`
is byte-identical to base. Mutations, never committed ([mutations.txt](mutations.txt)): M0–M3 ran first on code
commit `81f85248`, and M0–M4 ran again on merge commit `3264cdcc`; every run gave the same result.

| Mutation | Result |
| --- | --- |
| M1: restore the clause | fails the clause-absent assertion (`:68`) |
| M2: delete the RULES bullet | fails the rule-once assertion (`:70`) |
| M3: revert the template edit | fails the template assertion (`:74`) |
| M4: delete the kept sentence "If there are no filing-text markers, output []" | fails the kept-sentence assertion (`:69`) |

## Baseline of the declared measures on retained runs

Three retained main-prompt runs (`a88b6fb1`) and G stage 2's arm B run B1 (`16457055`). Inputs and full outputs are
in [baseline_context.txt](baseline_context.txt), [quote_inventory.txt](quote_inventory.txt) and
[crosscheck_count.txt](crosscheck_count.txt).

| Run | 20-F tool-using question-runs | Draws with tools | Quoted spans (table-figure) | Declared cross-checks (restating a tool figure) | Uncited figures | Cost USD (calls) |
| --- | --- | --- | --- | --- | --- | --- |
| [37049387017](https://github.com/neilmac91/EarningsNerd/actions/runs/37049387017) main | 0/3 | 10/18 | 1 (0) | 1 (1) | 3 (MSFT) | 0.005302 (28) |
| [37052760996](https://github.com/neilmac91/EarningsNerd/actions/runs/37052760996) main | 0/3 | 11/18 | 0 (0) | 0 (0) | 3 (MSFT) | 0.005463 (29) |
| [37063120532](https://github.com/neilmac91/EarningsNerd/actions/runs/37063120532) main | 1/3 | 11/18 | 0 (0) | 1 (1) | 3 (MSFT) | 0.005538 (29) |
| [37029156902](https://github.com/neilmac91/EarningsNerd/actions/runs/37029156902) arm B | 3/3 | 18/18 | 7 (4) | 8 (8) | 4 | 0.033333 (36, cold prefix) |

- Every logged call in the four runs carries fingerprint `aeb56401`.
- On all three main runs the label "deletion effect not preserved" (20-F tool-using ≤ 1/3) would apply.
- B1's four table-figure spans are the two withheld ASML candidates' `"Total net sales 32,667.3"` and
  `"Net income 9,609.4"`, the shape this candidate targets.
- No retained run uses single quotes, backticks, guillemets or blockquotes. Over all 23 retained runs in the lane's
  scratch directory, every quoted span is in double quotes.
- `prose_quote_audit.py` composed rows: 0 in each of the four runs. It audits only published answers, so B1's
  withheld candidates are seen by `f_attribution.py` and the inventory, not by it.
- The cross-check counter now reads the declared array on every row. In the four runs every declared cross-check
  is placed, so the counts equal the earlier method's. On arm C run C1 (37004589548, included in
  `crosscheck_count.txt` as a method check) it finds 25 declared cross-checks, 16 of them unplaced; the earlier
  method saw 9.

**Composed-quotation measurement (checks 3 and 4).** `prose_quote_audit.py` normalizes less than decision F. It
lacks marker blanking, edge stripping, the punctuation-spacing fold and the low/curly-mark, hyphen, minus and
invisible-character folds. Over the 23 retained runs it flags five runs:
- three runs from before F, all genuine compositions;
- two F-live runs whose flagged quotation F verified and published: B2 37029964566 ASML d1 (the MD&A sentence; the
  source reads `million\n, \nrepresenting`) and C1 37004589548 AAPL d0 (`"Gross margin,"`, comma inside the mark).
Read strictly, the audit would fail 2 of the 12 G and later-main runs and 1 of the 2 arm-B runs with no composed
quotation. The ASML MD&A shape alone gives about a 31–40% chance of one such false failure across Q1–Q3. The
pre-registration therefore registers one reading: a span is composed when the audit flags it and F's per-span test
(`quote_inventory.classify`, `in_source`) also fails. Other flagged spans are reported as audit normalization
differences. It applies to check 3 and check 4 alike, and `composed_quotes.py` implements it
([composed_quotes.txt](composed_quotes.txt)). Codex acknowledges it on #1029 before step 1, or directs the strict
reading instead, with the exposure above accepted.

## Failure-shape coverage (argued, not replayed)

A prompt change alters model output, so the retained G failure shapes cannot be replayed offline against it. The
coverage below is an argument; the shapes and their sources are in [design-history/design-v1.md](design-history/design-v1.md) §2.

| Retained shape | Decision F today | Clause addressing it |
| --- | --- | --- |
| Label plus one cell, other cells removed: `"Total net sales 32,667.3"` (ASML, 7 rows) | `quotation_not_in_source` | "Keep table figures outside quotation marks"; "never quote a table row with cells left out"; "copied verbatim" |
| Interior ellipsis: `"Net income 7,571.6 ... 9,609.4"`, `"Revenue ... 996,347"` | `elided_quotation` | "never put an ellipsis inside a quotation"; "Keep table figures outside quotation marks" |
| Label and value with no separator in the source: `"Total net sales 416,161"` | `quotation_not_in_source` | "copied verbatim"; "Keep table figures outside quotation marks" |
| Verified label plus the wrong-year cell: `"Net income 7,571.6"` | publishes | "Keep table figures outside quotation marks" (stricter than F, deliberately) |
| Bare cell under the floor: `"9,609.4"`, `"996,347"` | exempt (under 8) | "Keep table figures outside quotation marks"; the figure is still stated |
| Quoted absent metric in a not-disclosed reason | withheld (pinned in `test_copilot_prose_quotations.py`) | template (c); unmeasured live (no not-disclosed golden question) |

Legitimate shapes the wording keeps: contiguous MD&A sentences carrying figures (BABA "further increased by 3% to
RMB1,023,670 million …", ASML "Net income for 2025 amounted to €9,609.4 million …"), quoted labels with figures
outside the quotes, the unquoted cross-check, and an unquoted not-disclosed reason. The wording is stricter than F in
two places, both disclosed in the pre-registration: table figures inside quotation marks, and an edge ellipsis
(`"by 3% to RMB1,023,670 million …"`, which F verifies after stripping the ellipsis). The model can truncate
without the ellipsis, and F still verifies the span.

## Review record

- The design was reviewed adversarially before implementation by three lenses: decision fidelity, model behaviour,
  and repository rules and gates. Each returned NEEDS CHANGES; design v2 resolves their findings. All four documents
  are preserved in [design-history/](design-history/design-v2.md).
- The exact-head independent review of the commit containing this folder, the full gate tails and the head SHA are
  recorded in the step-0 comment on #1029, not here, so that recording them does not move the head.

### Review round 1 (exact-head review of `cd8199f1`)

Three lenses reviewed `cd8199f1` (code commit `81f85248` on `efdc33f4`) and returned one blocker, four should-fix
findings and twelve nits. The findings are kept verbatim in
[design-history/exact-head-review-r1.md](design-history/exact-head-review-r1.md). Resolution:

| Finding | Resolution |
| --- | --- |
| R1-3 (blocker): main moved past the head with a backend change (#1066 runtime pins), so the gated tree differed from the measured tree | Merged main `11681b9c` (merge `5e5e80a5`), then main `b40fa703` after #1067 landed during the fix round (merge `3264cdcc`). Gates use main's pins: `openai` 3.20.0, `PyJWT` 2.15.1 and `sentry-sdk` 2.71.0 come from an overlay on the gate venv, and venv plus overlay match all 99 pins of `requirements.txt` and the dev pins. Re-ran the full gate, the five RUNBOOK files with the owner test, and the tests that read `tasks/`, all on the integrated head with HEAD-stamped logs (tails in the step-0 comment). Regenerated `prompt_identity.txt` and `scope_hashes.txt` against `b40fa703`; the scope proof now covers the requirements files. Base lines updated. Precondition 1 is now a general deploy-receipt rule (#1066, #1067 and any later backend merge). New precondition 2 stops the lane if main's backend moves before step 1. Runtime versions are reported as context. The integrated head needs a fresh exact-head review (precondition 6). |
| R1-1, R1-2, R1-5: the strict audit leg of checks 3 and 4 fails F-verified quotations (B2 ASML d1 MD&A sentence; C1 AAPL d0 `"Gross margin,"`), and the gap was understated | The pre-registration now lists every normalization gap and both retained cases, and quantifies the strict-reading exposure. It registers one reading: a span is composed when the audit flags it and F's per-span test also fails (`composed_quotes.py`). The reading applies to check 3 and check 4. Over the 23 retained runs it keeps the 3 genuine pre-F compositions and clears the 2 F-verified spans. Codex acknowledges it on #1029 before step 1 (precondition 5), or directs the one predeclared alternative, the strict reading, with its exposure accepted. This lane cannot post on #1029, so the reading is fixed in the frozen file and Codex's choice between the two is recorded before any paid trigger. Neither reading is chosen after data. |
| R1-4: the pre-trigger diff check could never pass (the merge ref contains the candidate) | Restated as `git diff --quiet <previous merge ref>^1 origin/main -- backend .github`. For Q1 the previous merge ref is the `eval-baseline` run's `source_sha` (`ci-execution.txt`). The validity chain runs `eval-baseline`, Q1, Q2, Q3. |
| N1: the 20-F label can miss ASML alone going tool-less | Exposure denominators (tool-using ASML and BABA-viewed draws, per run and across Q1–Q3) are now reported in context and the handback. A check-3 pass on tool-less ASML draws is reported as such: 0 of the 44 retained tool-less ASML draws was withheld. |
| N2: "edge ellipses" listed as kept | Dropped from the kept list; disclosed as a second place where the wording is stricter than F. |
| N3: the cross-check counter used different bases for published and withheld rows | Declared objects are now counted on every row, placed and unplaced separately. The four baseline runs are unchanged (every declared cross-check is placed). On C1 the counter finds 25 declared cross-checks, 16 of them unplaced, where the earlier method saw 9. |
| N4: inventory surfaces and classes | A withheld candidate's not-disclosed reason is scanned (surface `withheld-reason`). The docstring says short prose figure phrases can be classed table-figure, so in_source is read alongside the class. A straight single-quoted span may now contain an apostrophe between word characters. All 23 retained runs still have only double-quoted spans. |
| N5: "recorded in the step-0 comment" | Now "recorded on #1029 before step 1". |
| N6: the step-1 spend rule was a constant | Explicit step-1 stops: the shared remainder after other owners' later known charges and reservations is at least 0.75, and the DeepSeek balance is at least 0.75. |
| N7: "MSFT uncited figures" mislabel | Now "`uncited_figure_rows` (any ticker) and `tool_less_rows` are reported, not thresholds". |
| N8: R(iii) did not address `--runs 5` | Added: the rule makes no marker or density demand, and 9 draws per question exceeds 5 in any case. |
| N9: no hash for the `eval-baseline` artifact | The sha256 of its zip and report JSON are recorded in step 2 and under Custody. |
| N10: an error row without a recorded request read as Incomplete | "Invalidity never erases a failure": such a row also fails check 5, and the outcome is Not qualified. |
| N11: gate logs did not name their HEAD | Every round-1 gate log starts with `git rev-parse HEAD`, `git status --short` and the provider-SDK versions. |
| N12: no mutation proof for the kept-sentence assertion | M4 deletes that sentence and fails the owner test at `:69` ([mutations.txt](mutations.txt)). |

## Limitations

- **Small denominators.** Failures concentrate on about six tool-using ASML and BABA-viewed draws per run. The
  exposure denominators are reported per run; a check that passes on tool-less draws did not exercise the shape.
- **Not-disclosed is unmeasured live.** The golden set has no live not-disclosed question.
- **Double quotes only.** Decision F and `prose_quote_audit.py` check double quotes only. Other quote forms are
  visible only through `quote_inventory.py`, whose classes are a declared heuristic, not F's parser.
- **Composed-quotation reading.** Checks 3 and 4 read the audit through F's per-span test (copied, not imported).
  An F defect that the copy shares would not be caught by the audit leg. The F-withheld, error and 18/18 legs still
  catch every composed quotation F withholds.
- **Argued coverage.** Offline coverage of the failure shapes is argued, not replayed.
