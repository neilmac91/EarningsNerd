# Judge an SEC-library bump by every accessor our code calls, not only the functions its fixes name: a fix can revive a dormant input path

Date: 2026-10-15   Area: sec / dependencies

**Context**: The hold record for edgartools 5.61.1 (#1285) read 5.61.0's fix to `Filing.homepage_url`
and `Filing.html()` and concluded that `app/` calls neither. But
`app/services/edgar/xbrl_sections.py` calls `Filing.obj()`, which loads the filing's index page
through `homepage_url`. On 5.58.0, SEC's 403 on that URL had been disabling the summary's native
sections since early October. The regex fallback hid it: in CI's evaluation, citation fidelity fell
from 0.97 to 0.84, and the drop showed only as a WARN. On 5.62.0 the same call returns sections
again, so the bump would have changed every 10-K, 10-Q and 20-F excerpt inside a dependency change
(E28).

**Rule**: When a release fixes a failure, find every path of ours that the failure was silently
disabling. Trace each library accessor `app/` calls (`obj()`, `html()`, `text()`, attachments,
`xbrl()`) through the fixed function, not just the fixed function's direct callers. Then compare a CI
evaluation report's excerpt sources (`coverage_inventory.source`) under the old and new versions. A
path that comes back to life is a model-input change: measure it per `backend/evals/RUNBOOK.md` and
decide it before the bump, never inside it.

**Evidence**: `tasks/review-evidence/e28-native-sections-2026-10-15/README.md`; the 2026-10-15
addendum to `tasks/review-evidence/edgartools-5.61.1-hold-2026-10-13/README.md`; the gate
`backend/tests/unit/test_edgartools_sections_revival_tripwire.py` covers this instance only (the
summary's section source and `homepage_url`).
