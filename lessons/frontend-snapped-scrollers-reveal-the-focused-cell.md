# A snap-scrolled table picks the snap stop that reveals a focused cell; the browser's focus scroll plus the mandatory snap can hide it

Date: 2026-10-11   Area: frontend

**Context**: The prototype's metrics table snaps whole columns (`scroll-snap-type: x mandatory`) beside a
sticky label column. Tabbing to a value made the browser scroll it into view, and the snap then settled on the
nearest stop. At 320 px with 200% text only 11% of "Revenue, Q4 2023" stayed visible, and at 1024 px 40% of
another value. The rest-position, clipping and occlusion probes all passed, because each value fit its cell.
`main`'s `DataTable` corrects the sticky layout in `onFocusCapture` (it has no unstuck layout yet: review
item 18); the prototype had neither.

**Rule**: A horizontally snapped scroller with focusable cells handles focus itself. It computes the snap stop
that shows the focused cell's whole column and sets `scrollLeft` to it:
- the column's own stop when the column starts under a sticky overlay;
- otherwise the first stop that shows its far edge, never past the column's own stop (a column a pixel wider
  than the room beside a sticky overlay would otherwise land under it: at a 245 px viewport every Tab-focused
  value did);
- in an unstuck layout, the label column is a stop of its own.

Prove it with real Tab and Shift+Tab at every width where the table scrolls, phone widths and 200% text
included, measuring each focused element's visible share and the number of stops the walk reached. Static
probes cannot see it.

**Evidence**: `frontend/components/ui/DataTable.tsx` (`onFocusCapture`);
`tasks/analysis-redesign-2026-10/prototype/app.js` (the `focusin` handler);
`tasks/analysis-redesign-2026-10/harness/measure-proto.mjs` (`focusReveal`); the founder's review on #1197.
