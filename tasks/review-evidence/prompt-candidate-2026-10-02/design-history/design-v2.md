# Prompt fix candidate — settled design (v2)

Supersedes `design.md` where they differ. Sources: `design.md`, `critique0.md` (decision fidelity), `critique1.md` (model behaviour), `critique2.md` (repo rules and gates), Codex decision #1029 comment 5958742492 (`fidelity/codex.md`).

## 1. Prompt diff (exactly two insertions plus the arm B deletion; `backend/app/services/copilot_service.py` only)

(a) **Arm B deletion**, verbatim, at `:122`: remove `, including when all cited figures use tool markers` (51 chars). `"If there are no filing-text markers, output []"` stays.

(b) **RULES bullet**, appended at the end of RULES, after the `[F#]` bullet (`:106-111`, ends "— never an [F#] marker.") and before `OUTPUT FORMAT` (`:113`). ASCII, no braces, `\` line continuations as in the surrounding source:

```
- Each quotation in your answer prose must be one contiguous span copied verbatim from the filing. \
Keep table figures outside quotation marks, never quote a table row with cells left out, and never \
put an ellipsis inside a quotation.
```

(c) **Not-disclosed template** (`:143`): extend the placeholder to
`<one sentence stating what is missing and why this filing would not contain it; name the missing metric without quotation marks>`

Rationale (from the critiques):
- Formatting-only ("Keep table figures outside quotation marks"), not an answer-shape imperative ("state table figures") — avoids a hypothesis-1 tool-skipping cue next to the no-tool fallback sentence (critique1 #1).
- "answer prose" — matches Codex's scope; keeps the citations/followups JSON string quotes out of scope (critique0 #7b).
- Dropped "a label joined to its value" (not in Codex's wording; could suppress genuine MD&A sentences; every targeted shape is covered by "table figures"/"cells left out"/"ellipsis") (critique0 #7a, critique1 #5).
- Dropped "only one ... such as a sentence or phrase" (reads as one-quote limit; invites quoting) — per-quotation framing "Each quotation ... must be one contiguous span" still preserves genuine contiguous quotations (critique1 #3).
- Absence clause moved to the not-disclosed template (C placement): no tension with `:100-102` "never announce that a figure was omitted"; not on the disclosed path (critique1 #2). Codex: "Absence explanations should name an absent metric without quotation marks."
- Disclosed deliberately: "Keep table figures outside quotation marks" is stricter than F (F lets `"Net income 7,571.6"` and sub-8-char cells through) — reported as context, not enforced by F.

Identity: removing (b) and (c) yields arm B `16457055`; adding the clause back yields main `a88b6fb1`. Compute and pin the candidate composed sha256 + length in `prompt_identity.py`.

## 2. Owner test (`backend/tests/unit/test_copilot_live_regressions.py::test_contiguous_citation_instruction_reaches_actual_service_messages`, extend; no new function/file)

Add, reading `messages[0]['content']` as the test already does:
- `', including when all cited figures use tool markers' not in instruction` (G stage-2 cause)
- `'If there are no filing-text markers, output []' in instruction`
- the full RULES-bullet sentence text (joined, as composed) occurs exactly once
- `'name the missing metric without quotation marks>' in instruction` exactly once

No full-prompt hash pin in tests. `test_copilot_prose_quotations.py` byte-identical.

Mutations (run against the owner test, never committed): M1 restore clause → fails clause-absent; M2 delete the RULES bullet → fails rule-once; M3 revert the template edit → fails template assertion. Record failing-test tails.

## 3. Evidence folder `tasks/review-evidence/prompt-candidate-2026-10-03/` (new files only; no `tasks/todo.md` edit)

- `README.md` — the candidate, rationale, offline evidence, review record.
- `prompt_identity.py` + output — full sha256 + length of composed prompt; `_build_messages(...)[0]['content'] == SYSTEM_PROMPT`; candidate minus (b),(c) == `16457055`; plus clause == `a88b6fb1`; `_MIN_QUOTED_LEN == 8`; `_MIN_VERIFIABLE_LEN == 24`.
- `PREREGISTRATION.md` — see §5. Refers to "the commit containing this file"; no self-referential SHAs/PR numbers/review results.
- `scope_hashes.txt` — `git diff --exit-code <BASE> HEAD -- <paths>` for scorer, runner, bootstrap, schema, golden set, sources, baseline files, regression_gate, ai-model.env, config.py, ci.yml, copilot-eval.yml, copilot_tools.py, ai/copilot_chat.py, citation_markers.py, provenance_service.py, locked tests (full rule-6 inventory incl. T5–T10 per `tasks/architecture-refactor-plan.md:668-677`), measurement tools (`f_attribution.py`, `prose_quote_audit.py`, `g_decide.py`, `g_precheck.py`, `copilot_cost_runnerlog.py`). Plus AST scope check: only `SYSTEM_PROMPT` changes in `copilot_service.py`.
- `crosscheck_count.py` — the redundant cross-check counter (declared method), and `quote_inventory.py` — classifies every quoted span (double quotes, single quotes, backticks, guillemets, blockquotes) as verified / sub-floor / table-figure-in-quotes / other; runs offline on retained runs to show it works (baseline numbers on main runs).
- Offline replay on the retained G failure shapes is NOT possible for a prompt change (model output); state that the failure-shape coverage is argued, not replayed.

## 4. Gates (on the frozen head, before any paid trigger)

- Full backend gate from `backend/`, provider keys unset: `ruff check . && bandit -q -r app -ll && python -m pytest -q -p no:cacheprovider`. Expected 5565 + 0 new cases (assertions only).
- Explicitly also: the five RUNBOOK offline files (`RUNBOOK.md:808`) and `test_copilot_live_regressions.py`; the 13 tests that read `tasks/`; frontend `testHomesAllowlist.spec.ts` rule (no `test_*.py` under `tasks/`) — evidence scripts must not be named `test_*.py`.
- Named owner controls (unchanged, must pass): MSFT identities `test_copilot.py:484-498` (`identity_*`, `empty_array`, `mixed_fact_valid`); legitimate quotations `test_copilot_prose_quotations.py:110` and `prose_quote_valid`; table fragments `test_copilot_live_regressions.py:69-86`; not-disclosed `test_copilot_prose_quotations.py:1094-1109`, `test_copilot.py:597-611`.
- Exact-head independent review, three lenses (correctness/scope, model-behaviour, rules/gates/custody), on the head that contains the pre-registration. Findings fixed and re-reviewed before freeze.

## 5. Pre-registration content (PREREGISTRATION.md)

- Authorization: Codex 5958742492 (2026-10-02 18:27Z, under the founder's delegation). Ceiling USD 0.75 total including the automatic eval-baseline and ready jobs; hard stop. No merge, no production prompt release.
- Absolute qualification, not comparative. Historical G results are context only.
- Candidate identity: base main `<BASE>` (named concretely: efdc33f4 or later post-γ main, with γ's deploy verified); the composed prompt full sha256 and length; the two-insertions-plus-deletion description; `prompt_identity.py` output.
- Preconditions before step 1 (recorded in the step-0 #1029 comment): #1036 (00433-vcp), #1056 (00434-nbg), #1060 (00436-pkk), #1065 (receipt) deploys verified; no other active prompt-candidate PR; backend-slot + `copilot_service.py` claim posted on #1029 and acknowledged by the active Codex implementation owner (#1050 successors) — do not open the draft without acknowledgement or an explicit "no backend merges planned" from that owner.
- Steps: 0 (free) push branch; #1029 comment with head SHA, PREREGISTRATION.md sha256, gate tails, review verdicts, spend start point. 1 (≈0.18) balance+ledger read; spend rule `0.19 + 3×0.1725 ≤ remaining reservation`; off-peak (not Mon–Fri 01–04 or 06–10 UTC, and ≥ 20 min before a peak start — eval-baseline takes ~10–11 min); open draft PR with the Review section + `Review override:` line. 2 after eval-baseline: record verdict + telemetry (summary.incurred_provider_usage, unknown_calls); spend rule `spent + 3×0.1725 ≤ 0.75`; check PR mergeable and `git diff --quiet <prev merge ref> origin/main -- backend .github`; ready → Q1. 3 after Q1: download artifact, record zip/copilot-eval.json/runner.log sha256; inspect validity, cost, checks 1–5 BEFORE continuing; draft; same spend + diff-quiet checks; ready → Q2. 4 same for Q3; then convert back to draft. Never push/rebase/close/reopen during or after the window; never toggle during a run.
- Validity (one rule): every row matches the identity table (system prompt full sha256 + length checked per row, contexts, tool schema `b6958973`, options deepseek-flash/2400/0.2, golden_sha256, requested flags, planned attempts 18); `git diff --quiet` of `backend/` and `.github` between the runs' merge refs. Mismatch, cancelled run or missing artifact → invalid: stop, record, no rule, no replacement. Fingerprints reported (expected `aeb56401`; other values reported, not invalid; a stable fingerprint does not prove provider state unchanged).
- Acceptance per run: checks 1–5 verbatim from `tasks/copilot-tool-nonexecution-2026-09-30.md` (with the explicit note that "18/18 across both runs"/"every run, both runs" is applied per run: 9/9 10-K draws per run) and their measurement methods; check 4/5 audit policy: `prose_quote_audit` exit 2 categories (MSFT uncited figures, 20-F tool-less rows) are reported, not thresholds, following D14/D17 precedent (composed 0 and uncited answers 0 = pass).
- R. RUNBOOK aggregate evidence (separate row, after checks 1–5 unchanged): (i) the eval-baseline on the frozen head passes against the unchanged baseline (reported as a normal gate; red = not qualified; never re-run); (ii) `score.fact_adjacency == 1.0` on every scored row in each run (TRUST veto, `RUNBOOK.md:888-890`); (iii) three runs × `--runs 3` = 9 draws per question (meets `RUNBOOK.md:888-896`).
- Context (reported, no threshold): 20-F tool use per run (question-runs and draws, `g_decide.py`) with the predeclared label "deletion effect not preserved" if a run has 20-F tool-using question-runs ≤ 1/3; quote inventory across all forms (displacement report); non-F withholds; redundant cross-check counts (declared method); not-disclosed rows (expected 0; unmeasured live); uncited figures (MSFT advisory not a threshold); per-run cost incl. cache-miss tokens; fingerprints.
- Outcome: Qualified = all three runs valid and each passes checks 1–5 and R. Not qualified = any check fails in any run; continue the predeclared set while validity and spend permit; no retry, rerun, replacement or candidate edit; the #1056 triage rule does not apply (model-facing bytes change). Incomplete = validity or spend stop, reported.
- Spend accounting: every physical call incl. withheld/error rows and unknowns (`copilot_cost_runnerlog.py` for copilot runs; `summary.incurred_provider_usage` for eval-baseline). Shared-ledger start point: last posted remainder 7.346893 (#1029 comment 5961781714) before other owners' later costs; reserve 0.75 from it.
- Custody: artifacts downloaded and sha256-recorded in PR/#1029 comments after each run; durable private copy requested from the founder-side Codex custody owner (as for G); this lane cannot write founder storage.
- Handback (#1029): frozen head, all three outcomes or the explicit stop, actual telemetry/unknowns, exact-head review, gates, remaining limitations (small denominators; not-disclosed unmeasured live; checks cannot see quote forms outside double quotes except via the inventory; offline coverage of the failure shapes is argued, not replayed). Preserve this design's earlier versions and the review findings in the evidence folder.
