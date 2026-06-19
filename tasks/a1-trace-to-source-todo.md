# A1 — Trace-to-Source (Risk Factors) — Implementation Todo

Implements the **NOW / A1** item from `docs/competitive-strategy-roadmap-2026.md`: surface verifiable
provenance for AI claims. This first slice covers **risk factors** (where an evidence excerpt + section
reference already exist in the data); per-metric XBRL provenance is a deliberate follow-up.

## Design decisions
- **Enrich at serialization (`GET /api/summaries/filing/{id}`), not at generation.** Additive and
  works for *every existing summary* with no migration / no re-gen. Minimal impact.
- **Verified vs. cited (honest labeling).** Check the AI's `supporting_evidence` against the cached
  filing text (`FilingContentCache.critical_excerpt` → fallback `markdown_content`). If found, build a
  `#:~:text=` deep link to the exact quote and mark `source_verified=true` ("Verified in filing"). If
  not, link to the filing/section and mark `source_verified=false` ("Cited — open section"). We never
  claim "verified" for text we can't actually locate — this is the anti-hallucination brand.
- **Canonical UI source is `raw_summary.sections.risk_factors[]`** (confirmed in
  `SummarySections.tsx:108-126`), so enrichment targets that path (top-level `risk_factors` enriched
  too, for export consistency).
- Fully backward compatible: all new fields are optional; UI renders cleanly when they're absent.

## Backend
- [ ] `backend/app/services/provenance_service.py` (pure, unit-tested):
  - [ ] `normalize_for_match(text)` — lowercase + collapse whitespace.
  - [ ] `extract_quoted_span(evidence)` — pull the quoted span out of strings like
        `Item 1A: "Supply chain constraints…"` (curly + straight quotes); else return the whole string.
  - [ ] `verify_excerpt_in_text(excerpt, source_text)` — min-length gate + substring match on
        normalized text.
  - [ ] `build_text_fragment_url(base_url, excerpt)` — append percent-encoded `#:~:text=` snippet
        (first ~10 words / ~120 chars).
  - [ ] `build_risk_source(risk, filing, source_text)` → `{source_section_ref, source_url, source_verified}`.
  - [ ] `enrich_risk_factors(raw_summary, filing, source_text)` — non-mutating deep copy; tolerant of
        missing `sections`/`risk_factors`.
- [ ] Wire into `summaries.py:get_summary`: `joinedload(Filing.content_cache)`, derive source text,
      enrich `raw_summary.sections.risk_factors` + top-level `risk_factors`, return explicit dict.
- [ ] `backend/tests/unit/test_provenance_service.py`.

## Frontend
- [ ] `types/summary.ts`: add optional `source_url`, `source_verified`, `source_section_ref` to `RiskFactor`.
- [ ] `lib/formatters.ts:normalizeRisk`: pass the three fields through.
- [ ] `features/filings/components/SummaryRisks.tsx`: render a quiet "View in filing ↗" link +
      verified/cited label; dark-mode-aware, calm styling (no loud rose box).
- [ ] Frontend unit test asserting the link + label render.

## Verify
- [x] `pytest backend/tests/unit/test_provenance_service.py -q` → **20 passed**
- [x] frontend `vitest` (new spec + existing risk specs) → **9 passed**; `eslint --max-warnings 0` → clean; `tsc -p tsconfig.ci.json` → clean
- [x] Manual reasoning: verified vs unverified path, missing-cache resilience, existing-summary compatibility.

## Review (completed)
All items above implemented and verified. Highlights:
- **No migration / no re-gen**: enrichment runs in `get_summary`, so provenance lights up for every
  existing summary immediately. All new fields are optional → fully backward compatible.
- **Honest labeling**: "Verified in filing" only when the evidence excerpt is actually located in the
  cached filing text (with a `#:~:text=` deep link to the passage); otherwise "Cited — open section".
- **Scope held**: risk factors only. Per-metric XBRL provenance is the deliberate follow-up PR.
- Backend logic is pure/isolated in `provenance_service.py` (stdlib-only, 20 unit tests).
