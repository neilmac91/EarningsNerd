# Measure a glyph advance where it paints; a font's em ratio is not the width every browser draws

Date: 2026-10-25   Area: frontend

**Context**: E197's KPI strip sized its columns from its widest value at Geist Mono's 0.6em advance, 0.9rem a glyph at
24px. This container's headless shell is a wrapper that passes `--font-render-hinting=none`, so it draws 14.4px glyphs
and every local gate held. CI's browser, headless Chrome under its default full hinting, snaps glyphs to whole pixels:
14px at 24px and 29px at 48px. "$60.8B" painted 84px against an 86.4px budget, and at 200% text "26.1%†a" painted 179px
against 178.4px, so 67 e2e cases failed on the pull request. A budget under the painted width brings E197's bug back: a
dagger that wraps, or a value past its card.

**Rule**: When a layout sizes itself from text it has not laid out (a grid track's minimum, a reserved width), measure
the advance in the browser: a hidden run of the same glyphs in the same classes, measured again by a ResizeObserver as
the face arrives or the text size changes. Multiply glyph counts by it, and keep the em ratio only as the value before
the first measurement. Pin `--font-render-hinting=full` in the gate's spec (`test.use({ launchOptions })`), as the
chart specs do, so it runs in the snapping case wherever it runs.

**Evidence**: E197's pull request: `frontend/features/analysis/components/KpiStrip.tsx` (the probes, `--kpi-figure` and
`--kpi-mark`), `frontend/features/analysis/lib/kpiStripLayout.ts` (`kpiValueGlyphs`, `kpiWidestCss`) and
`frontend/tests/e2e/analysis-layout.spec.ts`, whose budget check and "the figure face" case failed in CI at the 0.6em
model and pass under full hinting with the probes, and its "a text size set after the strip mounts" case. Gated for
the KPI strip by that spec; other layouts sized from text they have not laid out are review-checked.
