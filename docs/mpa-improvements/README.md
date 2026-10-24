# Multi-Period Analysis improvements

Plans for the Multi-Period Analysis page (`/analysis`), one report per area. The reports share
this folder and its evidence.

| Report | Area | Status |
|---|---|---|
| [coherence.md](coherence.md) | notation semantics (†, note letters), data notes, page hierarchy, exports, sequencing across the plans | 2026-10-24 |
| charts | trend charts and chart exports | not yet in this folder |
| analysis | AI trend analysis and its sources | not yet in this folder |
| table | metrics by period and the workbook | not yet in this folder |

Evidence for coherence.md:
- [`verification/`](verification/): the flag-frequency census, comprehension and heuristic
  transcripts, the export inspection and the file-overlap matrix.
- [`screens/`](screens/): before, after and final captures, light and dark, desktop and 390px.
- [`exports/`](exports/): REGN's PDF, workbook and chart PNGs in both themes.
- [`competitors/`](competitors/): Roic.ai, Yahoo Finance, Finviz and Alpha Spread.
- [`prototype/`](prototype/): the notation prototype as a diff against `a41c6e4`.
- [methods.md](methods.md): every script that produced a number.

The full-population frequency query lives with the other detection SQL, in
[`ops/detection/mpa_notation_frequency.sql`](../../ops/detection/mpa_notation_frequency.sql).
