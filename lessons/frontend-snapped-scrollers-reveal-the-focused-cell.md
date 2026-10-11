# A snap-scrolled table picks the snap stop that reveals a focused cell; the browser's focus scroll plus the mandatory snap can hide it

Date: 2026-10-11   Area: frontend

**Context**: The prototype's metrics table snaps whole columns (`scroll-snap-type: x mandatory`) beside a
sticky label column. Tabbing to a value made the browser scroll it into view, and the snap then settled on the
nearest stop. At 320 px with 200% text only 11% of "Revenue, Q4 2023" stayed visible, and at 1024 px 40% of
another value. The rest-position, clipping and occlusion probes all passed, because each value fit its cell.
`main`'s `DataTable` already corrects this in `onFocusCapture`; the prototype had not.

**Rule**: A horizontally snapped scroller with focusable cells handles focus itself. It computes the snap stop
that shows the focused cell's whole column and sets `scrollLeft` to it:
- the column's own stop when the column starts under a sticky overlay;
- otherwise the first stop that shows its far edge;
- in an unstuck layout, the label column is a stop of its own.

Prove it with real Tab and Shift+Tab at phone widths and 200% text, measuring each focused element's visible
share. Static probes cannot see it.

**Evidence**: `frontend/components/ui/DataTable.tsx` (`onFocusCapture`);
`tasks/analysis-redesign-2026-10/prototype/app.js` (the `focusin` handler);
`tasks/analysis-redesign-2026-10/harness/measure-proto.mjs` (`focusReveal`); the founder's review on #1197.
