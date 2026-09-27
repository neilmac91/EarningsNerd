# Notable filings disposition review — 2026-09-27

## Disposition

**Retain the implemented scanner, storage, API and mounted frontend, but keep serving deferred/dark until engineering completes the missing source-quality readout. Do not kill the feature on the available evidence, and do not open the flag PR yet.**

The ownership blocker is stale. The controlling CEO plan assigns Notable acceptance to **engineering**: review observed source quality, record retain/kill, then prepare the flag PR if retained ([CEO plan](../../ceo-implementation-plan-2026-09-08.md)). Later handovers and the blank worksheet continued to call this a founder decision, but they do not contain a completed decision or new evidence that engineering cannot perform the review. The latest delegation authorizes engineering to complete implementation. Founder involvement is therefore not a prerequisite for the bounded acceptance review; root still owns release and any production change.

## Evidence actually retained

| Date | Evidence | What it establishes | What it does not establish |
|---|---|---|---|
| 2026-09-08 | Smoke `w4wnv` returned 0 raw hits and 0 source errors for a weekend/holiday window. Seed `j6l78` searched 24 queries/30 pages, found 838 raw hits, dropped 377 duplicates, 94 no-ticker hits and 97 low-signal hits, inserted 270 rows, reported 0 source errors and no truncated queries ([todo](../../todo.md)). | The job was provisioned, could query the source and populate candidates; mechanical filtering and counters operated for the seed. | Candidate precision, freshness, reason accuracy, issuer diversity, seven-day autonomous reliability or usefulness. A successful seed is explicitly insufficient ([worksheet](../../readiness-2026-09-21/beta/notable-acceptance.md)). |
| 2026-09-13 | Read-only Jobs inventory saw the Notable job and a last-execution timestamp of Sep 13 00:30:01; the status icon was not available as a textual verdict ([job inventory](../cloud-run-capacity-2026-09-13/job-inventory.md)). | The job still existed and had been attempted. | Success, counters or source quality. |
| 2026-09-15 | Authenticated read-only inspection recorded a single-task Notable job, three retries, 900-second timeout, 1 CPU/1 GiB, and an enabled twice-daily scheduler whose last attempt was Sep 14 22:30:01Z ([observations](../resumption-2026-09-14/cloud-run-observations-2026-09-15.md)). | Provisioning and schedule existed through the planned review boundary. | The last attempt's result, the expected-slot ledger, stored candidate quality or a retain/kill decision. |
| 2026-09-21 | The canonical worksheet remained explicitly **blank**. Every required receipt—seven-day runs, distinct accessions/issuers, age distribution, duplicates/reasons/errors, editorial sample, EDGAR checks and recommendation—was empty ([worksheet](../../readiness-2026-09-21/beta/notable-acceptance.md)). | The missing evidence is precisely specified. | Acceptance. |
| 2026-09-26/27 | The continuation still calls Notable retain/kill unverified ([continuation](../../continuation-plan-2026-09-26.md)). The runtime/configuration files reviewed at main `e39b475e13a0599d037303aacc75a82d51b053b8` pin `NOTABLE_FILINGS_ENABLED=false` in the service and pregenerate deployment maps ([CI](../../../.github/workflows/ci.yml)); application default is false ([config](../../../backend/app/config.py)); the mounted homepage section self-omits on an empty dark response ([page](../../../frontend/app/page.tsx)). | Current repository intent is dark and the implementation remains present. | This is not a fresh observation of the effective production flag. No live flag state is claimed here. |

Two tempting conclusions fail:

1. **“270 seeded rows and zero source errors justify retain-and-enable.”** Those are transport and filtering counters. They do not measure whether a displayed reason is supported by the EDGAR filing, whether the card is fresh, or how noisy the cohort is.
2. **“No clicks or visible usage justify kill.”** The serving flag is dark in repository configuration, and the worksheet explicitly says a dark section's zero impressions/clicks cannot decide utility ([worksheet](../../readiness-2026-09-21/beta/notable-acceptance.md)).

## Next engineering action

Engineering should complete the existing worksheet as a bounded, read-only acceptance slice; no model/provider call, reseed or flag change is needed. The inspection below requires an authorized read path. It does not authorize retrying the earlier denied SQL SELECT route, changing IAM, or exporting internal data through an unapproved destination. Use retained authorized job/export evidence where available; otherwise resolve access first:

1. Query `earningsnerd_job_runs` for every expected Notable slot in one recoverable consecutive seven-day window and record success/failure/missing status plus counters. Prefer Sep 8–15 only if retained job records actually support it.
2. Query the matching `notable_filings` cohort for distinct accessions/issuers, freshness, duplicates, reason mix and source errors. The table is pruned after 14 days, so it cannot now be assumed to reconstruct Sep 8–15 ([worksheet](../../readiness-2026-09-21/beta/notable-acceptance.md)). If that cohort is gone, use the latest recoverable consecutive seven-day window and label it as a superseding observation rather than inventing historical completeness.
3. Select a bounded stratified sample across reasons, days and issuers and inspect each cited EDGAR filing for accession/form/date and whether the stated Notable reason is actually supported. Record every false positive and the selection rule.
4. Engineering records **retain** only if the completed record supports acceptable source precision, freshness and run reliability; otherwise record **kill** with the observed failure mode. If retained, the subsequent isolated flag PR updates both deployment parity locations and their existing gate. Production activation remains a separate root-owned release action.

Until that readout exists, **retain-dark/defer** is the only evidence-consistent disposition: implementation has positive provisioning evidence and no recorded fatal defect, while activation lacks the required source-quality proof.
