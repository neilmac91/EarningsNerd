# Cash financial applicability — final independent review, 2026-09-13

Reviewed final committed `475cac2ad47a03d0b93743a2ab9c65f155e94f67` in `work/cash-lead-basis`, including the applicability changes since published `486fd25d`. No surviving blocker was found in the bounded correctness, rules and tests review. This is local implementation acceptance, not publication clearance or evidence that an actual retained issuer has freshly acquired the classification.

## Correctness and prior risk reconciliation

`backend/app/services/edgar/instance_extractor.py:974` reads only the selected company's already cached `business_category`. A known financial profile, financial category or SIC 6000–6799 dominates conflicting nonfinancial signals. Only a valid SIC plus cached OperatingCompany yields exactly false; missing, malformed, zero, unclassified 9995/9999, boolean SIC or unavailable category remains unknown. The new owner at `backend/app/services/ai/cash_claims.py:107` requires that exact false before applying the cash-lead rewrite. Existing bank vetoes remain.

The lazy-classifier/extra-fetch concern was refuted twice: installed SDK `Company.business_category` is a cached property whose evaluation can inspect filings, while the new implementation reads `__dict__` directly; the focused control verifies the real SDK descriptor and uses an unavailable property that raises if invoked. The extraction control also asserts one selected-filing resolver call. This does not claim the existing extraction pipeline itself makes no requests.

The unknown-as-nonfinancial concern was refuted twice: the decision code explicitly requires positive operating classification and a valid SIC; the mutation removes only the cash eligibility guard and breaks seven source-to-visible/retained controls. A category from a financial class or a financial profile cannot be overridden by a conflicting operating SIC.

The metadata-only extraction/cache concern was refuted twice: classification is added after the existing income-statement anchor check, and standardization copies the annotation separately from metric series; the persisted-XBRL control returns old data without fetching or adding classification. Companyfacts and existing database/cache payloads therefore remain unknown. No financial-fact identity, backfill or cache invalidation is introduced. The annotation is trusted application metadata, not a cryptographic certificate; this review found no model/user write route into it.

## Tests and visible behavior

`backend/tests/unit/test_cash_financial_applicability.py` exercises the real instance extraction and standardization route with source-shaped XML and controlled selected-company metadata, then real summary generation and partial Markdown preview. It distinguishes these controlled forward-classified inputs from the exact retained unannotated metrics, which continue to abstain. Tests do not establish that the original retained filer already has the required SDK classification at runtime.

The prompt-displacement concern was refuted twice: Copilot removes the internal annotation before its capped JSON block and eval generation/judge projections remove it before serialization; the test compares complete captured primary-plus-recovery request sequences with versus without classification, asserts more than one request, and separately checks eval text and Copilot compact-block equality. It is not merely a primary-request parity test. The existing earnings-quality cash card is also byte-preserved with/without annotation. The older bank-only cash-conversion applicability gap is explicitly still open in the RUNBOOK.

## Committed proof and locks

Read the actual feature, mutation and restore logs under `outputs/cash-financial-applicability/`; no tests were executed by this reviewer.

Feature `d85ca6fa0b192a500820fc4ce71719a84dae92bd`:

```text
71 passed, 2 warnings in 5.78s
```

Mutation `c4ea72555ee0fb00efcd651d487afc0ab2184dce` removes only the exactly-false applicability guard. Failures cover insurer, BDC, generic financial profile, missing SIC, unclassified SIC, missing category and exact retained unknown metrics:

```text
7 failed, 19 passed, 2 warnings in 5.63s
```

Restore `11dbcf9349e9fb0093262aa60afe489ab9de68ff`:

```text
71 passed, 2 warnings in 6.28s
```

Feature and restore independently resolve to the identical tree `e2ca0fec3d5e814fde2fb49f8875f185c970817a`. The final head differs from restore only in `backend/evals/RUNBOOK.md` and `tasks/cash-lead-basis-local.md` (40 added documentation lines). All eleven locked anchors were compared by Git blob bytes against `cab4b78c` and remain identical, including the actual T4 subscription-webhook file and the previously approved T9 contract state. No additional exception is implied.

## Limits and next acceptance

Final follow-up: independently read `work/cash-financial-publication-gate.log`, which identifies final head `475cac2ad47a03d0b93743a2ab9c65f155e94f67`, PostgreSQL 15.15, Ruff `All checks passed!`, Bandit no issues (severity medium/high zero), and `3189 passed, 29 warnings in 109.12s (0:01:49)`. Root reports process exit 0. The log includes the previously recorded post-pytest closed-stream logging noise; it is not a test failure. Read the rewritten `outputs/cash-lead-PR-BODY.md`: it preserves the unknown/cache boundary and distinguishes prior assessment results from the corrected head's pending assessment. No contradictory acceptance claim found. Fresh retained assessment must verify actual classification availability, compare other source/tool inputs after removing only the internal annotation, and confirm the intended visible cash rewrite. Older retained/cache/companyfacts cases remain unchanged and cannot be called repaired by these forward-only controls. No provider call, source fetch, test run, publication, setting change or spending was performed for this review.
