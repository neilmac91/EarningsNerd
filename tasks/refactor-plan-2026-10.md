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

Main moved by three commits after the plan was written (`1868ddf8`, `4c0563ad`, `76d45732`: two Code
Red records and the hermetic test gate). The plan was re-checked against `76d45732` on 2026-10-09; no
module, test file or document it cites changed except as item 9 under [What changed](#what-changed-from-the-inherited-premises-verified-corrections-folded-in)
records, and the three statements those commits affect are corrected in place.

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

- **2026-10-09, decisions.** The founder delegated the open decisions (items 1 and 3–9) to the plan's
  author with full authority; each is decided under [Founder decisions](#founder-decisions-decided-2026-10-09)
  with the options weighed, on evidence re-checked against main at `76d45732`. Three decisions change
  the plan as first proposed, and the sections below are updated to match: spend (decision 1: the
  refactor's own ceiling and log, not the Code Red ledger), dead code (decision 4: deleted before the
  moves, as T-dead and I-dead in Wave 1, with the test edits corrected) and ceiling raises (decision 6:
  a file ceiling is raised by the PR author with a recorded reason; the long-function ceilings are
  frozen inside the gate).
- **Spend log** (decision 1; every paid run a PR of this plan fires, at its measured cost):

| Date | PR | Head | Run | Job | Cost (USD) | Running total |
|---|---|---|---|---|---:|---:|
| — | — | — | — | — | — | 0.00 |

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
   them populated. The "fix pending" bullet in `docs/ARCHITECTURE.md:341` is stale (decision 7 fixes it).
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
   The `copilot_service.py` hunks of `claude/copilot-prompt-candidate`, `claude/g-stage1-arm-c`,
   `claude/g-stage2-arm-b` and `codex/wave3-copilot-typed-evidence` all fall inside `SYSTEM_PROMPT`
   (`backend/app/services/copilot_service.py:101-174`); `copilot-prompt-candidate` also carries a
   `test_copilot_live_regressions.py` change and review-evidence artefacts, and `typed-evidence` a
   `tasks/todo.md` edit. The router binds `answer_filing_question`,
   `snapshot_filing` and `PROVIDER_STARTED_STAGE` by name (`backend/app/routers/summaries.py:45`),
   and the locked T5 anchor patches `answer_filing_question` on the ROUTER's namespace
   (`backend/tests/unit/test_expired_trial_gating.py:279,295`), so the router must keep its
   module-global name and bare-name call (`backend/app/routers/summaries.py:550`).
6. **None of the six stale `openai_service.py` branches touches `summarize_filing`.** They land in
   `generate_structured_summary`'s prompt region (`backend/app/services/openai_service.py:293-384,412,427,428`)
   and the import blocks (:21-25, :84-87). Two are measurement-only reverts of #899, one is
   superseded by #899, one is already main's text; only `codex/wave3-return-ratio-basis` and
   `codex/wave3-thinking-low-pilot` carry unmerged changes, and those are not one line: an import of
   `return_ratio_basis` after :22 plus the rule at :428 that interpolates it, and unlanded prompt bytes
   in `backend/prompts/10k-analyst-agent.md`, `10q-analyst-agent.md`, `20f-analyst-agent.md` and
   `backend/app/services/ai/xbrl_narrative.py` (their three-dot diffs also touch `ai/cash_claims.py`,
   `ai/debt_scope.py`, `ai/markdown_render.py`, `financial_basis.py`, `summary_schema.py` and
   `summary_versioning.py`, landed status unchecked). Picking any of it is a prompt change under the
   RUNBOOK gate; decision 3 leaves it unpicked.
7. **The two codex xbrl branches would revert #1122 if rebased naively.** Their one unlanded line is
   the tuple at `backend/app/services/edgar/xbrl_service.py:464` gaining `"shareholders_equity",
   "total_assets"`; the rest of their hunk is on main (`:1243-1251`), and a two-dot diff shows they
   would put `asyncio.to_thread` back where `run_owned_sync` now is (`:37`, `:680`). Cherry-pick the
   one line or close them; never rebase them onto a split.
8. **The eval cost figure lives in AGENTS.md, not the RUNBOOK.** "an `eval-baseline` run is about
   USD 0.30" is [AGENTS.md](../AGENTS.md) §3 (line 54); the RUNBOOK gives only the call count for
   the comparison harness (`backend/evals/RUNBOOK.md:162`). The `copilot-eval` reservation figure,
   USD 0.06, is the Code Red ledger's (`tasks/code-red-20261004/runtime/control/DECISIONS-16.md:152-153`).
   Record 18 has since measured four `eval-baseline` runs at USD 0.35–0.36 each and reserves every
   push that fires it at the dearest run × 2, rounded up, USD 0.73
   (`tasks/code-red-20261004/runtime/control/DECISIONS-18.md:119-127`); the spend figures below use the
   measured cost.
9. **Main moved after the plan was written** (three commits on 2026-10-09: `1868ddf8` record 17,
   `4c0563ad` the hermetic test gate (#1145), `76d45732` record 18). Re-checked against `76d45732`:
   no module, test file or document this plan cites changed, except that CLAUDE.md gained the gate's
   description at :162-164 (below the lines cited), the Code Red checkpoint's reservation rule now
   sits at `tasks/code-red-20261004/runtime/CHECKPOINT.md:373`, and `tasks/todo.md`'s hermetic item
   is ticked at :6486. Folded in: decision 2 is resolved; the Wave 0 exit text drops the
   SEC-reaching caveat; D3 stage 2 is implemented and held, not "not drafted yet"; the
   `eval-baseline` cost and reservation above.

---

## Ground truth (verified)

### Triggers every PR in this plan must price in

| Trigger | Fires when | Cost or effect | Source |
|---|---|---|---|
| Cloud Run deploy | a merge to `main` changes any `backend/` path outside `backend/tests/` | deploys the API service and refreshes the jobs; one unverified deploy at a time, so code-bearing merges are serial | `.github/workflows/ci.yml:533-546` (detector), `backend/tests/unit/test_backend_deploy_scope.py`, [AGENTS.md](../AGENTS.md) §6 |
| `eval-baseline` (summary eval, paid) | every `pull_request` event, draft or not, whose diff touches `backend/app/*`, `backend/evals/*` or `backend/prompts/*`; also manual dispatch | measured at USD 0.35–0.36 per run (four runs, record 18; AGENTS.md says 0.30) and ~6 min; advisory (`continue-on-error`), but the report must be read before an AI-relevant merge | `.github/workflows/ci.yml:282-336`, `backend/evals/RUNBOOK.md:339-345`, [AGENTS.md](../AGENTS.md) §3, `tasks/code-red-20261004/runtime/control/DECISIONS-18.md:119-127` |
| `copilot-eval` (paid) | a non-draft PR whose diff touches `backend/**`; re-runs on each push while ready | measured USD 0.006–0.026 per run (settled Code Red runs: `tasks/code-red-20261004/runtime/control/DECISIONS-09.md:149`, `tasks/code-red-20261004/runtime/control/DECISIONS-18.md:168-169`); the Code Red reserves 0.06 | `.github/workflows/copilot-eval.yml:3-8,20`; `tasks/code-red-20261004/runtime/control/DECISIONS-16.md:152-159` |
| This plan's spend rule (decision 1) | before any paid run a PR of this plan fires | read the provider balance first (`.github/workflows/deepseek-balance.yml`, a dispatch that makes no inference call), then log each paid run at its measured cost in the Spend log; programme ceiling USD 18 | [AGENTS.md](../AGENTS.md) §3; decision 1 |
| Code Red ledger reservation (Code Red PRs only) | before any paid trigger the Code Red chief, its officers or its workers fire | "every paid action still needs a reservation written first" (`copilot-eval` USD 0.06 per run, `eval-baseline` USD 0.73 per push); the chief is the ledger's only writer, and its USD 25 ceiling is shared by the chief, officers and workers; other writers' paid runs are not in it | `tasks/code-red-20261004/runtime/CHECKPOINT.md:373`; `tasks/code-red-20261004/runtime/control/LEDGER-ACCESS.md:47,65-66`; `tasks/code-red-20261004/runtime/control/DECISIONS-18.md:121-124` |

Open draft PR #1123 narrows `copilot-eval` to the eval's import closure (`backend/app/services/**`,
`models/**`, `schemas/**`, `utils/**`, `backend/app/*`, prompts, golden set, requirements). Every
module in this plan lives under `backend/app/services/`, so #1123 does not spare the code-bearing
PRs; it does spare tests-only PRs. Tests-only PRs never arm `eval-baseline` and never deploy, but on
today's main they still arm `copilot-eval` once each when marked ready for review (`backend/**`;
measured USD 0.006–0.026 a run). Wave 0 does not wait for #1123 (decision 8): its seven un-drafts
cost about USD 0.10 at measured rates, logged under decision 1, and nothing if #1123 lands first.

### Open branches and PRs that touch these modules

Eight PRs are open on 2026-10-08 (#1133, #1132, #1126, #1123, #1121, #1118, #1035, #1009); none
changes any of the six modules (checked file by file). Re-checked on 2026-10-09 against `76d45732`:
25 PRs are open and still none changes the six modules; the only branches that do are the ten in the
table below, all evidence-only by decision 3. Two of them collide with files this plan
edits: the heads of #1126 and #1118 (`claude/agent-workflow-gates`, `claude/agent-workflow-cost`)
rewrite the CLAUDE.md hunk at lines 149–165, which contains the rule-5 line F1 edits (:152), and touch
the engineering brief F1 edits (`backend-developer.md`, at its lines 7–8, a different hunk from F1's :30); the head of #1121 (`codex/wave3-email-setup`) edits
`backend/scripts/backfill_facts.py` at lines X4 does not touch (:145, :185 vs :79). So F1 merges after
the two agent-workflow PRs or rebases over them, and X4 rebases over #1121. Remote branches that do
touch the six modules, measured as `git diff origin/main...origin/<branch>`:

| Branch | Module | Hunk | Disposition for this plan |
|---|---|---|---|
| `claude/copilot-prompt-candidate` (kept by founder decision of 2026-10-08, PR #1130) | M1 | +5/−2 inside `SYSTEM_PROMPT`; also test and `tasks/review-evidence/` files | evidence only (decision 3): its PR #1074 closed as measurement-only, never merging (`tasks/pr-disposition-2026-10-07.md:46,212`) |
| `claude/g-stage1-arm-c`, `claude/g-stage2-arm-b` ("DO NOT MERGE" experiments) | M1 | 1–5 lines inside `SYSTEM_PROMPT` | evidence only (decision 3); never merges |
| `codex/wave3-copilot-typed-evidence` | M1 | +8/−1 inside `SYSTEM_PROMPT` | evidence only (decision 3); never merges |
| `codex/measure-n-control-2`, `codex/wave3-e8-n-pilot` ("MEASUREMENT ONLY") | M4 | 27-line revert of #899 in `generate_structured_summary` | evidence only (decision 3); never merges |
| `codex/wave3-supported-financial-explanations`, `codex/wave3-segment-margin-basis` | M4 | superseded by #899 / already main's text (#932) | evidence only (decision 3); never merges |
| `codex/wave3-return-ratio-basis`, `codex/wave3-thinking-low-pilot` | M4, M5 | two unlanded `openai_service.py` lines (import after :22, rule :428), unlanded prompt bytes in the three `backend/prompts/` analyst prompts (10k, 10q, 20f) and `ai/xbrl_narrative.py`, one tuple line at `xbrl_service.py:464`; would revert #1122 | evidence only (decision 3): candidate r's deterministic half landed as #1039, its model-facing half is held; any revival is a fresh prompt PR under the RUNBOOK gate |

### Code Red D3 stage 2 is file-disjoint

Stage 2 makes the insider endpoint fit the 1 req/s edgartools budget and pins the API service
(`tasks/code-red-20261004/runtime/control/DECISIONS-16.md:135-150`). The founder chose option A, "guard, then
pin" (`tasks/code-red-20261004/runtime/control/DECISIONS-17.md:149-157,255-263`): one code PR with the
insider endpoint behind a server-side switch (off unless set), the always-failing fuzzy-search fallback
deleted, both SEC pins on the API service, a deploy step that prints the variable-driven switches, the
budget gate rewritten for the pinned fleet, and docs. It is implemented and three-lens- and delta-reviewed
with no blocker (`tasks/code-red-20261004/runtime/control/DECISIONS-18.md:77-118`); it went up on 2026-10-09 as
#1151 (`claude/vigilant-goodall-633yx3`) and merges only after the founder moves `backfill-facts-weekly`
to Monday 07:30 (:173–176). Its 20 files, read from the PR: `.github/workflows/ci.yml` and `ops.yml`,
`backend/app/config.py`, `backend/app/routers/insiders.py` and `internal.py`,
`backend/app/services/edgar/client.py` and `compat.py`, `backend/app/services/notable_filings_service.py`,
`backend/docs/plan_sec_pipeline.md`, six test files, `docs/CONFIGURATION.md`, `docs/DEPLOYMENT.md`,
`docs/OPERATIONS.md`, `frontend/lib/featureFlags.ts` and `tasks/gcp-deploy-runbook.md`. None of the
six modules is among them, and no PR in this plan edits those files except `docs/OPERATIONS.md`, where
X1's cache lines (:228–232) are a different hunk, so X1 rebases over it. One citation moves when #1151
merges: it removes 11 net lines from `edgar/compat.py` above the shim, so the shim's citations
(`:532–582`) read 11 lower afterwards. The couplings are runtime and procedural only: the same
4-thread edgar pool and breaker, and the one-deploy-at-a-time rule, so #1151's deploy and a Wave 1
deploy never overlap.

### Locked contract tests (rule 6) that bind to these modules

Three locked artifacts bind to the six modules: the harness and T9 by name, T5 through the router.
The Stripe tests (`backend/tests/unit/test_subscription_webhook_sync.py` and
`backend/tests/unit/test_stripe_webhook.py`) bind none.

- `backend/tests/support/summary_stream_harness.py:50-58` (imported by fourteen test files, among
  them T1, T2, the T3 successor, T5 and T8; `tests/integration/test_summary_stream_heartbeat.py:81,180,245`
  patches the same singleton attribute directly) patches
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
| M2 → M5, lazy | `backend/app/services/facts_service.py:690,759` import `edgar.compat.xbrl_service` | no module-level edge either way; `facts/concepts.py` must never import `app.services.edgar` at module level (a `forbidden_imports` row from F1), and `facts/__init__.py` must not eagerly import a module that does |
| M1 → M4, import time | `backend/app/services/copilot_service.py:44-47` binds the singleton | over 40 sites (eight copilot test files and the eval runner) patch `copilot_service.openai_service.stream_chat_with_tools` on the singleton object; safe under any move that calls the singleton's attribute at call time |
| M3 → M4, lazy | `backend/app/services/trend_analysis_service.py:1728` | `backend/tests/unit/test_copilot_cost.py:177` swaps the module attribute and relies on this laziness |
| `peers_service.py:22` → M2 PRIVATE | imports `_unit_for` at module level | façade re-export |
| `backend/scripts/backfill_facts.py:60,79` → M2, M5 PRIVATE | `_fetch_companyfacts_sync`, `_extract_from_filing_instance_sync` | façade re-exports or a one-line re-point in X4 |
| `backend/evals/copilot_scorers.py:34-41` → M1 PRIVATE | four adjacency guards and two public names | façade re-exports |
| `backend/evals/build_golden_set.py:151,167-170,189,227,251` → M6 | lazy imports of four names | the move keeps the names; renaming any breaks golden-set regeneration |

### Stale documentation found tonight (not edited: this PR carries only this file)

`docs/ARCHITECTURE.md:341` (buckets "fix pending", see correction 1);
`docs/audit-2026-09/03-data-platform.md:106,125,180,198` and
`docs/audit-2026-09/06-unfinished-work-inventory.md:59` (still describe the pre-fix un-metered
companyfacts fetcher; :106 names the 0.2 s sleep);
`docs/audit-2026-09/06-unfinished-work-inventory.md:60` (says persisted `Filing.xbrl_data` is never
read; `xbrl_service.py:680` reads it). Decision 7 fixes the living one, `docs/ARCHITECTURE.md`, in a
docs-only PR and leaves the audit appendices as written: each is a dated report "reproduced as
written" (`docs/audit-2026-09/03-data-platform.md:3`), and none of their rows has been updated since
2026-09-06. Two more statements ride code PRs: `docs/OPERATIONS.md:230` ("In xbrl_service.py
`_cache_max_size`") is accurate today (`backend/app/services/edgar/xbrl_service.py:98`) and goes stale
only when X1 moves the cache, so X1 edits it; the stale `PROMPT_VERSION` comment at
`backend/app/services/trend_analysis_service.py:34-40` (its v2–v4 bump notes) sits in a file that
deploys, so T1 fixes it as it moves `PROMPT_VERSION`.

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
| A. Source and prompt assembly | `_select_source_text` C:177–182, `snapshot_filing` C:185–223, `_without_source_durations` C:276–286, `_compact_xbrl_block` C:289–309, `_build_context_message` C:312–348, `_merge_consecutive_roles` C:351–368, `_build_messages` C:371–392 | `SYSTEM_PROMPT` C:101–174 (f-string over the sentinels at C:69–74 and `_MIN_VERIFIABLE_LEN`, imported at C:50); `settings.COPILOT_CONTEXT_CHAR_CAP` C:321, `COPILOT_HISTORY_TURNS` C:379, `COPILOT_HISTORY_ITEM_CHAR_CAP` C:388; the 8,000-char cap C:309 |
| B. Fact provenance and identity | `_reporting_currency` C:226–229, `_valid_fact_provenance` C:232–266, `_fact_identity` C:269–273 | `copilot_tools.canonical_unit` C:228, C:246 |
| C. Envelope parsing | `_parse_citations` C:395–443, `_parse_followups` C:446–473 | `_FOLLOWUPS_RE` C:75; raises `_UnpublishableAnswer` C:93 |
| D. Citation verification | `section_label_is_quoted` C:482–484, `_verify_citations` C:487–533 | `_QUOTE_MARK_RE` C:543 (an E constant), provenance helpers imported at C:49–55, `_RegenerableEvidenceMismatch` C:97 |
| E. Prose quotation admission | `_markdown_parser` C:598–607 … `_withhold_unsupported_quotations` C:942–952 (C:536–952, ~417 lines with constants) | the import-time singleton `_MARKDOWN` C:610, `_MARKDOWN_BLOCKS` C:616, caps C:549–560; `normalize_for_match` C:929/936 |
| F. Activity labels | `_safe_activity_label` C:955–967 | `copilot_tools._CONCEPT_LABELS` C:964, `describe_tool_call` C:967 |
| G. Fact-marker adjacency guards | `_claim_span_start` C:979, `_adjacency_window` C:986, `_fact_matches_adjacent_number` C:991–1051, `_fact_matches_adjacent_currency` C:1061–1083, `_fact_matches_adjacent_concept` C:1133–1157 | `_NUMBER_TOKEN` C:973–976, `_CURRENCY_*` C:1055–1058, `_CONCEPT_SYNONYMS` C:1091–1117, `_CONCEPT_PATTERNS` C:1122–1125 |
| H. Server-owned uncited-claim repair | `_is_annual_report_form` C:1235–1236, `_iso_day` C:1239–1247, `_plan_uncited_fact_citation` C:1250–1286, `_repair_paired_annual_claim` C:1300–1344, `_fact_certifies_claim` C:1347–1389, `_repair_uncited_fact_claim` C:1392–1421 | `_ANNUAL_FIGURE_CLAIM` C:1209–1220 and `_PAIRED_ANNUAL_CLAIM` C:1291–1297 (built from its `.pattern`, must move together); `copilot_tools.run_tool` C:1320/1405 |
| I. Coverage telemetry | `count_uncited_figures` C:1424–1472 | `_NUMBER_TOKEN`, `_claim_span_start` |
| J. Marker resolution | `_resolve_citations` C:1475–1588 | `_COPILOT_MARKER_RE` C:76, the G matchers C:1535–1537, `copilot_tools.fact_to_citation` C:1556 |
| K. Orchestration | `answer_filing_question` C:1591–1635, `_answer_filing_question_attempt` C:1638–1934 | `PROVIDER_STARTED_STAGE` C:78, `_PUBLICATION_ERROR` C:77, `_STREAM_FAILURE` C:79, `_EVIDENCE_RETRY_GUIDANCE` C:84–90, `openai_service` + sentinels C:44–48, `monotonic` C:35, `chat_deadline` C:43, `settings.COPILOT_MAX_TOKENS` C:1713 |

**Public surface.** The router imports `PROVIDER_STARTED_STAGE`, `answer_filing_question` and
`snapshot_filing` by name (`backend/app/routers/summaries.py:45`; used at :557, :550, :475).
`backend/evals/copilot_runner.py` imports `snapshot_filing`, `_UnpublishableAnswer`, `logger`,
`answer_filing_question`, `openai_service` and `_build_messages` inside functions (:170, :194,
:221, :313); it installs a logging filter on `copilot_service.logger` (:201–205) that recognises
withheld attempts by `_UnpublishableAnswer`. `backend/evals/copilot_scorers.py:34-41` imports the
four G guards plus `count_uncited_figures` and `section_label_is_quoted`. Eleven test files bind the
module object and eight import names directly, three doing both (for example
`acquisition_period_cases.py:12` `_build_messages`; `test_copilot_prose_quotations.py:43-50` four caps
and two E functions; `test_copilot_gate.py:451` the exception and the logger).

**Seams to cut.** K is the only cluster with edges into the others (A, B, C, D, E, F, H, I, J); H
depends on B and G; J and I depend on G; D reads one E constant. A, C, F and G have no inbound edges
except from K. So E, B+G, H, J+I and C+D+exceptions are each a clean leaf package module, and the
only decision is where the loop lives. Recommendation: keep `answer_filing_question` and the loop in
`copilot_service.py` (in-place decomposition, C2), because moving them changes the logger name the
eval runner filters on (C:1624 warning, `copilot_runner.py:201`) and forces five more test re-points.

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
  prompt.py        ← (C3) SYSTEM_PROMPT, sentinels, _EVIDENCE_RETRY_GUIDANCE, cluster A
  __init__.py      ← empty
backend/app/services/copilot_service.py  ← answer_filing_question + the attempt loop (decomposed in place) + re-exports; ≈ 750 lines after C1, ≈ 800 after C2
```

Phase map of `_answer_filing_question_attempt` (C:1638–1934) for C2: P0 messages C:1657–1659; P1
tool binding C:1666–1691 (`used_facts`, `_register_fact`, `_run_tool`) → a ~30-line `FactRegistry`
over cluster B; P2 progress and provider open C:1693–1717; P3 delta loop C:1718–1792 (error sentinel
:1726–1728, provider-start :1730–1732, activity events :1736–1749, heartbeat on `monotonic()`
:1751–1753, sentinel scan with `_SENTINEL_TAIL` hold-back :1764–1791) → a pure `SentinelScanner.feed`
(~30 lines) with the yields staying in the generator; P4 usage and tail flush C:1794–1798; P5
not-disclosed admission C:1800–1833 → `_admit_not_disclosed` (~21 lines); P6–P11 join, parse, expand
markers, verify, repair/resolve (C:1868–1894), final checks, markdown quotation gate, telemetry
(C:1835–1914) → one async `_admit_answer` (~75 lines); P12 complete event C:1915–1926; P13 exception
policy and `provider_stream.aclose()` C:1927–1934. Result: the loop drops from 297 to ≤80 lines.

**Anchor tests to add first** (C0, tests-only; existing strong pins: the publication boundary at
`backend/tests/unit/test_copilot.py:505` with its case names :486–504 and builder `_publication_case`
:338–483, the retry suite in `test_copilot_quotation_retry.py`, repair in
`test_copilot_citation_repair.py:90-617`):
1. `_compact_xbrl_block` caps at 8,000 chars (C:289–309); no test pins the cap.
2. `_safe_activity_label` fallback strings (C:955–967): unknown tool → "Reading financial
   information"; unknown concept → `concept=None`. The no-leak behaviour is pinned through it
   (`test_copilot.py:529-531,591`, happy path :1369–1397); only the fallback strings are not.
3. Heartbeat: patch `copilot_service.monotonic` (the loop stays in place, so the seam survives C1
   and C2), drive the clock so only the third chunk crosses 3 s, and assert exactly one extra
   `{"type":"progress","stage":"reading"}` (C:1751–1753). `test_copilot.py:519` only patches the clock;
   its assertions (:587, :591) stay green if those three lines are deleted, and C2 reshapes them.
4. A failure before the attempt starts (C:1603–1606, `_select_source_text` raising) yields one
   `{"type":"error","message":_STREAM_FAILURE}` (C:1633–1635); `test_copilot.py:1262-1281` drives the
   same handler only from inside the attempt.
Already covered, no anchor needed: `_register_fact` dedupe (`test_copilot_provenance.py:113-133`),
the `_verify_citations` matrix (`test_copilot_quotation_retry.py:78-159,185-230`).

**Traps.**
- Patch bindings that survive a move because they bind to shared objects: over 40 sites on the
  `openai_service` singleton (`stream_chat_with_tools`, in eight copilot test files and the eval
  runner) and 25 on the `copilot_tools` module object
  (`run_tool`); new modules must keep calling `copilot_tools.run_tool` and `openai_service.<attr>` as
  attributes at call time.
- Patch bindings on the `copilot_service` MODULE namespace that go blind when the reading code
  moves (C1): `normalize_for_match` (`test_copilot_quotation_retry.py:123`, `test_copilot_prose_quotations.py:841`),
  and in `test_copilot_prose_quotations.py` also `_rendered_text` (:1219), `_MARKDOWN_BLOCKS` (:1229),
  `_MARKDOWN`/`_markdown_parser` (:1318) and the `__file__` exec at :1292 (the thread-safety test
  re-executes the file). Bindings that SURVIVE because the loop stays in place and is their only
  reader: `_withhold_unsupported_quotations` (`test_copilot_prose_quotations.py:1134`; read at
  C:1822, C:1900), `_resolve_citations` (`test_copilot_paired_claims.py:59`; read at C:1879, C:1891),
  `monotonic` (`test_copilot.py:519`), the `openai_service` name (`test_copilot_cost.py:167`,
  `test_copilot_provenance.py:166`): do not re-point them, a re-point would blind them.
- Source-level gates that go red at C1 and need a same-PR edit: `test_copilot.py:322-336` parses
  `inspect.getsource(copilot_service)` and looks for `_verify_citations` (:331), which moves to
  `envelope.py`; `test_copilot_prose_quotations.py:178-185` counts reads of `_MIN_QUOTED_LEN` in the
  façade source (its only read is C:931, cluster E) and asserts `copilot_service.verify_whole_excerpt_in_text`
  identity. C1 re-points about ten lines in three files; keeping the loop in place avoids the rest.
- Names tests read off the façade that the move must keep exporting: `_display_may_differ`
  (`test_copilot_prose_quotations.py:703,768`), `_UNICODE_SPACES` (:728), `_ANNUAL_DURATION_DAYS`
  (`test_copilot_citation_repair.py:339-340`), `verify_whole_excerpt_in_text` (:185); the `names`
  list in the budget file gates the whole set.
- The router must keep the bare-name call (`backend/app/routers/summaries.py:550`) because T5 patches
  the router's name; never switch it to `copilot_service.answer_filing_question(...)`.
- `SYSTEM_PROMPT` bytes: a pure move keeps them identical iff the interpolated constants keep their
  values; prove with a sha256 of `SYSTEM_PROMPT` and equality of `_build_messages(snap, source, q,
  None)` before/after (the runner records exactly that, `backend/evals/copilot_runner.py:337`).
  C3 (moving the prompt) waits on no branch: decision 3 makes the four evidence-only.
- No SEC transport, no module state mutated at runtime; the only import-time singleton is the
  markdown parser (C:610). No filename-keyed allowlist names this module; the `rglob` gates
  auto-cover new files.

**Estimated diff size.** C0 +150–250 test lines. C1 pure moves: −1,225/+1,225 across five new
modules plus ~100 lines of imports and re-exports; ~10 test re-points in three files; optional re-point of
`copilot_scorers.py:34-41`; AST per-symbol proof. C2 in-place decomposition: net +40–60 lines, loop
297 → ≤80. C3: ~250 lines moved.

### M2 — `backend/app/services/facts_service.py` (2,153 lines; `F:` below)

**Responsibilities today** (36 top-level functions + 6 nested closures; no classes; every import of
`app.services.edgar`, `httpx`, `settings` and `sec_rate_limiter` is lazy at F:690, F:759,
F:1905–1909, F:1952):

| Cluster | Functions (def range) | State used |
|---|---|---|
| A. Per-filing normalization (pure) | `_parse_date` F:101, `_fiscal_period` F:112, `_duration_start` F:119, `_unit_for` F:130–141, `normalize_standardized_to_facts` F:144–211 | `_CONCEPT_UNITS` F:47–84 |
| B. Reconciliation and authoritative cross-check | `reconcile_facts` F:214–322, `_prior_values` F:325–349, `extract_authoritative_values` F:373–424, `cross_check_facts` F:427–469 | `NON_NEGATIVE_CONCEPTS` F:89–94, `HEADLINE_GAAP_TAGS` F:358–367 |
| C. SEC companyfacts transport | `_fetch_companyfacts_sync` F:477–509, `_running_loop_in_this_thread` F:512, `_fetch_companyfacts_async` F:1898–1926 | `COMPANYFACTS_SYNC_TIMEOUT_SECONDS` F:474 |
| D. Per-filing writer | `_lock_fact_companies` F:519–525, `upsert_facts` F:528–656, `process_filing_facts` F:659–718 | lazy `edgar.compat.xbrl_service` F:690 |
| E. Jobs | `backfill_facts` F:721–864, `remediate_industry_facts` F:867–968, `backfill_company_sic` F:971–1041, `sync_companyfacts_batch` F:2100–2153 | `AFFECTED_FINANCIAL_CONCEPTS` F:38–41 |
| F. Read model | `_fundamentals_payload` F:1044–1068, `get_filing_fundamentals` F:1071–1105 | — |
| G. Companyfacts normalization and period labelling | `_classify_duration` F:1205–1215, `_collect_companyfacts_values` F:1218–1290, `_fiscal_year_windows` F:1293–1309, `_label_quarters` F:1315–1355, `normalize_companyfacts` F:1358–1512, `_is_financial_sic` F:1929–1932 | `COMPANYFACTS_DURATION_TAGS` F:1140–1176, `COMPANYFACTS_INSTANT_TAGS` F:1178–1198, windows F:1129–1131 |
| H. Derived facts | `_matching_ytd9` F:1515–1542, `derive_q4_facts` F:1545–1606, `derive_q4_eps_facts` F:1627–1723, `derive_same_period_metrics` F:1726–1809 | `_EPS_SHARES_TAGS` F:1611–1617 |
| I. Bulk writer | `upsert_facts_bulk` F:1812–1895 | shares `_lock_fact_companies` (F:1829) |
| J. Ingest and in-flight dedup | `_companyfacts_fresh_result` F:1942–1968, `_persist_companyfacts_payload` F:1971–1993 (owns the ingest path's one commit, F:1984), `ingest_companyfacts` F:1996–2037, `ingest_companyfacts_by_id` F:2040–2097 | `_inflight_syncs` F:1938 (per-process dict of `asyncio.Event`) |

**Public surface.** Twelve importing files; nine bind the module object (`from app.services import
facts_service`) and three import names directly (`peers_service.py:22`, `edgar/xbrl_service.py:1002`,
`evals/copilot_bootstrap.py:101`): `ingest_companyfacts_by_id` (`backend/app/routers/analysis.py:92`,
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
`sec_rate_limiter.execute_with_backoff` F:1922, URL from `companyfacts_url` F:1914, User-Agent from
`settings.SEC_USER_AGENT` F:1911, no breaker). It can move to `facts/transport.py` without changing
the request path (same limiter singleton, same URL helper, same backoff ladder, same loop bridge
F:491–506), and the file carries no `sec.gov` literal, so `backend/tests/unit/test_sec_gov_importers_allowlist.py`
needs no new entry. What must change in the same PR is the prose that names the owner by file:
[CLAUDE.md](../CLAUDE.md) rule 5 (lines 105 and 152), `docs/ARCHITECTURE.md:189`,
`docs/adr/0003-edgartools-for-sec-data.md:30`, `lessons/sec-edgar-resilience-layer.md:23-24`,
`.claude/agents/engineering/backend-developer.md:30`, and the allowlist test's docstring
(`test_sec_gov_importers_allowlist.py:5`); `.claude/agents/engineering/database-specialist.md:25`
names no transport owner and stays true for the façade.

**Target layout** (`facts_service.py` becomes a ≤60-line façade re-exporting every name above,
including the private ones production and tests import, and the SAME `_inflight_syncs` dict object):

```
backend/app/services/facts/
  concepts.py      ← cluster A helpers, _classify_duration, _is_financial_sic, every registry and constant
                     (F:38–98, 358–370, 1129–1202, 1312, 1611–1624); byte-identical tuples; never imports edgar at module level
  reconcile.py     ← cluster B
  transport.py     ← cluster C (the rule-5 owner; the prose updates above ride this PR)
  upsert.py        ← normalize_standardized_to_facts, _lock_fact_companies, upsert_facts (split), process_filing_facts, upsert_facts_bulk
  companyfacts.py  ← cluster G minus the leaves; normalize_companyfacts (split)
  derive.py        ← cluster H
  ingest.py        ← cluster J (owns _inflight_syncs)
  jobs.py          ← cluster E; backfill_facts (split);   fundamentals.py ← cluster F
  __init__.py      ← empty (the cycle rule below depends on it)
```

Phase maps (each step ≤80 lines):
- `normalize_companyfacts` F:1358–1512 → root and IFRS meta F:1374–1380, duration collection
  F:1382–1389, instant collection F:1391–1395, windows and labels with `_base_fact` lifted to top level
  F:1397–1415, duration rows F:1417–1438, instant rows F:1440–1460, transient shares +
  `derive_q4_eps_facts` F:1464–1482 (after `derive_q4_facts` F:1462), hard-reject before
  `derive_same_period_metrics` F:1484–1499 (ordering pinned by `backend/tests/unit/test_companyfacts_ingest.py:216`),
  identity dedup F:1501–1512.
- `backfill_facts` F:721–864 → fetcher resolution and query F:758–780, counters F:782–791, extract
  F:792–799, per-company authoritative cache and demotion guard F:800–819, process and dry-run
  rollback F:821–829, stats and audit log F:830–849, stats shape F:851–864 (pinned by
  `backend/tests/unit/test_facts_service.py:737`).
- `upsert_facts` F:528–656 → lock, gate and cross-check F:564–579, counters and prefetch F:581–588,
  identity hit or flag-only repair F:589–616, `flags_only` F:617–619, current-row query and
  `newer_filing` predicate F:621–641, demote and insert F:642–646, commit and result keys F:648–656.

**Anchor tests to add first** (F0, tests-only):
1. `backfill_facts` default fetcher: with `companyfacts_fetcher=None, cross_check=True` it calls the
   module's `_fetch_companyfacts_sync` once per company and caches by company (F:763, F:804–809);
   every existing call injects a fetcher or disables the cross-check (`test_facts_service.py:548-885`).
2. `_fetch_companyfacts_sync` edge branches: inside a running loop → None without touching the
   limiter (F:493–496); `FuturesTimeoutError` → cancel and None (F:502–505). `TestCompanyfactsSyncBridge`
   (`test_facts_service.py:1175-1292`) covers the other seven branches.
3. `remediate_industry_facts` atomic rollback when `process_filing_facts` raises after the delete
   (F:947–962); `TestRemediateIndustryFacts` (:1002–1097) covers replace, dry-run and None-skip only.
4. `sync_companyfacts_batch` per-company failure handling and cohort precedence (F:2100–2153); it is
   only ever patched today (`backend/tests/unit/test_internal_durable_tasks.py:203`).
5. `normalize_companyfacts` in-batch identity dedup, first wins (F:1502–1512).
6. `extract_authoritative_values` restatement tie-break (`<=` at F:420).
Already covered, do not duplicate: untied-companyfacts preservation and newer-amendment protection
(`backend/tests/unit/test_data_completeness.py:324,439`), NULL-twin demotion (:263), the ordered
`FOR NO KEY UPDATE` lock compiled against the postgresql dialect for both writers (:420–435),
dry-run and flags-only (`test_facts_service.py:608-736`).

**Traps.**
- Monkeypatch targets that bind to module globals at call time: `backend/tests/unit/test_job_reporting.py:242`
  patches `facts_service.process_filing_facts` and expects `backfill_facts` (F:824) to see it;
  `backend/tests/unit/test_analysis_coverage_pool_lifetime.py:78` patches
  `facts_service._fetch_companyfacts_async` and expects `ingest_companyfacts_by_id` (F:2082) to see
  it; :81 and :140 call `facts_service._inflight_syncs.clear()` in place. After the split each needs a
  one-line re-point to the module that READS the name (`facts.jobs` for `backfill_facts`,
  `facts.ingest` for the ingest path) in the PR that moves the reader (F4), and `ingest.py` must own
  the one `_inflight_syncs` object the façade re-exports.
- `test_facts_service.py:1278-1292` reads the URL off `request_fn.__closure__` by the free-variable
  name `url`; the `_get` closure (F:1916) must keep that name.
- Commit ownership is per function and must not move: `upsert_facts` F:648–649,
  `process_filing_facts` (passes `commit=False` at F:710, commits rows and stamp together at
  F:716–717), `backfill_facts` (delegates through `commit=not dry_run` at F:826 and rolls back dry
  runs at F:829), `remediate_industry_facts` F:957/959, `backfill_company_sic` (toggles
  `expire_on_commit` at F:1008–1009, batch commits at F:1035/1038, restores at F:1040),
  `upsert_facts_bulk` F:1893–1894, `_persist_companyfacts_payload` F:1984 (the ingest path's single
  commit); `sync_companyfacts_batch` owns no commit, only the `expire_on_commit` toggle
  F:2130–2131/2152 and the per-company rollback F:2139.
- Import cycle: `backend/app/services/edgar/__init__.py:35-36` eagerly loads `client` and
  `xbrl_service`; `xbrl_service.py:1002` lazily imports facts_service; facts_service imports edgar only
  lazily. `facts/concepts.py` must never import `app.services.edgar` at module level.
- `datetime.now(timezone.utc)` at F:715, F:1954, F:1983 is not the `utcnow()` helper but is not
  flagged by the naive-utcnow gate (it matches `.utcnow` attribute calls only); leave it in a pure move.
- Eval triggers: facts rows do not feed the summary prompt (no `FinancialFact` reference in
  `services/ai/`, `openai_service.py` or `summary_pipeline.py`), but they ARE model-facing for the
  copilot (`backend/app/services/copilot_tools.py:234-236,269-276`; `backend/evals/copilot_bootstrap.py:101`
  seeds them). A pure move changes no row bytes.

**Estimated diff size.** F0 +150–200 test lines. F1 leaves + transport + façade (+ the six prose
edits): ~300 moved, ~50 added; `F` → ~1,850. F2 companyfacts + derive with the `normalize_companyfacts`
split: ~600 moved, ~60 added; `F` → ~1,250. F3 writers + reconcile with the `upsert_facts` split:
~520 moved, ~50 added, 1–2 patch-target edits; `F` → ~730. F4 jobs + ingest + fundamentals with the
`backfill_facts` split: ~700 moved, ~60 added, three patch-target edits; `F` → ≤60. Nine new modules
plus an empty `__init__.py`; the three named splits bring their functions to ≤80, while
`reconcile_facts` 109, `remediate_industry_facts` 102, `derive_q4_eps_facts` 97, `upsert_facts_bulk`
84 and `derive_same_period_metrics` 84 keep ratchet rows re-keyed to their new modules unless a Wave 3
S-PR splits them.

### M3 — `backend/app/services/trend_analysis_service.py` (1,923 lines; `T:` below)

**Responsibilities today** (52 top-level functions + 1 class; the "57" counts 5 nested defs at
T:366, 946, 1247, 1255, 1667):

| Cluster | Functions (def range) | Notes |
|---|---|---|
| A. Period keys, labels, coverage | `parse_period_key` T:126–136, `available_periods` T:148–215 | constants `PROMPT_VERSION` T:41, `DATASET_CONCEPT_ORDER` T:72, `_CORE_REVENUE_CONCEPTS` T:145 |
| B. Dataset grid and growth math | `_growth` T:228, `_cagr` T:248, `build_dataset` T:271–530, `dataset_fingerprint` T:739–743, `marker_index` T:1322–1351 | reads `settings.ANALYSIS_MAX_ANNUAL_PERIODS` T:331, `ANALYSIS_MAX_QUARTERLY_PERIODS` T:359 |
| C. Detectors | `detect_growth_deceleration` T:546–588 … `detect_inflections` T:726–733 | `_DETECTORS` T:717–723; `detect_inflections` swallows detector exceptions (untested) |
| D. Formatting | `_format_value` T:746, `_pct_str` T:799, `_fmt_growth` T:803, `_ratio_threshold_value` T:844 | `compact_dataset_for_prompt` T:756–796 is NOT on the live prompt path (the stream sends `compact_observation_catalogue`, T:1810); only tests call it (`backend/tests/unit/test_trend_analysis_service.py:854,883,977,1000`) |
| E. Observation catalogue and selection | `TrendObservation` T:830–836, `build_observation_catalogue` T:935–1237, `parse_observation_selection` T:1264–1284, `render_observation_selection` T:1287–1311 | `ANALYSIS_SECTIONS` T:816–823; order is load-bearing (first-wins dedup T:953–956 inside `add`, order-dependent `required` T:1064–1066 and T:1151–1153, fallback to `section_items[0]` T:1304–1306) and the catalogue text IS the prompt's user message (T:1807–1814) |
| F. Citations | `_point_citation` T:1366–1399, `resolve_narrative_citations` T:1402–1447 | `_illegal_refs` T:1450–1460 is dead |
| G. Numeric-fidelity scan | `scan_numeric_fidelity` T:1539–1579 | `_mismatch_details` T:1582 and `_retry_instruction` T:1593 are dead; `NOT_ENOUGH_DATA_SENTINEL` T:1356 unused |
| H. Cache and persistence | `_load_cached_analysis` T:1616, `has_cached_analysis` T:1630–1640, `_persist_analysis` T:1643–1701 | owns its own `SessionLocal()` T:1665; commits at T:1684/1692/1695; swallows failures to `None` T:1697–1699 |
| I. Narrative streaming | `stream_trend_narrative` T:1704–1923 (async generator) | lazy imports T:1727–1729 (`SessionLocal`, `STREAM_ERROR_SENTINEL` + `openai_service`, `get_named_prompt`) |

Dead code (zero callers in `app/`, `evals/`, `scripts/` by `git grep`): `_illegal_refs`,
`_mismatch_details`, `_retry_instruction`, `NOT_ENOUGH_DATA_SENTINEL`.

**Public surface.** One app importer: `backend/app/routers/analysis.py:39`
(`from app.services import facts_service, trend_analysis_service`), which looks up `available_periods`
(:158, :170), `build_dataset` (:207, :237), `has_cached_analysis` (:357), `stream_trend_narrative`
(:374) and `PROMPT_VERSION` (:441) on the module object at call time. No module under `backend/evals/` imports
it. Three test files bind the module object (`backend/tests/unit/test_trend_analysis_service.py:16`,
`backend/tests/unit/test_analysis_stream.py:16`, `backend/tests/unit/test_data_completeness.py:21`)
and read 26 distinct attributes off it (23 in the first file alone), including the privates `_growth`,
`_fmt_growth`, `_pp_delta`, `_point_citation`, `_cagr`, `_has_minimum_analysis_data` and `NOT_MEANINGFUL`.

**Seams to cut.** The one tangle is B→C→E→A: detectors (C) call `_growth_operand_markers` (E, T:571),
which calls `parse_period_key` (A, T:909). Cutting a `series.py` (`_series_map` T:536,
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
  __init__.py      ← empty
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
  loop T:1824–1877 (keeps `openai_service.stream_chat(...)` T:1847–1852, sentinel handling T:1853–1857,
  `merge_chat_usage` T:1866), publication T:1879–1890, persistence + complete event T:1892–1923.

**Anchor tests to add first** (T0, tests-only):
1. Catalogue order snapshot: pin the literal `[(id, section, required), …]` list of
   `build_observation_catalogue` on the `TestCodeOwnedObservations._dataset` fixture
   (`test_trend_analysis_service.py:200-238`); today's tests assert sentence membership only (:240–447).
2. Selection prompt bytes: drive `stream_trend_narrative` through `_drain`
   (`test_analysis_stream.py:196-206`) and pin the sha256 of both provider messages; only the retry
   substring is pinned today (:418–421). A byte change here is a `PROMPT_VERSION` event under
   `backend/evals/RUNBOOK.md:959-971`.
3. `dataset_fingerprint` hex for a literal dataset; `test_trend_analysis_service.py:933-958` pins
   determinism and inequality only, and a `json.dumps` change at T:742 would silently invalidate every
   cached row (the fingerprint comparison is T:1753).
4. A raising detector does not break `build_dataset` (the swallow at T:726–733 has no test).
5. Exact key sets of the fresh (T:1906–1923) and cached (T:1761–1774) complete events.
6. `_persist_analysis` regenerates in place: two calls for one key keep the same `row.id` with new
   `narrative_md` and `prompt_version` (T:1643–1701); the router's PDF export relies on that id
   stability (`backend/app/routers/analysis.py:438-449`) and nothing pins it.
Already covered, no anchor needed: marker ordering (`test_trend_analysis_service.py:549-569,831-857`),
CAGR window, pp deltas, derived-Q4 badging (`:602,622,641-858`), coverage shape (`:510-532`).

**Traps.**
- Keep the router's call-time lookups: tests patch those names on the router's module attribute
  (`test_analysis_stream.py:597-612,729-731,755`; `backend/tests/unit/test_excel_export.py:323-327,354`;
  `backend/tests/unit/test_durable_request_ownership.py:29-32`).
- Keep `openai_service` and `SessionLocal` lazily imported inside the narrative (T:1727–1729) and
  cache (T:1662) units: `test_copilot_cost.py:177` patches `openai_service.openai_service` on the
  module and `test_data_completeness.py:31` patches `database.SessionLocal`; a hoisted import in
  `narrative.py` goes blind to both.
- Keep this out of `app/services/ai/`: the façade convention in `docs/ARCHITECTURE.md:171-176` is
  per domain (`test_llm_no_pii.py:44-45` walks only that package's direct children for a bound
  `User`, which a sub-package would not even trigger, so the gate is not the reason).
- Eval triggers: no prompt bytes live here except the user-message literals (T:1804–1813,
  T:1826–1834); the system prompt is `backend/prompts/trends-analyst-agent.md` loaded via
  `backend/app/services/prompt_loader.py:118-131` (path resolved relative to the loader, so moving
  `T` cannot change it). A pure move keeps the selector byte-identical; the AST per-symbol diff plus
  anchor 2 prove it.
- No SEC transport, no datetime calls, no module-level mutable state (constants only, T:41–123, 145,
  225, 717, 816–826, 1356–1363, 1468–1483).
- Docs to touch: `docs/ARCHITECTURE.md:158` (catalog row; T3 updates it with the final façade). The
  comment at `backend/app/models/trend_analysis.py:32` names `trend_analysis_service.PROMPT_VERSION`,
  which the façade keeps re-exporting, so it stays true and needs no edit.

**Estimated diff size.** T0 +130–180 test lines. T1 leaf moves (periods, formatting, series,
detectors, citations, fidelity, cache + façade) ±800, `T` → ~1,150. T2 dataset + observations ±870,
`T` → ~330. T3 narrative + final façade and docs ±300, `T` → ~60. T4 the three splits inside the new
modules: +70/−30, +100/−40, +90/−40. T-dead (decision 4; Wave 1, before T1; deletes the two
`TestPromptRendering` tests and two trailing assertions) about −130.

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
| `summarize_filing` | O:682–1233 (552 lines) | post-provider finalization; uses `self.` on exactly four lines (O:704, O:808, O:859 twice, O:1000) |

Phase map of `summarize_filing` (every phase after P0 is post-provider, so none emits prompt bytes):
P0 primary extraction O:702–709 → P0b error envelope O:711–734 → P1 strip, taxonomy and table
guards O:735–761 → P2 risk projection O:762–782 → P3 forward-quote gate O:784–800 → P3b attribution
gate and the one side provider call `self._verify_attributions` O:801–816 → P4 source binders and
evidence snap O:818–886 (flags `EVIDENCE_SNAP_MIN_SCORE` O:852, `AI_EVIDENCE_SNAP` O:853) → P5
coverage snapshot O:887–921 → P6 compat strings with the nested `_stringify` O:923–958 → P7 render
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
pin at `backend/tests/unit/test_filing_only_inputs.py:89-117`, the forwarding pin at :121–145, and all
~28 `summarize_filing` patch sites keep working). Move the post-provider phases into `ai/summary_finalize.py` as functions
over a `SummaryRun` dataclass, 1:1 with the phase map; pass the four `self` dependencies in as
arguments (`layout = self._SECTION_LAYOUT[...]`, `fallback_render = self._build_structured_markdown`),
pass `snap_evidence` in the same way from the façade's module binding (so the spy at
`backend/tests/unit/test_statement_relationship_integration.py:357-368` keeps seeing it without
`ai/` importing the façade), and keep `await self._verify_attributions` in the orchestrator. The decomposition is prompt-identical
by construction, which keeps the baseline pin valid (`backend/evals/RUNBOOK.md:530-535`). Optionally
(O2) move prompt assembly O:261–456 to `ai/summary_prompt.py` with `schema_template` as a module
constant, proven byte-identical by anchor A1.

**Target layout:**

```
backend/app/services/ai/summary_finalize.py   ← SummaryRun + one function per phase P0b–P12 (≤80 lines each; ~520 lines); P3b's `await self._verify_attributions` and the P13 return stay in the orchestrator
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
- A3 error envelope (O:717–734) for a non-timeout extraction failure: `message`, `summary_title`,
  `sections == []`, the insights and the legacy keys; `backend/tests/unit/test_eval_attempt_diagnostics.py:291-323`
  already pins status, code and detail, and timeout propagation is pinned by
  `test_filing_only_inputs.py:121-145` and `backend/tests/unit/test_provider_resilience.py:615`.
- A4 status and message thresholds (O:1184–1207: 0.5, 0.7; no sections and zero covered sections → "error", O:1199).
- A5 title derivation (O:1047–1061).
- A6 aliasing invariant: `result["raw_summary"]["sections"] is result["raw_summary"]["structured"]["sections"]`
  and no `_`-prefixed top-level key inside `raw_summary["structured"]` (the nested
  `sections["_risk_source_projection"]`, O:782, is the sanctioned exception); the in-place binders
  depend on it (O:754–755, O:787–790, O:875–882).

**Traps.**
- `backend/tests/unit/test_evidence_snap.py:231-239` reads `openai_service.py` as TEXT and asserts
  five literals with their exact indentation (O:848, O:853–855, O:832, O:550, O:1020). O1 must redirect that
  test in the same PR (an ordinary unit test, not a locked anchor). `backend/tests/unit/test_verbatim_contract.py:19-21`
  reads the same file as text too, for the prompt literals at O:321–434 ("VERBATIM COPYING" O:433,
  "COPY, don't COMPOSE" O:434): it survives O1 and goes red at O2, which must redirect it.
- MRO: `_request_content` (`backend/app/services/ai/provider_requests.py:210`) calls
  `self._stream_collect` (:290), which calls `self._partial_markdown_preview` (O:601); keep these
  `self.` calls, never module functions.
- `client`: nine `create` patches and 13 direct `service.client = …` assignments mean the request
  must stay `self.client.chat.completions.create` (`provider_requests.py:238,298`, O:577).
- `get_prompt` and `snap_evidence` are monkeypatched on the façade module
  (`test_sixk_variant_wiring.py:30,36,55-57`; `backend/tests/unit/test_statement_relationship_integration.py:251,357-362`);
  the orchestrator must keep calling them by the façade's binding, or those tests get a one-line
  re-point in the same PR.
- Usage accounting fires at provider start inside `_request_content` (`signal_provider_start()`
  `provider_requests.py:288`, armed by `summary_pipeline.py:1010-1014`); the ContextVars are
  task-local, so phases must stay in the same task. The one threadpool hop (O:848) carries no provider call.
- `@bounded_summary` (O:222, O:681) shares one deadline ContextVar (`provider_requests.py:80-87`);
  `summarize_filing` must keep re-raising `asyncio.TimeoutError` (O:711–713) so the pipeline's
  deterministic fallback runs.
- In-place mutation order: `sections_info` is one object shared by `structured_summary["sections"]`
  (O:749), the render envelope (O:988) and `raw_summary["sections"]` (O:1012); private keys are popped
  in order (O:765, O:832, O:869, O:873, O:977–985) before embedding at O:1011. Phases must not copy or reorder.
- `ai/summary_finalize.py` must not import `summary_pipeline` or `summary_generation_service` (both
  import the façade: cycle) and must not bind a `User` name (`test_llm_no_pii.py:35-49` walks
  `app.services.ai` with `hasattr(mod, "User")`; keeping `app.models` out of it is the simple way).
- Open branches: see correction 6. O1 never conflicts with them; decision 3 makes them evidence-only, so O2 waits on none of them.
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
| A. Two-tier cache | `_get_cache_lock` X:113–123, `clear_xbrl_cache` X:126–136, `async_clear_xbrl_cache` X:139–146 (tests only), `_cache_set_sync` X:149–197, `get_xbrl_cache_stats` X:200–235 | state X:90–110 (`_XBRL_CACHE_VERSION` "v6", `_xbrl_cache`, `_cache_max_size`, counters, lazy loop-bound lock); `get_xbrl_data` mutates the counters through `global` X:676 |
| B. Filing-instance extraction (sync, executor-run) | `_extract_segments` X:238–293, `_source_duration` X:296–304, `_extract_from_filing_instance_sync` X:307–545 | run by `_fetch_from_filing_instance` X:802–815 under `run_in_executor_with_timeout` X:809–812; deliberately breaker-exempt (comment X:29–35, S4 review finding 2); network inside the lambda = `resolve_filing_by_accession` X:320 and edgartools `filing.xbrl()` X:337 |
| C. Sections extraction | `_extract_sections_sync` X:553–631 | run by `get_filing_sections` X:817–848 (form gate :829–831, 30s/40s timeout :837); zero unit coverage |
| D. Service class | `EdgarXBRLService` X:634–1312: `get_xbrl_data` X:646–728, `get_filing_sections` X:817–848, `extract_standardized_metrics` X:1054–1312 | singleton `edgar_xbrl_service` X:1316 |
| E. Persisted-snapshot-first and orchestration | `_persisted_xbrl` X:731–755 (`@staticmethod`, own `SessionLocal`), `_get_from_redis` X:757, `_set_to_redis` X:766, `_fetch_xbrl_data` X:775–800 | `run_owned_sync(self._persisted_xbrl, …)` X:680 (`backend/app/services/request_work.py:95-108`); never move it under the 4-thread edgar pool |
| F. Companyfacts fallback transport and parser | `_fallback_to_company_facts` X:850–889, `_parse_company_facts` X:891–1052 | `sec_rate_limiter.execute` single wait X:883, no breaker (comment X:868–872); `CASH_TAG_CANDIDATES` X:69–75; inline concept lists X:1036–1047; lazy `_classify_duration` X:1002; neither method uses instance state (the transport delegates to `self._parse_company_facts` at X:885) |

**Public surface.** `edgar/__init__.py:36-40` re-exports `EdgarXBRLService`, `edgar_xbrl_service`,
`clear_xbrl_cache`, `get_xbrl_cache_stats` (`__all__` :50–83); `backend/app/routers/admin.py:22,559,562,583`
and `backend/app/services/metrics_service.py:91` use the last two; `backend/app/services/edgar/compat.py:21`
wraps the singleton as `XBRLServiceCompat` (:532–577, instance :582), which `summary_pipeline.py:36`,
`backend/app/routers/summaries.py:646-647`, `facts_service.py:690-692,759-761`, `backend/evals/runner.py:107`
and `backend/evals/copilot_bootstrap.py:100-106` import. The private `_extract_from_filing_instance_sync`
is imported by `backend/scripts/backfill_facts.py:79` and eight test files; `_extract_segments` by
`backend/tests/unit/test_segment_extraction.py:9`; `CASH_TAG_CANDIDATES` by
`backend/tests/unit/test_cash_registry_consistency.py:31,40`.

**Seams to cut.** Clusters A, B, C and F are each self-contained; D and E stay together as the
service. The riskiest cut is B, because about 30 test sites in seven files (27 single-line patches
plus three multi-line helpers) patch names on the MODULE namespace that B
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
  vote X:342–367, financial-institution statement path X:368–389, duration loop X:391–435, dividends
  fallback X:437–452 (uncovered inside the extractor), statement emit + instant loop X:454–478, debt
  observations X:480–499, ADS ratio X:501–506, segments X:508–519 (always stubbed in tests), anchor
  requirement + fiscal labels + classification X:521–545. `_record_currency` closes over
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
   (`test_accession_xbrl_extraction.py:416,430,448`; `acceptance_archive.py:630`).
2. Sections: `_extract_sections_sync` over a fake `obj` for 10-K, 10-Q and 20-F plus the
   `_SECTION_MIN_CHARS` stub rejection; `get_filing_sections` form gate (X:830) and timeout choice
   (X:837). Zero coverage today.
3. Segment wiring inside the extractor (X:508–522) with `_extract_segments` un-stubbed.
4. Dividends component fallback inside the extractor (X:437–452).
5. `get_xbrl_data` L1 expiry branch (X:698–702) via `get_xbrl_cache_stats()` deltas.
6. Standardized label inheritance (X:1294–1305) and the two pass-throughs (X:1306–1311).

**Traps.**
- `_cache_max_size` is REBOUND as an int by `backend/tests/unit/test_two_tier_cache.py:61-62,148-150,341-343`;
  a re-export does not carry a rebinding, so X1's cache module needs a function API and those sites a
  retarget, together with the from-import of the name at :16 (read at :58, :336; restored at
  :80/:159/:364).
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
- Accession and period invariants: fallback facts carry the target `accn` (X:908–913, X:979–986);
  `period_start` only from the source fact, never synthesised (X:296–304, X:1025).
- `datetime.now()` naive stamps at X:180, 207, 692, 713, 722 are not gated; leave them in a move.
- New leaf modules that call edgartools rely on `set_identity` (X:78, `client.py:49`) having run;
  importing them through the package keeps that order.
- Stale branches: see correction 7. Docs: `docs/OPERATIONS.md:230` moves with X1.

**Estimated diff size.** X0 +250–350 test lines. X1 cache: ~155 moved + ~30 API lines + 3 retargets;
`X` → ~1,160. X2 companyfacts: ~215 moved, parser into 5 functions (+40), 2 delegating methods, 6 doc
edits, the `_classify_duration` import re-pointed at `facts.concepts`; `X` → ~950. X3 standardized:
259 into ~9 helpers (+80), 1 delegating method, no retargets; `X` → ~700. X4 instance: ~308 into ~8
phase functions (+70), about 30 patch retargets in 7 test files + `acceptance_archive.py:604` (which
must then patch both `xbrl_service` and `xbrl_instance`, because `tests/unit/test_acceptance_archive.py:130,147`
read the frozen binding it installs, and whose channel classifier at `acceptance_archive.py:381-387`
keys on the frame function NAMES `_extract_from_filing_instance_sync` and `_extract_sections_sync`,
so the orchestrators keep those exact names) + `backfill_facts.py:79`; `X` → ~400; longest function
83 (`get_xbrl_data`, a ratchet row). X5 (optional) sections ~85 (~115 with `get_filing_sections`);
`X` → ~300.

### M6 — `backend/app/services/edgar/instance_extractor.py` (1,229 lines; `IE:` below)

This module's problem is breadth, not length: 40 top-level functions, none over 69 lines, no
`__all__`, no module state beyond constants and a logger (IE:25). It makes no network calls of its
own; the fetch boundary is `filing.xbrl()` at `xbrl_service.py:337`, and IE only receives duck-typed
edgartools objects (`xb.facts.query()` IE:231, IE:682 and IE:816, `by_dimension` IE:815–819,
`xb.statements.income_statement()` IE:1038). Whether edgartools performs hidden I/O behind
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
`duration_series_with_currency` (:168, :189, :227, :251), `instant_series_with_currency` (:169) and
`DURATION_CONCEPTS` (:189, :251), and mirrors the registries by copy (:37–67, :78–104);
`backend/tests/unit/test_accession_xbrl_extraction.py:503-541` pins that mirror against
`DURATION_CONCEPTS`. Fourteen test files import it; three of them import seven private names (`_parse_decimals`,
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

**Target layout** (sub-package; IE kept as an explicit re-export façade of the 27 public names it
defines, the two it re-imports from `debt_concepts`, plus
the 7 test-imported private names, so every current import path keeps working):

```
backend/app/services/edgar/instance/
  core.py                ← clusters A + B + C + D (~215 lines: primitives, currency, DURATION_WINDOWS/duration_in_window, _CONCEPT_NAMESPACES/_fact_records_with_concept)
  concepts.py            ← cluster E registries, byte-identical order
  series.py              ← cluster F (~200)
  debt.py                ← cluster G;   segments.py ← cluster H
  financial_profiles.py  ← cluster I (keep the lazy edgartools enum import at IE:981 lazy)
  statements.py          ← cluster J (~270, the largest piece)
  __init__.py            ← empty
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
3. `duration_series_with_starts` `selected_sources` contract (clear-on-entry IE:397–398, row shape
   IE:434–438); today only indirect via `backend/tests/unit/test_financing_source.py:67-150`.
4. `_one_undimensioned_instant_fact`: a row without currency is never an observation even when
   `reporting_currency` is None (IE:644–645); entity whitespace normalisation (IE:648–650).
5. `_statement_period_columns`: 20-F/40-F accept `(FY)` (IE:1072, IE:1081–1083) and `(end, marker)`
   de-dup (IE:1089–1092); tests cover 10-Q quarter-vs-YTD only (`test_financial_statement_extraction.py:379-400`).
Already covered, no anchor needed: the `cash_financial_classification` outcome matrix
(`backend/tests/unit/test_cash_financial_applicability.py:24-45,48-56`).

**Traps.**
- Registry ORDER is tag priority and is pinned by `test_cash_registry_consistency.py:24-47` and
  `test_accession_xbrl_extraction.py:503-541`; `concepts.py` carries the lists byte-for-byte. The
  three revenue registries stay deliberately separate (correction 2).
- Keep `xbrl_service.py:43-58` as name-binding imports; switching xbrl_service to attribute access
  (`concepts.DURATION_CONCEPTS`) silently blinds the monkeypatches above.
- No case-insensitive DataFrame column lookup exists here (contrast
  `backend/app/services/ownership_extractor.py:71-75`); the NaN/NA guards at IE:191–194, 253–256,
  593–594, 798–800 and 1105–1108, and the instant-type check at IE:635–636, are load-bearing.
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
I-dead, a separate Wave 1 PR that lands before I1 (decision 4).

---

## The size-budget gate (rule 12)

Prose ceilings rot; this one is a test. `W0.G` adds
`backend/tests/unit/test_hot_module_size_budget.py` (tests-only: no deploy, no `eval-baseline`) with
today's sizes as ceilings. The ceilings live in one JSON file per module under
`backend/tests/fixtures/size_budgets/` (`copilot_service.json`, `facts_service.json`,
`trend_analysis_service.json`, `openai_service.json`, `xbrl_service.json`, `instance_extractor.json`),
so a PR that shrinks a module edits only its own budget file and the waves stay file-disjoint
(`lessons/ops-serial-merge-adjacent-line-prs.md`). Each file has five keys: `files` (path → ceiling),
`functions` (`path::name` or `path::Class.name` → ceiling), `names` (the base file's top-level names
at `da636f6`, each mapped to the sub-module that defines it after its move, `null` until moved),
`forbidden_imports` (list of [file glob, forbidden module prefix]) and `note` (free text; every raised
ceiling records a dated line here: the PR, the row, old → new and why extraction was not possible
in that PR; decision 6). Each later
PR that shrinks a file or function lowers its ceiling in the same commit (a ratchet); a PR that would
grow one fails CI with a message naming the row. The twenty long-function rows are also frozen
inside the test itself at their W0.G values, keyed by `name` or `Class.name` so a re-key keeps the
freeze: a JSON row above its frozen value fails, so raising one means editing the gate (decision 6). A move PR re-keys a function row to its destination
path at the same number (a re-key is not a raise); a row whose function is absent from its file fails
as stale; a function in a new module with no row is held to 80.

Mechanics (prototyped tonight against `da636f6`; passes with these rows, fails on a one-line pad):
file size = the count of `\n` bytes (what `wc -l` prints); function size = `end_lineno - lineno + 1`
for every `ast.FunctionDef` AND `ast.AsyncFunctionDef` that is a direct child of the module or of a
module-level class, counted from the `def`/`async def` line with decorators excluded, physical lines
including blanks, comments and docstring (six of the twenty rows are `async def`, including the largest,
`summarize_filing` at 552, and four of the eight rows over 200 lines; two carry `@bounded_summary`,
which must not be counted); nested defs and lambdas count
inside their parent and have no row; classes have no row; the key is `name` or `Class.name`. Any
function in a budgeted file that is not listed is held to the **new-function ceiling of 80 lines**
(ten unlisted functions sit at 60–79 today, `_extract_sections_sync` at 79). Any NEW module, meaning
a path under `app/services/copilot/`, `app/services/facts/`, `app/services/trend_analysis/`,
`app/services/edgar/instance/`, or one of `edgar/xbrl_cache.py`, `edgar/xbrl_instance.py`,
`edgar/xbrl_companyfacts.py`, `edgar/xbrl_standardized.py`, `edgar/xbrl_sections.py`,
`ai/summary_finalize.py`, `ai/summary_prompt.py` (none of the eleven locations exists at `da636f6`,
so "new" needs no list; a glob such as `xbrl_*.py` would match the existing 1,316-line `xbrl_service.py`
and be red on day one), is held to **600 lines** (the largest planned modules, `copilot/quotations.py` at ~417 and
`ai/summary_finalize.py` at ~520, fit; functions ≤80 still bound bloat), so bloat cannot simply move.
The gate also asserts the ratchet is not stale: a ceiling more than 100 file lines or 20 function
lines above the actual size fails with "lower the ceiling". Each budget file also carries a
`forbidden_imports` list of (file glob, forbidden module prefix) pairs that the same test enforces
with an AST walk over every import statement in the file, lazy imports inside functions included
(dynamic `importlib` calls are a stated limit) (empty at W0.G; F1 adds `app/services/facts/concepts.py →
app.services.edgar`, X1 adds the five named `edgar/xbrl_*` modules → `app.services.edgar.xbrl_service`, I1
adds `app/services/edgar/instance/* → app.services.edgar.xbrl_service` and the absolute
`app.services.edgar` package import), so the plan's own never-rules are gates, not prose
(`lessons/arch-structural-gates-over-prose-rules.md`). The walk resolves `ImportFrom.level` against
the importing file's package before matching, because the package uses relative imports
(`backend/app/services/edgar/xbrl_service.py:43`, `backend/app/services/edgar/instance_extractor.py:23`)
and the new sub-modules must (M6 seams): `from ..xbrl_service import x` in `edgar/instance/core.py`
counts as `app.services.edgar.xbrl_service`, and `from .. import xbrl_service` counts as both the
package and the module; an absolute-prefix match alone would leave the three rows as prose. W0.G also checks in the AST per-symbol move
proof as `backend/tests/support/ast_move_proof.py` (tests-only, so it does not deploy), which every
pure-move PR and its reviewers run. Mutation proof for the PR body (one, per AGENTS.md §4): pad one
budgeted function by one line on committed state, show the row fail, restore
(`lessons/test-proofs-run-on-committed-state.md`); each `forbidden_imports` row gets its own proof
when it lands, written in the relative form the package uses (F1: `from ..edgar import compat` in
`facts/concepts.py`; X1: `from .xbrl_service import get_xbrl_data` in `edgar/xbrl_cache.py`; I1:
`from ..xbrl_service import get_xbrl_data` in `edgar/instance/core.py`), on committed state, shown
failing, then restored.

| File | Ceiling (lines) | Function ceilings today |
|---|---:|---|
| `app/services/copilot_service.py` | 1,934 | `_answer_filing_question_attempt` 297; `_resolve_citations` 114 |
| `app/services/facts_service.py` | 2,153 | `normalize_companyfacts` 155; `backfill_facts` 144; `upsert_facts` 129; `reconcile_facts` 109; `remediate_industry_facts` 102; `derive_q4_eps_facts` 97; `upsert_facts_bulk` 84; `derive_same_period_metrics` 84 |
| `app/services/trend_analysis_service.py` | 1,923 | `build_observation_catalogue` 303; `build_dataset` 260; `stream_trend_narrative` 220 |
| `app/services/openai_service.py` | 1,252 | `OpenAIService.summarize_filing` 552; `OpenAIService.generate_structured_summary` 250; `OpenAIService._assemble_structured_summary` 87 |
| `app/services/edgar/xbrl_service.py` | 1,316 | `EdgarXBRLService.extract_standardized_metrics` 259; `_extract_from_filing_instance_sync` 239; `EdgarXBRLService._parse_company_facts` 162; `EdgarXBRLService.get_xbrl_data` 83 |
| `app/services/edgar/instance_extractor.py` | 1,229 | (none over 80) |

End-state targets the ratchet drives toward: façades ≤60 lines for M2 and M3, ≤300 for M5, ≈45 for
M6, ≈670–840 for M4, ≈800 for M1; every function a named PR splits ≤80 lines, the eight unsplit rows
(`_resolve_citations` 114, `reconcile_facts` 109, `remediate_industry_facts` 102,
`derive_q4_eps_facts` 97, `_assemble_structured_summary` 87, `upsert_facts_bulk` 84,
`derive_same_period_metrics` 84, `get_xbrl_data` 83) ratcheting at today's size until a Wave 3
S-PR splits them; every new module ≤600 lines. The façade contract is gated the same way: each budget
file carries `names`, the base file's top-level names at `da636f6` mapped to the sub-module that
defines each after its move (`null` until moved), and the gate asserts each still resolves on the
façade and, once mapped, is the same object as the sub-module's (constants carry no `__module__`,
so the map is what makes that check possible); after a move the façade declares `__all__` (ruff's F401 would otherwise fail
re-export-only imports, `backend/ruff.toml` ignores F401 only for `__init__.py`).

---

## Waves (file-disjoint PRs, dependencies, triggers)

Rules that shape the order: (1) tests-only PRs never deploy and never arm `eval-baseline`, so they
run fully in parallel; until #1123 lands each still arms `copilot-eval` once when marked ready
(measured USD 0.006–0.026, logged under decision 1); (2) every code-bearing PR deploys on merge and arms `eval-baseline` on
every push, draft or not, so merges are serial (one verified deploy at a time, AGENTS.md §6) and
pushes are batched (push once when the local gate is green; stay draft until review so `copilot-eval`
fires once; a second push within a run cancels the first, `.github/workflows/ci.yml:290-292`); (3) paid
runs follow decision 1 (read the provider balance, then log each run at its measured cost); no
refactor PR writes under `tasks/code-red-20261004/runtime/`, whose records are digest-indexed and
gated by `backend/tests/unit/test_code_red_runtime_records.py`; (4) leaf-first: a module is moved before it
is split, and a module is split only after its anchors are green, and every Wave 1 PR also depends on
W0.G because it lowers its module's budget file; (5) PRs in one wave edit disjoint files, including
test files (anchors go in NEW test files; each module has its own budget file) and docs. The two
adjacent-line collisions that remain are `docs/ARCHITECTURE.md:181-189` (F1 edits :189, X2 edits
:181 and :185–187) and `lessons/sec-edgar-resilience-layer.md:23-25` (F1 edits :23–24, X2 edits :25):
F1 and X2 merge serially with a rebase between (`lessons/ops-serial-merge-adjacent-line-prs.md`); T3's
edit at `docs/ARCHITECTURE.md:158` is same-file only and merges cleanly.

Legend: D = deploys on merge; E = arms `eval-baseline` on every push (balance read, run logged); CE = arms
`copilot-eval` when marked ready and on each push while ready; CE* = the same, but only until #1123
lands (its filter drops `backend/tests/**`); AST = pure-move proof required.

### Wave 0 — the gate and the anchors (tests-only, all parallel; no deploy, no `eval-baseline`)

| PR | Files | Triggers | Depends on |
|---|---|---|---|
| W0.G size-budget gate | new `backend/tests/unit/test_hot_module_size_budget.py`, six budget files under `backend/tests/fixtures/size_budgets/`, `backend/tests/support/ast_move_proof.py` | CE* | — |
| C0 copilot anchors (4) | new `backend/tests/unit/test_copilot_refactor_anchors.py` | CE* | — |
| F0 facts anchors (6) | new `backend/tests/unit/test_facts_refactor_anchors.py` | CE* | — |
| T0 trend anchors (6) | new `backend/tests/unit/test_trend_refactor_anchors.py` | CE* | — |
| O0 openai anchors (A1–A6) | new `backend/tests/unit/test_summarize_filing_anchors.py` + JSON fixtures under `backend/tests/fixtures/` | CE* | — |
| X0 xbrl anchors (6) | new `backend/tests/unit/test_xbrl_service_anchors.py` | CE* | — |
| I0 instance anchors (5) | new `backend/tests/unit/test_instance_extractor_anchors.py` | CE* | — |

Wave 0 does not wait for #1123 (decision 8): if it lands first, all seven un-drafts are free;
otherwise each fires one `copilot-eval` run at un-draft, about USD 0.10 in all at measured rates,
logged under decision 1.
Anchors patch shared objects (singletons, `settings`, third-party modules) wherever possible; an
anchor that must patch a name on one of the six modules is listed as a re-point in the PR that moves
its reader: T1 re-points T0's detector anchor (`trend_analysis.detectors._DETECTORS`), F4 re-points
F0's default-fetcher and remediate anchors (`facts.jobs`). Exit gate: all seven merged; each anchor shown to FAIL under a spot mutation of its guarded behaviour
(table in the PR body, as the 2026-07 plan did); baseline recorded {backend test count, wall time,
green SHA}. The hermetic gate landed on main on 2026-10-09 (#1145, `4c0563ad`):
`backend/tests/support/network_gate.py`, registered by `backend/tests/conftest.py:34`, fails any test
that reaches a non-loopback host, or the session for a stray (CLAUDE.md:162-164); subprocesses and
C-level clients are outside it, so every Wave 0 anchor fakes its boundary in-process. Wave 0 adds no
network-reaching test.

### Wave 1 — leaf moves (code-bearing; develop in parallel, merge serially)

| PR | What | Files | Triggers | Depends on |
|---|---|---|---|---|
| I-dead | M6 dead code: delete `_fact_records` (IE:240–243); `git grep -w` over `backend/` finds no other reference, before and after | `instance_extractor.py`, `size_budgets/instance_extractor.json` | D, E, CE | I0, W0.G |
| T-dead | M3 dead code: delete `_illegal_refs` (T:1450), `_mismatch_details` (T:1582), `_retry_instruction` (T:1593), `NOT_ENOUGH_DATA_SENTINEL` (T:1356) and `compact_dataset_for_prompt` (T:756); delete the two `TestPromptRendering` tests (`test_trend_analysis_service.py:960-1002`) and only the trailing dead-renderer assertions of the two CAGR tests (:853–855, :883–884), whose live assertions stay; `git grep -w` → 0 for each name | `trend_analysis_service.py`, `test_trend_analysis_service.py`, `size_budgets/trend_analysis_service.json` | D, E, CE | T0, W0.G |
| I1 | M6 split into `edgar/instance/` + façade; adds its `forbidden_imports` rows | `instance_extractor.py`, new `edgar/instance/*`, `size_budgets/instance_extractor.json` | D, E, CE, AST | I-dead, I0, W0.G |
| T1 | M3 leaf moves (periods, formatting, series, detectors, citations, fidelity, cache) + façade; fixes the stale `PROMPT_VERSION` comment block (T:34–40) as it moves; re-points T0's detector anchor | `trend_analysis_service.py`, new `trend_analysis/*`, `test_trend_refactor_anchors.py`, `size_budgets/trend_analysis_service.json` | D, E, CE, AST | T-dead, T0, W0.G |
| C1 | M1 pure moves (quotations, fact_guards, claim_repair, resolution, envelope) + façade with `__all__`; ~10 test re-points incl. the two source-level gates | `copilot_service.py`, new `copilot/*`, `test_copilot_prose_quotations.py`, `test_copilot_quotation_retry.py`, `test_copilot.py`, `size_budgets/copilot_service.json` | D, E, CE, AST | C0, W0.G |
| F1 | M2 leaves + transport + façade with `__all__`; the six rule-5 prose edits; adds the `concepts.py → app.services.edgar` forbidden-import row | `facts_service.py`, new `facts/{__init__,concepts,transport}.py`, `size_budgets/facts_service.json`, CLAUDE.md:105/152, ARCHITECTURE.md:189, ADR-0003:30, `lessons/sec-edgar-resilience-layer.md:23-24`, `backend-developer.md:30`, the allowlist docstring | D, E, CE, AST | F0, W0.G; merges after #1126/#1118 or rebases over them (decision 9) |
| X1 | M5 cache → `xbrl_cache.py` with a function API; the `test_two_tier_cache.py` retargets; `docs/OPERATIONS.md:230`; adds the forbidden-import row for the five named `xbrl_*` modules → `xbrl_service` | `xbrl_service.py`, new `xbrl_cache.py`, `test_two_tier_cache.py`, `docs/OPERATIONS.md`, `size_budgets/xbrl_service.json` | D, E, CE, AST | X0, W0.G |
| O1 | M4 `summarize_filing` post-provider phases → `ai/summary_finalize.py`; `test_evidence_snap.py:231-239` redirected; `snap_evidence` passed in from the façade's binding | `openai_service.py`, new `ai/summary_finalize.py`, `test_evidence_snap.py`, `size_budgets/openai_service.json` | D, E, CE, AST | O0, W0.G |

Every Wave 1 PR lowers the rows in its own budget file. Merge order recommendation (smallest blast
radius first, verified deploy between each): I-dead → I1 → T-dead → T1 → X1 → C1 → F1 → O1. F1 and X2 (next wave) touch
adjacent lines of `docs/ARCHITECTURE.md` and of `lessons/sec-edgar-resilience-layer.md`; keep them
serial.

### Wave 2 — remaining moves and the long-function splits (serial within a module, parallel across modules)

| PR | What | Files | Triggers | Depends on |
|---|---|---|---|---|
| T2 → T3 → T4 | M3 dataset + observations; narrative + final façade (+ `docs/ARCHITECTURE.md:158`); then the three splits | M3 files only | D, E, CE (T2/T3: AST) | T1 |
| F2 → F3 → F4 | M2 companyfacts + derive (split `normalize_companyfacts`); writers + reconcile (split `upsert_facts`); jobs + ingest + fundamentals (split `backfill_facts`; re-point `test_job_reporting.py:242` to `app.services.facts.jobs.process_filing_facts`, `test_analysis_coverage_pool_lifetime.py:78` to `app.services.facts.ingest._fetch_companyfacts_async`, and F0's default-fetcher and remediate anchors to `facts.jobs`) | M2 files + `size_budgets/facts_service.json`; F4 also the two named tests and `test_facts_refactor_anchors.py` | D, E, CE, AST | F1 |
| X2 → X3 → X4 (→ X5) | M5 companyfacts (+ re-point the `_classify_duration` import to `facts.concepts`; the six rule-5 doc edits); standardized; instance (about 30 test retargets in 7 files, `backfill_facts.py:79`, `acceptance_archive.py:604`; folds I2's re-points, not its deletion); optional sections | X2: `xbrl_service.py`, new `xbrl_companyfacts.py`, `docs/ARCHITECTURE.md:181,185-187`, `lessons/sec-edgar-resilience-layer.md:25`, `lessons/sec-runtime-facts-carry-no-duration.md:12,29`, `backend/evals/RUNBOOK.md:793`, and the docstring that today sits at `copilot_service.py:1355` (after C1 it lives in `copilot/claim_repair.py`); X3/X4: M5 files, the retargeted tests, `scripts/backfill_facts.py` (rebase over #1121), `evals/acceptance_archive.py` | D, E, CE, AST | X1, F1 (X2 needs `facts.concepts`), I1 (X4 folds I2), C1 (the docstring's new home) |
| C2 | M1 attempt-loop decomposition in place (FactRegistry, SentinelScanner, `_admit_not_disclosed`, `_admit_answer`) | `copilot_service.py` | D, E, CE | C1 |

### Wave 3 — follow-ups and the ratchet

| PR | What | Gate |
|---|---|---|
| C3 | M1 prompt module (`copilot/prompt.py`: `SYSTEM_PROMPT`, sentinels, cluster A) | after C2; no branch gate (decision 3) |
| O2 | M4 prompt assembly → `ai/summary_prompt.py`; A1 proves bytes identical; redirects the text pin in `test_verbatim_contract.py:19-21` | after O1; no branch gate (decision 3) |
| Ratchet | final ceilings: façades and new modules at their end-state sizes | after the last split |

Spend estimate for the whole plan (decision 1): 20–21 code-bearing PRs (Wave 1 eight, Wave 2 ten
plus the optional X5, Wave 3 two); at two pushes each, 40–42 `eval-baseline` runs ≈ USD 14.40–15.10 at
the measured USD 0.36 (record 18; USD 12.00–12.60 at AGENTS.md's 0.30) and 20–42 `copilot-eval` runs
≈ USD 0.12–1.10 at the measured USD 0.006–0.026, plus up to USD 0.20 for Wave 0's un-drafts if #1123
has not landed: about USD 14.5–16.4 in all, under the USD 18 ceiling, each run logged at its measured
cost, and less in practice because a branch opens its PR only once it is review-clean and a second
push cancels an in-progress `eval-baseline` run. 20–21 serialized deploys.

---

## Founder decisions (decided 2026-10-09)

On 2026-10-09 the founder delegated these decisions to the plan's author with full authority: weigh
the pros and cons, then decide. Each item records the options, the evidence (re-checked that day on
main at `76d45732`), the decision and what it changes. Nothing in this plan now waits on the founder.

1. **Spend: the refactor is its own paid programme, ceiling USD 18, logged at measured cost.**
   - Options. (a) One USD 20 hold in the Code Red ledger, as first proposed. (b) A Code Red
     reservation before every paid push, as record 18 does for its own stage-2 PR. (c) A ceiling of
     the refactor's own: read the balance, then log each paid run, outside the Code Red ledger.
   - Against (a) and (b): the ledger has one writer, the Code Red chief
     (`tasks/code-red-20261004/runtime/control/LEDGER-ACCESS.md:47`), and one USD 25 ceiling shared by
     the chief, its officers and its workers (:65–66), with USD 22.35 of headroom left
     (`tasks/code-red-20261004/runtime/CHECKPOINT.md:373`). A USD 20 hold would take almost all of it,
     and either form makes about 60 paid refactor runs wait on the chief's records PRs. Other writers'
     paid runs are already outside the ledger: record 18 measured four on other lanes' PRs
     (`tasks/code-red-20261004/runtime/control/DECISIONS-18.md:121-124`).
   - For (c): [AGENTS.md](../AGENTS.md) §3 asks a new paid programme for a stated ceiling and for the
     balance to be read first; (c) meets both without coupling two programmes. What it gives up is the
     ledger's hash chain; for about USD 15–16.5 in total a plain per-run log is proportionate.
   - **Decision: (c).** The ceiling is USD 18 for every paid run this plan's PRs fire. Before each wave,
     and before un-drafting a PR whose un-draft is paid, dispatch `.github/workflows/deepseek-balance.yml`
     (it makes no inference call) and note the balance. Log every paid run (PR, head, run id, job,
     measured cost from the eval report or the job log) in the Spend log under Implementation Notes.
     A code-bearing branch opens its PR only once its local gate and local review are clean, and
     pushes once per review round. If the log passes USD 15 with work left that would cross 18, stop
     and put it to the founder. A PR run by the Code Red chief or one of its officers or workers
     follows the Code Red rule instead.
2. **Hermetic suite before Wave 1 — resolved on main.** Landed as #1145 (`4c0563ad`, 2026-10-09)
   after this plan was written: the outbound-network gate (`backend/tests/support/network_gate.py`;
   `lessons/test-conftest-hermetic-env.md`) fails any test that reaches a non-loopback host, and the
   full suite ran 5,829 passed with 0 attempts (`tasks/todo.md:6486`, ticked;
   `tasks/code-red-20261004/runtime/control/DECISIONS-18.md:38-76`). No decision needed; the item
   stays so the numbering of items 3–9 holds.
3. **Stale branches: evidence only. None merges, none is rebased onto a split, none is deleted.**
   - Evidence. None of the ten branches heads an open PR. The 2026-10-07 disposition sweep classed each
     as evidence: `claude/copilot-prompt-candidate`'s PR #1074 closed as measurement-only, never
     merging, with its 30 evidence files landed on main (`tasks/pr-disposition-2026-10-07.md:46,212`);
     the G-stage arms say "DO NOT MERGE"; `codex/measure-n-control-2` and `codex/wave3-e8-n-pilot` are
     measurement-only; `supported-financial-explanations` and `segment-margin-basis` are superseded.
     Candidate r (`codex/wave3-return-ratio-basis`) was implemented but never accepted: its
     deterministic, render-only half landed as #1039
     (`tasks/review-evidence/pr942-successor-2026-09-30/README.md:3-9`), its model-facing half is held
     (:97–99), and the thinking-low pilot built on it stopped at its first pair
     (`tasks/continuation-plan-2026-09-26.md:72-75`).
   - Options. (a) Delete the branches. (b) Cherry-pick their unlanded bytes into the refactor. (c) Treat
     them as evidence and plan as if they did not exist.
   - Against (a): deletion buys the refactor nothing; it is the founder-held "approval by name" list of
     the 10-07 sweep (`tasks/pr-disposition-2026-10-07.md:285-302`), and for
     `codex/wave3-thinking-low-pilot` the branch is the only ref to commits the records cite by SHA
     (:165). Against (b): every candidate byte is a prompt or quality change that needs the RUNBOOK
     gate and an adoption decision, which a refactor must not carry.
   - **Decision: (c).** C3 and O2 lose their branch gates and run after C2 and O1. Any future use of
     this content is a fresh PR from current main, under the RUNBOOK gate where it changes prompt
     bytes. Branch deletion stays where the 10-07 sweep left it.
4. **Dead code: delete it, before the moves, with the test edits corrected.**
   - Evidence. `_illegal_refs` (T:1450), `_mismatch_details` (T:1582), `_retry_instruction` (T:1593),
     `NOT_ENOUGH_DATA_SENTINEL` (T:1356) and `_fact_records` (IE:240) have no reference in `backend/`
     beyond their definitions (`git grep -w`). `compact_dataset_for_prompt` (T:756) is called only by
     four tests, and the plan was wrong about them: only the two `TestPromptRendering` tests are about it
     (`backend/tests/unit/test_trend_analysis_service.py:960-1002`). The other two pin live CAGR
     markers and windows (:831–856, :858–885) and end with one assertion on the dead renderer's text
     (:853–855, :883–884); deleting them would lose live coverage this plan cites.
   - Options. (a) Keep the dead code. (b) Delete it in Wave 3, after the moves, as first proposed.
     (c) Delete it before the moves.
   - (a) leaves code every reader must check and the moves must carry. (b) moves dead code into new
     modules only to delete it there: double churn and larger move proofs. (c) costs the same two
     deploys and two `eval-baseline` runs as (b), only earlier.
   - **Decision: (c).** T-dead and I-dead open Wave 1, each before its module's first move. T-dead
     deletes the five names and the two `TestPromptRendering` tests, and removes only the trailing
     dead-renderer assertions from the two CAGR tests, which keep every live assertion. I-dead deletes
     `_fact_records`. Each PR proves `git grep -w` → 0 for every deleted name.
5. **The copilot attempt loop stays in place (C2).**
   - Options. (a) Decompose it in place in `copilot_service.py`. (b) Move it to `copilot/stream.py`.
   - Against (b): the eval runner attaches its withheld-answer filter to `copilot_service`'s own logger
     (`backend/evals/copilot_runner.py:194-201`). A logging filter sees only records logged by that
     logger, so the moved loop's records would bypass it, silently. (b) also costs five more test
     re-points, and the locked T5 anchor binds the router's name either way.
   - **Decision: (a).**
6. **New-code ceilings and the freeze: adopted. A file ceiling may be raised by the PR author with a
   recorded reason; a long-function ceiling never rises.**
   - Evidence. On 2026-10-09 no open PR changes any of the six files (25 open PRs checked); only the
     ten evidence branches of decision 3 do. The freeze costs no live lane anything today.
   - Options for raising a ceiling. (a) Founder sign-off for every raise, as first proposed. (b) Any
     raise, with a reason recorded. (c) Split: a file ceiling may be raised by the PR author with a
     recorded reason; the ceiling of one of the twenty long functions never rises.
   - (a) puts a solo founder on the path of routine fixes to files that change weekly (25 commits since
     August on `openai_service.py` alone). (b) lets the giant functions grow while the refactor splits
     them. (c) keeps the founder out of routine fixes and keeps the one invariant that matters
     absolute: a fix inside a 200-line function extracts a helper first, which is the refactor's
     direction anyway.
   - **Decision: (c).** The gate holds the twenty long-function rows' W0.G values in a frozen table
     inside the test and fails any JSON row above its frozen value, so raising one means editing the
     gate. A file-ceiling raise lands with a dated `note` line (PR, row, old → new, why extraction was
     not possible in that PR) and a "Ceiling raise" paragraph in its PR body. New code stays at 80
     lines per function and 600 per new module, as specified.
7. **Docs: fix the living architecture doc now; leave the audit appendices as written.**
   - Evidence. `docs/ARCHITECTURE.md:337-342` says the two companyfacts fetchers still need unifying on
     the limiter and that `_parse_company_facts` never fills two buckets. Both are false: WS-8
     (`d517ef19`, 2026-09-04) made the facts fetcher a bridge onto the rate-limited async fetcher (the
     xbrl twin was already limiter-wired), and `499648e6` (2026-09-05) fills both buckets, pinned by
     the locked T9 test (`backend/tests/unit/test_companyfacts_fixture.py:116-127`). The audit
     appendices each call themselves a "workstream report reproduced as written"
     (`docs/audit-2026-09/03-data-platform.md:3`, `docs/audit-2026-09/06-unfinished-work-inventory.md:3`),
     and none of their rows has been updated since 2026-09-06.
   - **Decision:** one docs-only PR now for `docs/ARCHITECTURE.md`'s residual-debt bullet (no deploy, no
     paid run). The audit appendices stay as written: patching two rows of a dated report would imply
     its other rows are current. `docs/OPERATIONS.md:230` is accurate today and changes with X1; the
     `PROMPT_VERSION` comment rides T1. Separately, the naive `datetime.now()` stamps at
     `backend/app/services/edgar/xbrl_service.py:180,207,692,713,722` and the
     `datetime.now(timezone.utc)` calls at `backend/app/services/facts_service.py:715,1954,1983` are a
     rule-7 follow-up outside this plan; the moves leave them as they are.
8. **#1123: Wave 0 does not wait for it.**
   - Options. (a) Merge #1123 first, as first proposed. (b) Proceed, and un-draft Wave 0 under decision
     1. (c) Decline #1123 here.
   - #1123 belongs to another lane, its merge is #1118's founder decision 5, and its own review flags
     that a 2,000-line gate guards a 31-line filter change (#1123, "Founder actions"). Its value to
     this plan is about USD 0.10: seven tests-only un-drafts at the measured USD 0.006–0.026 a run.
     Neither waiting on it nor deciding it here is proportionate to that.
   - **Decision: (b).** If #1123 lands first, Wave 0's un-drafts are free; otherwise they are logged
     under decision 1. Whether #1123 merges stays #1118's decision 5.
9. **F1 edits rule 5's owner path, after #1126 and #1118.**
   - Options. (a) Approve the path edit in F1, ordered after #1126 and #1118 or rebased over them.
     (b) Keep companyfacts fetching in `facts_service.py` so rule 5's text never changes.
   - (b) would bend the module layout around one sentence. CLAUDE.md already says the code is the truth
     and the doc is fixed in the same PR; the edit changes a file path, not the rule.
   - **Decision: (a).** F1's PR body states that rule 5's substance is unchanged and lists the six prose
     files it edits. If #1126 or #1118 is still open when F1 is ready, F1 rebases over it.

Two founder items outside this plan still touch it: #1118's decision 5 (whether #1123 merges) and the
Code Red's `backfill-facts-weekly` move, which gates #1151 and so the first deploy slot before Wave 1.

---

## Verification (how the plan's claims were checked, and how execution is verified)

**Claims (this session, 2026-10-08).** Six independent read-only analysts, one per module, produced
file:line inventories (clusters, public surface by caller, patch targets by namespace, SEC transport
sites, eval triggers, traps, anchor gaps, diff estimates) and answered a fixed list of true/false
claims each; the plan author spot-checked the load-bearing ones (dead-code callers by `git grep`, the
router bindings, the T9 bucket pin, the source-text pin in `test_evidence_snap.py`, the private
imports in `scripts/backfill_facts.py`, the compat shim). Four adversarial lens passes then re-verified the
whole document against the code (citations, in two passes over M1–M3 and M4–M6: every file:line
resolves and says what the plan says; sequencing: dependencies, open branches, Code Red, deploy and
eval triggers; gates and locks: anchors, locked tests, allowlists, monkeypatch bindings, the size-gate
numbers), and one independent reviewer read the full plan and then re-reviewed the final head (a
delta pass over the folded corrections, with the size table reproduced under the counting rule
above); their corrections are folded in above and listed in the PR body.

**Per-PR gates (binding on every execution agent):**
- Backend: from `backend/`, `ruff check . && bandit -r app -ll && python -m pytest` before every push
  (AGENTS.md §8). The performance suite does not exercise these modules (its one file patches
  `summarize_filing` away), so a PR touching streaming code (M1, M3, M4) runs the default-lane suites
  that drive the streams: `test_copilot_quotation_retry.py`, `test_copilot_gate.py`,
  `test_analysis_stream.py`, `tests/integration/test_summary_stream_heartbeat.py`,
  `tests/integration/test_stream_latency.py`.
- Pure moves carry the AST per-symbol proof (`lessons/test-pure-move-ast-proof.md`) produced by
  `backend/tests/support/ast_move_proof.py` (checked in by W0.G), run on committed state; zero
  undisclosed deltas or the "pure move" claim is false. Reviewers re-run the proof. Every façade PR
  declares `__all__` and keeps the budget file's `names` gate green (each top-level name of the base
  file at `da636f6` still resolves on the façade and, once mapped, is the same object as the sub-module's).
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

**Payoff.** Six files of 1,229–2,153 lines become façades of 45–840 lines over about 40 cohesive
modules of ≤600 lines; twelve of the twenty functions over 80 lines become ≤80 by named PRs (the
552-line `summarize_filing` becomes a 70-line orchestrator) and the other eight ratchet at today's
size until split; every refactor PR is behaviour-preserving by proof, not by assertion; and the gate
keeps it that way.

---

## On approval

Approved on 2026-10-09 under the founder's delegation ([Founder decisions](#founder-decisions-decided-2026-10-09)).
Persist this document as `tasks/refactor-plan-2026-10.md` (this PR). **Wave 0** starts the same day:
the size-budget gate PR and the six anchor PRs in parallel, then T-dead and I-dead open Wave 1.
Record every deviation, and every paid run, in the Implementation Notes section above.
