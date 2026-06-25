# Fix: PDF export 500 + limited-data CSV export

## Root causes (verified against code)

1. **PDF "Failed to export PDF"** — `ExportService.generate_pdf_html` passes structured
   **dict/list** section objects (`executive_snapshot`, `management_discussion_insights`,
   `segment_performance`, `guidance_outlook`, `three_year_trend`) into `_format_markdown`,
   whose first op is `text.strip()`. A dict has no `.strip()` → `AttributeError`. This runs
   inside `export_pdf` *before* `write_pdf()`, so WeasyPrint never executes → router 500 → toast.
   (export_service.py:105,142,184,191,198 + :217; export_pdf at :303 before :305.)
   - **Latent secondary:** the Docker image installs Pango/Cairo but no fonts / `fontconfig` /
     `libpangoft2-1.0-0`. Masked today by the AttributeError; would become the next failure
     once #1 is fixed. Must ship together. (backend/Dockerfile:11-22.)

2. **CSV limited data** — `generate_csv` only serializes `financial_highlights.table` +
   `risk_factors`; it drops every other section (exec summary, profitability/cash-flow/
   balance-sheet, MD&A, guidance, liquidity, footnotes, trend, segments). Server-side bug
   (the "Generated" timestamp is `datetime.now()`, not client-built). (export_service.py:241-297.)

## Decisions (from product owner)
- CSV: **rich — all sections** (+ fix PDF to render all sections).
- Risks: **match the page** (only risks with non-placeholder supporting evidence).
- Keep both endpoints **Pro-gated** (no change).

## Plan
- [x] Investigate + verify root causes (workflow + direct code read)
- [x] New module `app/services/summary_sections.py`: single source of truth that turns
      `raw_summary["sections"]` into an ordered list of format-agnostic Section/Block objects.
      Mirrors the frontend placeholder filter + `normalizeRisk` so exports match the page.
- [x] Refactor `export_service.generate_pdf_html` to render Sections → HTML (with HTML escaping).
- [x] Refactor `export_service.generate_csv` to render Sections → CSV rows (all sections).
- [x] Remove now-dead `_format_markdown`; fix the `summary` variable shadow (gone with rewrite).
- [x] Dockerfile: add `libpangoft2-1.0-0 fontconfig fonts-dejavu-core`.
- [x] Regression test `tests/unit/test_export_service.py` (9 tests).
- [x] Run pytest; verify (9/9 new + 19/19 smoke pass; ruff clean).
- [x] Commit + push to `claude/eager-ride-bxoveg`; open draft PR.

## Review

**What changed**
- `backend/app/services/summary_sections.py` (new): `render_sections(raw_summary)` → ordered
  `Section`/`Block` list. Per-section builders for all 9 sections, mirroring the canonical
  renderer in `openai_service.py`. Replicates the frontend `PLACEHOLDER_PATTERNS` +
  `normalizeRisk` so risks (and empty/placeholder sections) match the on-page UI exactly.
- `backend/app/services/export_service.py`: both `generate_pdf_html` and `generate_csv` now
  render from `render_sections` (single source of truth — kills the page/PDF/CSV divergence).
  All filing-derived text is HTML-escaped in the PDF (was unescaped). Removed dead
  `_format_markdown` + `re` import; the `summary` variable shadow is gone with the rewrite.
- `backend/Dockerfile`: added `libpangoft2-1.0-0`, `fontconfig`, `fonts-dejavu-core` (the
  latent gap that would have surfaced once the AttributeError was fixed).
- `backend/tests/unit/test_export_service.py` (new): pins both bugs.

**Verification**
- 9/9 new tests pass, incl. an end-to-end `export_pdf` that produced a valid `%PDF` (16.7KB).
- 19/19 smoke tests pass; `ruff check` clean; router imports clean.
- Generated a Biogen-mirroring sample: CSV now spans Exec Assessment, full Financials (incl.
  Change col + profitability/cash-flow/balance-sheet/notes), Risks, MD&A, Outlook; PDF renders.

**Not changed (by decision)**: Pro-gating on both endpoints; frontend handlers (the bug was
100% server-side — frontend just downloads the blob).
