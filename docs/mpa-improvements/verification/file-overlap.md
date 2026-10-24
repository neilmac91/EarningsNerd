# File-overlap matrix (report §6, verification §9e)

The live branches are measured: `git diff --name-only $(git merge-base origin/main origin/<branch>) origin/<branch>`, on
2026-10-24 at 22:18 UTC (first measured at 21:10; re-measured when WP1 changed to the quiet scheme, §2). This plan's work packages (WP0–WP5) list the files each change edits. The
sibling plans' rows list the files each area owns, because no sibling branch or report existed when
this was measured (44 remote branches checked at 22:18 UTC). When one lands, replace its row with its measured `git diff --name-only` and
rerun the script (in the [methods appendix](../methods.md#file-overlap-script)).

Cells count shared files; · means none.

| | WP0 | WP1 | WP2 | WP3 | WP4 | WP5 | charts | analysis | table | #1601 | #1597 | section-nav | #1583 | #1600 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **WP0 lineage backfill** (10 files) | — | · | · | · | · | · | · | · | · | · | 1 | 1 | 1 | 1 |
| **WP1 quiet notation** (29 files) | · | — | 4 | · | 6 | 2 | 3 | 2 | 5 | · | 3 | 2 | · | · |
| **WP2 data-notes words** (10 files) | · | 4 | — | 1 | · | 3 | · | · | · | · | · | · | · | · |
| **WP3 exports** (9 files) | · | · | 1 | — | · | · | 2 | 1 | 1 | 3 | · | · | · | · |
| **WP4 surfaces + results header** (8 files) | · | 6 | · | · | — | · | 1 | · | 1 | · | 2 | 2 | · | · |
| **WP5 restatement note** (7 files) | · | 2 | 3 | · | · | — | · | · | · | · | · | · | · | · |
| **charts plan (scope)** (7 files) | · | 3 | · | 2 | 1 | · | — | · | 1 | · | 1 | 1 | · | · |
| **analysis plan (scope)** (7 files) | · | 2 | · | 1 | · | · | · | — | · | 1 | · | · | · | · |
| **table plan (scope)** (7 files) | · | 5 | · | 1 | 1 | · | 1 | · | — | · | 1 | 1 | · | · |
| **#1601 export-source** (6 files) | · | · | · | 3 | · | · | · | 1 | · | — | 1 | · | · | · |
| **#1597 status-line** (19 files) | 1 | 3 | · | · | 2 | · | 1 | · | 1 | 1 | — | 3 | 2 | 1 |
| **section-nav (no PR)** (9 files) | 1 | 2 | · | · | 2 | · | 1 | · | 1 | · | 3 | — | 1 | 1 |
| **#1583 per-filing-currency** (9 files) | 1 | · | · | · | · | · | · | · | · | · | 2 | 1 | — | 1 |
| **#1600 waitlist-source** (5 files) | 1 | · | · | · | · | · | · | · | · | · | 1 | 1 | 1 | — |

Shared files by pair:

- WP0 lineage backfill × #1597 status-line: `tasks/todo.md`
- WP0 lineage backfill × section-nav (no PR): `tasks/todo.md`
- WP0 lineage backfill × #1583 per-filing-currency: `tasks/todo.md`
- WP0 lineage backfill × #1600 waitlist-source: `tasks/todo.md`
- WP1 quiet notation × WP2 data-notes words: `analysis/components/DataNotes.tsx`, `analysis/lib/dataNotes.ts`, `frontend/tests/unit/analysis-source-quality.spec.tsx`, `frontend/tests/unit/data-notes.spec.ts`
- WP1 quiet notation × WP4 surfaces + results header: `.impeccable/design.json`, `DESIGN.md`, `frontend/DESIGN_SYSTEM.md`, `analysis/components/AnalysisPageClient.tsx`, `analysis/components/KpiStrip.tsx`, `frontend/tests/e2e/analysis-layout.spec.ts`
- WP1 quiet notation × WP5 restatement note: `analysis/components/DataNoteMark.tsx`, `analysis/lib/dataNotes.ts`
- WP1 quiet notation × charts plan (scope): `frontend/DESIGN_SYSTEM.md`, `analysis/components/TrendCharts.tsx`, `frontend/tests/unit/trend-charts-annotation.spec.tsx`
- WP1 quiet notation × analysis plan (scope): `analysis/components/NarrativePane.tsx`, `frontend/tests/unit/narrative-pane.spec.tsx`
- WP1 quiet notation × table plan (scope): `frontend/DESIGN_SYSTEM.md`, `analysis/components/MetricsTable.tsx`, `analysis/lib/tableFormat.ts`, `frontend/tests/unit/analysis-table-format.spec.ts`, `frontend/tests/unit/metrics-table.spec.tsx`
- WP1 quiet notation × #1597 status-line: `DESIGN.md`, `frontend/DESIGN_SYSTEM.md`, `frontend/tests/e2e/text-floors.spec.ts`
- WP1 quiet notation × section-nav (no PR): `DESIGN.md`, `frontend/DESIGN_SYSTEM.md`
- WP2 data-notes words × WP3 exports: `backend/app/services/analysis_export_metadata.py`
- WP2 data-notes words × WP5 restatement note: `backend/app/services/trend_analysis/data_notes.py`, `backend/tests/unit/test_analysis_data_notes.py`, `analysis/lib/dataNotes.ts`
- WP3 exports × charts plan (scope): `analysis/lib/chartExport.ts`, `frontend/tests/unit/chart-export.spec.ts`
- WP3 exports × analysis plan (scope): `backend/app/services/export_service.py`
- WP3 exports × table plan (scope): `backend/app/services/excel_export_service.py`
- WP3 exports × #1601 export-source: `backend/app/services/export_service.py`, `backend/tests/unit/test_export_service.py`, `backend/tests/unit/test_export_voice.py`
- WP4 surfaces + results header × charts plan (scope): `frontend/DESIGN_SYSTEM.md`
- WP4 surfaces + results header × table plan (scope): `frontend/DESIGN_SYSTEM.md`
- WP4 surfaces + results header × #1597 status-line: `DESIGN.md`, `frontend/DESIGN_SYSTEM.md`
- WP4 surfaces + results header × section-nav (no PR): `DESIGN.md`, `frontend/DESIGN_SYSTEM.md`
- charts plan (scope) × table plan (scope): `frontend/DESIGN_SYSTEM.md`
- charts plan (scope) × #1597 status-line: `frontend/DESIGN_SYSTEM.md`
- charts plan (scope) × section-nav (no PR): `frontend/DESIGN_SYSTEM.md`
- analysis plan (scope) × #1601 export-source: `backend/app/services/export_service.py`
- table plan (scope) × #1597 status-line: `frontend/DESIGN_SYSTEM.md`
- table plan (scope) × section-nav (no PR): `frontend/DESIGN_SYSTEM.md`
- #1601 export-source × #1597 status-line: `docs/brand/08-applications.md`
- #1597 status-line × section-nav (no PR): `DESIGN.md`, `frontend/DESIGN_SYSTEM.md`, `tasks/todo.md`
- #1597 status-line × #1583 per-filing-currency: `lessons/README.md`, `tasks/todo.md`
- #1597 status-line × #1600 waitlist-source: `tasks/todo.md`
- section-nav (no PR) × #1583 per-filing-currency: `tasks/todo.md`
- section-nav (no PR) × #1600 waitlist-source: `tasks/todo.md`
- #1583 per-filing-currency × #1600 waitlist-source: `tasks/todo.md`
