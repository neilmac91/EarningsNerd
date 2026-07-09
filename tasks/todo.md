# Tier 3.1 v2 — SummaryDoc content re-architecture

**Goal:** cut the summary generator from the v1 9-section taxonomy to the plan's v2 9-section
content architecture (`docs/summary-quality-improvement-plan.md` Part 3.1) — the core
"world-class content" jump. Filing-only, DeepSeek stays the generator, one universal cached
summary, eval-gated + re-pinned.

## v2 taxonomy (Part 3.1) and the v1→v2 map

| # | v2 section | from v1 | change |
|---|---|---|---|
| 1 | `the_print` | `executive_snapshot` | absorbs Key Takeaways; ≤3 headline figures by reference |
| 2 | `results_that_matter` | `financial_highlights` | P&L table only; **cash lines removed** → §3 |
| 3 | `earnings_quality` | **NEW** | operating-vs-one-time bridge, NI-vs-CFO, FCF, red-flags (model-extracted in T3.1; deterministic feeds in T5) |
| 4 | `value_drivers` | **NEW** | buybacks/dividends/capex, ROIC level+trend from filing XBRL |
| 5 | `forward_signals` | `guidance_outlook` | elevated; guidance as the filing states it |
| 6 | `risks` | `risk_factors` | 10-Q = the filing's own change statement |
| 7 | `segments` | `segment_performance` | segment table + mix commentary |
| 8 | `balance_sheet_liquidity` | `liquidity_capital_structure` | absorbs the orphan `covenants_contingencies` node |
| 9 | `notable_footnotes` | `notable_footnotes` | unchanged shape |
| — | dissolved | `management_discussion_insights` | distributes into §1/§3/§5 |
| — | dissolved | `three_year_trend` | trend framing → Multi-Period Analysis product |

Prune the orphan `covenants_contingencies` node (emitted today; tracked/rendered nowhere).

## Research findings that shape the plan

- **Render dispatch is a ready stub** — `summary_sections._builders_for(schema_version)`
  (`summary_sections.py:522`) already receives `schema_version` but ignores it; register
  `_BUILDERS_V2` there. **Additive:** legacy v1 rows keep rendering via v1 builders until
  refreshed. All 4 consumers (web/markdown/PDF/CSV) flow through it.
- **Generation is single-version** — flipping `SUMMARY_SCHEMA_VERSION`→2 is an atomic cutover of
  `schema_template` + prompts + fallbacks + version bump.
- **Eval layer is DECOUPLED** — it scores its own canonical 5-key shape (executive_summary /
  financial_highlights / risk_factors / management_discussion / outlook). No scorer rewrites;
  redundancy/delta scorers are already taxonomy-agnostic (split on `## ` markdown). **The one
  eval break:** if `summarize_filing`'s compat-field derivations
  (`openai_service.py:749,758,813-816,1022-1026`) aren't re-pointed to v2 keys, canonical
  `management_discussion`/`outlook` go empty → coverage 5/5→3/5 → **HARD `mean_coverage` breach →
  CI fails.** Fix lives in the generation compat layer, not the eval.
- **Quality badge will lie** — `assess_quality`/`_verdict_coverage`
  (`summary_generation_service.py:149-166`) count against hardcoded `_TRACKED_STRUCTURED_SECTIONS`
  (v1). Under v2, every summary tiers "partial" and (with `AI_QUALITY_GATE`) billing stops. Must
  count the v2 taxonomy; re-validate the 4/9 bar.
- **`SummaryDoc` pydantic module does not exist** — create it.
- **SSE:** `GET` already returns `schema_version` and the frontend refetches on `complete` (T2.5
  deferred deliberately) → **no SSE contract amendment needed.** Verify in PR B.
- **Locked contract test:** `test_background_generation_characterization.py` has v1 `per_section`
  fixtures (`total_count: 9`) → re-key via the sanctioned PR-body-documented contract-change path.
  `test_summary_stream_contract.py` is NOT taxonomy-coupled (no change).

## Decomposition — 2 PRs

### PR A — v2 infra, DARK (additive; default stays v1; zero eval/user impact)
- [ ] New `backend/app/services/summary_schema.py` — `SummaryDoc` pydantic v2 model (9 sections +
      sub-shapes; `metric_id` references; per-block evidence-ready).
- [ ] `summary_sections.py`: author `_BUILDERS_V2` (9 v2 Section/Block builders; use the `callout`
      kind + `evidence` field already present); make `_builders_for` dispatch
      (`{1:_BUILDERS, 2:_BUILDERS_V2}`, default v1 for legacy/NULL).
- [ ] Quality-badge schema_version dispatch: `_verdict_coverage`/`assess_quality` pick the
      taxonomy tuple by `raw_summary.schema_version`; define the v2 tracked tuple; keep 4/9.
- [ ] Unit tests: v2 builders render synthetic v2 payloads; dispatch picks v2 for
      `schema_version=2`, v1 otherwise; badge counts v2 on a synthetic v2 `per_section`.
- [ ] Full backend gate. No eval run / no re-pin (generation unchanged).

### PR B — v2 cutover (eval-gated, atomic; structure-first prompts)

**STATUS: complete, pending final eval re-pin + push.** Full backend gate GREEN (1557 passed),
frontend gate GREEN (lint+tsc+vitest 392+build). Live `--runs 3` eval verified the cutover and drove
one correctness fix (below).

- [x] `openai_service.py`: `schema_template` → v2 (pruned covenants_contingencies); re-pointed
      `_TRACKED_STRUCTURED_SECTIONS` → `TRACKED_SECTIONS_V2` (safe: badge's v1 tuple frozen in
      summary_schema, PR A); re-pointed compat-field derivations
      (results_that_matter/risks/earnings_quality/forward_signals); stamped `schema_version` before
      `render_sections`; **deterministic taxonomy filter** (drops the model's stray v1 keys — structure
      from code, not model compliance); ONE-HOME rule + insights/legacy-card reads → v2 keys.
- [x] `SUMMARY_SCHEMA_VERSION`=2 + `SUMMARY_PROMPT_VERSION`=summary-2026-07-c.
- [x] `ai/section_recovery.py`: ordered-keys + section-context + schema-snippet maps → v2.
- [x] `ai/markdown_render.py`: `_apply_structured_fallbacks` → compact v2 anchor filler (the_print +
      results_that_matter), removed ~157 lines dead v1 filler.
- [x] `ai/fallback_summary.py`: `generate_xbrl_summary` `sections_for_frontend` reshaped v1→v2.
- [x] `summary_pipeline.py`: compat block re-pointed; retired the MD&A/guidance wrapper injection
      (phantom v1 nodes); kept `management_section`/`guidance_section` for the DB-compat columns.
- [x] Per-form prompts: **structure-first outcome — no rewrite needed.** Structured prompts defer to
      schema ("schema is the single source of truth for structure"); analyst prompts carry no v1 keys
      / no conflicting structural directives. Assembled prompt pins the nine v2 sections + v2 homes.
- [x] Tests: added `test_generation_taxonomy_is_v2`; re-keyed the fallback-filler assertion →
      `the_print`; the LOCKED characterization test needed no re-key (compat fields unchanged in shape).
- [x] **Eval-driven fix — v2 numeric-recall floor.** `--runs 3` #1 showed recall 0.8429→0.7426 (HARD
      breach): the cutover dropped v1's deterministic `financial_highlights.cash_flow[]`/`balance_sheet[]`
      XBRL surfacing. Missing facts = investing/financing cash flow + current assets/liabilities. Fix #1
      (seed-if-no-"$") only partially recovered (#2 = 0.7918): the model writes an UNRELATED "$" figure
      in those fields that defeats a presence check, and it mislabelled non-USD filers (currency
      1.0→0.9866). Redesign: `_apply_structured_fallbacks` now ALWAYS authors the two figure-only fields
      — `working_capital` (current assets/liabilities + ratio) + a dedicated `cash_flow` bridge
      (operating/investing/financing) — currency-aware (ISO-prefixed for non-USD), leaving the model's
      `leverage`+`liquidity` prose untouched; the v2 builder renders `cash_flow`. Content dims IMPROVED
      at cutover: redundancy 0.829→0.927, delta_consistency 0.898→0.968.
- [ ] Re-run `--runs 3` #3 to confirm recall + currency recover; re-pin `baseline_scores.json`
      (activates redundancy/delta WARN gates at v2 values). [gate_fail = the known JPM/G5 bank-revenue
      flake, exempt.]
- [x] Frontend audit: confirmed `SummaryBlocks` renders v2; **deleted** dead v1-key readers —
      `SummaryExecutiveSnapshot.tsx`, its spec, and `formatters.ts::{ExecutiveSnapshot,asTrimmedString,
      parseExecutiveSnapshot}` (no non-test callers).
- [ ] Push (rebased on latest main after #610); open draft PR B; subscribe + arm check-in.
- [ ] Post-merge: operator `refresh-stale` drains v1 rows → v2 in place (cost/traffic decision).

### Follow-up (not this tier): CI eval-baseline single-run gate_fail flakiness
The PR-triggered `eval-baseline` runs `--runs 1`; a single transient veto on 1/26 filings = 0.0385
hard-fails the epsilon (0.005) `gate_fail_rate` tolerance, on ANY `backend/app` PR (dark or not).
Founder-flagged as a RUNBOOK policy question (single-veto-on-single-run ≠ a 3-run regression), NOT
to solve inside the content PRs. Options: PR eval at `--runs 2–3`, or a granularity-aware gate_fail
tolerance. Also fix the `#606` RUNBOOK note, which flagged pass_rate/stdev single-run wobble but not
that `gate_fail_rate` *hard*-fails.

## Risks & mitigations
- **Eval churn at cutover** — eval is decoupled; only compat-field re-pointing + re-pin.
- **Badge honesty** — badge dispatch (PR A) lands before generation flips (PR B).
- **New §3/§4 sourcing** — model-extracted in T3.1 (no fabrication: omit rules + worked examples);
  T5 adds deterministic feeds. Watch numeric recall/precision in the eval.
- **PR B size** — large atomic cutover; keep tightly documented for review.

## Decisions (founder-confirmed 2026-07-08)
1. **Taxonomy:** **Full v2 now (all 9 sections)**, incl. the two new analytical homes
   (earnings_quality, value_drivers) model-extracted in T3.1; T5 hardens with deterministic feeds.
2. **Cutover prompt scope:** **Structure-first** — v2 structurally live + eval-passing with focused
   prompts in PR B; iterate the full prose-quality bar (10 rules, per-form flexes, worked examples)
   in tight eval-gated follow-ups.
3. **Decomposition:** **2 PRs** — PR A (dark infra) → PR B (cutover). Confirmed.

Currently implementing **PR A**.
