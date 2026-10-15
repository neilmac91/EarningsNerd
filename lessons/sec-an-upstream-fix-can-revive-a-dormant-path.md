# Judge an SEC-library bump by every accessor our code calls, not only the functions its fixes name: a fix can revive a dormant input path

Date: 2026-10-15   Area: sec / dependencies

**Context**: The hold record for edgartools 5.61.1 (#1285) read 5.61.0's fix to `Filing.homepage_url`
and `Filing.html()` and concluded that `app/` calls neither of them. But
`app/services/edgar/xbrl_sections.py` calls `Filing.obj()`, and the report object it returns reads
its sections through `html()`. On 5.58.0, `html()` re-reads each inline-XBRL primary document from
the filing's index page through `homepage_url`. Since early October, SEC's 403 on that URL had been
disabling the summary's native sections. The regex fallback hid the failure:

- In CI's evaluation, citation fidelity fell from 0.97 to 0.818–0.871. The regression gate treats
  that dimension as a WARN, so every run still passed.
- Decision 3 of `tasks/pr-disposition-2026-10-07.md` recorded the drop and the 35-of-35 fallback on
  7 October, and called it worth a diagnosis PR.
- It was queued as a follow-up but never became an open item, so the hold review six days later did
  not connect it to the bump (`ops-write-down-the-second-anomaly-before-chasing-the-first.md`).

Upstream then fixed the failure by two routes. 5.61.0 moved the URL inside the accession folder.
5.62.0 also stopped sending XML-declared HTML to the index page. Either release would have switched
every newly built 10-K, 10-Q and 20-F excerpt back to native sections inside a dependency change
(E28).

**Rule**: When a release fixes a failure, find every path of ours that the failure was silently
disabling:

- Trace each library accessor `app/` calls (`obj()`, `html()`, `text()`, attachments, `xbrl()`)
  through the fixed functions, not just the fixed functions' direct callers.
- Compare a CI evaluation report's excerpt sources (`coverage_inventory.source`) under the old and the
  new version.
- A requirements-only PR does not trigger `eval-baseline`, so dispatch it on the bump's branch, after
  the balance read and reservation that the spend rule requires.

A path that comes back to life is a model-input change. Measure it per `backend/evals/RUNBOOK.md` and
decide it before the bump, never inside it. When a fix can arrive by more than one route, gate the
version, not one URL shape or code path.

**Evidence**: `tasks/review-evidence/e28-native-sections-2026-10-15/README.md` and its
`upstream_fixes.txt`; the 2026-10-15 addendum to
`tasks/review-evidence/edgartools-5.61.1-hold-2026-10-13/README.md`. The gate
`backend/tests/unit/test_edgartools_sections_revival_tripwire.py` covers this instance only: it holds
edgartools at 5.58.0 while the summary's section source keeps its `obj()` allow-list entry. Tracing
the accessors and dispatching the eval for the next library are review-checked.
