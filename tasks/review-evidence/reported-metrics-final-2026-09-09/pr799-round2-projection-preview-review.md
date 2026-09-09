# Final #799 numeric surfaces and observed preview chronology — 2026-09-09

Inputs: final actual `work/pr799-summary-round2/eval_20260909T083945Z.json` (SHA2564ea2c816b08e2c405e80ff5eb6c46d046e6b13effb0690d7a97f0a2f865de24e), and `work/pr799-round2-normalization-projection/comparison.json`, produced by gated **b36ad45433b6b2eef05d259c168b90ccfe1b9452**. First d and first corrected projections remain unchanged. No generation, network/source call, test, proof or repository edit. This review performs offline artifact comparisons, arithmetic checks and read-only code inspection.

## Numeric projection: scoped clearance across all52 outcomes

All **272 AFTER rows** preserve model metric label/current/prior strings through normalization: **zero supplied-prior replacements or added textual priors**. All272 web rows’ first four cells (label, current, prior, computed change) match rows in the actual CSV body and PDF HTML body; these strings also occur in the Markdown. This is helper/body serialization evidence, not a live browser, persisted summary or PDF-pagination inspection.

Every computable normalized current/prior pair has deltaPercent consistent with `(current−prior)/abs(prior)` (zero prior remains unknown). PDD both ×1000 and TSM both ×1000000 base values are correct; ordinary EPS remains unscaled. BA/INTC/COIN/RIVN explicit accounting signs retain the corrected direction across final projections. No current unit correction is lost between the inspected final surfaces. The two added per_ads blocks belong to JD1 dilutedordinary6.45×2=12.9CNY and TSM0 dilutedordinary65.47×5=327.35TWD; explicit BABA/JD model ADS rows retain their own current/prior text. This checks preservation/arithmetic, not new certification of ADS metadata dates or accounting provenance.

Four JPM rows retain eight date-bearing amount strings, have unknown currentValue/deltaPercent and web change“—”; numeric priorValue is still supplied by existing XBRL fallback. This is the disclosed anchored-scalar limitation. It does not silently delete an entire row or rewrite dates. All other268 rows have both numeric values. Provided margin priors are preserved; explicit percent-valued margins use shared ppts on final display. Normalized percentage fields are not a claim to change the established ppts rendering policy.

## Preview semantics: confirmed inherited mismatch, not clear

The metadata total is correct: **380 retained callbacks,161770 characters**. Exact chronological comparison shows **zero text revisions between frames within every one of the52 outcomes**. Each outcome has precisely **one distinct frame**, repeated5–14 times. Removing only the company/form/period header leaves **one identical generic body across all52**. Thus it was feasible to read all distinct observed text without pretending duplicated frames contain new evidence: all52 headers and every line of the shared body were read. `work/pr799-round2-preview-chronology.json` records per-outcome frame/character counts, hashes, header and zero revisions.

Shared body, verbatim:

> ## Financials
> - Key financial metrics were not disclosed in the structured extract.
> ## Risks
> - No material incremental risks were highlighted beyond routine disclosures.
> ## Management Commentary
> - Management commentary was limited in the structured extract.
> ## Outlook
> - Guidance was not disclosed; monitor subsequent updates for direction.

These are deterministic absence/default claims, **not invented financial amounts**. They are preview-only and superseded at final completion. Every final raw result contains a financial table (272rows total); examples clearly contradict the preview absence claims: ASML gives2026EUR34–39B sales andQ1EUR8.2–8.9B guidance; TSM gives2026USD52–56B capex; final foreign risks include specific credit, earthquake and concentration exposures. The previews contain no financial values or reported-basis labels at all, so complete frame retention does not establish preview financial coverage or exercise the unit fix on that transient surface.

**Correctness refutation1:** an early partial JSON may reasonably lack metrics. That can justify not emitting yet, but every retained frame through the last callback is identical, including long14-callbackBABA0; generic “not disclosed/no material” assertions are not faithful staged evidence. We cannot reconstruct precisely when each source JSON property arrived from these frames alone.

**Correctness refutation2:** authoritative final Markdown is complete and replaces previews. Confirmed, and no final corruption is asserted. It does not make transient negative assertions correct while the UI is loading. `summary_pipeline.py:795–803` coalesces queued previews as SSE preview events when its existing preview path is enabled. This is a code path, not observation that all380 callbacks reached a browser (coalescing explicitly prevents that inference).

Cause is supported by actual code: `openai_service._partial_markdown_preview:493–502` repairs partial JSON, then calls legacy `_build_structured_markdown`. That builder in `ai/markdown_render.py` reads `executive_snapshot`, `financial_highlights`, `risk_factors`, `management_discussion_insights` and emits these defaults when absent. Final rendering at `openai_service.py:691–701` stamps the schema version and calls `render_sections`, which handles the actual current section names. The partial method's “SAME builder” docstring and legacy builder's “PRIMARY…not a fallback” description are inconsistent with current final code.

This is an **inherited preview-rendering defect newly measurable by d's retained frames**, not evidence that d created it. First d also has52/52 single-distinct generic previews. The legacy builder has no diff between reviewed c16ff38 andb36ad454. Final c lacks retained preview frames, so c's actual displayed chronology remains unknown; code identity is not a historical browser observation.

Smallest future repair seam: current-schema partial rendering at the existing preview owner, with no “not disclosed/no risk” assertions merely because a section has not arrived; use the shared final projection where safe. Preserve best-effort callback isolation, queue coalescing, cancellation and final authority. This report implements nothing and requests no new provider run. The observed semantic defect should remain explicit in release/readout decisions even if retention is accepted.

## Limits

No fabricated or subsequently revised numerical preview claim exists in these retained frames: there are no numerical business claims beyond company/form/period headers, and no within-outcome revisions. Only the unsupported absence/default claims above are established. Exact callback text and ordering do not identify internal provider attempts or prove final-generation association; metadata correctly retains not_observed. Full-frame semantic inspection here was achievable through exact deduplication, not a random sample. Final financial/source correctness beyond numeric preservation remains assigned to root/A/B financial reviews; no all52 full-filing reread or universal quality clearance is implied.


Count clarification, 2026-09-09: each of the 52 outcomes has one distinct retained full frame within that outcome. There are 29 distinct full strings globally across all 380 callbacks, owing to metadata headers; all share the same Financials-to-end body. The earlier per-outcome statement is not a claim of 52 globally unique strings.
