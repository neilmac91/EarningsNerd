# Tier 5.4 — Forward-quote hard gate (verbatim §5 quotes enforced at generation time)

**Goal (roadmap T5.4 / plan §5):** `forward_signals.quotes` are prompt-contracted as verbatim,
attributed, forward-looking-only — but NOTHING enforces it: figure_trace exempts them *because*
they're "verbatim" (figure_trace.py:79-83), T4's read-time enrichment merely withholds the Verified
badge, and the recovery re-ask snippet even drops the "verbatim" qualifier. T5.4 closes the loop:
every §5 quote is checked against the filing text at generation time; failures are ALWAYS measured
(greppable counter + per-row audit) and DROPPED when `AI_FORWARD_QUOTE_GATE` is armed. Advisory-first
(flag ships OFF, the figure-trace precedent) — the first fleet-wide fidelity measurement is this
slice's deliverable alongside the mechanism.

## Load-bearing facts (4-reader understand sweep, live-verified)

1. **The verbatim definition already exists and is shared**: provenance_service.normalize_for_match
   (lowercase + whitespace-collapse) + verify_excerpt_in_text (exact normalized substring,
   _MIN_VERIFIABLE_LEN=24) — used by T4 read-time enrichment AND the copilot eval scorer. rapidfuzz
   3.14.5 is pinned but has ZERO usages; "≥92" exists only in the plan doc. T4 chose exact-match for
   read-time latency (provenance_service.py:242-244) — a reason that doesn't apply at generation
   time, but ONE definition of verbatim across all surfaces beats a second looser one
   (lessons/arch-guard-every-model-facing-surface.md).
2. **normalize_for_match does NOT fold typography**: filings use curly quotes/apostrophes/dashes;
   model output usually straight — exact-match false-fails that entire class (copilot has a local
   ’→' fold precedent, copilot_service.py:484).
3. **Drop site must be inside `summarize_filing`** (openai_service.py), after risks normalization
   (~:771), BEFORE the coverage snapshot (:773) and render_sections→business_overview (:846-851) —
   later placement desyncs stored markdown/coverage from sections. This single site covers SSE +
   background/cron (one orchestrator) AND recovery-authored quotes (recovery merges upstream).
   `filing_excerpt`/`filing_text` are already parameters in scope (:653-662). Precedent shape:
   `_sanitize_bank_financial_highlights` (:757-765).
4. **Grounding corpus**: verify against `filing_excerpt or filing_text` — the same text the model
   generated from (the assess_quality rule, summary_pipeline.py:763-770). The 320k cap is a
   non-issue: model input == excerpt, so a genuine quote is in it by construction. BOTH empty →
   flag/drop NOTHING (figure_trace.py:262-267 — never punish the degraded population).
5. **Rule 6 safe by construction**: quality/audit keys are additive raw_summary metadata, never in
   SSE frames (COMPLETE_EVENT_KEYS pinned); the stream harness mocks summarize_filing at the
   pipeline boundary and CANONICAL_PAYLOAD has no forward_signals — pipeline-side reads must
   tolerate absence. No locked-test edits.
6. **Eval**: coverage/recall HARD gates can only move if a drop EMPTIES §5 (guidance/trends survive
   by design — quotes-only drops) or a ground-truth fact's sole rendering sat in a quote (facts live
   in the metrics table; verify in the readout run). gate_fail_rate is pinned 0.0/ε — the new scorer
   must be WARN-only, NEVER in compute_gate_failures; a metric absent from baseline_scores.json is
   skipped by the gate (the sanctioned inert-ship path). Runner has grounding['filing_text'] in
   _run_one; scorers are otherwise payload-pure — filing text enters scoring as an optional kwarg,
   normalized ONCE per case (copilot_runner precedent).
7. **No prompt text changes in this slice** → generation byte-identical, no SUMMARY_PROMPT_VERSION
   bump, no re-pin (T3.2 shape). Prompt tuning (incl. the recovery snippet's missing "verbatim"
   qualifier) stays in the T4 follow-up, informed by this slice's measurement. Stored-row staleness
   for pre-gate summaries is an ARM-TIME decision — surfaced in the PR, not decided here.
8. **No tier effect, no new reasons string**: T5.4 is a content-repair gate (armed = fabricated
   quote removed, summary served full), not a tier gate — avoids the frontend GROUNDING_REASON
   single-reason de-escalation contract entirely (SummaryDisplay.tsx:41).

## Design decisions (locked)

- **Verbatim = exact substring after upgraded shared normalization.** Fold curly double quotes →
  `"`, curly apostrophes → `'`, en/em/horizontal dashes → `-`, in `normalize_for_match` itself so
  generation gate, T4 read-time enrichment, and the copilot eval keep ONE definition (strictly
  fewer false-unverified everywhere). Divergence from the plan doc's "rapidfuzz ≥92" as the drop
  criterion is deliberate: ≥92 keeps word-changed quotes, and quotation marks assert exactness.
- **rapidfuzz is telemetry, not the gate**: failing quotes also get `fuzz.partial_ratio` on the
  normalized strings; `near_miss` (≥92 = lightly-paraphrased) vs hard-fail (<92 = fabrication-class)
  buckets are the data that decides arming + T4-follow-up prompt tuning. First repo rapidfuzz use.
- **Short quotes (<24 normalized chars) pass uncounted** (unverifiable-by-construction; the
  conservative figure-trace posture). Malformed/non-string entries pass untouched.
- **Armed behavior**: remove failing ManagementQuote items entirely (plan wording "dropped");
  guidance/known_trends/subsequent_events NEVER touched. Dropped items preserved in the audit for
  forensics.
- **Audit home**: `raw_summary["forward_quote_audit"] = {checked, unverified:[{speaker,score}],
  near_miss, dropped:[{speaker,quote}] (armed only)}` written by the gate at generation time;
  pipeline logs the greppable counter from it (measurement-always, flag on or off):
  `forward_quote_unverified count=%d near_miss=%d dropped=%d flag=%s filing_id=%s sic=%s speakers=%s`.

## Plan

- [ ] **provenance_service**: typography folds in `normalize_for_match` (+ docstring: one shared
      verbatim definition, now also the generation gate's) + new pins in test_provenance_service
      (existing pins must pass unchanged).
- [ ] **New leaf module `app/services/ai/forward_quote_gate.py`** (figure_trace sibling, pure — no
      settings import): `gate_forward_quotes(sections, source_text, armed) -> Optional[dict]` —
      normalize source once; per-quote exact-verify else fuzz-score; mutate (drop) only when armed;
      return audit or None (no quotes / no source basis).
- [ ] **config.py**: `AI_FORWARD_QUOTE_GATE: bool = False` after AI_FIGURE_TRACE_GATE, same
      advisory-first comment style; docs/CONFIGURATION.md one-liner under the figure-trace entry.
- [ ] **openai_service**: call the gate inside `summarize_filing` after risks normalization, before
      the coverage snapshot; attach audit to raw_summary payload. Update figure_trace.py:78-83
      exemption comment (+ module docstring) to point at the now-enforced invariant (docs-vs-code).
- [ ] **summary_pipeline**: greppable counter next to figure_trace_untraceable, reading the audit
      key tolerantly (CANONICAL_PAYLOAD lacks it).
- [ ] **Eval**: `score_forward_quote_fidelity` (verified fraction; near-misses in violations; 1.0
      neutral when no quotes/no filing text) with filing_text threaded from runner (normalized once);
      RubricScore field default 1.0; report row; `_WARN_GATES` entry (inert until a future re-pin);
      NOT in compute_gate_failures. RUNBOOK WARN-dim paragraph.
- [ ] **Tests (rule 12)**: test_forward_quote_gate.py (verbatim/case/whitespace/typography pass;
      fabricated flagged + dropped-when-armed; near-miss bucketed; short-quote pass; empty-source
      nothing; no-quotes None; malformed kept; guidance/trends untouched; audit shape; armed
      list-surgery); flag on/off at the openai_service seam (patch settings object); scorer pins in
      test_eval_content_scorers style + regression-gate WARN pin; normalization fold pins.
- [ ] **Gate + readout**: full backend gate; live dev probes (flag off: audit counts; flag on: drop
      + markdown/coverage sync); eval `--runs 3` NOT to re-pin but for (a) no-dim-moved confirmation
      and (b) the first fleet-wide forward-quote fidelity readout (per-filing) → PR body.
- [ ] **Adversarial review** (2+ reviewers: gate semantics/boundaries; eval/runner contract) → fix →
      commit → push → draft PR (subscribe + ~1h check-ins).

## Not in scope (documented)
- Prompt tuning (schema_template quote instruction, recovery-snippet "verbatim" qualifier) — T4
  follow-up, informed by this measurement; keeps this slice eval-neutral.
- Arming the flag + stale-refresh of pre-gate rows — founder decision once the FP readout is in.
- Other verbatim-claimed surfaces (risks/results/footnotes supporting_evidence) — already read-time
  excerpt-nulled by T4; generation-gating them is a separate decision.
- Read-vs-generation verification-text mismatch (generation: excerpt/filing_text; read:
  critical_excerpt/markdown_content) — conscious note; both are the filing's own text.
- T5.2b/T5.3 deferred ledgers carry over (M&A payments, effective tax rate, ROIC, segment axes,
  buyback-halt narration probe, IFRS equity-holders dividend variant).
