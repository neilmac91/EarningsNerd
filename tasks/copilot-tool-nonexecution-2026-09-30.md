# Copilot tool nonexecution and prose-quote custody — diagnosis (2026-09-30)

Diagnostic successor to #1023, which closes unmerged at head
`d58c1a59774793336168e8d3c18e976d267a00c7`. This document changes no prompt, model, service,
runner, scorer, repair grammar, coverage policy or flag, and no paid call was made to produce it.
Code references are to main `c13b069a`; the Copilot request and publication path is unchanged since
`0dcc4ee3` (`git diff 0dcc4ee3 c13b069a` over `copilot_service.py`, `ai/copilot_chat.py`,
`copilot_tools.py`, `provenance_service.py`, `citation_markers.py`, `evals/copilot_runner.py`,
`evals/copilot_scorers.py`, the golden set, `copilot-eval.yml` and `.github/ai-model.env` is empty).

## Evidence base and method

Ten retained `copilot-fidelity` artifacts were audited offline with a scratch tool that imports the
repo's own `provenance_service.normalize_for_match`, `_QUOTED_RE` (quotes of 8+ characters) and
`copilot_service.count_uncited_figures`. Per row it reports tool calls (`tool_trace.tool_results`,
cross-checked with the wrapper's activity controls), physical provider calls (the sequential
`ai_call` lines in `runner.log`, attributed to rows by round constraints and prompt-token growth),
`[F#]` markers in the private candidate versus markers a tool issued, final citation origin (tool,
`server_citation_lookup`, or model text excerpt), uncited figures, and every quotation in the final
answer checked against the row's normalized filing source.

| Run | UTC | System prompt | Formal | Rows with tools | Physical calls | `copilot-eval.json` sha256 (prefix) |
|---|---|---|---|---|---|---|
| [36500418287](https://github.com/neilmac91/EarningsNerd/actions/runs/36500418287) | 09-28 23:56 | pre-#1022 `93dc6565` | 17/18, 1 error | 16/18 | not retained | `93741077db33` |
| [36511300921](https://github.com/neilmac91/EarningsNerd/actions/runs/36511300921) | 09-29 02:11 | pre-#1022 `93dc6565` | 18/18 | 17/18 | not retained | `8ea5006e6dc7` |
| [36516634768](https://github.com/neilmac91/EarningsNerd/actions/runs/36516634768) | 09-29 03:21 | pre-#1022 `93dc6565` | 17/18 (ASML d0) | 17/18 | 35 | `e39c43bd2f62` |
| [36519321075](https://github.com/neilmac91/EarningsNerd/actions/runs/36519321075) | 09-29 03:57 | pre-#1022 `93dc6565` | 18/18 | 16/18 | 34 | `6a1cc858a71b` |
| [36624149908](https://github.com/neilmac91/EarningsNerd/actions/runs/36624149908) | 09-29 20:09 | pre-#1022 `93dc6565` | 17/18, 1 error | 18/18 | 36 | `dd051e3b16a2` |
| [36630506944](https://github.com/neilmac91/EarningsNerd/actions/runs/36630506944) | 09-29 21:03 | pre-#1022 `93dc6565` | 17/18, 1 error | 18/18 | 36 | `bf1d3b3462e6` |
| [36640254449](https://github.com/neilmac91/EarningsNerd/actions/runs/36640254449) | 09-29 22:34 | main `a88b6fb1` | 18/18 | 10/18 | 28 | `a94ef795bb38` |
| [36647075136](https://github.com/neilmac91/EarningsNerd/actions/runs/36647075136) | 09-29 23:49 | #1023 `b52ea094` | 18/18 | 0/18 | 18 | `2ca0a6e9e489` |
| [36754723895](https://github.com/neilmac91/EarningsNerd/actions/runs/36754723895) | 09-30 17:55 | main `a88b6fb1` | 18/18 | 11/18 | 29 | `7ea313523cbb` |
| [36777581481](https://github.com/neilmac91/EarningsNerd/actions/runs/36777581481) | 09-30 21:11 | main `a88b6fb1` | 18/18 | 12/18 | 30 | `8b3084e7afb2` |

Across all ten runs the tool schema (`b6958973`), generation options (`deepseek-flash`, 2400 tokens,
temperature 0.2) and the per-question context message are byte-identical; all 246 logged calls
carry provider fingerprint `aeb56401ca74e127821c4f9126dcb669`. The system prompt is the only request
input that varies. Pre-#1022 runs also ran older post-processing code, so their citation outcomes
are not comparable with main's; their tool decisions are, because those depend only on the request.
Row attribution of physical calls is unique in all eight logged runs, no row used more than one tool
round, and calls = rows without tools + 2 × rows with tools in every run. 36777581481 is the #1030
ready run: #1030 changed only `backend/requirements.*`, so its Copilot path is main's.

## What is known

**#1023's ready run 36647075136.** Formal verdict 18/18 PASS, accepted, estimated USD 0.029114. No
row made a tool call: 18 physical calls, one per row. All 30 `[F#]` markers in the candidates were
unissued and stripped. The 5 final citations all came from server repair (BABA native-2026 d0–d2 and
viewed-2025 d1–d2); 13/18 answers shipped with no citation and 25/30 figures were uncited. Nine of
the 13 uncited rows (AAPL gross profit, TSLA operating income, MSFT diluted EPS) could not be
repaired in any phrasing that answers the question, because the repair vocabulary covers only
revenue and the explicit paired revenue/net-income shape (`copilot_service.py:705-733`,
`:803-809`). Phrasing explains only the other four (ASML ×3, BABA viewed-2025 d0 with no fiscal
year-end date).

**Dose-response by prompt.** Draws with at least one tool call; the question is the effective unit,
because draws at temperature 0.2 are near-identical.

| Question | pre-#1022 (6 runs) | main (3 runs) | #1023 (1 run) |
|---|---|---|---|
| AAPL sales-gross-profit-2025 | 18/18 | 9/9 | 0/3 |
| TSLA sales-operating-income-2024 | 18/18 | 9/9 | 0/3 |
| MSFT sales-diluted-eps-2025 | 18/18 | 9/9 | 0/3 |
| BABA native-revenue-2026 | 13/18 | 0/9 | 0/3 |
| BABA viewed-native-revenue-2025 | 18/18 | 4/9 | 0/3 |
| ASML us-gaap-sales-net-income-2025 | 17/18 | 2/9 | 0/3 |
| **Total** | **102/108** | **33/54** | **0/18** |

At question-run level (tool use in at least two of three draws), the 10-K questions were
tool-using in 18/18 pre-#1022 and 9/9 main question-runs, against 0/3 under #1023 (one-sided Fisher
p = 0.05 with the question as the unit). For the 20-F questions, 17/18 pre-#1022 question-runs were
tool-using against 1/9 on main. #1023's run is bracketed by main-prompt runs about 75 minutes
before and about 18 and 21 hours after, each with the 10-K questions at 9/9. The pre-#1022 and main
runs are not interleaved in time.

**Main's BABA/ASML nonexecution is masked, but not completely.** On main's prompt, 21 of 27 BABA/ASML
draws called no tool and wrote 28 unissued markers. Twenty of those 21 answers used exactly the
shape the server repair certifies, for example `Consolidated revenue for the year ended March 31,
2026 was RMB1,023,670 million [F1].`: the unissued marker is stripped and the second repair pass
(`copilot_service.py:1341-1350`) attaches a `server_citation_lookup` fact. The 21st did not.
36777581481 ASML d1 answered `For the year ended December 31, 2025, ASML reported total net sales of
€32,667.3 million and net income of €9,609.4 million.` with two unissued markers; both were
stripped, repair abstained by design, and the answer shipped with 0 citations and 2/2 figures
uncited. It was scored PASS, and the run was accepted 18/18.

**Composed prose quotations pass on main-equivalent code.** The verifier checks declared citation
excerpts (`_verify_citations`, `copilot_service.py:441-469`); nothing checks text the answer puts in
quotation marks, and the scorer does not either. The audit found no quotation that is wholly absent
from the filing, but many that are composed from separate spans:

| Prompt | Rows with a composed quotation | All passed | Examples |
|---|---|---|---|
| pre-#1022 | 17/108 (ASML 12, BABA viewed-2025 5) | yes | `"Total net sales 32,667.3"`, `"Total net sales 28,262.9 ... 32,667.3"`, `"Revenue ... 996,347"` |
| main | 2/54 | yes | 36640254449 ASML d2, 36777581481 BABA viewed-2025 d0 |
| #1023 | 0/18 | — | no quotations |

Both main rows called tools, stated the figures with verified fact chips, then appended a
narrative cross-check. 36640254449 ASML d2: `The filing's own operating results table confirms
these figures, showing "Total net sales 32,667.3" and "Net income 9,609.4" for 2025 [3].`
36777581481 BABA d0: `This is confirmed by the consolidated income statements, which report
"Revenue ... 996,347" for the year ended March 31, 2025 [2].` In both, the declared citation excerpt
is a contiguous, verified table row (`Total net sales 28,262.9 100.0 32,667.3 100.0 15.6`;
`Revenue 5, 24 868,687 941,168 996,347 137,300`), but the text shown in quotation marks is not a
span of the filing. The prompt forbids stitching and ellipses inside citation excerpts
(`copilot_service.py:118`); it says nothing about quotation marks in prose.

**The #1021 ASML defect is still open on main.** In #1021's run 36516634768, ASML d0 stated the
tool figures correctly and then added a redundant cross-check whose citation excerpt stitched two
KPI tiles (`Total net sales €32.7bn ... Net income €9.6bn`); it failed verification and vetoed the
row. On main the same candidate would be withheld as an error row, which still fails readiness.
Main's prompt says not to add a text citation merely to restate a tool figure
(`copilot_service.py:120`), yet 5 of the 33 main-prompt tool rows still did so (all five excerpts
verified). Main's ASML tool skipping (7 of 9 ASML draws) currently lowers exposure to this path; it
does not remove it.

## What is refuted

- **"#1023's worked example moved phrasing outside the repair grammar, so 13/18 shipped uncited."**
  The shape copying is real, but it explains 4 of the 13 rows. The other 9 are uncited because no
  tool ran and no repair exists for those concepts.
- **The proposed lesson "a worked example in a tool-using prompt must show the tool step."** Main's
  prompt already carries a tool-step-free example (`copilot_service.py:88-89`) under which the 10-K
  questions call tools in 27/27 draws. #1023 also relaxed the lead verbatim-excerpt rule, and the
  evidence does not separate the two edits. No lesson is recorded.
- **"Time drift or request-path faults cannot explain #1023."** Downgraded to *unlikely*: the
  request bytes match apart from the prompt and the bracketing main runs call tools, but the
  evidence is one #1023 run with effectively three 10-K questions.
- **"Every no-tool answer on main ends up cited because it uses the repair shape."** True in two
  of three main-prompt runs; false in 36777581481 (ASML d1 above).
- **"Tools or `tool_choice` may not reach the provider."** The wrapper sets `tools` and
  `tool_choice="auto"` on every round (`ai/copilot_chat.py:237-250`), and the same unchanged wrapper
  produced tool calls on other rows of every run. Live runs do not record native request bodies or
  `finish_reason` (`evals/copilot_runner.py:185`), so this rests on code reading plus call counting;
  offline, this PR now asserts it (see below).
- **"A same-window A/B fits under USD 0.25."** No dispatch path exists (below); the realistic cost
  is USD 0.4–0.8.

## Unresolved hypotheses, ranked

1. **Prompt clause.** Text that describes the finished answer shape — step 3's "output []… including
   when all cited figures use tool markers" (`copilot_service.py:111-112`) on main, plus #1023's
   worked example and relaxed lead rule — makes skipping tools look compliant, because every
   requested figure is already in the preloaded excerpt and XBRL block. For: the only request
   difference in every comparison; monotone dose-response (102/108 → 33/54 → 0/18); #1023 is
   bracketed in time. Against: not interleaved for pre-#1022 vs main; the 10-K questions are
   unaffected on main.
2. **Question wording.** Only the 20-F questions degrade on main, and they share wording the 10-K
   questions lack ("native reporting currency", "in RMB", "In this Form 20-F's US GAAP … in euros").
   BABA native-2026 fell from 13/18 to 0/9. Wording cannot be separated from a prompt × wording
   interaction without a non-golden question variant.
3. **Model tool-selection variance.** Nonexecution predates both prompts: RUNBOOK.md:699-700 records
   MSFT and historical BABA answers without tools at #703 (2026-09-05). This sets a base rate, not a
   cause of the old→main shift.
4. **Time drift.** One fingerprint on all 246 logged calls and bracketing make this least likely for
   #1023. It is not excluded for the 20-F shift, because every pre-#1022 run precedes every main run.

## Latent production risks

- **Uncited figures when tools are skipped.** Coverage is advisory, and repair certifies only annual
  revenue and the explicit revenue/net-income pair, each in one exact sentence shape. A skipped tool
  call on gross profit, operating income, EPS or any other concept always ships the figure uncited;
  revenue and net income ship uncited whenever the sentence differs from the shape. The documented
  production alert (RUNBOOK) fires only above 5 uncited figures per hour. The eval accepted 13 such
  rows under #1023 (9 of them on non-revenue questions) and one on main (ASML, an uncertified shape).
- **Unverified prose quotations.** Text in quotation marks is published without verification; on
  main-equivalent code 2 of 54 rows showed composed quotations, and a reader has no way to tell.
- **Readiness does not measure tool execution.** A run with 0/18 tool calls was accepted 18/18. The
  scorer has no tool-use, unissued-marker or prose-quote measure.

These are eval-cohort observations; production frequency was not measured here.

## Validated offline versus measured live

All six offline owners pass on this branch (counts in the PR). Live runs exercise only six numeric
questions; qualitative and refusal questions remain in `pending_cases`.

| Path | Offline owners (exact tests) | Live evidence |
|---|---|---|
| Tool path: tools offered every round, call assembly, execution, `cite` issuance, native SDK wire | `test_copilot.py::test_stream_chat_with_tools_assembles_tool_call_deltas` (now asserts `tools` and `tool_choice="auto"` on both `create()` rounds), `::test_stream_chat_with_tools_suppresses_tool_round_narration`, `::test_service_emits_activity_events`, `::test_service_surfaces_xbrl_fact_as_verified_citation`, `::test_service_resolves_back_to_back_fact_markers`; `test_copilot_provenance.py::test_native_sdk_tool_wire_carries_viewed_scope_and_currency`, `::test_real_closure_rejects_bad_provenance_before_marker`; `test_copilot_gate.py::test_trace_retains_uncited_and_rejected_tools_and_restores_provider`; `test_copilot_cost.py::test_completion_telemetry_preserves_physical_call_accounting` | Exercised (10-K 27/27 on main). Native request, `finish_reason` and tool execution are not scored. |
| Unissued `[F#]` markers | `test_copilot.py::test_service_strips_fabricated_fact_markers`, `::test_service_strips_fabricated_marker_between_words`, `::test_service_keeps_plain_unmatched_markers_literal` | Observed: 9–10 per main run, 30 under #1023. |
| Mixed text + tool citations | `test_copilot.py::test_service_unifies_text_and_fact_citation_numbering`, `::test_service_publication_boundary[mixed_fact_valid]`, `::test_service_publication_boundary[mixed_fact_invalid]`; `test_copilot_paired_claims.py::test_existing_verified_text_citation_survives_without_repair`, `::test_surviving_fact_citation_is_not_reinterpreted` | Incidental only (5 main rows); no mixed question in the cohort. |
| Fallback: no tool → text excerpt, server repair or uncited | `test_copilot_citation_repair.py::test_uncited_answer_gains_a_citation_when_the_fact_proves_the_year`, `::test_unsupported_claim_shapes_abstain`, `::test_uncertified_evidence_abstains`, `::test_non_annual_or_mismatched_filing_abstains`, `::test_declared_but_unplaced_text_citation_still_gets_the_certified_chip`; `test_copilot_paired_claims.py::test_retained_pair_has_two_distinct_grounded_chips`, `::test_final_visible_pair_repairs_after_unresolved_markers`, `::test_final_visible_pair_missing_operand_still_abstains`, `::test_unsupported_pair_never_adds_a_fact_marker`; `test_copilot.py::test_service_complete_event_carries_coverage_counters`, `::test_service_publication_boundary[empty_array]` | Incidental: repair on 20 of 21 main no-tool rows; one uncited row. No deliberate case. |
| Not disclosed | `test_copilot.py::test_service_not_disclosed_path`, `::test_service_not_disclosed_carries_followups`, `::test_service_publication_boundary[not_disclosed]` and the `nd_*` cases; `test_copilot_gate.py::test_single_terminal_not_disclosed_and_guard_count_are_retained`, `::test_actual_service_refusal_terminal_is_accepted_without_invented_counter`, `::test_refusal_provided_malformed_counter_is_rejected` | Never measured live. |
| Provider or stream failure | `test_copilot.py::test_service_stream_error_becomes_error_event`, `::test_service_stream_error_after_prose_becomes_error_event`, `::test_stream_chat_with_tools_yields_error_sentinel_on_failure`; `test_copilot_gate.py::test_attempt_trace_retains_candidate_and_closes_provider` | Not observed. |
| Quotation marks in answer prose | none | Composed quotations published (above). |

The `tools`/`tool_choice` assertion closes a real gap: with `tools` removed from every `create()`
call, or `tool_choice` set to `"none"`, all 351 tests in these six owners still passed on main.

## Pre-registered next experiment (not run; needs its own founder authorization and ceiling)

**Question.** Is main's 20-F nonexecution caused by #1022's step-3 wording, by time drift, or by
something prompt-insensitive (question wording or model selection)?

**Mechanism and honest cost.** There is no dispatch path. `copilot-eval.yml` runs a fixed command on
same-repository non-draft PRs that touch `backend/**`, and the runner uses the module's
`SYSTEM_PROMPT`. Each prompt arm is therefore a PR whose `backend/app` differs, and every push to it
also runs `eval-baseline` (about USD 0.18 off-peak, 0.35 at peak). One 18-row Copilot run cost USD
0.0055–0.0315 in the retained telemetry. Stage 1 (two arms × two runs) costs about USD 0.4–0.8.
A founder-run local invocation against the retained 36777581481 preparation bundle would cost only
the Copilot calls (about USD 0.02–0.13), but needs the founder-held key and an out-of-repo wrapper,
and gives weaker custody. Proposed ceiling: USD 1.00 for stage 1, hard stop.

**Design.** Arm A = main prompt `a88b6fb1`. Arm C = pre-#1022 step 3 (`93dc6565`, verbatim from
36630506944's `initial_messages`). Two runs per arm, interleaved A, C, A, C within six hours, on the
unchanged golden set, scorer and runner. Stage 2, only if stage 1 finds the prompt responsible and
under a separate authorization: arm B = main minus the clause "including when all cited figures use
tool markers", interleaved with A the same way.

**Decision rules (question level).** A question-run is tool-using when at least two of its three
draws call a tool. Each arm has six 20-F question-runs (three questions × two runs), counted with the
audit tool:

- **Prompt-caused:** C ≥ 5/6 and A ≤ 2/6 → proceed to stage 2 only with new authorization.
- **Not the prompt:** A ≥ 5/6 → close the prompt hypothesis; no prompt change.
- **Prompt-insensitive:** A ≤ 2/6 and C ≤ 2/6 → the next discriminator is question wording, which
  needs a non-golden variant set and its own authorization.
- **Anything else:** inconclusive; stop and record.
- Any arm below 6/6 tool-using 10-K question-runs is recorded as a regression, whatever the outcome.

**Acceptance checks for any fix candidate** (every run, both runs):

1. MSFT string-ID rejections: 0 (no withheld MSFT row; no string or `F#` identity in the citation array).
2. AAPL/TSLA/MSFT tool use: every draw (18/18 across both runs).
3. ASML: no stitched or unverified citation excerpt, no withheld ASML row, and no composed prose
   quotation; redundant cross-check citations are counted and reported.
4. Composed-quote audit clean: 0 composed or absent quotations across all rows.
5. Formal acceptance 18/18 with 0 errors, and 0 answers without any citation; uncited figures reported.

Any prompt change that follows must also satisfy `backend/evals/RUNBOOK.md` (aggregates of at least
three runs, never a single draw; its negative result on density-forcing prompts) and land as its own
PR with the normal offline gate.
