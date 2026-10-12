# Parse section text from the HTML the app fetched, never through edgartools' Filing or CompanyReport accessors

Date: 2026-10-12   Area: sec

**Context**: Building the Item 1A extraction for the "what changed" workflow, the existing
`edgar/xbrl_sections.py::_extract_sections_sync` path (edgartools `filing.obj()["Item 1A"]`)
returned nothing for every filing probed: that path first fetches the filing homepage and the SGML
index through edgartools' own HTTP client, outside the app's limiter and breaker, and the primary
document resolved to None in the build environment (`'NoneType' object has no attribute
'download'`). The app's own transport (`sec_edgar_service.get_filing_document`) fetched the same
primary documents, and `edgar.documents.HTMLParser(ParserConfig(form=form)).parse(html)
.sections.get_item("1A", part)` located Item 1A in 56 of 56 10-K/10-Q documents (14 companies,
2024 to 2026) in under 8 s each, the 13 MB JPMorgan 10-K included.

**Rule**: For section text, fetch the primary document once through the app's SEC transport
(limiter + breaker, CLAUDE.md rule 5) and parse it locally with edgartools' HTML parser
(breaker-exempt CPU work, off the event loop). Do not reach for edgartools' `Filing`,
`CompanyReport` or `obj()` accessors for document text: they fetch again outside the budget and
fail wherever the homepage does not resolve. Part keys differ by form: a 10-K's Item 1A is Part I,
a 10-Q's is Part II; ask for the part first and fall back to any part.

**Evidence**: `backend/app/services/filing_section_service.py::parse_item_1a` and its tests in
`backend/tests/unit/test_filing_section_service.py`; the corpus measures in the PR body of the
"what changed" backend PR (2026-10-12).
