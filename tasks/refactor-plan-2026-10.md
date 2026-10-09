# EarningsNerd — Hot-module refactor plan (2026-10, execution-ready)

## Context

Six backend modules carry most of the change pressure and most of the size. On `main` at `da636f6`
(2026-10-08, the night this plan was written):

| Module | Lines | Functions | Longest function | Commits since 2026-08-01 (last 30 days) |
|---|---:|---:|---|---:|
| M1 `backend/app/services/copilot_service.py` | 1,934 | 49 | `_answer_filing_question_attempt` 297 (`backend/app/services/copilot_service.py:1638-1934`) | 17 (13) |
| M2 `backend/app/services/facts_service.py` | 2,153 | 42 | `normalize_companyfacts` 155 (`backend/app/services/facts_service.py:1358-1512`) | 10 (2) |
| M3 `backend/app/services/trend_analysis_service.py` | 1,923 | 57 | `build_observation_catalogue` 303 (`backend/app/services/trend_analysis_service.py:935-1237`) | 4 (3) |
| M4 `backend/app/services/openai_service.py` | 1,252 | 12 | `OpenAIService.summarize_filing` 552 (`backend/app/services/openai_service.py:682-1233`) | 25 (22) |
| M5 `backend/app/services/edgar/xbrl_service.py` | 1,316 | 30 | `EdgarXBRLService.extract_standardized_metrics` 259 (`backend/app/services/edgar/xbrl_service.py:1054-1312`) | 15 (11) |
| M6 `backend/app/services/edgar/instance_extractor.py` | 1,229 | 40 | `duration_series_with_starts` 69 (`backend/app/services/edgar/instance_extractor.py:372-440`) | 6 (6) |

(Line counts are `wc -l`; function lengths are `ast` `end_lineno - lineno + 1` counted from the `def`
line, nested functions counted inside their parent; commit counts are `git log origin/main
--since=2026-08-01 -- <file>` on the full history.)

The plan follows the format and discipline of [the 2026-07 architecture refactor plan](./architecture-refactor-plan.md):
anchor first, move second (pure moves proven by an AST per-symbol diff), split third, and every
"never again" rule becomes a machine gate in the same PR ([CLAUDE.md](../CLAUDE.md) rule 12). It
covers only these six modules. `summary_pipeline.py` and the routers are being refactored in other
lanes and are out of scope here; every cut below keeps the public names those lanes import, so no
coordinated change is needed across lanes.

**No application code is modified by this document.** It is the execution spec. Its factual claims
were verified against the code by six independent read-only module analysts (one per module), then
re-verified by adversarial lenses and an independent whole-plan reviewer, whose corrections are
folded in (see [Verification](#verification-how-the-plans-claims-were-checked-and-how-execution-is-verified)).

---

## Implementation Notes / Deltas (recorded during execution)

Where execution diverges from the plan below, log it here. The plan text is preserved as the
original proposal; these notes are authoritative for what actually shipped.

_(Nothing has shipped. The first entry will be the W0 gate PR.)_

---

## What changed from the inherited premises (verified corrections folded in)

The brief and the 2026-07 plan's delta log carry a few statements that no longer match the code.
Each was checked against `main` at `da636f6`:

1. **T9 now pins the liabilities and cash buckets as POPULATED.** The 2026-07 plan recorded that
   `_parse_company_facts` never fills `total_liabilities`/`cash_and_equivalents` and pinned that as a
   characterization. That was fixed on 2026-09-05 (commit `499648e6`): the parser fills both at
   `backend/app/services/edgar/xbrl_service.py:1042-1044`, and the locked anchor
   `backend/tests/unit/test_companyfacts_fixture.py:116-127`
   (`test_fallback_parser_preserves_liabilities_and_cash`) asserts them present. A split must keep
   them populated. The "fix pending" bullet in `docs/ARCHITECTURE.md:341` is stale (founder item 7).
2. **The `sleep(0.2)` follow-up (S4-followup-b) is done.** `facts_service.py` contains no `sleep`
   (`backend/app/services/facts_service.py:482` is a docstring describing the removed throttle);
   `_fetch_companyfacts_async` runs through `sec_rate_limiter.execute_with_backoff`
   (`backend/app/services/facts_service.py:1922`). The concept-list unification (S4-followup-a) is
   still open: the three revenue registries differ in order
   (`backend/app/services/edgar/instance_extractor.py:48-56` `Revenues` first;
   `backend/app/services/edgar/xbrl_service.py:1037-1038`; `backend/app/services/facts_service.py:1141-1147`
   contract-revenue first). This plan keeps them separate; unifying them is a behaviour change and
   is not scheduled here.
3. **`_TRACKED_STRUCTURED_SECTIONS` has no production importer.** The 2026-07 note that
   `summary_generation_service` imports it is stale: that file mentions it in comments only
   (`backend/app/services/summary_generation_service.py:146,180`); the sole importer is
   `backend/tests/unit/test_summary_schema_v2.py:283-284`. The alias at
   `backend/app/services/openai_service.py:88` is still used inside the façade (:747, :888).
4. **`model_flags` is a leaf.** No `ai/` module imports the façade back, `model_flags` included
   (`backend/app/services/ai/model_flags.py:3-8`; it is imported by `provider_requests.py:19` and
   `copilot_chat.py:18`, not by the façade). There is no cycle to protect.
5. **The four copilot branches touch only the system prompt, but the router imports three names.**
   The hunks of `claude/copilot-prompt-candidate`, `claude/g-stage1-arm-c`, `claude/g-stage2-arm-b`
   and `codex/wave3-copilot-typed-evidence` all fall inside `SYSTEM_PROMPT`
   (`backend/app/services/copilot_service.py:101-174`). The router binds `answer_filing_question`,
   `snapshot_filing` and `PROVIDER_STARTED_STAGE` by name (`backend/app/routers/summaries.py:45`),
   and the locked T5 anchor patches `answer_filing_question` on the ROUTER's namespace
   (`backend/tests/unit/test_expired_trial_gating.py:279,295`), so the router must keep its
   module-global name and bare-name call (`backend/app/routers/summaries.py:550`).
6. **None of the six stale `openai_service.py` branches touches `summarize_filing`.** They land in
   `generate_structured_summary`'s prompt region (`backend/app/services/openai_service.py:293-384,412,427,428`)
   and the import blocks (:21-25, :84-87). Two are measurement-only reverts of #899, one is
   superseded by #899, one is already main's text; only `codex/wave3-return-ratio-basis` and
   `codex/wave3-thinking-low-pilot` carry unmerged changes, and those are not one line: an import of
   `return_ratio_basis` at :22 plus the rule at :428 that interpolates it, and unlanded prompt bytes
   in `backend/prompts/10k-analyst-agent.md`, `10q-analyst-agent.md`, `20f-analyst-agent.md` and
   `backend/app/services/ai/xbrl_narrative.py`. Picking any of it is a prompt change under the RUNBOOK
   gate (founder item 3).
7. **The two codex xbrl branches would revert #1122 if rebased naively.** Their one unlanded line is
   the tuple at `backend/app/services/edgar/xbrl_service.py:463` gaining `"shareholders_equity",
   "total_assets"`; the rest of their hunk is on main (`:1243-1251`), and a two-dot diff shows they
   would put `asyncio.to_thread` back where `run_owned_sync` now is (`:38`, `:680`). Cherry-pick the
   one line or close them; never rebase them onto a split.
8. **The eval cost figure lives in AGENTS.md, not the RUNBOOK.** "an `eval-baseline` run is about
   USD 0.30" is [AGENTS.md](../AGENTS.md) §3 (line 54); the RUNBOOK gives only the call count for
   the comparison harness (`backend/evals/RUNBOOK.md:162`). The `copilot-eval` reservation figure,
   USD 0.06, is the Code Red ledger's (`tasks/code-red-20261004/runtime/control/DECISIONS-16.md:152-153`).

---

## Ground truth (verified)

### Triggers every PR in this plan must price in

| Trigger | Fires when | Cost or effect | Source |
|---|---|---|---|
| Cloud Run deploy | a merge to `main` changes any `backend/` path outside `backend/tests/` | deploys the API service and refreshes the jobs; one unverified deploy at a time, so code-bearing merges are serial | `.github/workflows/ci.yml:533-546` (detector), `backend/tests/unit/test_backend_deploy_scope.py`, [AGENTS.md](../AGENTS.md) §6 |
| `eval-baseline` (summary eval, paid) | every `pull_request` event, draft or not, whose diff touches `backend/app/*`, `backend/evals/*` or `backend/prompts/*`; also manual dispatch | about USD 0.30 and ~6 min per run; advisory (`continue-on-error`), but the report must be read before an AI-relevant merge | `.github/workflows/ci.yml:282-336`, `backend/evals/RUNBOOK.md:339-345`, [AGENTS.md](../AGENTS.md) §3 |
| `copilot-eval` (paid) | a non-draft PR whose diff touches `backend/**`; re-runs on each push while ready | about USD 0.06 per run | `.github/workflows/copilot-eval.yml:3-8,20`; `tasks/code-red-20261004/runtime/control/DECISIONS-16.md:152-159` |
| Code Red ledger reservation | before any paid trigger fires | "no paid trigger without a reservation written first" (CHECKPOINT); for `eval-baseline`, "before its first push of such a change and before each later one", draft or not (record 16) | `tasks/code-red-20261004/runtime/CHECKPOINT.md:346`; `tasks/code-red-20261004/runtime/control/DECISIONS-16.md:155-159` |

Open draft PR #1123 narrows `copilot-eval` to the eval's import closure (`backend/app/services/**`,
`models/**`, `schemas/**`, `utils/**`, `backend/app/*`, prompts, golden set, requirements). Every
module in this plan lives under `backend/app/services/`, so #1123 does not spare the code-bearing
PRs; it does spare tests-only PRs. Tests-only PRs never arm `eval-baseline` and never deploy, but on
today's main they still arm `copilot-eval` once each when marked ready for review (`backend/**`,
USD 0.06, reserved first). Wave 0 is free only once #1123 is merged (founder item 8).

### Open branches and PRs that touch these modules

Eight PRs are open on 2026-10-08 (#1133, #1132, #1126, #1123, #1121, #1118, #1035, #1009); none
changes any of the six modules (checked file by file). Two of them collide with files this plan
edits: the heads of #1126 and #1118 (`claude/agent-workflow-gates`, `claude/agent-workflow-cost`)
rewrite the CLAUDE.md hunk at lines 149–165, which contains the rule-5 line F1 edits (:152), and both
engineering briefs F1 edits; the head of #1121 (`codex/wave3-email-setup`) edits
`backend/scripts/backfill_facts.py` at lines X4 does not touch (:145, :185 vs :79). So F1 merges after
the two agent-workflow PRs or rebases over them, and X4 rebases over #1121. Remote branches that do
touch the six modules, measured as `git diff origin/main...origin/<branch>`:

| Branch | Module | Hunk | Disposition for this plan |
|---|---|---|---|
| `claude/copilot-prompt-candidate` (kept by founder decision of 2026-10-08, PR #1130) | M1 | +5/−2 inside `SYSTEM_PROMPT`; also test and `tasks/review-evidence/` files | M1 leaves `SYSTEM_PROMPT` and cluster A in `copilot_service.py` until this branch is merged or closed (founder item 3) |
| `claude/g-stage1-arm-c`, `claude/g-stage2-arm-b` ("DO NOT MERGE" experiments) | M1 | 1–5 lines inside `SYSTEM_PROMPT` | close |
| `codex/wave3-copilot-typed-evidence` | M1 | +8/−1 inside `SYSTEM_PROMPT` | founder item 3 |
| `codex/measure-n-control-2`, `codex/wave3-e8-n-pilot` ("MEASUREMENT ONLY") | M4 | 27-line revert of #899 in `generate_structured_summary` | close |
| `codex/wave3-supported-financial-explanations`, `codex/wave3-segment-margin-basis` | M4 | superseded by #899 / already main's text (#932) | close |
| `codex/wave3-return-ratio-basis`, `codex/wave3-thinking-low-pilot` | M4, M5 | two unlanded `openai_service.py` lines (import :22, rule :428), unlanded prompt bytes in three `backend/prompts/*-analyst-agent.md` files and `ai/xbrl_narrative.py`, one tuple line at `xbrl_service.py:463`; would revert #1122 | dispose before O2 and X2 (founder item 3); any pick is a prompt change under the RUNBOOK gate |

### Code Red D3 stage 2 is file-disjoint

Stage 2 makes the insider endpoint fit the 1 req/s edgartools budget and pins the API service
(`tasks/code-red-20261004/runtime/control/DECISIONS-16.md:135-150`). Stage 2 is not drafted yet;
its expected files, inferred from the record, are `backend/app/services/insider_service.py` (imports
only `ownership_extractor` :30, edgartools' `Company` :104, the edgar exceptions :106 and
`run_with_circuit_breaker` :169), `backend/app/routers/insiders.py` and `.github/workflows/ci.yml`.
None of the six modules is touched, and no PR in this plan edits `ci.yml`. The couplings are runtime and
procedural only: the same 4-thread edgar pool and breaker, the one-deploy-at-a-time rule, and the
reservation rule above, which this plan adopts for every code-bearing PR.

### Locked contract tests (rule 6) that bind to these modules

Only two of the locked files reference any of the six modules:

- `backend/tests/support/summary_stream_harness.py:50-58` (used by T1 and T2) patches
  `summary_pipeline.openai_service.summarize_filing` (:55) and
  `summary_pipeline.xbrl_service.get_xbrl_data` / `.get_filing_sections` (:52-53). The first binds to
  the `OpenAIService` singleton bound at `backend/app/services/summary_pipeline.py:46`; the second
  pair binds to the compat shim instance `XBRLServiceCompat()`
  (`backend/app/services/edgar/compat.py:582`, delegating at :555/:563/:577), which
  `summary_pipeline.py:36` imports. Both survive every cut below because the façade modules keep
  those objects and attribute names.
- T9 `backend/tests/unit/test_companyfacts_fixture.py` imports only `EdgarXBRLService` (:41) and calls
  `EdgarXBRLService()._parse_company_facts(companyfacts, TARGET_ACCESSION)` (:59) and
  `EdgarXBRLService().extract_standardized_metrics(parsed)` (:133). It exercises
  `facts_service._classify_duration` transitively through `backend/app/services/edgar/xbrl_service.py:1002`.
- T5 `backend/tests/unit/test_expired_trial_gating.py:279,295` patches the router's
  `answer_filing_question` name (see correction 5).

### Cross-module coupling that decides the wave order

| Edge | Site | Consequence |
|---|---|---|
| M5 → M6, module level | `backend/app/services/edgar/xbrl_service.py:43-58` binds 14 names by `from .instance_extractor import` | M6 keeps a façade exporting those names; the M6 split never edits `xbrl_service.py`; tests that patch `xbrl_module.DURATION_CONCEPTS` etc. (`backend/tests/unit/test_accession_xbrl_extraction.py:602-605,715-720,796-800,880-886`) keep working only while M5 keeps name-binding imports |
| M5 → M2, lazy, PRIVATE | `backend/app/services/edgar/xbrl_service.py:1002` imports `_classify_duration` inside the T9-pinned parser | M2's façade re-exports `_classify_duration`; the import is re-pointed only when M5 moves that code (X2) |
| M2 → M5, lazy | `backend/app/services/facts_service.py:690,759` import `edgar.compat.xbrl_service` | no module-level edge either way; `facts/concepts.py` must never import `app.services.edgar` at module level, and `facts/__init__.py` must not eagerly import a module that does |
| M1 → M4, import time | `backend/app/services/copilot_service.py:44-47` binds the singleton | 40 test sites patch `copilot_service.openai_service.stream_chat_with_tools` on the singleton object; safe under any move that calls the singleton's attribute at call time |
| M3 → M4, lazy | `backend/app/services/trend_analysis_service.py:1728` | `backend/tests/unit/test_copilot_cost.py:176` swaps the module attribute and relies on this laziness |
| `peers_service.py:22` → M2 PRIVATE | imports `_unit_for` at module level | façade re-export |
| `backend/scripts/backfill_facts.py:60,79` → M2, M5 PRIVATE | `_fetch_companyfacts_sync`, `_extract_from_filing_instance_sync` | façade re-exports or a one-line re-point in X4 |
| `backend/evals/copilot_scorers.py:34-41` → M1 PRIVATE | four adjacency guards and two public names | façade re-exports |
| `backend/evals/build_golden_set.py:151,167-170,189,227,251` → M6 | lazy imports of four names | the move keeps the names; renaming any breaks golden-set regeneration |

### Stale documentation found tonight (not edited: this PR carries only this file)

`docs/ARCHITECTURE.md:341` (buckets "fix pending", see correction 1);
`docs/audit-2026-09/03-data-platform.md:106,125,180,198` and
`docs/audit-2026-09/06-unfinished-work-inventory.md:59` (still describe the removed `sleep(0.2)`);
`docs/audit-2026-09/06-unfinished-work-inventory.md:60` (says persisted `Filing.xbrl_data` is never
read; `xbrl_service.py:680` reads it). Founder item 7 schedules a docs-only PR for these four. Two
more ride code PRs because their files deploy: `docs/OPERATIONS.md:230` ("In xbrl_service.py
`_cache_max_size`") moves with X1, and the stale `PROMPT_VERSION` comment at
`backend/app/services/trend_analysis_service.py:34-35` is fixed in T1, which moves `PROMPT_VERSION`.

---

## Per-module plans

Each section gives: responsibilities today, the seams to cut, the target layout, the anchor tests to
add first, the traps, and the estimated diff per PR. PR identifiers (`C1`, `F2`, …) are the ones the
waves below sequence.

### M1 — `backend/app/services/copilot_service.py` (1,934 lines; `C:` below)

**Responsibilities today** (43 top-level functions, 2 exception classes, 6 nested functions; no
`__all__`):

| Cluster | Functions (def range) | Module-level names used |
|---|---|---|
| A. Source and prompt assembly | `_select_source_text` C:177–182, `snapshot_filing` C:185–223, `_compact_xbrl_block` C:289–309, `_build_context_message` C:312–348, `_build_messages` C:371–392 | `SYSTEM_PROMPT` C:101–174 (f-string over the sentinels at C:69–74 and `_MIN_VERIFIABLE_LEN` C:49); `settings.COPILOT_CONTEXT_CHAR_CAP` C:321, `COPILOT_HISTORY_TURNS` C:379, `COPILOT_HISTORY_ITEM_CHAR_CAP` C:388; the 8,000-char cap C:309 |
| B. Fact provenance and identity | `_valid_fact_provenance` C:232–266, `_fact_identity` C:269–273 | `copilot_tools.canonical_unit` C:249 |
| C. Envelope parsing | `_parse_citations` C:395–443, `_parse_followups` C:446–473 | `_FOLLOWUPS_RE` C:75; raises `_UnpublishableAnswer` C:93 |
| D. Citation verification | `section_label_is_quoted` C:482–484, `_verify_citations` C:487–533 | `_QUOTE_MARK_RE` C:543 (an E constant), provenance helpers imported at C:49–55, `_RegenerableEvidenceMismatch` C:97 |
| E. Prose quotation admission | `_markdown_parser` C:598–607 … `_withhold_unsupported_quotations` C:942–952 (C:536–952, ~417 lines with constants) | the import-time singleton `_MARKDOWN` C:610, `_MARKDOWN_BLOCKS` C:616, caps C:549–560; `normalize_for_match` C:929/936 |
| F. Activity labels | `_safe_activity_label` C:955–967 | `copilot_tools._CONCEPT_LABELS`, `describe_tool_call` C:966 |
| G. Fact-marker adjacency guards | `_claim_span_start` C:979, `_adjacency_window` C:986, `_fact_matches_adjacent_number` C:991–1051, `_fact_matches_adjacent_currency` C:1061–1083, `_fact_matches_adjacent_concept` C:1133–1157 | `_NUMBER_TOKEN` C:973–976, `_CURRENCY_*` C:1055–1058, `_CONCEPT_SYNONYMS` C:1090–1116, `_CONCEPT_PATTERNS` C:1121–1124 |
| H. Server-owned uncited-claim repair | `_plan_uncited_fact_citation` C:1250–1286, `_repair_paired_annual_claim` C:1300–1344, `_fact_certifies_claim` C:1347–1389, `_repair_uncited_fact_claim` C:1392–1421 | `_ANNUAL_FIGURE_CLAIM` C:1209–1220 and `_PAIRED_ANNUAL_CLAIM` C:1291–1297 (built from its `.pattern`, must move together); `copilot_tools.run_tool` C:1322/1407 |
| I. Coverage telemetry | `count_uncited_figures` C:1424–1472 | `_NUMBER_TOKEN`, `_claim_span_start` |
| J. Marker resolution | `_resolve_citations` C:1475–1588 | `_COPILOT_MARKER_RE` C:76, the G matchers C:1532–1535, `copilot_tools.fact_to_citation` C:1551 |
| K. Orchestration | `answer_filing_question` C:1591–1635, `_answer_filing_question_attempt` C:1638–1934 | `PROVIDER_STARTED_STAGE` C:78, `_PUBLICATION_ERROR` C:77, `_STREAM_FAILURE` C:79, `_EVIDENCE_RETRY_GUIDANCE` C:84–90, `openai_service` + sentinels C:44–48, `monotonic` C:35, `chat_deadline` C:43, `settings.COPILOT_MAX_TOKENS` C:1713 |

**Public surface.** The router imports `PROVIDER_STARTED_STAGE`, `answer_filing_question` and
`snapshot_filing` by name (`backend/app/routers/summaries.py:45`; used at :557, :550, :475).
`backend/evals/copilot_runner.py` imports `snapshot_filing`, `_UnpublishableAnswer`, `logger`,
`answer_filing_question`, `openai_service` and `_build_messages` inside functions (:170, :194,
:221, :313); it installs a logging filter on `copilot_service.logger` (:201–205) that recognises
withheld attempts by `_UnpublishableAnswer`. `backend/evals/copilot_scorers.py:34-41` imports the
four G guards plus `count_uncited_figures` and `section_label_is_quoted`. Seventeen test files import
the module object; nine import names directly (for example `acquisition_period_cases.py:12`
`_build_messages`; `test_copilot_prose_quotations.py:43-50` four caps and two E functions;
`test_copilot_gate.py:451` the exception and the logger).

**Seams to cut.** K is the only cluster with edges into the others (A, B, C, D, E, F, H, I, J); H
depends on B and G; J and I depend on G; D reads one E constant. A, C, F and G have no inbound edges
except from K. So E, B+G, H, J+I and C+D+exceptions are each a clean leaf package module, and the
only decision is where the loop lives. Recommendation: keep `answer_filing_question` and the loop in
`copilot_service.py` (in-place decomposition, C2), because moving them changes the logger name the
eval runner filters on (C:1623 warning, `copilot_runner.py:201`) and forces five more test re-points.

**Target layout** (`copilot_service.py` stays the import path for the router, evals and tests, and
re-exports every name listed above; NOT under `app/services/ai/`, which
`backend/tests/unit/test_llm_no_pii.py:44-45` walks):

```
backend/app/services/copilot/
  quotations.py    ← cluster E (C:536–952) incl. _MARKDOWN, _MARKDOWN_BLOCKS, _QUOTE_MARK_RE
  fact_guards.py   ← clusters B + G (C:226–273, C:970–1157)
  claim_repair.py  ← cluster H (C:1160–1421); calls copilot_tools.run_tool as an attribute, never `from … import run_tool`
  resolution.py    ← clusters J + I (C:1424–1588)
  envelope.py      ← the two exceptions (C:93–98) + clusters C and D (C:395–533)
  prompt.py        ← (C3, gated) SYSTEM_PROMPT, sentinels, _EVIDENCE_RETRY_GUIDANCE, cluster A
backend/app/services/copilot_service.py  ← answer_filing_question + the attempt loop (decomposed in place) + re-exports; ≈ 750 lines after C1, ≈ 800 after C2
```

Phase map of `_answer_filing_question_attempt` (C:1638–1934) for C2: P0 messages C:1657–1659; P1
tool binding C:1666–1691 (`used_facts`, `_register_fact`, `_run_tool`) → a ~30-line `FactRegistry`
over cluster B; P2 progress and provider open C:1693–1717; P3 delta loop C:1718–1792 (error sentinel
:1726–1728, provider-start :1730–1732, activity events :1736–1749, heartbeat on `monotonic()`
:1751–1753, sentinel scan with `_SENTINEL_TAIL` hold-back :1764–1792) → a pure `SentinelScanner.feed`
(~30 lines) with the yields staying in the generator; P4 usage and tail flush C:1794–1800; P5
not-disclosed admission C:1800–1833 → `_admit_not_disclosed` (~21 lines); P6–P11 join, parse, expand
markers, verify, repair/resolve (C:1868–1893), final checks, markdown quotation gate, telemetry
(C:1835–1914) → one async `_admit_answer` (~75 lines); P12 complete event C:1916–1926; P13 exception
policy and `provider_stream.aclose()` C:1927–1934. Result: the loop drops from 297 to ≤80 lines.

**Anchor tests to add first** (C0, tests-only; existing strong pins at
`backend/tests/unit/test_copilot.py:505` with its case table :330–470, the retry suite
`test_copilot_quotation_retry.py:79-329`, repair `test_copilot_citation_repair.py:90-520`):
1. `_compact_xbrl_block` caps at 8,000 chars (C:289–309); no test pins the cap.
2. `_safe_activity_label` fallbacks (C:955–967): unknown tool → "Reading financial information";
   unknown concept → `concept=None`; only non-dict args are pinned today (`test_copilot.py:1415`).
3. `_register_fact` dedupes identical tool results (C:1672–1691) through a fake stream calling
   `run_tool` twice: same `cite`, one `used_facts` entry; different `source_facts` → new marker.
4. `_verify_citations` classification matrix (C:487–533): excerpt-only mismatch →
   `_RegenerableEvidenceMismatch`; quoted label, colliding duplicate, short excerpt, short source,
   referenced-but-undeclared → `_UnpublishableAnswer` (:511–513, :529–531).
5. Heartbeat progress every three seconds (C:1751–1753) at generator level, patching `monotonic` on
   the loop's module; today pinned only through the ASGI test via the façade name (`test_copilot.py:519`).
6. A pre-attempt failure yields one `{"type":"error","message":_STREAM_FAILURE}` (C:1633–1635);
   existing stream-error pins exercise only the in-attempt path (C:1726).

**Traps.**
- Patch bindings that survive a move because they bind to shared objects: 40 sites on the
  `openai_service` singleton (`stream_chat_with_tools`) and 17 on the `copilot_tools` module object
  (`run_tool`); new modules must keep calling `copilot_tools.run_tool` and `openai_service.<attr>` as
  attributes at call time.
- Patch bindings on the `copilot_service` MODULE namespace that go blind when the reading code
  moves: `normalize_for_match` (`test_copilot_prose_quotations.py:841`, `test_copilot_quotation_retry.py:123`),
  `_rendered_text` (:1219), `_MARKDOWN_BLOCKS` (:1229), `_MARKDOWN`/`_markdown_parser` (:1318), the
  `__file__` exec at :1292 (the thread-safety test re-executes the file), `_withhold_unsupported_quotations`
  (:1134), `_resolve_citations` (`test_copilot_paired_claims.py:59`), `monotonic` (`test_copilot.py:519`),
  the `openai_service` name (`test_copilot_cost.py:167`, `test_copilot_provenance.py:166`). C1 re-points
  the E-cluster sites (about eight lines in two files); keeping the loop in place avoids the rest.
- The router must keep the bare-name call (`backend/app/routers/summaries.py:550`) because T5 patches
  the router's name; never switch it to `copilot_service.answer_filing_question(...)`.
- `SYSTEM_PROMPT` bytes: a pure move keeps them identical iff the interpolated constants keep their
  values; prove with a sha256 of `SYSTEM_PROMPT` and equality of `_build_messages(snap, source, q,
  None)` before/after (the runner records exactly that, `backend/evals/copilot_runner.py:337`).
  C3 (moving the prompt) waits for the four branches (founder item 3).
- No SEC transport, no module state mutated at runtime; the only import-time singleton is the
  markdown parser (C:610). No filename-keyed allowlist names this module; the `rglob` gates
  auto-cover new files.

**Estimated diff size.** C0 +150–250 test lines. C1 pure moves: −1,225/+1,225 across five new
modules plus ~100 lines of imports and re-exports; ~8 test re-points; optional re-point of
`copilot_scorers.py:34-41`; AST per-symbol proof. C2 in-place decomposition: net +40–60 lines, loop
297 → ≤80. C3 (gated): ~250 lines moved.

### M2 — `backend/app/services/facts_service.py` (2,153 lines; `F:` below)

**Responsibilities today** (36 top-level functions + 6 nested closures; no classes; every import of
`app.services.edgar`, `httpx`, `settings` and `sec_rate_limiter` is lazy at F:691, F:759,
F:1905–1908, F:1951):

| Cluster | Functions (def range) | State used |
|---|---|---|
| A. Per-filing normalization (pure) | `_parse_date` F:101, `_fiscal_period` F:112, `_duration_start` F:119, `_unit_for` F:130–141, `normalize_standardized_to_facts` F:144–211 | `_CONCEPT_UNITS` F:47–87 |
| B. Reconciliation and authoritative cross-check | `reconcile_facts` F:214–322, `_prior_values` F:325–349, `extract_authoritative_values` F:373–424, `cross_check_facts` F:427–469 | `NON_NEGATIVE_CONCEPTS` F:89–96, `HEADLINE_GAAP_TAGS` F:358–367 |
| C. SEC companyfacts transport | `_fetch_companyfacts_sync` F:477–509, `_running_loop_in_this_thread` F:512, `_fetch_companyfacts_async` F:1898–1926 | `COMPANYFACTS_SYNC_TIMEOUT_SECONDS` F:474 |
| D. Per-filing writer | `_lock_fact_companies` F:519–525, `upsert_facts` F:528–656, `process_filing_facts` F:659–718 | lazy `edgar.compat.xbrl_service` F:691 |
| E. Jobs | `backfill_facts` F:721–864, `remediate_industry_facts` F:867–968, `backfill_company_sic` F:971–1041, `sync_companyfacts_batch` F:2100–2153 | `AFFECTED_FINANCIAL_CONCEPTS` F:38–42 |
| F. Read model | `get_filing_fundamentals` F:1071–1105 | — |
| G. Companyfacts normalization and period labelling | `_classify_duration` F:1205–1215, `_collect_companyfacts_values` F:1218–1290, `_label_quarters` F:1315–1355, `normalize_companyfacts` F:1358–1512 | `COMPANYFACTS_DURATION_TAGS` F:1140–1176, `COMPANYFACTS_INSTANT_TAGS` F:1178–1200, windows F:1129–1131 |
| H. Derived facts | `derive_q4_facts` F:1545–1606, `derive_q4_eps_facts` F:1627–1723, `derive_same_period_metrics` F:1726–1809 | `_EPS_SHARES_TAGS` F:1611–1617 |
| I. Bulk writer | `upsert_facts_bulk` F:1812–1895 | shares `_lock_fact_companies` (F:1830) |
| J. Ingest and in-flight dedup | `ingest_companyfacts` F:1996–2037, `ingest_companyfacts_by_id` F:2040–2097 | `_inflight_syncs` F:1938 (per-process dict of `asyncio.Event`) |

**Public surface.** Twelve importers, all `from app.services import facts_service` plus attribute
access: `ingest_companyfacts_by_id` (`backend/app/routers/analysis.py:92`,
`backend/app/services/background_task_runner.py:43`), `get_filing_fundamentals`
(`backend/app/routers/filings.py:510`), `backfill_facts` (`backend/app/routers/internal.py:175`,
`backend/app/services/internal_task_runner.py:175`, `backend/scripts/backfill_facts.py:62`,
`backend/scripts/audit_reconciliation_flags.py:56`), `sync_companyfacts_batch`
(`backend/app/routers/internal.py:251`, `internal_task_runner.py:244`, `backend/scripts/sync_companyfacts.py:39`),
`process_filing_facts` (`backend/app/services/summary_pipeline.py:708`, `backend/evals/copilot_bootstrap.py:101`).
Three production sites import PRIVATE names: `backend/scripts/backfill_facts.py:60`
(`_fetch_companyfacts_sync`), `backend/app/services/peers_service.py:22` (`_unit_for`, module level),
`backend/app/services/edgar/xbrl_service.py:1002` (`_classify_duration`, lazily, inside the T9-pinned parser).

**Seams to cut.** The clusters share only small leaves (`_CONCEPT_UNITS`, `NON_NEGATIVE_CONCEPTS`,
`_parse_date`, `_QUARTER_PERIODS`, `_CF_QUARTER_WINDOW`, `_lock_fact_companies`), so a package split
along the cluster lines is mechanical. The transport cut is the one that touches rule 5:
`_fetch_companyfacts_async` is a sanctioned raw-HTTP owner (`httpx.AsyncClient` F:1917–1919 under
`sec_rate_limiter.execute_with_backoff` F:1922, URL from `companyfacts_url` F:1913, User-Agent from
`settings.SEC_USER_AGENT` F:1910, no breaker). It can move to `facts/transport.py` without changing
the request path (same limiter singleton, same URL helper, same backoff ladder, same loop bridge
F:491–506), and the file carries no `sec.gov` literal, so `backend/tests/unit/test_sec_gov_importers_allowlist.py`
needs no new entry. What must change in the same PR is the prose that names the owner by file:
[CLAUDE.md](../CLAUDE.md) rule 5 (lines 105 and 152), `docs/ARCHITECTURE.md:189`,
`docs/adr/0003-edgartools-for-sec-data.md:30`, `lessons/sec-edgar-resilience-layer.md:23-24`,
`.claude/agents/engineering/backend-developer.md:30`, `.claude/agents/engineering/database-specialist.md:25`,
and the allowlist test's docstring (`test_sec_gov_importers_allowlist.py:5`).

**Target layout** (`facts_service.py` becomes a ≤60-line façade re-exporting every name above,
including the private ones production and tests import, and the SAME `_inflight_syncs` dict object):

```
backend/app/services/facts/
  concepts.py      ← cluster A helpers, _classify_duration, _is_financial_sic, every registry and constant
                     (F:38–98, 358–370, 1129–1202, 1312, 1611–1624); byte-identical tuples; never imports edgar at module level
  normalize.py     ← normalize_standardized_to_facts
  reconcile.py     ← cluster B
  transport.py     ← cluster C (the rule-5 owner; the prose updates above ride this PR)
  upsert.py        ← _lock_fact_companies, upsert_facts (split), process_filing_facts, upsert_facts_bulk
  companyfacts.py  ← cluster G minus the leaves; normalize_companyfacts (split)
  derive.py        ← cluster H
  ingest.py        ← cluster J (owns _inflight_syncs)
  jobs.py          ← cluster E; backfill_facts (split);   fundamentals.py ← cluster F
```

Phase maps (each step ≤80 lines):
- `normalize_companyfacts` F:1358–1512 → root and IFRS meta F:1372–1377, duration collection
  F:1379–1390, instant collection F:1392–1396, windows and labels with `_base_fact` lifted to top level
  F:1398–1416, duration rows F:1418–1441, instant rows F:1443–1464, transient shares +
  `derive_q4_eps_facts` F:1466–1486 (after `derive_q4_facts` F:1462), hard-reject before
  `derive_same_period_metrics` F:1488–1495 (ordering pinned by `backend/tests/unit/test_companyfacts_ingest.py:216`),
  identity dedup F:1502–1512.
- `backfill_facts` F:721–864 → fetcher resolution and query F:757–779, counters F:781–790, extract
  F:792–799, per-company authoritative cache and demotion guard F:800–819, process and dry-run
  rollback F:821–829, stats and audit log F:830–849, stats shape F:851–864 (pinned by
  `backend/tests/unit/test_facts_service.py:737`).
- `upsert_facts` F:528–656 → lock, gate and cross-check F:562–577, counters and prefetch F:579–586,
  identity hit or flag-only repair F:587–611, `flags_only` F:612–614, current-row query and
  `newer_filing` predicate F:616–636, demote and insert F:637–641, commit and result keys F:643–656.

**Anchor tests to add first** (F0, tests-only):
1. `backfill_facts` default fetcher: with `companyfacts_fetcher=None, cross_check=True` it calls the
   module's `_fetch_companyfacts_sync` once per company and caches by company (F:762, F:800–807);
   every existing call injects a fetcher or disables the cross-check (`test_facts_service.py:548-885`).
2. `_fetch_companyfacts_sync` edge branches: inside a running loop → None without touching the
   limiter (F:491–494); `FuturesTimeoutError` → cancel and None (F:502–505). `TestCompanyfactsSyncBridge`
   (`test_facts_service.py:1175-1292`) covers the other seven branches.
3. `remediate_industry_facts` atomic rollback when `process_filing_facts` raises after the delete
   (F:947–962); `TestRemediateIndustryFacts` (:1002–1097) covers replace, dry-run and None-skip only.
4. `sync_companyfacts_batch` per-company failure handling and cohort precedence (F:2100–2153); it is
   only ever patched today (`backend/tests/unit/test_internal_durable_tasks.py:203`).
5. `normalize_companyfacts` in-batch identity dedup, first wins (F:1502–1512).
6. `extract_authoritative_values` restatement tie-break (`<=` at F:412–415).
Already covered, do not duplicate: untied-companyfacts preservation and newer-amendment protection
(`backend/tests/unit/test_data_completeness.py:324,439`), NULL-twin demotion (:263), the ordered
`FOR NO KEY UPDATE` lock compiled against the postgresql dialect for both writers (:420–435),
dry-run and flags-only (`test_facts_service.py:608-736`).

**Traps.**
- Monkeypatch targets that bind to module globals at call time: `backend/tests/unit/test_job_reporting.py:242`
  patches `facts_service.process_filing_facts` and expects `backfill_facts` (F:808) to see it;
  `backend/tests/unit/test_analysis_coverage_pool_lifetime.py:78` patches
  `facts_service._fetch_companyfacts_async` and expects `ingest_companyfacts_by_id` (F:2081) to see
  it; :81 and :140 call `facts_service._inflight_syncs.clear()` in place. After the split each needs a
  one-line re-point to the leaf module (`facts.upsert`, `facts.ingest`) in the same PR, and
  `ingest.py` must own the one `_inflight_syncs` object the façade re-exports.
- `test_facts_service.py:1278-1292` reads the URL off `request_fn.__closure__` by the free-variable
  name `url`; the `_get` closure (F:1916) must keep that name.
- Commit ownership is per function and must not move: `upsert_facts` F:648–649,
  `process_filing_facts` F:709/716–717, `backfill_facts` F:810/829, `remediate_industry_facts`
  F:957/959, `backfill_company_sic` F:1022–1040 (toggles `expire_on_commit`), `upsert_facts_bulk`
  F:1893–1894, `sync_companyfacts_batch` F:2124–2152.
- Import cycle: `backend/app/services/edgar/__init__.py:35-36` eagerly loads `client` and
  `xbrl_service`; `xbrl_service.py:1002` lazily imports facts_service; facts_service imports edgar only
  lazily. `facts/concepts.py` must never import `app.services.edgar` at module level.
- `datetime.now(timezone.utc)` at F:715, F:1954, F:1983 is not the `utcnow()` helper but is not
  flagged by the naive-utcnow gate (it matches `.utcnow` attribute calls only); leave it in a pure move.
- Eval triggers: facts rows do not feed the summary prompt (no `FinancialFact` reference in
  `services/ai/`, `openai_service.py` or `summary_pipeline.py`), but they ARE model-facing for the
  copilot (`backend/app/services/copilot_tools.py:234-236,269-276`; `backend/evals/copilot_bootstrap.py:101`
  seeds them). A pure move changes no row bytes.

**Estimated diff size.** F0 +150–200 test lines. F1 leaves + transport + façade (+ the seven prose
edits): ~300 moved, ~50 added; `F` → ~1,850. F2 companyfacts + derive with the `normalize_companyfacts`
split: ~600 moved, ~60 added; `F` → ~1,250. F3 writers + reconcile with the `upsert_facts` split:
~520 moved, ~50 added, 1–2 patch-target edits; `F` → ~730. F4 jobs + ingest + fundamentals with the
`backfill_facts` split: ~700 moved, ~60 added, 1 patch-target edit; `F` → ≤60. Nine new files; longest
function ≤80 everywhere.

### M3 — `backend/app/services/trend_analysis_service.py` (1,923 lines; `T:` below)

**Responsibilities today** (52 top-level functions + 1 class; the "57" counts 5 nested defs at
T:366, 946, 1247, 1255, 1667):

| Cluster | Functions (def range) | Notes |
|---|---|---|
| A. Period keys, labels, coverage | `parse_period_key` T:126–136, `available_periods` T:148–215 | constants `PROMPT_VERSION` T:41, `DATASET_CONCEPT_ORDER` T:72, `_CORE_REVENUE_CONCEPTS` T:145 |
| B. Dataset grid and growth math | `_growth` T:228, `_cagr` T:248, `build_dataset` T:271–530, `dataset_fingerprint` T:739–743, `marker_index` T:1322–1351 | reads `settings.ANALYSIS_MAX_ANNUAL_PERIODS` T:331, `ANALYSIS_MAX_QUARTERLY_PERIODS` T:359 |
| C. Detectors | `detect_growth_deceleration` T:546–588 … `detect_inflections` T:726–733 | `_DETECTORS` T:717–723; `detect_inflections` swallows detector exceptions (untested) |
| D. Formatting | `_format_value` T:746, `_pct_str` T:799, `_fmt_growth` T:803, `_ratio_threshold_value` T:844 | `compact_dataset_for_prompt` T:756–796 is NOT on the live prompt path (the stream sends `compact_observation_catalogue`, T:1810); only tests call it (`backend/tests/unit/test_trend_analysis_service.py:854,883,977,1000`) |
| E. Observation catalogue and selection | `TrendObservation` T:830–836, `build_observation_catalogue` T:935–1237, `parse_observation_selection` T:1264–1284, `render_observation_selection` T:1287–1311 | `ANALYSIS_SECTIONS` T:816–823; order is load-bearing (first-wins dedup T:947–953, order-dependent `required` T:1061–1063 and T:1151–1153, fallback to `section_items[0]` T:1304–1306) and the catalogue text IS the prompt's user message (T:1806–1813) |
| F. Citations | `_point_citation` T:1366–1399, `resolve_narrative_citations` T:1402–1447 | `_illegal_refs` T:1450–1460 is dead |
| G. Numeric-fidelity scan | `scan_numeric_fidelity` T:1539–1579 | `_mismatch_details` T:1582 and `_retry_instruction` T:1593 are dead; `NOT_ENOUGH_DATA_SENTINEL` T:1356 unused |
| H. Cache and persistence | `_load_cached_analysis` T:1616, `has_cached_analysis` T:1630–1640, `_persist_analysis` T:1643–1701 | owns its own `SessionLocal()` T:1665; commits at T:1684/1691/1694; swallows failures to `None` T:1696–1698 |
| I. Narrative streaming | `stream_trend_narrative` T:1704–1923 (async generator) | lazy imports T:1727–1729 (`SessionLocal`, `STREAM_ERROR_SENTINEL` + `openai_service`, `get_named_prompt`) |

Dead code (zero callers in `app/`, `evals/`, `scripts/` by `git grep`): `_illegal_refs`,
`_mismatch_details`, `_retry_instruction`, `NOT_ENOUGH_DATA_SENTINEL`.

**Public surface.** One app importer: `backend/app/routers/analysis.py:39`
(`from app.services import facts_service, trend_analysis_service`), which looks up `available_periods`
(:158, :170), `build_dataset` (:207, :237), `has_cached_analysis` (:357), `stream_trend_narrative`
(:374) and `PROMPT_VERSION` (:441) on the module object at call time. No module under `backend/evals/` imports
it. Tests import 23 names including privates (`_growth`, `_fmt_growth`, `_pp_delta`,
`_point_citation`, `_cagr`, `_has_minimum_analysis_data`, `NOT_MEANINGFUL`):
`backend/tests/unit/test_trend_analysis_service.py:16`, `backend/tests/unit/test_analysis_stream.py:16`,
`backend/tests/unit/test_data_completeness.py:21`.

**Seams to cut.** The one tangle is B→C→E→A: detectors (C) call `_growth_operand_markers` (E, T:578),
which calls `parse_period_key` (A, T:908). Cutting a `series.py` (`_series_map` T:536,
`_valued_points` T:540, `_growth_operand_points` T:902, `_growth_operand_markers` T:920) breaks it.
Everything else is pure functions over dicts plus two self-contained DB units (H, and the read session
in I at T:1733/1782). Admission, metering and the `analysis_inference_cost` event are NOT in this
module; they live in the router (`backend/app/routers/analysis.py:348,352,262-277,300-324`), so the
split never touches usage accounting.

**Target layout** (`T` stays importable and keeps every name above, including the test-used privates,
via explicit re-imports and `__all__`):

```
backend/app/services/trend_analysis/
  periods.py       ← cluster A and its constants
  formatting.py    ← NOT_MEANINGFUL, _format_value, _pct_str, _fmt_growth, _ratio_threshold_value, _ordered_percentage_values
  series.py        ← _series_map, _valued_points, _growth_operand_points, _growth_operand_markers
  detectors.py     ← cluster C
  dataset.py       ← _growth, _pp_delta, _cagr, _valued_endpoints, build_dataset (split), dataset_fingerprint, marker_index
  observations.py  ← cluster E incl. TrendObservation; build_observation_catalogue (split)
  citations.py     ← cluster F;   fidelity.py ← cluster G
  cache.py         ← cluster H + PROMPT_VERSION
  narrative.py     ← stream_trend_narrative (split into phases)
backend/app/services/trend_analysis_service.py  ← ~60-line façade (re-exports + __all__)
```

Phase maps (each step ≤60 lines):
- `build_dataset` T:271–530 → `_index_facts` (T:289–308), `_period_axis` (T:311–364, two branches),
  `_series_points` (T:366–411), `_attach_growth` (T:413–448), `_series_window_figures` (T:450–496),
  `_assign_markers` (T:498–511), assembly + `detect_inflections` (T:513–530).
- `build_observation_catalogue` T:935–1237 → a small collector object replacing the `add` closure
  (T:942–957), then the eleven phases in today's exact order: top line T:959–995, net income
  T:997–1014, growth pairs T:1018–1052, margins T:1054–1076, cash vs net income T:1078–1109, balance
  sheet T:1110–1122, current ratio T:1124–1141, EPS T:1143–1154, selected gap T:1156–1172, red flags
  T:1174–1202, watch next T:1204–1235.
- `stream_trend_narrative` T:1704–1923 → `_assemble` (the DB unit T:1733–1782, returning a cached event
  or the dataset tuple), not-enough-data T:1784–1800, `_selection_messages` T:1802–1820, the provider
  loop T:1824–1877 (keeps `openai_service.stream_chat(...)` T:1847–1850, sentinel handling T:1853–1857,
  `merge_chat_usage` T:1866), publication T:1879–1890, persistence + complete event T:1892–1923.

**Anchor tests to add first** (T0, tests-only):
1. Catalogue order snapshot: pin the literal `[(id, section, required), …]` list of
   `build_observation_catalogue` on the `TestCodeOwnedObservations._dataset` fixture
   (`test_trend_analysis_service.py:200-238`); today's tests assert sentence membership only (:240–447).
2. Selection prompt bytes: drive `stream_trend_narrative` through `_drain`
   (`test_analysis_stream.py:194-204`) and pin the sha256 of both provider messages; only the retry
   substring is pinned today (:418–421). A byte change here is a `PROMPT_VERSION` event under
   `backend/evals/RUNBOOK.md:959-971`.
3. `dataset_fingerprint` hex for a literal dataset; :933–958 pins inequality only, and a `json.dumps`
   change at T:742 would silently invalidate every cached row (compare T:1752).
4. A raising detector does not break `build_dataset` (the swallow at T:726–733 has no test).
5. Exact key sets of the fresh (T:1906–1923) and cached (T:1763–1775) complete events.
Already covered, no anchor needed: marker ordering, CAGR window, pp deltas, derived-Q4 badging
(`test_trend_analysis_service.py:510-532,602,622,641-858`).

**Traps.**
- Keep the router's call-time lookups: tests patch those names on the router's module attribute
  (`test_analysis_stream.py:597-612,729-731,755`; `backend/tests/unit/test_excel_export.py:323-327,354`;
  `backend/tests/unit/test_durable_request_ownership.py:29-32`).
- Keep `openai_service` and `SessionLocal` lazily imported inside the narrative (T:1727–1729) and
  cache (T:1662) units: `test_copilot_cost.py:176` patches `openai_service.openai_service` on the
  module and `test_data_completeness.py:31` patches `database.SessionLocal`; a hoisted import in
  `narrative.py` goes blind to both.
- Do not put any of this under `app/services/ai/` (`test_llm_no_pii.py:35-49` walks that package;
  the façade convention in `docs/ARCHITECTURE.md:171-176` is per domain).
- Eval triggers: no prompt bytes live here except the user-message literals (T:1804–1813,
  T:1826–1834); the system prompt is `backend/prompts/trends-analyst-agent.md` loaded via
  `backend/app/services/prompt_loader.py:118-131` (path resolved relative to the loader, so moving
  `T` cannot change it). A pure move keeps the selector byte-identical; the AST per-symbol diff plus
  anchor 2 prove it.
- No SEC transport, no datetime calls, no module-level mutable state (constants only, T:41–123, 145,
  225, 717, 816–826, 1356–1363, 1468–1483).
- Docs to touch in the move PR: `docs/ARCHITECTURE.md:158` (catalog row), the comment at
  `backend/app/models/trend_analysis.py:32`.

**Estimated diff size.** T0 +130–180 test lines. T1 leaf moves (periods, formatting, series,
detectors, citations, fidelity, cache + façade) ±800, `T` → ~1,150. T2 dataset + observations ±870,
`T` → ~330. T3 narrative + final façade and docs ±300, `T` → ~60. T4 the three splits inside the new
modules: +70/−30, +100/−40, +90/−40. T5 dead-code deletion (founder item 4; deletes four tests of
`compact_dataset_for_prompt`) −130.

### M4 — `backend/app/services/openai_service.py` (1,252 lines; `O:` below)

The façade the 2026-07 S2 split left behind: 21 `ai/` modules re-exported at O:15–65, the
mixin-composed `OpenAIService` (bases at O:110–116), and two large methods. It is the most-changed
backend file because every quality rider lands in one of those two methods.

**Responsibilities today:**

| Cluster | Lines | Notes |
|---|---|---|
| Re-exports and `__all__` | O:1–89, O:1241–1252 | `__all__` is the F401 shield; `_segments_not_applicable` (O:94–107), `get_prompt` (O:9) and `snap_evidence` (O:34) are consumed through the module namespace without being listed |
| Model routing | O:118–157 | `client` O:120–121 (`max_retries=0`), `model` O:123, `_task_models` O:125–133, `get_model_for_filing` O:140, `get_model_for_task` O:146 |
| `generate_structured_summary` | O:223–472 (250 lines) | the ONLY prompt-building code in the file: `get_prompt` O:264, `get_structured_prompt` O:398, system literal O:440–450, user f-string O:401–435, `schema_template` O:293–384, params O:438–455 |
| `_assemble_structured_summary` | O:474–560 (87) | JSON repair, grounding keys, `_recover_missing_sections` O:529–535, `_apply_structured_fallbacks` O:552–556 |
| `_stream_collect`, `_partial_markdown_preview` | O:562–616, O:618–679 | the streaming preview path tests inject on a bare mixin (`backend/tests/unit/test_acceptance_meter.py:24-27,64`) |
| `summarize_filing` | O:682–1233 (552 lines) | post-provider finalization; uses `self.` exactly four times (O:704, O:808, O:859, O:1000) |

Phase map of `summarize_filing` (every phase after P0 is post-provider, so none emits prompt bytes):
P0 primary extraction O:702–709 → P0b error envelope O:711–733 → P1 strip, taxonomy and table
guards O:735–761 → P2 risk projection O:763–786 → P3 forward-quote gate O:788–800 → P3b attribution
gate and the one side provider call `self._verify_attributions` O:801–816 → P4 source binders and
evidence snap O:818–885 (flags `EVIDENCE_SNAP_MIN_SCORE` O:852, `AI_EVIDENCE_SNAP` O:853) → P5
coverage snapshot O:887–921 → P6 compat strings with the nested `_stringify` O:923–957 → P7 render
O:959–1001 → P8 raw_summary payload O:1003–1037 → P9 title O:1039–1061 → P10 legacy cards
O:1064–1135 → P11 insights O:1137–1181 → P12 status and message O:1184–1207 → P13 return O:1210–1233.

**Public surface.** The `openai_service` singleton (O:1235) is bound at import by
`backend/app/services/summary_pipeline.py:46` (`.summarize_filing` at :1015),
`backend/app/services/summary_generation_service.py:11` (:509, :516),
`backend/app/services/copilot_service.py:44-47` (:1703, :1708), and lazily by
`backend/app/services/trend_analysis_service.py:1728`; `backend/evals/runner.py` and
`backend/evals/copilot_runner.py` use it too. No `ai/` module imports the façade back.

**Seams to cut.** Keep `summarize_filing` on the class as a ~70-line orchestrator (the
`_LLM_ENTRYPOINTS` check at `backend/tests/unit/test_llm_no_pii.py:22-25,52-58`, the exact signature
pin at `backend/tests/unit/test_filing_only_inputs.py:89-117`, the forwarding pin at :121–143, and all
27 patch sites keep working). Move the post-provider phases into `ai/summary_finalize.py` as functions
over a `SummaryRun` dataclass, 1:1 with the phase map; pass the four `self` dependencies in as
arguments (`layout = self._SECTION_LAYOUT[...]`, `fallback_render = self._build_structured_markdown`)
and keep `await self._verify_attributions` in the orchestrator. The decomposition is prompt-identical
by construction, which keeps the baseline pin valid (`backend/evals/RUNBOOK.md:530-535`). Optionally
(O2) move prompt assembly O:261–456 to `ai/summary_prompt.py` with `schema_template` as a module
constant, proven byte-identical by anchor A1.

**Target layout:**

```
backend/app/services/ai/summary_finalize.py   ← SummaryRun + 14 phase functions (≤80 lines each; ~520 lines)
backend/app/services/ai/summary_prompt.py     ← (O2, gated) build_primary_request; schema_template constant
backend/app/services/openai_service.py        ← façade + OpenAIService; summarize_filing ≈ 70 lines; ~840 lines after O1, ~670 after O2
```

**Anchor tests to add first** (O0, tests-only; fixtures are JSON, no provider calls):
- A1 provider-request snapshot: patch `_request_content` and `_assemble_structured_summary` (pattern
  `backend/tests/unit/test_verbatim_contract.py:170-193`), run `generate_structured_summary` for
  10-K, 10-Q, 20-F and 6-K with `sixk_class`, under `USE_STRUCTURED_OUTPUT` on and off, and compare the
  full `create_kwargs` (messages, model, temperature, max_tokens, response_format) to a fixture.
  Existing coverage is substring-only (`backend/tests/unit/test_structured_output_flag.py:36-76`,
  `backend/tests/unit/test_xbrl_narrative_section.py:359-400`, `backend/tests/unit/test_sixk_variant_wiring.py:26-47`).
  This is the eval tripwire for O2 and for every future prompt rider.
- A2 return-shape pin: fake client (`test_sixk_variant_wiring.py:13-22`), assert the key set of the
  result (O:1210–1229 plus the conditional `message`) and of `raw_summary` (O:1003–1037 including the
  conditional audit keys). Today only `backend/tests/unit/test_source_first_risks.py:180` touches this.
- A3 error envelope (O:717–733) for a non-timeout extraction failure; timeout propagation is already
  pinned (`test_filing_only_inputs.py:121-143`, `backend/tests/unit/test_provider_resilience.py:615`).
- A4 status and message thresholds (O:1184–1207: 0.5, 0.7, zero cards → "error").
- A5 title derivation (O:1047–1061).
- A6 aliasing invariant: `result["raw_summary"]["sections"] is result["raw_summary"]["structured"]["sections"]`
  and no `_`-prefixed key inside `raw_summary["structured"]`; the in-place binders depend on it
  (O:742–745, O:792–796, O:875–882).

**Traps.**
- `backend/tests/unit/test_evidence_snap.py:231-239` reads `openai_service.py` as TEXT and asserts
  five literals with their exact indentation (O:853–855, O:832, O:550, O:1025). O1 must redirect that
  test in the same PR (an ordinary unit test, not a locked anchor).
- MRO: `_request_content` (`backend/app/services/ai/provider_requests.py:210`) calls
  `self._stream_collect` (:291), which calls `self._partial_markdown_preview` (O:601); keep these
  `self.` calls, never module functions.
- `client`: seven `create` patches and 12+ direct `service.client = …` assignments mean the request
  must stay `self.client.chat.completions.create` (`provider_requests.py:237,297`, O:577).
- `get_prompt` and `snap_evidence` are monkeypatched on the façade module
  (`test_sixk_variant_wiring.py:30,36,55-57`; `backend/tests/unit/test_statement_relationship_integration.py:251,357-362`);
  the orchestrator must keep calling them by the façade's binding, or those tests get a one-line
  re-point in the same PR.
- Usage accounting fires at provider start inside `_request_content` (`signal_provider_start()`
  `provider_requests.py:289`, armed by `summary_pipeline.py:1010-1014`); the ContextVars are
  task-local, so phases must stay in the same task. The one threadpool hop (O:848) carries no provider call.
- `@bounded_summary` (O:222, O:681) shares one deadline ContextVar (`provider_requests.py:80-87`);
  `summarize_filing` must keep re-raising `asyncio.TimeoutError` (O:711–713) so the pipeline's
  deterministic fallback runs.
- In-place mutation order: `sections_info` is one object shared by `structured_summary["sections"]`
  (O:749), the render envelope (O:988) and `raw_summary["sections"]` (O:1022); private keys are popped
  in order (O:765, O:832, O:869, O:873, O:975–983) before embedding at O:1021. Phases must not copy or reorder.
- `ai/summary_finalize.py` must not import `summary_pipeline` or `summary_generation_service` (both
  import the façade: cycle) nor `app.models` (`test_llm_no_pii.py:35-49` walks `app.services.ai`).
- Open branches: see correction 6. O1 never conflicts with them; O2 would, so O2 waits for founder item 3.
- Eval triggers: every `settings.*` read is at O:120–137, O:170, O:396, O:656, O:799, O:813,
  O:852–853; O1 reads none of them differently. The paid job still arms on every push.

**Estimated diff size.** O0 +250–350 test lines and 2–4 JSON fixtures. O1: façade −480/+75
(O:735–1231 moved, orchestrator ≈ 70 lines), +520 new module, `test_evidence_snap.py:231-239`
redirected; file 1,252 → ~840; longest function 552 → 250. O2 (gated): façade −200/+30; file → ~670;
longest function → 87 (`_assemble_structured_summary`).

### M5 — `backend/app/services/edgar/xbrl_service.py` (1,316 lines; `X:` below)

**Responsibilities today** (30 defs including 10 nested):

| Cluster | Functions (def range) | Notes |
|---|---|---|
| A. Two-tier cache | `_get_cache_lock` X:113–123, `clear_xbrl_cache` X:126–136, `_cache_set_sync` X:149–197, `get_xbrl_cache_stats` X:200–235 | state X:90–110 (`_XBRL_CACHE_VERSION` "v6", `_xbrl_cache`, `_cache_max_size`, counters, lazy loop-bound lock); `get_xbrl_data` mutates the counters through `global` X:676 |
| B. Filing-instance extraction (sync, executor-run) | `_extract_segments` X:238–293, `_source_duration` X:296–304, `_extract_from_filing_instance_sync` X:307–545 | run by `_fetch_from_filing_instance` X:802–815 under `run_in_executor_with_timeout` X:809–812; deliberately breaker-exempt (comment X:29–35, S4 review finding 2); network inside the lambda = `resolve_filing_by_accession` X:320 and edgartools `filing.xbrl()` X:337 |
| C. Sections extraction | `_extract_sections_sync` X:553–631 | run by `get_filing_sections` X:817–848 (form gate :829–831, 30s/40s timeout :837); zero unit coverage |
| D. Service class | `EdgarXBRLService` X:634–1312: `get_xbrl_data` X:646–728, `get_filing_sections` X:817–848, `extract_standardized_metrics` X:1054–1312 | singleton `edgar_xbrl_service` X:1316 |
| E. Persisted-snapshot-first and orchestration | `_persisted_xbrl` X:731–755 (`@staticmethod`, own `SessionLocal`), `_get_from_redis` X:757, `_set_to_redis` X:766, `_fetch_xbrl_data` X:775–800 | `run_owned_sync(self._persisted_xbrl, …)` X:680 (`backend/app/services/request_work.py:95-108`); never move it under the 4-thread edgar pool |
| F. Companyfacts fallback transport and parser | `_fallback_to_company_facts` X:850–889, `_parse_company_facts` X:891–1052 | `sec_rate_limiter.execute` single wait X:883, no breaker (comment X:868–872); `CASH_TAG_CANDIDATES` X:69–75; inline concept lists X:1036–1047; lazy `_classify_duration` X:1002; neither method reads `self` |

**Public surface.** `edgar/__init__.py:36-40` re-exports `EdgarXBRLService`, `edgar_xbrl_service`,
`clear_xbrl_cache`, `get_xbrl_cache_stats` (`__all__` :50–83); `backend/app/routers/admin.py:22,559,562,583`
and `backend/app/services/metrics_service.py:91` use the last two; `backend/app/services/edgar/compat.py:21`
wraps the singleton as `XBRLServiceCompat` (:534–577, instance :582), which `summary_pipeline.py:36`,
`backend/app/routers/summaries.py:646-647`, `facts_service.py:690-692,759-761`, `backend/evals/runner.py:107`
and `backend/evals/copilot_bootstrap.py:100-106` import. The private `_extract_from_filing_instance_sync`
is imported by `backend/scripts/backfill_facts.py:79` and eight test files; `_extract_segments` by
`backend/tests/unit/test_segment_extraction.py:9`; `CASH_TAG_CANDIDATES` by
`backend/tests/unit/test_cash_registry_consistency.py:31,40`.

**Seams to cut.** Clusters A, B, C and F are each self-contained; D and E stay together as the
service. The riskiest cut is B, because about 35 test sites patch names on the MODULE namespace that B
reads: `resolve_filing_by_accession` (`test_accession_xbrl_extraction.py:329-333`, `test_fpi_currency.py:84-88`,
`test_cash_financial_applicability.py:75`, `test_data_completeness.py:85`, `test_financing_source.py:61`,
`test_financial_statement_extraction.py:314-317`, `backend/evals/acceptance_archive.py:604`) and the
concept-list stubs (`test_accession_xbrl_extraction.py:602-605,715-720,796-800,880-886`,
`test_debt_scope_owner.py:649-654`). Those patches stop intercepting the moment the reading code
moves, so X4 either retargets all of them (none is locked) or keeps the orchestrator in `X` and
injects collaborators into phase helpers. Recommendation: retarget, in the same PR, with the AST
proof and the T9 run as the gate.

**Target layout** (inside the package, so the `sec.gov` allowlist's directory rule
`test_sec_gov_importers_allowlist.py:23` keeps covering it; new modules are leaves that never import
from `X`, because `edgar/__init__.py:36` loads `X` eagerly):

```
backend/app/services/edgar/
  xbrl_cache.py          ← X:80–235 with a function API (record_hit/record_miss) so get_xbrl_data drops `global`
  xbrl_instance.py       ← X:238–545; _extract_from_filing_instance_sync split into ~8 phases
  xbrl_companyfacts.py   ← X:64–75 + X:850–1052; transport unchanged (execute, single wait, no breaker); parser into module functions
  xbrl_standardized.py   ← X:1054–1312 into ~9 helpers
  xbrl_sections.py       ← (X5, optional) X:548–631
  xbrl_service.py        ← imports, EdgarXBRLService with delegating methods, edgar_xbrl_service, set_identity (X:78), re-exports; ~300 lines
```

Phase maps:
- `_extract_from_filing_instance_sync` X:307–545 → resolve and gates X:320–340, result and currency
  vote X:342–366, financial-institution statement path X:368–389, duration loop X:391–435, dividends
  fallback X:437–452 (uncovered inside the extractor), statement emit + instant loop X:454–478, debt
  observations X:480–499, ADS ratio X:501–506, segments X:508–522 (always stubbed in tests), anchor
  requirement + fiscal labels + classification X:524–545. `_record_currency` closes over
  `currency_votes`; pass it explicitly.
- `_parse_company_facts` X:891–1052 → shape, `_is_target`, `_duration_penalty` X:897–932,
  `filter_and_sort` X:934–962, `select_fact_data_with_concept`/`select_fact_data` X:964–998,
  `append_items` X:1000–1027, wiring and inline lists X:1029–1050. T9 pins bucket order (:64–71),
  `period_start` on durations (:81–93), its absence on instants (:98–101), Basic-over-Diluted EPS
  (:104–113), populated liabilities and cash with the cash `raw_tag` (:116–127). Keep
  `EdgarXBRLService._parse_company_facts` as a delegating, instance-state-free method (T9:59;
  `__new__`-without-`__init__` callers at `test_copilot_citation_repair.py:145-147,277-278`).
- `extract_standardized_metrics` X:1054–1312 → guard and the two nested helpers X:1068–1110, headline
  and net margin X:1112–1143 (T9:135–149 pins `currency: None`, `raw_tag: None`, change keys),
  pass-through statement keys X:1145–1161 (T9:151–155), working capital X:1163–1187, FCF
  X:1189–1204, margins X:1206–1221, ROE/ROA operand binding X:1223–1253, reporting currency and
  per-ADS X:1255–1276, segments and debt pass-through X:1278–1292, label inheritance + financing
  source + classification X:1294–1312. No test monkeypatches anything this method reads: the safest move.

**Anchor tests to add first** (X0, tests-only):
1. Companyfacts transport with `httpx.AsyncClient` mocked: `sec_rate_limiter.execute` (not
   `execute_with_backoff`) called once, `User-Agent == EDGAR_IDENTITY`, `timeout=30.0`, non-200 →
   None, result == `_parse_company_facts(json, accession)`. Today the method is only patched away
   (`test_accession_xbrl_extraction.py:416,448`; `acceptance_archive.py:634`).
2. Sections: `_extract_sections_sync` over a fake `obj` for 10-K, 10-Q and 20-F plus the
   `_SECTION_MIN_CHARS` stub rejection; `get_filing_sections` form gate (X:830) and timeout choice
   (X:837). Zero coverage today.
3. Segment wiring inside the extractor (X:508–522) with `_extract_segments` un-stubbed.
4. Dividends component fallback inside the extractor (X:437–452).
5. `get_xbrl_data` L1 expiry branch (X:696–702) via `get_xbrl_cache_stats()` deltas.
6. Standardized label inheritance (X:1294–1304) and the two pass-throughs (X:1306–1311).

**Traps.**
- `_cache_max_size` is REBOUND as an int by `backend/tests/unit/test_two_tier_cache.py:61-62,148-150,341-343`;
  a re-export does not carry a rebinding, so X1's cache module needs a function API and those three
  sites a retarget.
- `_persisted_xbrl` is a `@staticmethod` patched on the class (`acceptance_archive.py:636-637`) and on
  instances (`test_cash_financial_applicability.py:148`); keep it a staticmethod on the class.
- Rule 5 documentation that names this file and moves with X2: `lessons/sec-edgar-resilience-layer.md:25`,
  `docs/ARCHITECTURE.md:181,185-187`, `backend/evals/RUNBOOK.md:793`, the docstring at
  `backend/app/services/copilot_service.py:1355`, `lessons/sec-runtime-facts-carry-no-duration.md:12,29`.
  Carry the breaker-exempt comment (X:29–35) with the code; `lessons/sec-edgar-resilience-layer.md:18-19`
  requires it. CLAUDE.md rule 5 needs no edit (it names no file for the fallback).
- Concept lists are behaviour (`lessons/sec-xbrl-period-selection.md:16-18`): the inline lists
  X:1036–1047 and `CASH_TAG_CANDIDATES` move byte-identical and the façade keeps
  `xbrl_service.CASH_TAG_CANDIDATES`.
- Accession and period invariants: fallback facts carry the target `accn` (X:908–913, X:979–985);
  `period_start` only from the source fact, never synthesised (X:296–304, X:1023).
- `datetime.now()` naive stamps at X:180, 207, 692, 713, 722 are not gated; leave them in a move.
- New leaf modules that call edgartools rely on `set_identity` (X:78, `client.py:49`) having run;
  importing them through the package keeps that order.
- Stale branches: see correction 7. Docs: `docs/OPERATIONS.md:230` moves with X1.

**Estimated diff size.** X0 +250–350 test lines. X1 cache: ~155 moved + ~30 API lines + 3 retargets;
`X` → ~1,160. X2 companyfacts: ~215 moved, parser into 5 functions (+40), 2 delegating methods, 6 doc
edits, the `_classify_duration` import re-pointed at `facts.concepts`; `X` → ~950. X3 standardized:
259 into ~9 helpers (+80), 1 delegating method, no retargets; `X` → ~700. X4 instance: ~308 into ~8
phase functions (+70), ~35 patch retargets in 8 test files + `acceptance_archive.py:604` +
`backfill_facts.py:79`; `X` → ~400; longest function ≤80. X5 (optional) sections ~180; `X` → ~300.

### M6 — `backend/app/services/edgar/instance_extractor.py` (1,229 lines; `IE:` below)

This module's problem is breadth, not length: 40 top-level functions, none over 69 lines, no
`__all__`, no module state beyond constants and a logger (IE:25). It makes no network calls of its
own; the fetch boundary is `filing.xbrl()` at `xbrl_service.py:337`, and IE only receives duck-typed
edgartools objects (`xb.facts.query()` IE:230 and IE:676, `by_dimension` IE:815–819,
`xb.statements.income_statement()` IE:1040–1043). Whether edgartools performs hidden I/O behind
`company.is_financial_institution()` (IE:1016–1018) is unverified from the repo; the plan treats the
module as breaker-exempt local parsing, as `docs/ARCHITECTURE.md` does.

**Responsibilities today:**

| Cluster | Functions (def range) | Constants |
|---|---|---|
| A. Core primitives (used by four other clusters) | `normalize_form` IE:180, `_iso_date` IE:185–198, `_numeric` IE:295, `_parse_decimals` IE:305, `_text_or_none` IE:590, `_resolve_period_value` IE:318–345, `_series_from_values` IE:348–369 | — |
| B. Currency | `_currency` IE:246–259, `_reporting_currency` IE:262–292 (tie-break IE:283–291) | — |
| C. Period windows | `duration_in_window` IE:201–212, `_unanimous_start` IE:443–448 | `DURATION_WINDOWS` IE:31–36 |
| D. Fact query, namespace binding | `_fact_records_with_concept` IE:220–237; `_fact_records` IE:240–243 is dead | `_CONCEPT_NAMESPACES` IE:217 |
| E. Concept registries | (data only) | `DURATION_CONCEPTS` IE:47–113, `DIVIDEND_COMPONENT_CONCEPTS` IE:119–122, `INSTANT_CONCEPTS` IE:130–153, `RICHER_*` IE:161–177 |
| F. Consolidated series | `duration_series_with_starts` IE:372–440 … `dividend_component_sum_series` IE:495–518, `instant_series_currency_concept` IE:521–558 | reads E |
| G. Debt components | `_one_undimensioned_instant_fact` IE:600–654, `debt_component_observations` IE:657–708 | `debt_concepts` import IE:23 |
| H. Segments | `_segment_fact_records` IE:805–826, `segment_series_by_member` IE:829–881 | `SEGMENT_AXIS` IE:744 |
| I. Financial-institution classification | `cash_financial_classification` IE:974–1006, `is_financial_institution` IE:1009–1026 | `FINANCIAL_SIC_LOW/HIGH` IE:907, `FINANCIAL_PROFILES` IE:913–963 |
| J. As-reported statement path | `income_statement_dataframe` IE:1029–1050, `_statement_period_columns` IE:1060–1095, `_select_statement_series` IE:1121–1160, `extract_financial_statement_metrics` IE:1187–1229 | reads `FINANCIAL_PROFILES` |

**Public surface.** `xbrl_service.py:43-58` binds 14 names by `from .instance_extractor import`.
`backend/app/services/ai/acquisition_period.py:9` imports `duration_in_window`.
`backend/evals/build_golden_set.py` lazily imports `duration_in_window` (:151),
`duration_series_with_currency` (:167, :189, :227, :251), `instant_series_with_currency` (:169) and
`DURATION_CONCEPTS` (:189, :251), and mirrors the registries by copy (:37–60, :78–104);
`backend/tests/unit/test_accession_xbrl_extraction.py:503-541` pins that mirror against
`DURATION_CONCEPTS`. Fourteen test files import it, seven of them private names (`_parse_decimals`,
`_resolve_period_value`, `_period_marker`, `_statement_period_columns`, `_truthy_flag`, `_currency`,
`_reporting_currency`: `test_accession_xbrl_extraction.py:234,245`,
`backend/tests/unit/test_financial_statement_extraction.py:14-16`, `backend/tests/unit/test_fpi_currency.py:15-16`).
Two tests read module attributes: `backend/tests/unit/test_cash_registry_consistency.py:13`
(`INSTANT_CONCEPTS`) and `backend/tests/unit/test_fi_predicate_single_source.py:12,27-29`, which
asserts `FINANCIAL_SIC_LOW/HIGH` on `app.services.edgar.instance_extractor` equal the copy in
`backend/app/services/ai/fi_signals.py:13-17`.

**Seams to cut.** The call graph is a clean fan-in on cluster A with one-way edges F→C, F→D, H→C,
J→I; no sibling in `edgar/` imports IE back (`debt_concepts.py`, `statement_parser.py`,
`fiscal_periods.py`, `financing_source.py`, `ads_ratios.py` are leaves). The only package constraint is
import order: `edgar/__init__.py:35-36` imports `.client` then `.xbrl_service`, which imports IE, so
sub-modules must use relative imports and never `from app.services.edgar import …`.

**Target layout** (sub-package; IE kept as an explicit re-export façade of all 29 public names plus
the 7 test-imported private names, so every current import path keeps working):

```
backend/app/services/edgar/instance/
  core.py                ← clusters A + B (~150 lines)
  contexts.py            ← DURATION_WINDOWS, duration_in_window, _unanimous_start
  query.py               ← _CONCEPT_NAMESPACES, _fact_records_with_concept
  concepts.py            ← cluster E registries, byte-identical order
  series.py              ← cluster F (~200)
  debt.py                ← cluster G;   segments.py ← cluster H
  financial_profiles.py  ← cluster I (keep the lazy edgartools enum import at IE:981 lazy)
  statements.py          ← cluster J (~270, the largest piece)
backend/app/services/edgar/instance_extractor.py  ← ~45-line façade
```

**Anchor tests to add first** (I0, tests-only):
1. Façade identity snapshot: for the 14 names bound at `xbrl_service.py:43-58`, assert
   `getattr(xbrl_service, n) is getattr(instance_extractor, n)`, and that the 7 private names plus
   `FINANCIAL_SIC_LOW/HIGH` resolve from the façade. This protects the monkeypatch seam (tests patch
   `xbrl_module.DURATION_CONCEPTS`, `INSTANT_CONCEPTS`, `dividend_component_sum_series`,
   `debt_component_observations` on the xbrl_service namespace).
2. `_reporting_currency` full tie-break (IE:283–291): equal period-end counts → present at the period
   of report → non-USD → alphabetical; `test_fpi_currency.py:109-122` covers only the "more periods"
   and None cases.
3. `duration_series_with_starts` `selected_sources` contract (clear-on-entry IE:389–390, row shape
   IE:427–433); today only indirect via `backend/tests/unit/test_financing_source.py:67-150`.
4. `_one_undimensioned_instant_fact`: a row without currency is never an observation even when
   `reporting_currency` is None (IE:644–645); entity whitespace normalisation (IE:647–648).
5. `_statement_period_columns`: 20-F/40-F accept `(FY)` (IE:1075) and `(end, marker)` de-dup
   (IE:1086–1090); tests cover 10-Q quarter-vs-YTD only (`test_financial_statement_extraction.py:379-400`).
6. `cash_financial_classification` outcome matrix (IE:985–1004).

**Traps.**
- Registry ORDER is tag priority and is pinned by `test_cash_registry_consistency.py:24-47` and
  `test_accession_xbrl_extraction.py:503-541`; `concepts.py` carries the lists byte-for-byte. The
  three revenue registries stay deliberately separate (correction 2).
- Keep `xbrl_service.py:43-58` as name-binding imports; switching xbrl_service to attribute access
  (`concepts.DURATION_CONCEPTS`) silently blinds the monkeypatches above.
- No case-insensitive DataFrame column lookup exists here (contrast
  `backend/app/services/ownership_extractor.py:71-75`); the NaN/NA guards at IE:187–189, 253–254,
  593–594, 635–636, 798–800, 1103–1105 are load-bearing.
- `FINANCIAL_PROFILES` is a mutable list of dicts read by clusters I and J; keep one object.
- Renaming any of the four names `build_golden_set.py` imports breaks golden-set regeneration; the move
  keeps them.
- No filename-keyed gate names this module. Docs that cite the path (prose only; keep the façade and
  they stay true): `docs/ARCHITECTURE.md:184`, `backend/docs/edgartools-best-practices.md:28`,
  `lessons/sec-xbrl-period-selection.md:7,20`, `lessons/sec-runtime-facts-carry-no-duration.md:25,30,38`.

**Estimated diff size.** I0 +150 test lines. I1 mechanical split: −1,229 / +~1,330 app lines (same
bytes plus headers and the façade), zero test edits, `xbrl_service.py:43-58` unchanged; arms
eval-baseline with an expected zero delta. I2 (optional, folded into X4): repoint xbrl_service,
build_golden_set and acquisition_period at the sub-modules (~25 lines). Deleting `_fact_records` is
a separate Wave 3 PR gated on founder item 4.

---

## The size-budget gate (rule 12)

Prose ceilings rot; this one is a test. `W0.G` adds
`backend/tests/unit/test_hot_module_size_budget.py` (tests-only: no deploy, no `eval-baseline`) with
today's sizes as ceilings. The ceilings live in one JSON file per module under
`backend/tests/unit/size_budgets/` (`copilot_service.json`, `facts_service.json`,
`trend_analysis_service.json`, `openai_service.json`, `xbrl_service.json`, `instance_extractor.json`),
so a PR that shrinks a module edits only its own budget file and the waves stay file-disjoint
(`lessons/ops-serial-merge-adjacent-line-prs.md`). Each later PR that shrinks a file or function
lowers its ceiling in the same commit (a ratchet); a PR that would grow one fails CI with a message
naming the row.

Mechanics (prototyped tonight against `da636f6`; passes with these rows, fails on a one-line pad):
`wc -l` per file; `ast` per function and method (`end_lineno - lineno + 1`, nested defs counted inside
their parent, only top-level functions and class methods budgeted); any function in a budgeted file
that is not listed is held to the **new-function ceiling of 80 lines**; any NEW module created under
`app/services/copilot/`, `app/services/facts/`, `app/services/trend_analysis/`,
`app/services/edgar/instance/`, `app/services/edgar/xbrl_*.py` or `app/services/ai/summary_*.py` is
held to **400 lines**, so bloat cannot simply move. Mutation proof for the PR body: pad one budgeted
function by one line, show the row fail, restore; pad a budgeted file by one blank line, show the
file row fail, restore (both on committed state, per `lessons/test-proofs-run-on-committed-state.md`).

| File | Ceiling (lines) | Function ceilings today |
|---|---:|---|
| `app/services/copilot_service.py` | 1,934 | `_answer_filing_question_attempt` 297; `_resolve_citations` 114 |
| `app/services/facts_service.py` | 2,153 | `normalize_companyfacts` 155; `backfill_facts` 144; `upsert_facts` 129; `reconcile_facts` 109; `remediate_industry_facts` 102; `derive_q4_eps_facts` 97; `upsert_facts_bulk` 84; `derive_same_period_metrics` 84 |
| `app/services/trend_analysis_service.py` | 1,923 | `build_observation_catalogue` 303; `build_dataset` 260; `stream_trend_narrative` 220 |
| `app/services/openai_service.py` | 1,252 | `OpenAIService.summarize_filing` 552; `OpenAIService.generate_structured_summary` 250; `OpenAIService._assemble_structured_summary` 87 |
| `app/services/edgar/xbrl_service.py` | 1,316 | `EdgarXBRLService.extract_standardized_metrics` 259; `_extract_from_filing_instance_sync` 239; `EdgarXBRLService._parse_company_facts` 162; `EdgarXBRLService.get_xbrl_data` 83 |
| `app/services/edgar/instance_extractor.py` | 1,229 | (none over 80) |

End-state targets the ratchet drives toward: façades ≤60 lines for M2 and M3, ≤300 for M5, ≈45 for
M6, ≈670–840 for M4, ≈800 for M1; every function ≤80 lines; every new module ≤400 lines.

---

## Waves (file-disjoint PRs, dependencies, triggers)

Rules that shape the order: (1) tests-only PRs never deploy and never arm `eval-baseline`, so they
run fully in parallel; until #1123 lands each still arms `copilot-eval` once when marked ready
(USD 0.06, reserved first); (2) every code-bearing PR deploys on merge and arms `eval-baseline` on
every push, draft or not, so merges are serial (one verified deploy at a time, AGENTS.md §6) and
pushes are batched (push once when the local gate is green; stay draft until review so `copilot-eval`
fires once; a second push within a run cancels the first, `.github/workflows/ci.yml:290-292`); (3) a
Code Red reservation is written before each paid trigger; (4) leaf-first: a module is moved before it
is split, and a module is split only after its anchors are green, and every Wave 1 PR also depends on
W0.G because it lowers its module's budget file; (5) PRs in one wave edit disjoint files, including
test files (anchors go in NEW test files; each module has its own budget file) and docs. The two
adjacent-line collisions that remain are `docs/ARCHITECTURE.md:181-189` (F1 edits :189, X2 edits
:181 and :185–187) and `lessons/sec-edgar-resilience-layer.md:23-25` (F1 edits :23–24, X2 edits :25):
F1 and X2 merge serially with a rebase between (`lessons/ops-serial-merge-adjacent-line-prs.md`); T3's
edit at `docs/ARCHITECTURE.md:158` is same-file only and merges cleanly.

Legend: D = deploys on merge; E = arms `eval-baseline` on every push (reservation first); CE = arms
`copilot-eval` when marked ready and on each push while ready; CE* = the same, but only until #1123
lands (its filter drops `backend/tests/**`); AST = pure-move proof required.

### Wave 0 — the gate and the anchors (tests-only, all parallel; no deploy, no `eval-baseline`)

| PR | Files | Triggers | Depends on |
|---|---|---|---|
| W0.G size-budget gate | new `backend/tests/unit/test_hot_module_size_budget.py` + six budget files under `backend/tests/unit/size_budgets/` | CE* | — |
| C0 copilot anchors (6) | new `backend/tests/unit/test_copilot_refactor_anchors.py` | CE* | — |
| F0 facts anchors (6) | new `backend/tests/unit/test_facts_refactor_anchors.py` | CE* | — |
| T0 trend anchors (5) | new `backend/tests/unit/test_trend_refactor_anchors.py` | CE* | — |
| O0 openai anchors (A1–A6) | new `backend/tests/unit/test_summarize_filing_anchors.py` + JSON fixtures under `backend/tests/fixtures/` | CE* | — |
| X0 xbrl anchors (6) | new `backend/tests/unit/test_xbrl_service_anchors.py` | CE* | — |
| I0 instance anchors (6) | new `backend/tests/unit/test_instance_extractor_anchors.py` | CE* | — |

Merging #1123 first (a workflow and one test file; no deploy; one USD 0.06 run for its own un-draft)
makes all seven free; otherwise each costs one reserved USD 0.06 run at un-draft (USD 0.42 in all).
Exit gate: all seven merged; each anchor shown to FAIL under a spot mutation of its guarded behaviour
(table in the PR body, as the 2026-07 plan did); baseline recorded {backend test count, wall time,
green SHA}. Until the hermetic-suite gate lands (founder item 2), every full local run and CI run of
the backend suite sends live requests to SEC (`tasks/todo.md:6458`); Wave 0 adds no such test.

### Wave 1 — leaf moves (code-bearing; develop in parallel, merge serially)

| PR | What | Files | Triggers | Depends on |
|---|---|---|---|---|
| I1 | M6 split into `edgar/instance/` + façade | `instance_extractor.py`, new `edgar/instance/*` | D, E, CE, AST | I0 |
| T1 | M3 leaf moves (periods, formatting, series, detectors, citations, fidelity, cache) + façade; fixes the stale `PROMPT_VERSION` comment (T:34–35) as it moves | `trend_analysis_service.py`, new `trend_analysis/*` | D, E, CE, AST | T0 |
| C1 | M1 pure moves (quotations, fact_guards, claim_repair, resolution, envelope) + façade; ~8 test re-points | `copilot_service.py`, new `copilot/*`, `test_copilot_prose_quotations.py`, `test_copilot_quotation_retry.py` | D, E, CE, AST | C0 |
| F1 | M2 leaves + transport + façade; the seven rule-5 prose edits | `facts_service.py`, new `facts/{__init__,concepts,transport}.py`, CLAUDE.md:105/152, ARCHITECTURE.md:189, ADR-0003:30, `lessons/sec-edgar-resilience-layer.md:23-24`, two agent briefs, the allowlist docstring | D, E, CE, AST | F0; merges after #1126/#1118 or rebases over them (founder item 9) |
| X1 | M5 cache → `xbrl_cache.py` with a function API; 3 test retargets; `docs/OPERATIONS.md:230` | `xbrl_service.py`, new `xbrl_cache.py`, `test_two_tier_cache.py` | D, E, CE, AST | X0 |
| O1 | M4 `summarize_filing` post-provider phases → `ai/summary_finalize.py`; `test_evidence_snap.py:231-239` redirected | `openai_service.py`, new `ai/summary_finalize.py`, `test_evidence_snap.py` | D, E, CE, AST | O0 |

Every Wave 1 PR lowers the rows in its own budget file. Merge order recommendation (smallest blast
radius first, verified deploy between each): I1 → T1 → X1 → C1 → F1 → O1. F1 and X2 (next wave) touch
adjacent lines of `docs/ARCHITECTURE.md` and of `lessons/sec-edgar-resilience-layer.md`; keep them
serial.

### Wave 2 — remaining moves and the long-function splits (serial within a module, parallel across modules)

| PR | What | Files | Triggers | Depends on |
|---|---|---|---|---|
| T2 → T3 → T4 | M3 dataset + observations; narrative + final façade (+ `docs/ARCHITECTURE.md:158`); then the three splits | M3 files only | D, E, CE (T2/T3: AST) | T1 |
| F2 → F3 → F4 | M2 companyfacts + derive (split `normalize_companyfacts`); writers + reconcile (split `upsert_facts`; re-point `test_job_reporting.py:242`); jobs + ingest + fundamentals (split `backfill_facts`; re-point `test_analysis_coverage_pool_lifetime.py:78`) | M2 files + the two named tests | D, E, CE, AST | F1 |
| X2 → X3 → X4 (→ X5) | M5 companyfacts (+ re-point the `_classify_duration` import to `facts.concepts`; the six rule-5 doc edits); standardized; instance (35 retargets, `backfill_facts.py:79`, `acceptance_archive.py:604`; folds I2's re-points, not its deletion); optional sections | X2: `xbrl_service.py`, new `xbrl_companyfacts.py`, `docs/ARCHITECTURE.md:181,185-187`, `lessons/sec-edgar-resilience-layer.md:25`, `lessons/sec-runtime-facts-carry-no-duration.md:12,29`, `backend/evals/RUNBOOK.md:793`, and the docstring that today sits at `copilot_service.py:1355` (after C1 it lives in `copilot/claim_repair.py`); X3/X4: M5 files, the retargeted tests, `scripts/backfill_facts.py` (rebase over #1121), `evals/acceptance_archive.py` | D, E, CE, AST | X1, F1 (X2 needs `facts.concepts`), I1 (X4 folds I2), C1 (the docstring's new home) |
| C2 | M1 attempt-loop decomposition in place (FactRegistry, SentinelScanner, `_admit_not_disclosed`, `_admit_answer`) | `copilot_service.py` | D, E, CE | C1 |

### Wave 3 — gated follow-ups and the ratchet

| PR | What | Gate |
|---|---|---|
| C3 | M1 prompt module (`copilot/prompt.py`: `SYSTEM_PROMPT`, sentinels, cluster A) | founder item 3 (the four copilot branches disposed) |
| O2 | M4 prompt assembly → `ai/summary_prompt.py`; A1 proves bytes identical | founder item 3 (the two codex branches with unmerged prompt bytes disposed) |
| T5, I2-del | M3 dead code (4 functions + the `compact_dataset_for_prompt` tests); M6 `_fact_records` (its re-points already rode X4) | founder item 4 |
| Docs | the four `docs/` fixes listed under Ground truth (docs-only: no deploy, no eval) | founder item 7 |
| Ratchet | final ceilings: façades and new modules at their end-state sizes | after the last split |

Spend estimate for the whole plan (founder item 1): 20–22 code-bearing PRs (Wave 1 six, Wave 2 ten
plus the optional X5, Wave 3 four); at two pushes each, ~40 `eval-baseline` runs ≈ USD 12.00 and
20–30 `copilot-eval` runs ≈ USD 1.20–1.80, plus USD 0.42 for Wave 0's un-drafts if #1123 has not
landed; about USD 13.6–14.2 in all, each run reserved first under the Code Red ledger, and less in
practice because a second push cancels an in-progress `eval-baseline` run. 20–22 serialized deploys.

---

## Founder decision points (sign off before the gated PRs)

1. **Spend and reservation protocol for the refactor.** A ceiling of about USD 15 for the paid evals
   this plan triggers, under the Code Red rule that every paid trigger is reserved first. Without a
   stated ceiling, AGENTS.md §3 treats this as "a new paid evaluation programme". Recommendation: set
   USD 20 and require one push per PR per round.
2. **Hermetic suite before Wave 1.** Eleven backend tests reach SEC and Yahoo on every full run
   (`tasks/todo.md:6458`, chief's open item). Wave 1 means ~20 CI runs plus local gates.
   Recommendation: land the outbound-network block first; otherwise say explicitly that the
   SEC-reaching runs are accepted and will be disclosed as the Code Red records do.
3. **Dispose of the stale branches** (table under Ground truth): close the two "DO NOT MERGE" copilot
   experiments and the two measurement-only openai branches; decide `claude/copilot-prompt-candidate`
   (kept on 2026-10-08) and `codex/wave3-copilot-typed-evidence` before C3; cherry-pick the one
   unlanded xbrl line and the one prompt rule from `codex/wave3-return-ratio-basis` /
   `codex/wave3-thinking-low-pilot` or close them before O2 and X2. The pick is not one line: two
   `openai_service.py` lines, prompt bytes in three `backend/prompts/*-analyst-agent.md` files and in
   `ai/xbrl_narrative.py`; it is a prompt change that needs the RUNBOOK gate and a re-pin decision.
4. **Dead-code deletions that change tests**: M3's four dead helpers plus `compact_dataset_for_prompt`
   and its four tests; M6's `_fact_records`. Recommendation: yes, as Wave 3 PRs with `rg` → 0 proofs.
5. **Where the copilot loop lives.** Recommendation: in place (C2), not `copilot/stream.py`, because a
   move changes the logger name the eval runner's withheld-answer filter listens on
   (`backend/evals/copilot_runner.py:201`) and costs five more test re-points.
6. **New-code ceilings in the gate**: 80 lines per function, 400 per new module. Recommendation: adopt;
   the only functions the plan leaves between 60 and 80 are orchestrators.
7. **A docs-only PR for the stale statements found tonight** (ARCHITECTURE.md:341 buckets, the two
   audit docs' `sleep(0.2)` rows, the unfinished-work row about `Filing.xbrl_data`). Recommendation:
   yes, any lane, no gate beyond the link check. (OPERATIONS.md:230 rides X1 and the `PROMPT_VERSION`
   comment rides T1, because those files deploy.)
8. **Merge #1123 before Wave 0.** It narrows `copilot-eval` so tests-only PRs stop arming a paid run;
   without it Wave 0 costs seven reserved USD 0.06 runs. Recommendation: merge it first.
9. **F1 rewrites CLAUDE.md rule 5's owner file name** (:105, :152) and the two engineering briefs,
   which the open agent-workflow PRs #1126 and #1118 also rewrite. Approve the rule-text edit riding
   a refactor PR, and the order: F1 after those two land (or rebased over them).

---

## Verification (how the plan's claims were checked, and how execution is verified)

**Claims (this session, 2026-10-08).** Six independent read-only analysts, one per module, produced
file:line inventories (clusters, public surface by caller, patch targets by namespace, SEC transport
sites, eval triggers, traps, anchor gaps, diff estimates) and answered a fixed list of true/false
claims each; the plan author spot-checked the load-bearing ones (dead-code callers by `git grep`, the
router bindings, the T9 bucket pin, the source-text pin in `test_evidence_snap.py`, the private
imports in `scripts/backfill_facts.py`, the compat shim). Three adversarial lenses then re-verified the
whole document against the code (citations: every file:line resolves and says what the plan says;
sequencing: dependencies, open branches, Code Red, deploy and eval triggers; gates and locks: anchors,
locked tests, allowlists, monkeypatch bindings, the size-gate numbers), and one independent reviewer
read the full plan; their corrections are folded in above and listed in the PR body.

**Per-PR gates (binding on every execution agent):**
- Backend: from `backend/`, `ruff check . && bandit -r app -ll && python -m pytest` before every push
  (AGENTS.md §8), plus `python -m pytest -m performance` when a PR touches streaming code (M1, M3, M4).
- Pure moves carry the AST per-symbol proof (`lessons/test-pure-move-ast-proof.md`), run on committed
  state; zero undisclosed deltas or the "pure move" claim is false. Reviewers re-run the proof.
- Prompt bytes: C1/C3 prove `SYSTEM_PROMPT` sha256 and `_build_messages` equality; T1–T4 prove the
  selection messages (anchor T0.2); O1/O2 prove `create_kwargs` (anchor A1). An intentional byte change
  is a RUNBOOK event (`backend/evals/RUNBOOK.md:530-535`) and never rides a refactor PR.
- Every code-bearing PR writes its Code Red reservation before its first push and reads the
  `eval-baseline` report (expected: zero delta) before merge; after merge, the deploy log and
  `/health/detailed` are checked before the next merge (AGENTS.md §5–§6).
- Locked tests (rule 6): the harness, T1, T2, T5, T9 and the rest of the inventory are byte-identical
  in every PR; the only sanctioned edits are the explicit re-points named in this plan, which are all
  in ordinary unit tests.
- The size-budget gate's ceilings move down in the same commit as the code that shrinks them; a PR
  that needs a ceiling raised stops and says why.
- Stop conditions: an anchor fails for a reason the PR did not intend; a locked test needs an edit; a
  patch target the plan did not list goes blind; the AST proof shows an undisclosed delta; the
  `eval-baseline` report shows a non-zero delta on a pure move. Stop, report, re-plan.

**Payoff.** Six files of 1,229–2,153 lines become façades of 45–840 lines over 35 cohesive modules
of ≤400 lines; the twenty functions over 80 lines become ≤80 (the 552-line `summarize_filing` becomes
a 70-line orchestrator); every refactor PR is behaviour-preserving by proof, not by assertion; and
the gate keeps it that way.

---

## On approval

Persist this document as `tasks/refactor-plan-2026-10.md` (this PR), then begin **Wave 0** with the
size-budget gate PR as the first unit of work, followed by the six anchor PRs in parallel. Record
every deviation in the Implementation Notes section above.
