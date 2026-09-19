# E9 bounded live database read — 2026-09-19

Outcome: existing IAM identity connected to the production database, but it cannot SELECT the job-outcome table. The route stopped at the first table query. No latest-attempt, last-success, status-count, counter, or incomplete-attempt evidence was obtained.

## Observed database and session limits

Snapshot time: `2026-09-19 18:53:24.627263+00` (transaction timestamp).

| Field | Observed value |
| --- | --- |
| Database | `earningsnerd` |
| `max_connections` | `25` |
| `transaction_read_only` | `on` |
| `lock_timeout` | `2s` |
| `statement_timeout` | `15s` |
| `idle_in_transaction_session_timeout` | `30s` |

The timeouts above are effective values set for this read transaction, not claims about global server defaults. The transaction was repeatable-read and read-only; the connection also set default_transaction_read_only before executing SQL.

## Exact blocking evidence

`psql` exit status: `3` (`ON_ERROR_STOP`).

```text
psql:/private/tmp/earningsnerd-wave3-20260919/work/e9-live-read-20260919/query.sql:38: ERROR:  permission denied for table earningsnerd_job_runs
```

The first requested job-outcome query failed. Subsequent queries and the explicit final ROLLBACK were not executed because ON_ERROR_STOP ended the session; PostgreSQL aborts the open transaction on disconnect. Nothing was committed. No alternate database identity or grant-changing route was attempted.

## Connection and scope evidence

- Existing authenticated gcloud/IAM identity: `neil@earningsnerd.io`.
- Target: `earnings-nerd:us-west1:earningsnerd-db`, database `earningsnerd`.
- Official Cloud SQL Auth Proxy `2.25.4+darwin.arm64`; its downloaded SHA-256 matched the official release checksum, recorded in `proxy-verification.txt`.
- Proxy v2.25.4 rejects `--gcloud-auth` with `--auto-iam-authn`; this initial startup failure is retained in `proxy.log`. There was no existing ADC file. The successful connection used automatic IAM with existing gcloud-generated access/login tokens passed only in the proxy child environment. Tokens were not printed, placed on command lines, or stored in artifacts.
- One local listener, `127.0.0.1:55434`, maximum one database connection. Parent's local PostgreSQL port `55433` was untouched.
- The proxy accepted one client, that client disconnected, then the wrapper terminated the proxy. `lsof -nP -iTCP:55434 -sTCP:LISTEN` afterward returned no listener (exit 1).
- No application Secret Manager access, application/runtime dependency change, IAM/database user or grant change, database/cloud flags or networking change, or job invocation occurred.

## Evidence artifacts

- `query.sql`: prepared SELECT-only batch and transaction/session guards.
- `query.out`: sanitized database metadata output; no job rows.
- `query.err`: exact permission error (plus harmless /dev/null password-file warning).
- `query-exit.txt`: psql exit status.
- `proxy-token-input.log`: sanitized proxy connection/shutdown log, no credentials.
- `read_via_iam.py`: bounded wrapper, showing in-memory credential handling and guaranteed proxy teardown.
- `proxy-verification.txt`: official download source and verified checksum.

The job-outcome portion of E9 remains unverified because existing database authorization does not allow SELECT. This is an access limit, not evidence of missing or unhealthy jobs.

## Founder Studio read handoff

`founder-studio-readonly.sql` contains the complete exact SQL batch, with psql-only display commands removed. Use Cloud SQL Studio on project `earnings-nerd`, instance `earningsnerd-db`, database `earningsnerd`, through an **existing identity that already has SELECT access**. Run the whole batch together because Studio creates a new session per execution. This is a prepared handoff, not a successful execution. Renewing gcloud authentication did not supply the missing database SELECT grant; using the same identity in Studio does not by itself resolve that denial. Do not create users, grant privileges, fetch application secrets, or run jobs as part of this read. If existing authorization still denies the table, preserve the exact error and stop.

Return the metadata and the four bounded result sets only. Preserve missing expected jobs as `never_observed`, and distinguish scheduled identities from maintenance names. Status `succeeded` requires a non-null finish to count as latest success. Incomplete rows do not prove a currently live process. No raw error payloads or personal data are requested.
