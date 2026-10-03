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
gated `backend/` and `.github` tree is the one the runs measure; the validity rule checks it for every run against
the frozen head. A run's merge ref also carries main's later merges outside `backend/` and `.github`. `b40fa703` is
the base for every comparison below. The candidate is
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
| [run_validity_post1066.txt](run_validity_post1066.txt) | the same checker on #1067's own `copilot-eval` run 37072989252 (post-#1066 runtime, `openai` 3.20.0): every identity row matches under the main-prompt control (precondition 2) |
| [composed_quotes.py](composed_quotes.py), [composed_quotes.txt](composed_quotes.txt) | the registered composed-quotation measurement for checks 3 and 4: the unchanged #1021 audit; on each row it flags, the answer's quotations paired in order and each re-tested by F's per-span test (floor, then source match); output on all 23 retained runs |
| [composed_quotes_probe.py](composed_quotes_probe.py), [composed_quotes_probe.txt](composed_quotes_probe.txt) | the reading against the product's `unsupported_prose_quotations` on 38 synthetic answers built on retained source texts (rounds 3 and 4) |
| [crosscheck_count.py](crosscheck_count.py), [crosscheck_count.txt](crosscheck_count.txt) | declared redundant cross-check method (declared objects on every row, placed and unplaced); also lists declared citation identities (check 1) |
| [quote_inventory.py](quote_inventory.py), [quote_inventory.txt](quote_inventory.txt) | every quoted span in every quote form, classified as table-figure, sub-floor, verified or other |
| [baseline_context.txt](baseline_context.txt) | input sha256, `g_decide.py`, `copilot_cost_runnerlog.py`, `prose_quote_audit.py` summaries and uncited figures on the retained runs |
| [mutations.txt](mutations.txt) | owner-test mutations M1–M4 failing, and M0 passing |
| [design-history/](design-history/design-v2.md) | design v1, design v2, the three adversarial critiques, Codex's decision and the exact-head review findings of round 1 ([exact-head-review-r1.md](design-history/exact-head-review-r1.md)), round 2 ([exact-head-review-r2.md](design-history/exact-head-review-r2.md)), round 3 ([exact-head-review-r3.md](design-history/exact-head-review-r3.md)) and round 4 ([exact-head-review-r4.md](design-history/exact-head-review-r4.md)), verbatim |

The scripts have no `test_` prefix or `_test` suffix, so the test-homes gate does not treat them as tests.
`prompt_identity.txt` was produced against merge commit `3264cdcc`, with base `b40fa703`. The commits after it
change only files in this folder, and re-running it on the frozen head gives the same result apart from the HEAD
line. `scope_hashes.txt` was regenerated in round 4 against the round-4 commit as it stood before this file was
rewritten (its head line). That commit has the same files as the frozen head, so re-running the script on the frozen
head gives the same output apart from the head line.

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

**Composed-quotation measurement (checks 3 and 4).** `prose_quote_audit.py` reads quotations more simply than
decision F. It lacks marker blanking, edge stripping, the punctuation-spacing fold and the low/curly-mark, hyphen,
minus and invisible-character folds. Its floor counts raw characters, so it checks a label such as `"EBITDA [1]"`
that F exempts under its floor. It also lacks F's markdown reading (emphasis delimiters, backslash escapes and
character references) and quote pairing: its regex `"([^"]{8,})"` cannot match a quotation under 8 characters, so a
sub-floor quoted label such as BABA's `"Revenue"` followed by another quotation makes it pair the label's closing
mark with the next opening mark, and the text between the two quotations becomes its span. Over the 23 retained runs
it flags five runs:
- three runs from before F, all genuine compositions;
- two F-live runs whose flagged quotation F verified and published: B2 37029964566 ASML d1 (the MD&A sentence; the
  source reads `million\n, \nrepresenting`) and C1 37004589548 AAPL d0 (`"Gross margin,"`, comma inside the mark).
Read strictly, the audit would fail 2 of the 12 G and later-main runs and 1 of the 2 arm-B runs with no composed
quotation. The ASML MD&A shape alone gives about a 31–40% chance of one such false failure across Q1–Q3. The pairing
shape is not in the retained runs (0 of 402 published answers), but BABA-viewed answers quote `"Revenue"` in 13 of
69 retained draws, and F publishes the shape.

The pre-registration therefore registers one reading. On each row the audit flags, the answer (folded with the
audit's FOLD and, for the pairing only, with `＂`, `„` and `‟` made straight, one character for one) has its double
quotes paired in order (`"([^"]*)"`, no floor, across line breaks, empty pairs allowed), and every pair is re-tested
by F's per-span test (`composed_quotes.verdict`: F's floor, then `quote_inventory.classify`'s `in_source`). A pair
the test neither exempts nor finds is composed, whether or not the audit flagged it. The other classes are reported
and are not composed: **audit pairing difference** (an audit span that is not one of the row's pairs, i.e. the text
between two quotations), **sub-floor label**, **audit normalization difference** (a flagged pair the test finds) and
verified (an unflagged pair it finds). A mark is left unpaired only when the row's count of F's six marks is odd.
That row falls back to testing the audit's own spans as the audit pairs them and is reported, so the pairing shape
can still fail there. An answer F publishes has an even count as displayed, so this needs a mark that the text and
the display count differently, such as a character reference. The reading applies to check 3 and check 4 alike, and
`composed_quotes.py` implements it ([composed_quotes.txt](composed_quotes.txt)). F's markdown reading (emphasis
delimiters `*`, `_`, `~`, backslash escapes and character references) and its nested reading are not copied, so a
published quotation that contains markdown emphasis, such as `"**Net income**"`, or an escaped mark (`\"Revenue\"`,
read with its backslash) is still read as composed and is reported with its span, a character reference is read as
written, and a nested quotation is read in order. None of the 402 published answers in the 23 retained runs contains
`*`, `_`, `~`, a backslash or a character reference, holds an odd number of marks or nests a quotation, and each of
the 15 spans the audit checks there is one of its row's pairs and matches a span of F's own reading. None of the 432
rows of the 24 retained runs (published answers and withheld candidates, run 37072989252 included) holds a backslash,
a character reference, a `＂`, `„` or `‟` mark or an odd number of marks. The probe
([composed_quotes_probe.txt](composed_quotes_probe.txt)) runs 38 synthetic answers through the product's
`unsupported_prose_quotations`, the round-2 reading and this one. The three round-3 pairing answers and the four
round-4 pairing answers that F publishes (a line-break quotation, an empty quotation first, a `＂` mix and a `„…”`
mix) are failed by the round-2 reading and read with 0 composed spans here. No answer F publishes is read as
composed, apart from three disclosed cases: markdown emphasis, a backslash-escaped mark and a one-sided character
reference. Codex acknowledges the reading on #1029 before step 1, or directs the strict reading instead, with the
exposure above accepted.

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

Legitimate shapes the wording keeps: contiguous MD&A sentences carrying figures (BABA's sentence beginning
"further increased by 3% to RMB1,023,670 million", ASML's beginning "Net income for 2025 amounted to €9,609.4
million"), quoted labels with figures outside the quotes, the unquoted cross-check, and an unquoted not-disclosed
reason. The wording is stricter than F in two places, both disclosed in the pre-registration: table figures inside
quotation marks, and an edge ellipsis (`"by 3% to RMB1,023,670 million …"`, an illustration that F verifies after
stripping the ellipsis). The model can truncate without the ellipsis, and F still verifies the span.

## Review record

- The design was reviewed adversarially before implementation by three lenses: decision fidelity, model behaviour,
  and repository rules and gates. Each returned NEEDS CHANGES; design v2 resolves their findings. All four documents
  are preserved in [design-history/](design-history/design-v2.md).
- The exact-head independent review of the commit containing this folder, the full gate tails and the head SHA are
  recorded in the step-0 comment on #1029, not here, so that recording them does not move the head. The gate tails
  there come from a gate run on the frozen head itself (precondition 6). The gate runs named in the rounds below
  were on earlier heads and do not satisfy precondition 6.

### Review round 1 (exact-head review of `cd8199f1`)

Three lenses reviewed `cd8199f1` (code commit `81f85248` on `efdc33f4`) and returned one blocker, four should-fix
findings and twelve nits. The findings are kept verbatim in
[design-history/exact-head-review-r1.md](design-history/exact-head-review-r1.md). Resolution:

| Finding | Resolution |
| --- | --- |
| R1-3 (blocker): main moved past the head with a backend change (#1066 runtime pins), so the gated tree differed from the measured tree | Merged main `11681b9c` (merge `5e5e80a5`), then main `b40fa703` after #1067 landed during the fix round (merge `3264cdcc`). Gates use main's pins: `openai` 3.20.0, `PyJWT` 2.15.1 and `sentry-sdk` 2.71.0 come from an overlay on the gate venv, and venv plus overlay match all 99 pins of `requirements.txt` and the dev pins. Re-ran the full gate, the five RUNBOOK files with the owner test, and the tests that read `tasks/`, all on the integrated head with HEAD-stamped logs. Regenerated `prompt_identity.txt` and `scope_hashes.txt` against `b40fa703`; the scope proof now covers the requirements files. Base lines updated. Precondition 1 is now a general deploy-receipt rule (#1066, #1067 and any later backend merge). New precondition 2 stops the lane if main's backend moves before step 1. Runtime versions are reported as context. The integrated head needs a fresh exact-head review (precondition 6). |
| R1-1, R1-2, R1-5: the strict audit leg of checks 3 and 4 fails F-verified quotations (B2 ASML d1 MD&A sentence; C1 AAPL d0 `"Gross margin,"`), and the gap was understated | The pre-registration now lists every normalization gap and both retained cases, and quantifies the strict-reading exposure. It registers one reading: a span is composed when the audit flags it and F's per-span test also fails (`composed_quotes.py`). The reading applies to check 3 and check 4. Over the 23 retained runs it keeps the 3 genuine pre-F compositions and clears the 2 F-verified spans. Codex acknowledges it on #1029 before step 1 (precondition 5), or directs the one predeclared alternative, the strict reading, with its exposure accepted. Codex's choice cannot be obtained before freeze, so both readings are fixed in the frozen file and Codex's choice is recorded on #1029 before step 1 (reworded in round 2, R2-N6). Neither reading is chosen after data. |
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

### Review round 2 (exact-head review of `61cce875`)

Three lenses reviewed `61cce875` (the round-1 fix commit on merge `3264cdcc`, base `b40fa703`) and returned one
should-fix finding and seven nits. The findings are kept verbatim in
[design-history/exact-head-review-r2.md](design-history/exact-head-review-r2.md). Round 2 changes only files in this
folder; `backend/` and `.github` are byte-identical to `3264cdcc`. Resolution:

| Finding | Resolution |
| --- | --- |
| R2-1 (should-fix): the pre-registration attributed the edge-ellipsis quotation `"by 3% to RMB1,023,670 million …"` to run 36800236360 d1, whose published quotation has no ellipsis (the `…` was an abbreviation in the research notes) | The run attribution is removed and the example is marked illustrative. Checked over the 23 retained runs: none of the 51 quoted spans the inventory finds (every form, published and withheld) starts or ends with an ellipsis, and the pre-registration now says so. The same abbreviation habit is removed where a quoted retained span was cut with `…`: the B2 MD&A sentence in the pre-registration (now quoted up to "representing", full span in `composed_quotes.txt`) and the README's list of kept shapes. The pre-registration's sha256 changes; the step-0 comment carries the new value. |
| R2-N1, R2-N7: the registered reading omitted F's floor, so a sub-floor label padded by a marker or edge punctuation (`"EBITDA [1]"`) could be classed composed | `composed_quotes.verdict` applies F's floor first: a needle under 8 normalized characters, after marker blanking and edge stripping, with no interior ellipsis, is a **sub-floor label**, reported and not composed. An offline probe (not committed) compared the verdict with the product's `unsupported_prose_quotations` on 14 spans (labels with markers and edge punctuation, interior and edge ellipses, table-cell compositions, the B2 sentence, bare numbers on each side of the floor): 0 disagreements. Over the 23 retained runs, `composed_quotes.txt` is unchanged apart from the new count, which is 0 in every run. The pre-registration's "Why the raw audit…", "Registered measurement" and "Decision owner" paragraphs and this README name the floor. |
| R2-N2: main moved again (#1064, #1071, and since then #1045) | No action on the tree: `git diff --name-only b40fa703 origin/main -- backend .github` is empty at `origin/main` `7337eba6`. Precondition 2 now records the `origin/main` SHA checked with its result. The "gated tree" sentences in both files now say `backend/` and `.github`. |
| R2-N3: F's markdown reading and quote pairing are not copied, so a quotation holding markdown emphasis reads as composed | Stated, with the measurement unchanged, in the pre-registration ("Why the raw audit…", "Registered measurement", handback), this README (measurement paragraph, limitations) and `composed_quotes.py`'s docstring. Such a span is still read as composed and is reported with its span. Exposure on the retained runs: 0 of 402 published answers contain `*`, `_` or `~`, and each of the 15 spans the audit checks matches a span of F's own reading. |
| R2-N4: validity had no anchor to the frozen head | The identity-table row (now "Backend tree of each run") and Validity require `git diff --quiet <head> <source_sha> -- backend .github` for each of `eval-baseline`, Q1, Q2 and Q3. This replaces the consecutive-pair chain, which it implies. The step-2 `^1` check stays as a pre-trigger guard against spending on a run that would be invalid. |
| R2-N5: precondition 1's list omitted #1041 | The list now reads "included" and adds #1041 (`5525a91d`, covered by #1060's 00436-pkk). It also names #1065's revision (00437-xsf) and the #1066 and #1067 receipts read on #1029: 00438-v8g (comment 5962491931) and 00439-llg (comment 5962762092). Precondition 4 notes that comment 5962762092 records the #1066/#1067 slot as free. |
| R2-N6: "This lane cannot post on #1029" contradicted step 0 | Reworded in the round-1 table as proposed. |

The owner test with the five RUNBOOK files, M0–M4, `prompt_identity.py`, `scope_hashes.py`, the tasks-reading tests
and the full backend gate are re-run on the round-2 commit with HEAD-stamped logs.

### Review round 3 (exact-head review of `198d0e78`)

Three lenses reviewed `198d0e78` (the round-2 fix commit on merge `3264cdcc`, base `b40fa703`). Scope and
correctness and rules/gates/custody returned APPROVE; model behaviour returned CHANGES NEEDED. Together they raised
one should-fix finding and ten nits, kept verbatim with what each lens ran in
[design-history/exact-head-review-r3.md](design-history/exact-head-review-r3.md). Round 3 changes only files in this
folder; `backend/` and `.github` are byte-identical to `198d0e78`. Resolution:

| Finding | Resolution |
| --- | --- |
| R3-1 (should-fix): the reading re-tested the audit's spans as the audit pairs them. A sub-floor quoted label followed by another quotation (BABA's `"Revenue"`, quoted in 13 of 69 retained BABA-viewed draws) makes the text between the two quotations a span that the reading classed composed, though F publishes the answer | `composed_quotes.py` now pairs each flagged row's quotations in order (the audit's FOLD, then `"([^"\n]+)"`, no floor) and applies `verdict` to every pair, flagged or not. An audit span that is not a pair is a new reported class, **audit pairing difference**, not composed. One safeguard goes beyond the proposed fix. When the in-order pairing leaves a mark unpaired (a quotation across a line break, an empty quotation, or a `„`, `‟` or `＂` mark, which the audit's FOLD leaves alone), the pairs are out of phase. Without the safeguard such a row could fail on the text between two quotations, or hide a real quotation as a pairing difference (probe cases 5 and 6). So that row keeps the round-2 reading of the audit's own spans and is reported. F's nested reading is now also named as not copied. Over the same 23 runs, `composed_quotes.txt` is unchanged apart from the new counts (audit pairing difference, unflagged pairs, rows with unpaired marks), all 0; the span lines and the exit status (1, from the three pre-F runs) are unchanged. The probe is now committed: `composed_quotes_probe.py`, with [composed_quotes_probe.txt](composed_quotes_probe.txt). It runs 30 synthetic answers through the product's `unsupported_prose_quotations`: the reviewer's three answers, three more pairing cases, 22 single-quotation cases covering the round-2 and round-3 spans (floor, interior and edge ellipses, normalization, verified quotations, table-cell compositions), and the two disclosed shapes. Outcome: 28 agree, 1 F-withheld leg (the disclosed nested case, which the audit does not flag) and 1 false failure (the disclosed markdown case). The round-2 reading failed the reviewer's three answers. The pre-registration ("Why the raw audit…", "Registered measurement", "Decision owner", handback limitations) and this README (measurement paragraph, Limitations) name the class and the shape. |
| R3-N1: the step-2 guard never applied the head-anchored check to `eval-baseline` before Q1, so "only avoids spending" overstated it | Before any ready transition, step 2 now runs three checks: the PR is mergeable, the Validity backend-tree check passes on the previous run's `source_sha`, and the `^1` comparison with `origin/main` passes. Step 3 applies the same three. The Validity paragraph now says what the checks catch, and that a backend merge after a ready transition is caught only after the run. |
| R3-N2, R3-N9: the `run_validity.py` docstring described the replaced consecutive-pair rule | It now reads "for the head-anchored `git diff --quiet <frozen head> <source_sha> -- backend .github` validity rule". Only the docstring changed; outputs are unchanged. |
| R3-N3: the 20-F label relied on `g_decide.py` for the 2-of-3 rule | The label now states the rule: a question-run is tool-using when at least 2 of its 3 draws have non-empty `tool_trace.tool_results`, as `g_decide.py` counts. |
| R3-N4: precondition 4 tied the acknowledgement to the #1050 successors, which are merged | The claim must now name every open PR that touches `backend/` or `.github` at step 1. It must be acknowledged by the merge-queue owner, or by the owner of each PR. At this commit there are three such PRs: #1069 (draft security hardening), #1070 (Dependabot: `requirements.txt` and `requirements.in`) and #1035 (draft: `backend/evals`, `backend/scripts` and one test). The reviewer did not name #1035. |
| R3-N5: no stated outcome for a failed mergeable or diff-quiet check | A failed check means no ready transition. The lane is a validity stop, reported; the outcome is Incomplete unless a check has already failed. |
| R3-N6: merge refs are transient | Custody: after each run, `git fetch origin <source_sha>` fetches the merge ref by SHA, and its `^1` and `^2` go in the custody comment. The compare API is the fallback. Fetching by SHA worked for the post-#1066 control ([run_validity_post1066.txt](run_validity_post1066.txt)). |
| R3-N7: the spend rule did not say how unknown calls count | A new Spend bullet charges each call without usage at the off-peak no-cache worst case of one call, doubled for a peak call. A Copilot call is USD 0.0071: the largest logged prompt, 37,115 tokens, plus the pinned 2,400-token completion cap. An `eval-baseline` call is USD 0.0179: the largest one-call prompt, 71,040 tokens, plus a 12,000-token completion. The DeepSeek balance delta replaces the charge only when the delta lies between the known cost and the known cost plus the charges. |
| R3-N8: the PR body lacked the mutation tails, and the override line was not tied to the window | Step 1: the draft's body carries the Review section, the M0–M4 tails from `mutations.txt`, and a `Review override:` line. Its reason is limited to the measurement window: no merge under this disposition, and the line is removed before any merge decision. |
| R3-N10: no validity control on the post-#1066 runtime | Ran `run_validity.py --control-prompt a88b6fb1…:5057` on #1067's `copilot-eval` run 37072989252. Its merge ref `bc0a96c3` is main `3084c024` (after #1066) plus #1067's head `b7bd5d19`, and its backend tree equals `b40fa703`'s. Result: VALID, 18 rows, `openai` 3.20.0. Without the control, only the 18 system-prompt rows mismatch. Contexts, tool schema, options and report fields match the pinned values, which are unchanged. The result is recorded in [run_validity_post1066.txt](run_validity_post1066.txt) and cited in precondition 2. |

The owner test, M0–M4, `prompt_identity.py`, `scope_hashes.py`, the composed-quote, inventory and cross-check
outputs and the tasks-reading tests are re-run on the round-3 commit with HEAD-stamped logs. `git diff --quiet
198d0e78 HEAD -- backend .github` exits 0. The full backend gate was not re-run in round 3; precondition 6 needs it
on the frozen head itself.

### Review round 4 (exact-head review of `f848de27`)

Two lenses, model behaviour and rules/gates/custody, reviewed `f848de27` (the round-3 fix commit on merge `3264cdcc`,
base `b40fa703`). Both returned APPROVE with nits only: three from model behaviour and six from rules/gates/custody,
kept verbatim with what each lens ran in
[design-history/exact-head-review-r4.md](design-history/exact-head-review-r4.md). Round 4 changes only files in this
folder; `backend/` and `.github` are byte-identical to `f848de27`. Resolution:

| Finding | Resolution |
| --- | --- |
| R4-N1: the unpaired-marks fallback brought back the round-2 false failure for the pairing shape when the later quotation crosses a line break or an empty `""` comes first | Took the proposed fix: `PAIR` is now `"([^"]*)"`. Pairs cross line breaks, as F's do, and an empty pair is allowed and reads as a sub-floor label. The fallback is now reached only when the row's count of marks is odd. The pre-registration ("Registered measurement", handback), this README (measurement paragraph, Limitations) and the `composed_quotes.py` docstring say so and state the residual: such a row is read as the audit pairs it, so the pairing shape can still fail there. F pairs every mark it reads, so for an answer F publishes an odd count needs a mark that the text and the display count differently, such as a character reference. Over the same 23 runs `composed_quotes.txt` is byte-identical, exit 1 (the three pre-F runs); run 37072989252 exits 0 with all counts 0. Probe cases 31 and 32 (the reviewer's line-break and empty-quotation answers) are published by F, failed by the round-2 reading and read with 0 composed spans. Round-3 cases 5 and 6 now pair in order and still agree with F. |
| R4-N2: a `＂` pair between straight marks kept the count even, so its out-of-phase pairing went undetected | Took the proposed fix. For the pairing only, `＂`, `„` and `‟` are folded to `"` (`PAIRING_FOLD`, one character for one, so positions still match the audit's located spans); the audit's FOLD and the located-span assertion are unchanged. The two folds make all six of F's marks straight. Probe case 33 (the reviewer's `＂` mix) and case 34 (a `„…”` quotation after the label) are published by F, failed by the round-2 reading and read with 0 composed spans. Case 35 (a `„…‟` quotation) is withheld by F as ambiguous (`‟` opens in F) and the audit flags nothing, so a run fails it through the F-withheld leg. |
| R4-N3: backslash escapes and character references are part of F's markdown reading and were not named as not copied | Named beside the emphasis delimiters in the pre-registration ("Why the raw audit…", "Registered measurement", handback), this README (measurement paragraph, Limitations) and the `composed_quotes.py` docstring. Measured: none of the 402 published answers in the 23 runs holds a backslash or a character reference (`&name;` or `&#…;`; none holds `&` at all), and none of the 432 rows of the 24 runs does (420 published answers and 12 withheld candidates, run 37072989252 included). Probe case 38 (the reviewer's `\"Revenue\"`) is published by F and read as composed: a disclosed false failure. Case 37 (a one-sided `&quot;`) is the odd-count residual of R4-N1, also a disclosed false failure. Case 36 (an unclosed quotation: an odd count, which F withholds as unbalanced) shows the fallback: the reading finds a composed span and agrees with F. |
| R4-N4: "Each provider call without usage is budget risk" read as an automatic stop, and a balance delta above the known cost plus the charges had no stated outcome | Spend now charges each such call to "spent so far" at the stated bound, and the call stops the lane only when the charged total fails the spend rule. A balance delta above the known cost plus the charges: if the run has unknown-cost calls, the charge may understate this lane's spend, which is budget risk and stops the lane (reported); if it has none, its known cost is exact and the excess is reported as other owners' concurrent spend, without stopping. "Budget risk stops the lane" now names both cases. |
| R4-N5: the `eval-baseline` telemetry is nested under the candidate name | `summary.baseline.incurred_provider_usage` (`.unknown_calls`) in step 2, Accounting and the unknown-cost bullet, as in the 9 retained reports (631 calls, 0 unknown). The README has no instance. |
| R4-N6: a failed mergeable check stops the lane, and `mergeable_state` reads `draft` on a draft PR | Steps 2 and 3: the REST pull-request `mergeable` field is true (re-read while it is null); `mergeable_state` is not the check (it reads `draft`, `blocked` or `unstable` on a draft PR or with failing non-required checks). |
| R4-N7: precondition 4 needs a named acknowledger for each of #1035, #1069 and #1070 | No file edit: handled in the step-0/precondition-4 comment on #1029. |
| R4-N8: `run_validity_post1066.txt` recorded only a 16-hex zip prefix | The file now records the full digest from the Actions artifacts API (read only): `sha256:fe4b718ef8be6907068cdb2ddc83727e1550eecc3b4131030855a3d0775b5f0c` for artifact `copilot-fidelity-37072989252` (78,712,108 bytes), which matches the prefix. Custody and steps 2 and 3 record the API `digest` beside the locally computed zip sha256 for `eval-baseline` and each of Q1–Q3. |
| R4-N9: precondition 6 requires the gate on the exact frozen head, and the round-3 record reused the round-2 gate | Precondition 6 now says a gate run on an earlier head does not satisfy it, even with identical `backend/` and `.github`, and step 0 posts the tails of the gate run on the frozen head. This README no longer says the round-2 gate "still applies" or that earlier rounds' tails go in the step-0 comment. |

`composed_quotes.py` (the 23 runs and run 37072989252), the probe (38 cases: 33 agree, 2 F-withheld legs, 3 disclosed
false failures, exit 0), `prompt_identity.py`, `scope_hashes.py` (regenerated, see Files) and the tasks-reading tests
are re-run on the round-4 commit. `git diff --quiet f848de27 HEAD -- backend .github` exits 0. The full backend gate
is not re-run here; precondition 6 needs it on the frozen head itself.

## Limitations

- **Small denominators.** Failures concentrate on about six tool-using ASML and BABA-viewed draws per run. The
  exposure denominators are reported per run; a check that passes on tool-less draws did not exercise the shape.
- **Not-disclosed is unmeasured live.** The golden set has no live not-disclosed question.
- **Double quotes only.** Decision F and `prose_quote_audit.py` check double quotes only. Other quote forms are
  visible only through `quote_inventory.py`, whose classes are a declared heuristic, not F's parser.
- **Composed-quotation reading.** Checks 3 and 4 read the audit through F's per-span test (copied, not imported). An
  F defect that the copy shares would not be caught by the audit leg. The F-withheld, error and 18/18 legs still
  catch every composed quotation F withholds. Quotations are paired in order, not by F's parser: across line breaks,
  empty pairs included, with `＂`, `„` and `‟` read as straight marks. A sub-floor quoted label such as BABA's
  `"Revenue"` followed by another quotation makes the audit flag the text between them; that span is an audit pairing
  difference, reported and not composed. A row with an odd mark count falls back to the audit's own spans and is
  reported, so the pairing shape can still fail there; for an answer F publishes this needs a mark that the text and
  the display count differently, such as a character reference. F's markdown reading (emphasis delimiters, backslash
  escapes and character references) and its nested reading are not copied: a published quotation holding markdown
  emphasis or an escaped mark reads as composed (stricter than F), a character reference is read as written, and a
  nested quotation is read as two pairs with a gap between them. None of these shapes is in the retained runs.
- **Argued coverage.** Offline coverage of the failure shapes is argued, not replayed.
