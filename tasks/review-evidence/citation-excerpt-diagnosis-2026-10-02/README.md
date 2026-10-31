# Copilot citation excerpt-boundary diagnosis (queued after F; Codex 5939835749)

This is an offline, zero-spend diagnosis on main `02628e57`. Nothing was pushed, and there were no provider or paid calls. The test change is a local commit `17e6e545` on `claude/cite-excerpt-diagnosis`, kept here as `regression-and-control.patch`.

**The gap.** On main:
- `copilot_service._verify_citations` (:456–468) verifies a citation through `verify_excerpt_in_text`, which checks only `extract_quoted_span(excerpt)`.
- It then publishes the **full** model excerpt as `verified: True`.
- The Sources panel shows that full excerpt in quote marks, with "Source match found".
- `section_ref` is never verified.

**Bottom line.** The gap is real on main, but it **did not occur in any retained eval run**: 0 of the 9 text citations across 8 runs are affected. No `section_ref` contains quote characters.

## 1. Regression and control

Both are in the existing owner, `backend/tests/unit/test_copilot.py`. That file owns the Copilot publication boundary and is not a locked contract test.

- **`test_service_withholds_excerpt_verified_only_by_inner_quoted_span`** is a strict xfail (`xfail(strict=True, raises=AssertionError)`, labelled KNOWN DEFECT).
  - Its excerpt is the file's existing `_KNOWN_SENTENCE` behind an invented prefix, and its section is `Item 7 "Fake words here"`.
  - It expects the existing withholding error, `_PUBLICATION_ERROR`, rather than a trimmed excerpt.
  - Run with `--runxfail` it FAILS on main: the terminal event is `complete`, publishing the prefixed excerpt with `verified: True`. The verified span is only the inner sentence; `full_excerpt_in_source` is False. See `runxfail.log`.
- **`test_service_publishes_full_excerpt_contiguous_in_source`** is the control and passes. The same sentence without the prefix publishes byte-identical, with `verified: True` and a fragment link.
- **Gates:**
  - With the xfail marker: `136 passed, 1 xfailed`.
  - Across the owner and the related suites: `221 passed, 1 xfailed`. Ruff is clean.
  - A throwaway full-excerpt check, reverted and never committed, flips the regression to XPASS(strict). The other 450 `test_copilot*` tests pass. See `probe-full-excerpt.log`.

## 2. Caller inventory

Both helpers check only the inner quoted span: `extract_quoted_span` takes the first quoted span of 8+ characters, and `verify_excerpt_in_text` applies the 24-character floor.

| Site | What is checked | What is displayed | Prefix tolerance intended? | Display matches what was verified? |
|---|---|---|---|---|
| `copilot_service._verify_citations` :456–468 | inner span | full excerpt, shown as a "verified" quotation; `section_ref` is the link label | No: the prompt requires a verbatim excerpt | **No. This is the defect.** |
| `build_text_fragment_url` (Copilot :462) | — | link to the inner span | n/a | follows from the defect |
| `build_evidence` :516–522, used by footnotes, metric takeaways and commentary | inner span | the quoted span only, when verified | **Yes**, pinned by `test_provenance_service.py` | Yes |
| Forward quotes, via `build_evidence` :548 | inner span | the full quote `“{block.text}”` | Not by design; the generation gate is off in prod | sibling exposure on a separate surface, out of scope |
| `project_risk_list` :176–189 | whitespace-exact, then inner span | a span sliced from the source, labelled "Filing excerpt" | Yes, deliberately | Yes |
| `evidence_snap` :145/:173 | inner span, mirroring `build_evidence` | none directly | Yes, pinned | follows `build_evidence` |
| `evals/copilot_scorers.py:65` | same check | eval metric only | — | **cannot see this class today** |

**Conclusion:** do not change the shared helpers globally. The defect is confined to Copilot's `_verify_citations`.

## 3. Offline replay

Run with `replay_excerpt_boundaries.py`; results in `replay-results.json`.

**Copilot citations.** 8 retained copilot-eval runs, 144 rows, 245 citations: 236 XBRL (application-built, excluded) and 9 text.
- All 9 text citations verified.
- All 9 are fully contiguous in their source; 0 verified only through the inner span. **0 affected.**
- The `source_text` sha256 per accession is identical across runs.
- All 9 `section_ref` values are plain labels with no quote characters. But 7 of these 9 legitimate labels are not themselves in the source, so verifying labels against the source is not viable.

**Summary surfaces.** Run with `replay_summary_surfaces.py` over 2 retained summary-eval artifacts; results in `replay-summary-surfaces.json`.

| Surface | Fully contiguous | Not contiguous | Below floor | Inner span only |
|---|---|---|---|---|
| Forward quotes | 175 | 0 | 3 | 0 |
| Metric-takeaway evidence | 491 | 16 | 12 | 0 |
| Footnote evidence | 460 | 9 | 24 | **1** |
| Risks | 532 | 0 | 5 | 0 |

The one inner-span-only case is BYND `0001655210-26-000037`, a sentence stitched across a page break. On the summary page it is displayed safely as the span only. It still shows that the shape occurs in practice.

No evidence-snap audit artifacts exist offline.

## 4. Fix proposal (not implemented; for review before any paid step)

1. In `copilot_service._verify_citations` only, verify the **whole displayed excerpt**. Use a new sibling helper, for example `provenance_service.verify_whole_excerpt_in_text`:
   - strip one quote pair only when it wraps the whole excerpt (never an inner span);
   - normalize;
   - apply the 24-character floor;
   - test containment.
2. On failure, use the existing path: a referenced failure withholds the whole answer (`_PUBLICATION_ERROR`); an unreferenced one stays omitted. Nothing is trimmed, stitched, snapped or substituted, and the published bytes are unchanged.
3. Leave `verify_excerpt_in_text` and `extract_quoted_span` untouched. Also:
   - optional: build the fragment URL from the whole excerpt;
   - with approval: point `evals/copilot_scorers.py:65` at the new helper;
   - update the copilot_service docstring and the RUNBOOK "Excerpt verification" row.
4. **`section_ref`** needs a separate, explicitly approved contract. Recommended: withhold citations whose `section_ref` contains `"`, `“` or `”`; 0 of 9 retained would be affected. The alternative is publishing a null `section_ref`.
5. **Forward quotes** are a separate decision: arm the existing gate, or add a read-time whole-quote check.
6. **Predicted impact on retained evidence:** 0 changes. Summary, Risks and evidence snap stay byte-identical, and nothing changes in the frontend.

## 5. Validation plan

**Offline (free):**
- Remove the xfail.
- Add controls for:
  - a wrapped `"…"` excerpt;
  - a typography- and whitespace-folded excerpt;
  - an excerpt that contains an inner `“…”` term but is fully contiguous;
  - a below-floor excerpt, which is withheld;
  - an unreferenced prefixed declaration, which stays omitted.
- Run the full backend gate and the RUNBOOK offline Copilot gate.

**Mutations M1–M7**, each of which must turn a test red: revert to the old helper; drop normalization; drop the wrapping-quote strip; use the inner span; drop the floor; apply the change globally (the provenance test must fail); remove the section_ref guard if it is adopted.

**Replay:** re-run both replay scripts with a column for the new helper. Expect 9 of 9 citations verified and the summary counts unchanged.

**Paid (proposed only):** a PR touching `backend/app/**` automatically triggers:
- `copilot-eval`, about $0.005–0.012 per run, warm, off-peak;
- `eval-baseline`, about $0.13–0.43 off-peak. It is not informative for a change that touches only Copilot.

The worst case is under $1.50.

## Not verified

- The production rate: live traffic was not observed, and 9 retained citations cannot bound it.
- The retained `verified` flags were produced by older code shas.
- No evidence-snap data exists offline.
- The summary replay uses `grounding_excerpt` as a proxy for the cached source.
- The production forward-quote flag value comes from the 2026-09-20 receipts, not a live check.
- The frontend display contract was read statically, not rendered.
