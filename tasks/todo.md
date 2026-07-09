# Tier 3.2 — Number-diff machine gate ("figure not traceable")

**Goal (plan Part 4.3.2 / roadmap 3.2):** post-generation, diff every numeric token in the summary's
free prose against the legitimate set — (XBRL standardized values ∪ code-computed deltas ∪
filing-excerpt numbers) — and surface untraceable figures as a deterministic `assess_quality` reason.
The "numbers from code, words from the model" principle enforced as a runtime grounding gate: it
catches any figure the model invents. $0, no infra.

## Load-bearing design decisions (from the integration map)

1. **Advisory-first, flag-gated — MANDATORY (billing safety).** `assess_quality`'s `tier` (`summary_generation_service.py:276`)
   is a hard AND wired to the quota gate (`summary_pipeline.py:714`, `AI_QUALITY_GATE` default **on**):
   `tier=="partial"` ⇒ user not charged + "partial" badge. A false positive = lost revenue + a bad
   badge on a good summary, and it poisons the precompute corpus + can block a good keep-better
   refresh. So: attach `figures_untraceable: [...]` to the verdict **additively**; do NOT fold it into
   the tier. A new **`AI_FIGURE_TRACE_GATE` (default False)** is the ONLY thing that lets an untraceable
   figure affect the tier — ships off until the false-positive rate is measured on the corpus. (House
   pattern: `AI_QUALITY_GATE` itself is flagged; T3.0 scorers WARN-first.)
2. **Police free prose only.** v2 renderer-injects XBRL figures into `results_that_matter` (traceable
   by construction), so exclude the metric TABLE and verbatim QUOTES (a management quote may cite any
   figure — exempt, like the ONE-HOME rule). The real fabrication surface is narrative prose.
3. **Reuse app-side helpers; keep evals independent.** evals/scorers deliberately does NOT import app
   code and the app keeps mirror copies (`_xbrl_value_appears` "mirrors the eval harness without
   importing it"). So build an app-side figure-trace helper; do NOT import `evals.scorers` into the
   request path. Reuse: `metric_delta_service.compute` (delta strings), `_xbrl_value_appears`
   (value→text match), `copilot_service`'s year/count filtering, `score_delta_consistency`'s
   conservative tolerance as the model.
4. **Conservative matching (avoid FPs).** Scale-aware (81.6B=81,600M), rounding tolerance, drop
   years (1900–2100) + bare small counts + page/item numbers; ppts/% matched against computed deltas
   or excerpt %; foreign-currency + per-share + bank/no-total edge cases guarded (the whole
   `test_assess_quality_bank.py` suite exists because a grounding rule once false-fired on 100% of banks).

## Plan

**STATUS: value-based matcher rewrite done; full backend gate GREEN (1582 passed). Corpus residual measured
(73 untraceable / 3-of-27 clean, a 4× cut from the string matcher's 295). Amend + push + draft PR next.**

### Key finding from the FP readout (drove the matcher rewrite)

The first matcher (canonical-key substring + ≥3-sig-digit renderings + flat 0.5% tolerance) over-flagged
massively (607 → then 295 dollar-only). A decisive per-figure categorization on KO (14 flagged) showed
**~64% were matcher brittleness** — the model had COPIED real figures from its own input ("$10 million",
"$73M", "3,659" all literally in the excerpt) that the substring matcher couldn't see (round forms like
"$10M" render to "10.0", never the natural "10"; prose rounds "$1,531M" from a raw "1,531.4"; a flat 0.5%
tolerance is too tight for a one-decimal rounding). The remaining **~36% are genuinely model-DERIVED
aggregates** ("total debt $43,890M" = a summed set of named line items present individually but never as
one number) — the real "numbers from code, words from the model" signal, i.e. the T5 work-list.

**Rewrite:** value-based, rounding-aware. A prose dollar figure grounds when its VALUE is within HALF the
place-value of its last significant digit of any XBRL value OR any excerpt number resolved to scale
(explicit scale word authoritative; comma-grouped magnitude admits units/thousands/millions; a BARE
number is never scaled up — that would ground a fabricated "$60B" against an incidental "60"). Recovers
the copied figures; the residual is the derived-aggregate / fabrication surface the gate exists to flag.

- [x] **`app/services/ai/figure_trace.py`** (new, app-side): (a) `prose_figures(sections) -> list[str]`
      — enumerate financial figures from the v2 narrative prose fields ONLY (the_print, earnings_quality,
      value_drivers, forward_signals guidance/known_trends, balance_sheet_liquidity leverage/liquidity,
      segment commentary), excluding the `results_that_matter` table + `forward_signals.quotes` verbatim;
      filter years/counts. (b) `legitimate_figures(xbrl_metrics, excerpt) -> set` — XBRL current/prior/
      series renderings (reuse `_number_renderings`-style scaling) ∪ `metric_delta_service.compute`
      display strings ∪ figures parsed from the normalized excerpt. (c) `untraceable_figures(sections,
      xbrl_metrics, excerpt) -> list[str]` — figures in (a) with no scale-aware match in (b), conservative.
- [x] **`config.py`**: `AI_FIGURE_TRACE_GATE: bool = False` (Settings; documented in docs/CONFIGURATION.md).
- [x] **`summary_generation_service.py::assess_quality`**: add optional `excerpt: str | None = None` param;
      after the grounding block (~:271), compute `figures_untraceable`; add it to the verdict dict
      (:277–283) additively; tier stays unchanged UNLESS `settings.AI_FIGURE_TRACE_GATE` and the list is
      non-empty (guarded so default-off = pure advisory). Keep `fi_components_present` usage intact
      (`test_fi_predicate_single_source` lock).
- [x] **`summary_pipeline.py:695`**: pass `excerpt=excerpt` to `assess_quality` (already in scope).
- [x] **Frontend badge**: `figures_untraceable` is additive-only; flag-off ⇒ tier/reasons unchanged ⇒
      badge unaffected. `summary-quality-badge.spec.tsx` GREEN (4 passed). No frontend code change.
- [x] **Tests (rule 12 gates):** `test_figure_trace.py` — traceable (XBRL value, computed delta, excerpt
      number) pass; a fabricated prose figure flagged; years/counts/quotes/table values NOT flagged;
      foreign-currency + per-share + bank no-total NOT false-flagged. Extend `test_quality_assessment.py`
      — verdict carries `figures_untraceable`; flag OFF ⇒ tier unchanged even with untraceable figures;
      flag ON ⇒ tier→partial + reason. Bank FP guard in `test_assess_quality_bank.py`.
- [x] **Full backend gate** GREEN (ruff + bandit + pytest, 1576 passed). **No eval re-run/re-pin:** the
      gate is post-generation + read-only and the eval calls `summarize_filing` directly (never
      `assess_quality`), so generation output + eval means are unchanged by construction. The FP readout
      below regenerates the corpus, so it doubles as the generation sanity check.
- [x] Committed + pushed (0f5ee68).
- [x] **Value-based matcher rewrite** (drove by the readout finding): figure_trace now grounds by VALUE
      with a rounding-aware tolerance (half last-sig-digit) against XBRL ∪ scale-cued excerpt numbers, not
      by string. Conservative excerpt scale policy (scale word / comma-grouped only; bare never scaled up).
      Recovers the ~64% that were the model copying real figures; residual = derived aggregates + fabs.
- [x] **FP corpus readout** (scratchpad/fp_readout.py over all 27 golden filings): 73 untraceable /
      3-of-27 clean / ~2 per filing (max 9 TSLA) — a 4× cut from the string matcher's 295. Residual is the
      derived-aggregate (T5) / fabrication surface. Feeds the PR body so the founder can time the flag flip.
- [x] Opened **draft PR #612** with the advisory-first rationale + the FP readout table (2 commits:
      b8a7b46 initial gate + 7f5636c value-based matcher). Subscribed; ~1h self check-in armed.

## Not in scope
- Flipping `AI_FIGURE_TRACE_GATE` on (needs the measured FP readout first).
- The citation/anchoring sibling (T4). The forward-signals verbatim hard gate (T5.4).
- Any change to the tier formula or the eval baseline.
