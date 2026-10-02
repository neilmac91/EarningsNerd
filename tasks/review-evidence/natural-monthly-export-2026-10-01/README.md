# Natural October monthly SQL export — verified October 3

The October 1 natural scheduled export completed. [Run 36852004473](https://github.com/neilmac91/EarningsNerd/actions/runs/36852004473) records `event=schedule`, source `116c91d2fca93d13bf9015f8c82ffa05d5cd625b`, and a successful export job (`110335599212`). This closes the earlier unverified natural-trigger observation; it adds no managed restore result.

The actual output at `2026-10-01T10:57:41.5843188Z` was:

```text
monthly SQL export complete: period=2026-10 bytes=4931278
```

This is an emitted result, not an echoed script line. The [machine-readable receipt](receipt.json) binds that output to run metadata, the exact workflow source and hashes of the privately retained logs. Verification read GitHub metadata and logs only: no export was triggered or rerun, no SQL object was downloaded and no IAM or schedule setting changed.

## What completion establishes

The [workflow at the run's source commit](https://github.com/neilmac91/EarningsNerd/blob/116c91d2fca93d13bf9015f8c82ffa05d5cd625b/.github/workflows/monthly-sql-export.yml) reaches this line after an exact-context export operation is `DONE` without errors, matching object metadata is present, its size is positive, its storage class is `STANDARD`, and a two-byte range read matches gzip magic. These checks are inferred from the pinned executed source; the full metadata and operation ID are not printed.

The reported size is **4,931,278 bytes** for period **2026-10**. The source-derived key is `monthly/2026-10/earningsnerd-2026-10.sql.gz`; this is not direct observation of the masked bucket identity. The completion path can submit an export or adopt one already active. The output does not distinguish those paths, so it does not prove a new export was submitted by this run.

The before/after health checks require `checks.database.healthy=true` and a top-level status other than `unhealthy`. They do not require the literal overall status `healthy`; the raw health payloads are absent from the log.

The source cron is `15 4 1 * *` (04:15 UTC). GitHub created this run at 10:54:14 UTC, **6 hours 39 minutes 14 seconds** after that clock time. Its export step completed at 10:57:41 UTC. The cause of the later run creation is not established.

## Remaining limits

The two-byte gzip check proves neither full compressed-file integrity nor SQL restore integrity. Object generation, full checksum, bucket identity and direct operation metadata are not available in this output. No claim of current object retention is made from this historical run.

The [isolated restore record](../../readiness-2026-09-21/operations/restore-rehearsal.md) retains the separate PITR and local PostgreSQL import results. Managed Cloud SQL re-import remains unproved. This receipt does not close fleet capacity, quality acceptance or beta evidence.

This verification made zero new model calls and spent USD 0 on DeepSeek. Historical export/cloud costs were not measured. Raw GitHub evidence remains private on the founder's non-iCloud storage; its hashes in the receipt establish custody without publishing the full logs or any SQL archive.
