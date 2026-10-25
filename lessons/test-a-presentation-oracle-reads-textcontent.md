# Build a presentation change's text oracle from textContent and accessible names, never innerText

Date: 2026-10-25   Area: testing

**Context**: The metrics-table study needed proof that restyling every cell changed no text: a per-cell
snapshot taken before any change, diffed byte for byte after it, over 114 runs. `innerText` is computed
from layout and CSS: it uppercases what `uppercase` paints, drops what `display: none` hides, keeps or
skips `sr-only` text by its clip, and inserts line breaks where blocks wrap. A pure restyle (new marks as
inline-blocks, a heading in another case, a wrapped header) would have shown as a text change, and a real
text change could hide behind a CSS change that moved the same characters.

**Rule**: Snapshot `textContent` of each cell, header and caption, plus every control's accessible name
(`aria-label`, else its text), never `innerText`. Capture it before the first edit, from the same build
command and browser the after-run uses. When a change is meant to alter text, write the intended edit as a
transform of the baseline and require the after-run to equal the transformed baseline exactly, so every
unintended difference still fails.

**Evidence**: the metrics-table number system's pull request, whose Verification section records the run:
114 of 114 oracle files equal the baseline with exactly the intended edits applied (the caption's count and
wording, and n/m's spoken words), 27,798 table cells and 1,700 KPI lines. The study's harness (a capture
script and an expected-transform diff) lived in its working directory, outside this repository, so the
method is the Rule above. Review-checked; no gate reads a study's tools.
