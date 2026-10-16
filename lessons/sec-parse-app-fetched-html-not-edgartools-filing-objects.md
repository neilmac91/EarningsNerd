# Parse section text from the HTML the app fetched, never through edgartools' Filing or CompanyReport accessors

Date: 2026-10-12   Area: sec

**Context**: Building the Item 1A extraction for the "what changed" workflow (PR #1286), the
existing `edgar/xbrl_sections.py::_extract_sections_sync` path (edgartools `filing.obj()["Item 1A"]`,
the `USE_EDGARTOOLS_SECTIONS` summary-section path) returned nothing for every filing probed: it
first fetches the filing homepage and the SGML index through edgartools' own HTTP client, and the
primary document resolved to None in the build environment (`'NoneType' object has no attribute
'download'`). The app's own transport (`sec_edgar_service.get_filing_document`) fetched the same
primary documents, and `edgar.documents.HTMLParser(ParserConfig(form=form)).parse(html)
.sections.get_item("1A", part)` located Item 1A in 56 of 56 10-K/10-Q documents (14 companies,
2024 to 2026) in under 8 s each, the 13 MB JPMorgan 10-K included.

**Rule**: For section text, fetch the primary document once through the app's SEC transport
(limiter + breaker, CLAUDE.md rule 5) and parse it locally with edgartools' HTML parser
(breaker-exempt CPU work, off the event loop). Do not add a `Filing`, `CompanyReport` or `obj()`
accessor for document text: its requests go through edgartools' client, which the deploy pins to
the same 1 req/s (`EDGAR_RATE_LIMIT_PER_SEC`) but which the app's limiter, breaker and diagnostics
never see, and they fail wherever the homepage does not resolve. The two sites that predate the
rule stay as they are: `edgar/sixk_extractor.py` (6-K exhibit text, through a getattr wrapper) and
`insider_service.py` (Form 4 objects, behind `ENABLE_INSIDER_ACTIVITY`). The summary-section path,
`edgar/xbrl_sections.py`, joined the rule with E28: it parses the document the pipeline fetched with
the same parser and holds no `obj()` entry. Before that it called `filing.obj()` and returned nothing
from early October 2026, because edgartools 5.58.0 re-read inline-XBRL documents from an index URL
SEC refuses. Part keys differ by
form: a 10-K's Item 1A is Part I, a 10-Q's is Part II; ask for the part first and fall back to
any part.

**Evidence**: `backend/app/services/filing_section_service.py::parse_item_1a` and its tests in
`backend/tests/unit/test_filing_section_service.py`; the corpus measures in the body of PR #1286;
`backend/app/services/edgar/xbrl_sections.py::_sections_from_html` and
`backend/tests/unit/test_summary_sections_parity.py` (PR #1347).
Gate: `backend/tests/unit/test_edgartools_obj_allowlist.py` (every access to the accessor under
`app/`, the call, a bare `.obj` read that aliases it or `"obj"` passed by name to `getattr` or a
wrapper around it, is on its allow-list).
