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

**Root cause, found 2026-10-15**: this was not specific to the build environment. Since about
2026-10-06, SEC answers the short index URL that edgartools 5.58.0 builds
(`/Archives/edgar/data/<cik>/<accession>-index.html`) with 403 "Access Denied" from every network
tried: CI, two agent containers, and very likely production. edgartools 5.61.0 fixed it upstream
(GH #1421). `backend/app/services/edgar/edgartools_compat.py` backports that fix while #1063 holds the
pin, which restores `xbrl_sections.py` (see
`tasks/review-evidence/edgartools-homepage-403-2026-10-15/`). The rule below still holds for new code,
for its limiter and breaker reason.

**Rule**: For section text, fetch the primary document once through the app's SEC transport
(limiter + breaker, CLAUDE.md rule 5) and parse it locally with edgartools' HTML parser
(breaker-exempt CPU work, off the event loop). Do not add a `Filing`, `CompanyReport` or `obj()`
accessor for document text: its requests go through edgartools' client, which the deploy pins to
the same 1 req/s (`EDGAR_RATE_LIMIT_PER_SEC`) but which the app's limiter, breaker and diagnostics
never see, and they fail wherever the homepage does not resolve. The two sites that predate the
rule stay as they are: `xbrl_sections.py` (the summary-section path; its production hit rate is
open item E28) and `insider_service.py` (Form 4 objects, behind `ENABLE_INSIDER_ACTIVITY`). Part
keys differ by form: a 10-K's Item 1A is Part I, a 10-Q's is Part II; ask for the part first and
fall back to any part.

**Evidence**: `backend/app/services/filing_section_service.py::parse_item_1a` and its tests in
`backend/tests/unit/test_filing_section_service.py`; the corpus measures in the body of PR #1286.
Gate: `backend/tests/unit/test_edgartools_obj_allowlist.py` (every access to the accessor under
`app/`, the call, a bare `.obj` read that aliases it or `getattr(x, "obj")`, is on its allow-list).
