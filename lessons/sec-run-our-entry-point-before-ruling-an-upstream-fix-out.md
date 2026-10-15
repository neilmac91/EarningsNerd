# Before ruling that an upstream fix does not reach us, run our entry point against the failure

Date: 2026-10-15   Area: sec

**Context**: From about 2026-10-06, SEC answered edgartools' short filing-index URL with 403. Every
eval-baseline run from 2026-10-07 then fell back to regex section extraction for 35 of 35 filings, and
`mean_citation_fidelity` fell from the pinned 0.9648 (0.818–0.871 across the eight runs of 7 October,
0.8258 on 15 October). Four records met the symptom and each concluded something else:
- The edgartools 5.61.1 hold record (2026-10-13) saw that 5.61.0 fixes `Filing.homepage_url` /
  `Filing.html()` against the 403. It concluded "`app/` has no call to either", because grepping `app/`
  for the two names finds nothing.
- PR #1286 and its lesson saw `'NoneType' object has no attribute 'download'` on every filing and put
  it down to the build environment.
- Open item E28 then proposed measuring, and possibly retiring, the path.
- Decision 3 of the 2026-10-07 PR-disposition sweep blamed `evals/runner.py::_get_grounding` for
  swallowing the exception. The runner never received one: the extractor returned None.

The calls were there all along, made by edgartools on our behalf: `_extract_sections_sync` reads
`obj["Item 1A"]` and `obj.sections`, and edgartools' `TenK.document` calls `Filing.html()`, which reads an
inline-XBRL document through the homepage. Our own code hid the error twice: a per-label `except` and
`getattr(obj, "sections", None)`, whose default swallows an AttributeError raised inside the property.

**Rule**: To decide whether a library change reaches us, exercise our entry point (here
`_extract_sections_sync` on a real filing) on the old and new version, or trace the library's own call
graph from our call sites. A grep of `app/` for the changed symbol cannot clear it. Never let
`getattr`'s default or a bare `except` turn a failing read into silence: when the section parse
returns nothing, it logs the first read error (gated). Logging the cause of every other fallback
(a partial parse, the thin-excerpt fallback, other parse paths) is the same practice, review-checked.

**Evidence**: `tasks/review-evidence/edgartools-homepage-403-2026-10-15/README.md` (the root cause, the
SEC responses, and section extraction for the 32 golden 10-K/10-Q/20-F filings before and after);
`backend/app/services/edgar/edgartools_compat.py`. Partly gated:
`backend/tests/unit/test_edgartools_compat.py` pins this instance end to end, and
`backend/tests/unit/test_xbrl_sections_errors.py` pins the warning when the section parse returns
nothing. The rest is review-checked.
