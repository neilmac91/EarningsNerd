# Edgartools 5.59.1 remains held

Tracked in [issue #1063](https://github.com/neilmac91/EarningsNerd/issues/1063).
The runtime successor retains Edgartools **5.58.0** in the compiled lock and the unchanged
5.58.0 input floor. Closing aggregate [#1050](https://github.com/neilmac91/EarningsNerd/pull/1050)
as superseded must preserve this open disposition and link the separate runtime and optional
Anthropic successors; it does not mean the fifth upgrade passed.

The original [backend CI failure](https://github.com/neilmac91/EarningsNerd/actions/runs/36983187306/job/110762172391)
was a glued-string Outlook assertion: **1 failed, 5498 passed, 39 skipped, 2 deselected**.
Independent retained parser evidence proves more than a whitespace change:

- 5.58.0: `ROIC (a)8.6%(12.5%)`
- 5.59.1: `ROIC (a)  8.6  %  (12.5`

The multi-character `%)` table cell is dropped, and three prose/table seams lose a line break.
[Original evidence README](../edgartools-5.59.1-hold-2026-10-01/README.md),
[ROIC row](../edgartools-5.59.1-hold-2026-10-01/roic-row.txt),
[content comparison](../edgartools-5.59.1-hold-2026-10-01/content_compare.txt), and
[table seams](../edgartools-5.59.1-hold-2026-10-01/probe_table_seams.txt)
retain source/package comparisons on the same Ford bytes. These receipts predate this split;
they are not relabelled as freshly repeated extraction.

A future successor needs a fixed parser, complete numeric/percent/negative affixes, intact
paragraph/table and section boundaries, complete Outlook including the final Ford Energy
assumption, and unchanged recovery/source budgets. Only after the loss is fixed may the brittle
Outlook literal become a row-preserving horizontal-whitespace check, with controls that reject
removed or split rows and changed labels/values plus explicit affix/seam coverage. This update
changes no assertion, adds no blanket dependency ignore, and does not waive filing integrity.
