# Acceptance-test chart annotations on a dense real-world series, never only fixtures

Date: 2026-07-07   Area: frontend

**Context**: The data-labels toggle (Phase C, #566) looked fine on sparse fixtures and shipped with every-other-period "thinning" as its overlap mitigation. On real AAPL data the labels collided into unreadable stacks (Cash generation: operating CF, FCF and net income within a few $B of each other), and the thinning read as *missing data*. The founder killed the feature after one production field test — build + PR + removal PR, all avoidable with one dense-data screenshot during acceptance.

**Rule**: Before shipping any chart annotation (data labels, point markers, inline callouts), acceptance-test it visually against a real ticker with ≥10 periods AND at least one panel whose series nearly overlap. If the annotation needs thinning/decimation to survive that test, that is the signal it doesn't fit the surface — values belong in the tooltip and the metrics grid, not on the plot.

**Evidence**: AAPL FY2016–FY2025 screenshots (owner feedback, 2026-07-07); removal in the chart-polish follow-up PR after #574; thinning logic deleted from `frontend/features/analysis/components/TrendCharts.tsx` (`LABEL_THINNING_THRESHOLD`, `makeValueLabel`).
