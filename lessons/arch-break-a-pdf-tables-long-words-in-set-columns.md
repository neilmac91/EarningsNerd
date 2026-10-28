# Break a PDF table's long words in set columns, never with `overflow-wrap: anywhere`

Date: 2026-10-28   Area: arch

**Context**: E75 set a located risk excerpt in the summary PDF as the device's marked block, inside the
Risks table's excerpt cell. The web's marked block carries `overflow-wrap: anywhere`, so a URL in an
excerpt breaks inside it; copied into the PDF, the same declaration made WeasyPrint 70 take 34 s to lay
out one 4,400-character excerpt and over 100 s for a longer one, against 0.1 s without it. An auto table
sizes each column by its cells' min-content, and under `anywhere` WeasyPrint measures that by laying the
text out a character to a line. Without it, a token wider than the page (a 260-character URL) widened the
column and ran the excerpt about 1,100 px past the page's edge, on main as well; `overflow-wrap:
break-word` alone does not help, because it leaves min-content alone.

**Rule**: In a WeasyPrint PDF, give a table that can hold a long token set columns (`table-layout: fixed`,
widths on its header cells) and `overflow-wrap: break-word` on its cells, as `table.excerpts` in
`backend/app/services/pdf_branding.py` does. Never set `overflow-wrap: anywhere` on anything a table, a
flex container or another intrinsically sized box measures; the analysis meta line's `.snapshot`, a short
id in normal flow, is the one rule that keeps it. A cell that must not wrap (`td.num`'s `nowrap`) holds
figures only: the excerpt column is prose whatever it holds, so `numeric_columns` never classes it.

**Evidence**: `backend/tests/unit/test_export_service.py::TestBrandedShell::test_no_pdf_breaks_a_word_anywhere_a_column_is_measured`
holds every PDF rule that sets `anywhere` to `.snapshot`; `TestLocatedRisks::test_the_rendered_pdf_sets_the_device_and_keeps_every_excerpt_on_the_page`
lays out a page-spanning excerpt and a 240-character URL and holds every text box inside the page's content
edge; `test_a_figure_only_excerpt_wraps_as_prose` holds the excerpt column off `num`. Timings from a
scratch benchmark on the session host (4 CPUs), not CI.
