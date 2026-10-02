# Copilot prompt fix candidate (2026-10-02)

One prompt candidate, authorized by Codex's decision on #1029 (comment 5958742492, 2026-10-02 18:27Z, under the
founder's delegation; text in [design-history/codex-decision-5958742492.md](design-history/codex-decision-5958742492.md)).
It is cut from main `efdc33f42bbf95a70ceb78d0c6615d59788800df` (post-#1065). It is qualified by three fresh paid
runs under [PREREGISTRATION.md](PREREGISTRATION.md). No merge and no production prompt release follow from them.

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
| [scope_hashes.py](scope_hashes.py), [scope_hashes.txt](scope_hashes.txt) | byte identity to base (`git diff --exit-code` and sha256 at both) of the scorer, runner, bootstrap, schema, golden set, sources, baselines, regression gate, RUNBOOK, flags and model, workflows, tool path, citation floor, decision F's owner test, every locked test and the measurement tools; allowed diff; AST scope |
| [run_validity.py](run_validity.py), [run_validity.txt](run_validity.txt) | the validity checker for each qualification run (full prompt hash and length per row), with negative and control results on retained runs |
| [crosscheck_count.py](crosscheck_count.py), [crosscheck_count.txt](crosscheck_count.txt) | declared redundant cross-check method; also lists declared citation identities (check 1) |
| [quote_inventory.py](quote_inventory.py), [quote_inventory.txt](quote_inventory.txt) | every quoted span in every quote form, classified as table-figure, sub-floor, verified or other |
| [baseline_context.txt](baseline_context.txt) | input sha256, `g_decide.py`, `copilot_cost_runnerlog.py`, `prose_quote_audit.py` summaries and uncited figures on the retained runs |
| [mutations.txt](mutations.txt) | owner-test mutations M1–M3 failing, and M0 passing |
| [design-history/](design-history/design-v2.md) | design v1, design v2, the three adversarial critiques and Codex's decision, verbatim |

The scripts have no `test_` prefix or `_test` suffix, so the test-homes gate does not treat them as tests.
`scope_hashes.txt` and `prompt_identity.txt` were produced against the code commit, the parent of the evidence
commit. The evidence commit adds only files in this folder; re-running both scripts on the frozen head gives the
same results, with this folder's files added to the allowed-diff list.

## Owner test and mutations

`backend/tests/unit/test_copilot_live_regressions.py::test_contiguous_citation_instruction_reaches_actual_service_messages`
reads `messages[0]['content']` from the real `_build_messages`. It gains four assertions and no new test case:
- the clause is absent (the G stage-2 cause);
- "If there are no filing-text markers, output []" is present;
- the RULES bullet's full composed text occurs exactly once;
- `name the missing metric without quotation marks>` occurs exactly once.

There is no full-prompt hash pin in tests; the pre-registration carries the hash. `test_copilot_prose_quotations.py`
is byte-identical to base. Mutations, never committed ([mutations.txt](mutations.txt)):

| Mutation | Result |
| --- | --- |
| M1: restore the clause | fails the clause-absent assertion (`:68`) |
| M2: delete the RULES bullet | fails the rule-once assertion (`:70`) |
| M3: revert the template edit | fails the template assertion (`:74`) |

## Baseline of the declared measures on retained runs

Three retained main-prompt runs (`a88b6fb1`) and G stage 2's arm B run B1 (`16457055`). Inputs and full outputs are
in [baseline_context.txt](baseline_context.txt), [quote_inventory.txt](quote_inventory.txt) and
[crosscheck_count.txt](crosscheck_count.txt).

| Run | 20-F tool-using question-runs | Draws with tools | Quoted spans (table-figure) | Cross-checks (restating a tool figure) | Uncited figures | Cost USD (calls) |
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

**Known audit difference.** `prose_quote_audit.py` lacks the product's punctuation-spacing fold. On B2
(37029964566) it flags ASML d1's published, F-verified MD&A quotation as composed: the source reads
`million\n, \nrepresenting`. The pre-registration keeps check 4 as written and adds a report-only label for this case.

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
outside the quotes, the unquoted cross-check, edge ellipses, and an unquoted not-disclosed reason.

## Review record

- The design was reviewed adversarially before implementation by three lenses: decision fidelity, model behaviour,
  and repository rules and gates. Each returned NEEDS CHANGES; design v2 resolves their findings. All four documents
  are preserved in [design-history/](design-history/design-v2.md).
- The exact-head independent review of the commit containing this folder, the full gate tails and the head SHA are
  recorded in the step-0 comment on #1029, not here, so that recording them does not move the head.

## Limitations

- **Small denominators.** Failures concentrate on about six tool-using ASML and BABA-viewed draws per run.
- **Not-disclosed is unmeasured live.** The golden set has no live not-disclosed question.
- **Double quotes only.** Decision F and `prose_quote_audit.py` check double quotes only. Other quote forms are
  visible only through `quote_inventory.py`, whose classes are a declared heuristic, not F's parser.
- **Argued coverage.** Offline coverage of the failure shapes is argued, not replayed.
