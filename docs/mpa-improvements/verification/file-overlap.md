# File-overlap matrix (report §6, verification §9e)

The live branches are measured: `git diff --name-only $(git merge-base origin/main origin/<branch>) origin/<branch>`, on
2026-10-25 at 08:20 UTC (first measured 2026-10-24 at 21:10, again at 22:18 when WP1 changed to the quiet scheme, and again when the sibling plans opened PRs). This plan's work packages (WP0–WP5) list the files each change edits. The
sibling plans' rows list the files each area owns, because the charts plan's later steps and the analysis plan have no branch. The table plan (#1606)
and the charts plan's step 4 (#1609) are measured from their branches. When one lands, replace its row with its measured `git diff --name-only` and
rerun the script (in the [methods appendix](../methods.md#file-overlap-script)).

Cells count shared files; · means none.

| | WP0 | WP1 | WP2 | WP3 | WP4 | WP5 | charts | analysis | #1606 | #1609 | #1601 | #1583 | #1608 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **WP0 lineage backfill** (10 files) | — | · | · | · | · | · | · | · | · | 1 | 1 | 1 | 2 |
| **WP1 quiet notation** (29 files) | · | — | 4 | · | 6 | 2 | 3 | 2 | 21 | 3 | · | · | · |
| **WP2 data-notes words** (10 files) | · | 4 | — | 1 | · | 3 | · | · | 3 | 1 | · | · | · |
| **WP3 exports** (9 files) | · | · | 1 | — | · | · | 2 | 1 | 1 | 1 | 3 | · | · |
| **WP4 surfaces + results header** (8 files) | · | 6 | · | · | — | · | 1 | · | 5 | 1 | · | · | · |
| **WP5 restatement note** (7 files) | · | 2 | 3 | · | · | — | · | · | 2 | · | · | · | · |
| **charts steps 5-7 (scope)** (8 files) | · | 3 | · | 2 | 1 | · | — | · | 3 | 5 | · | · | · |
| **analysis plan (scope)** (7 files) | · | 2 | · | 1 | · | · | · | — | 2 | · | 1 | · | · |
| **#1606 table plan** (125 files) | · | 21 | 3 | 1 | 5 | 2 | 3 | 2 | — | 5 | · | 1 | · |
| **#1609 charts renderer** (26 files) | 1 | 3 | 1 | 1 | 1 | · | 5 | · | 5 | — | 1 | 1 | 2 |
| **#1601 export-source** (12 files) | 1 | · | · | 3 | · | · | · | 1 | · | 1 | — | 1 | 1 |
| **#1583 per-filing-currency** (11 files) | 1 | · | · | · | · | · | · | · | 1 | 1 | 1 | — | 2 |
| **#1608 admin units** (12 files) | 2 | · | · | · | · | · | · | · | · | 2 | 1 | 2 | — |

Shared files by pair:

- WP0 lineage backfill × #1609 charts renderer: `tasks/todo.md`
- WP0 lineage backfill × #1601 export-source: `tasks/todo.md`
- WP0 lineage backfill × #1583 per-filing-currency: `tasks/todo.md`
- WP0 lineage backfill × #1608 admin units: `backend/tests/unit/test_migration_lock_safety.py`, `tasks/todo.md`
- WP1 quiet notation × WP2 data-notes words: `analysis/components/DataNotes.tsx`, `analysis/lib/dataNotes.ts`, `frontend/tests/unit/analysis-source-quality.spec.tsx`, `frontend/tests/unit/data-notes.spec.ts`
- WP1 quiet notation × WP4 surfaces + results header: `.impeccable/design.json`, `DESIGN.md`, `frontend/DESIGN_SYSTEM.md`, `analysis/components/AnalysisPageClient.tsx`, `analysis/components/KpiStrip.tsx`, `frontend/tests/e2e/analysis-layout.spec.ts`
- WP1 quiet notation × WP5 restatement note: `analysis/components/DataNoteMark.tsx`, `analysis/lib/dataNotes.ts`
- WP1 quiet notation × charts steps 5-7 (scope): `frontend/DESIGN_SYSTEM.md`, `analysis/components/TrendCharts.tsx`, `frontend/tests/unit/trend-charts-annotation.spec.tsx`
- WP1 quiet notation × analysis plan (scope): `analysis/components/NarrativePane.tsx`, `frontend/tests/unit/narrative-pane.spec.tsx`
- WP1 quiet notation × #1606 table plan: `.impeccable/design.json`, `DESIGN.md`, `docs/design/analysis-data-notes-redesign-2026-10.md`, `frontend/DESIGN_SYSTEM.md`, `analysis/components/AnalysisTeaser.tsx`, `analysis/components/DataNoteMark.tsx`, `analysis/components/DataNotes.tsx`, `analysis/components/DataNotesContext.tsx`, `analysis/components/KpiStrip.tsx`, `analysis/components/MetricsTable.tsx`, `analysis/components/NarrativePane.tsx`, `analysis/components/TrendCharts.tsx`, `analysis/lib/dataNotes.ts`, `frontend/features/marketing/components/AnalysisDemo.tsx`, `frontend/tests/e2e/analysis-layout.spec.ts`, `frontend/tests/e2e/fixtures/analysisLayoutApi.ts`, `frontend/tests/e2e/text-floors.spec.ts`, `frontend/tests/unit/analysis-source-quality.spec.tsx`, `frontend/tests/unit/kpi-strip.spec.tsx`, `frontend/tests/unit/metrics-table.spec.tsx`, `frontend/tests/unit/narrative-pane.spec.tsx`
- WP1 quiet notation × #1609 charts renderer: `frontend/DESIGN_SYSTEM.md`, `analysis/components/TrendCharts.tsx`, `frontend/tests/e2e/fixtures/analysisLayoutApi.ts`
- WP2 data-notes words × WP3 exports: `backend/app/services/analysis_export_metadata.py`
- WP2 data-notes words × WP5 restatement note: `backend/app/services/trend_analysis/data_notes.py`, `backend/tests/unit/test_analysis_data_notes.py`, `analysis/lib/dataNotes.ts`
- WP2 data-notes words × #1606 table plan: `analysis/components/DataNotes.tsx`, `analysis/lib/dataNotes.ts`, `frontend/tests/unit/analysis-source-quality.spec.tsx`
- WP2 data-notes words × #1609 charts renderer: `frontend/tests/unit/analysisPeriodWindows.spec.tsx`
- WP3 exports × charts steps 5-7 (scope): `analysis/lib/chartExport.ts`, `frontend/tests/unit/chart-export.spec.ts`
- WP3 exports × analysis plan (scope): `backend/app/services/export_service.py`
- WP3 exports × #1606 table plan: `analysis/lib/chartExport.ts`
- WP3 exports × #1609 charts renderer: `analysis/lib/chartExport.ts`
- WP3 exports × #1601 export-source: `backend/app/services/export_service.py`, `backend/tests/unit/test_export_service.py`, `backend/tests/unit/test_export_voice.py`
- WP4 surfaces + results header × charts steps 5-7 (scope): `frontend/DESIGN_SYSTEM.md`
- WP4 surfaces + results header × #1606 table plan: `.impeccable/design.json`, `DESIGN.md`, `frontend/DESIGN_SYSTEM.md`, `analysis/components/KpiStrip.tsx`, `frontend/tests/e2e/analysis-layout.spec.ts`
- WP4 surfaces + results header × #1609 charts renderer: `frontend/DESIGN_SYSTEM.md`
- WP5 restatement note × #1606 table plan: `analysis/components/DataNoteMark.tsx`, `analysis/lib/dataNotes.ts`
- charts steps 5-7 (scope) × #1606 table plan: `frontend/DESIGN_SYSTEM.md`, `analysis/components/TrendCharts.tsx`, `analysis/lib/chartExport.ts`
- charts steps 5-7 (scope) × #1609 charts renderer: `frontend/DESIGN_SYSTEM.md`, `analysis/components/TrendCharts.tsx`, `analysis/components/TrendChartsV2.tsx`, `analysis/lib/chartExport.ts`, `analysis/lib/charts/layout.ts`
- analysis plan (scope) × #1606 table plan: `analysis/components/NarrativePane.tsx`, `frontend/tests/unit/narrative-pane.spec.tsx`
- analysis plan (scope) × #1601 export-source: `backend/app/services/export_service.py`
- #1606 table plan × #1609 charts renderer: `docs/design/analysis-trend-charts-spec-2026-10.md`, `frontend/DESIGN_SYSTEM.md`, `analysis/components/TrendCharts.tsx`, `analysis/lib/chartExport.ts`, `frontend/tests/e2e/fixtures/analysisLayoutApi.ts`
- #1606 table plan × #1583 per-filing-currency: `lessons/README.md`
- #1609 charts renderer × #1601 export-source: `tasks/todo.md`
- #1609 charts renderer × #1583 per-filing-currency: `tasks/todo.md`
- #1609 charts renderer × #1608 admin units: `.github/workflows/ci.yml`, `tasks/todo.md`
- #1601 export-source × #1583 per-filing-currency: `tasks/todo.md`
- #1601 export-source × #1608 admin units: `tasks/todo.md`
- #1583 per-filing-currency × #1608 admin units: `docs/ARCHITECTURE.md`, `tasks/todo.md`
