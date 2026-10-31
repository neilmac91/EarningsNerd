# Summary recovery readout

`python3 ops/summary_readout/readout.py` is the fixed, read-only companion to the
durable-summary rollout. It uses the existing Ops SQL proxy's libpq environment,
accepts no arguments, and writes `summary-recovery-receipt.json` with mode 0600.
Only normalized JSON reaches stdout or that artifact. It imports no application
code and starts no generation, task delivery, recovery or provider request.

The committed SQL uses a repeatable-read, read-only transaction, a 15-second
statement deadline and a 2-second lock deadline. The client has a 5-second connect
deadline, a 25-second process deadline and a 32 KiB accepted output limit. It
rolls the transaction back. The client startup also forces read-only transactions
and disables psql startup files and password prompts.

## Fixed evidence

- REGN application filings 45003 and 45004 are checked against their exact CIK,
  accession and form before their job details are used. The receipt reports
  generation, attempt count, closed status/stage/charge classes and intervals
  relative to the database snapshot. Ages outside 30 days remain explicitly
  outside the bound; infinite or maximum-date source holds are not shortened.
- Referenced reservations are checked for existence, account/kind agreement,
  month shape and expiry inside the database. Only the closed result is emitted.
  Summary references are checked for existence and the same filing; no summary
  body is selected and this does not establish ready or correct output.
- The oldest 1,000 jobs in the known active statuses (`queued`, `running`,
  `retry_wait`) contribute aggregate counts. A 1,001st-row probe sets `truncated`.
  When truncated, those counts describe the retained sample, never the fleet.
  Terminal rows and corrupt or unknown statuses are outside this aggregate; it
  does not validate every job row. IDs break ordering ties inside SQL only.
  The 300-second dispatch and 3,600-second age checks are reference thresholds,
  not readings of deployed Settings. An overdue queued job need not have been
  attempted or terminalized: the worker enforces its horizon when claiming it.
- The SEC coordinator's singleton existence and next-admission/cooldown intervals
  are observed. They do not measure physical request dispatch or successful
  cooldown publication by every producer.

`lease_state` describes the stored fields. `active_owner` additionally requires a
running job with a token and a finite future lease; stale lease fields retained on
a terminal job do not show an active owner. Receipt observations identify shapes
that need review, not automatic repair instructions. System-funded jobs do not
require a user charge. Monthly usage counters, provider invoices and historical
generations are outside this snapshot, so this is not complete billing
reconciliation or proof of exactly-once provider charges.

## Failure and interpretation

Missing tables, denied reads, timeouts, malformed/extra fields and oversized
responses yield `UNVERIFIED` with a closed reason and nonzero exit. Raw stderr,
SQL errors, URLs, account/job/lease/reservation identities, prompt versions and
stored error text never become output. A missing fixed filing or coordinator row
is an observed absence, not a healthy result. A valid snapshot exits zero even
when its observations identify unresolved work; it is evidence, not a rollout
approval or health verdict.

The unit gate executes the actual client wrapper with its psql boundary stubbed,
including privacy sentinels and malformed outputs. The existing required
PostgreSQL summary-job transaction gate executes this exact SQL in disposable
schemas, verifies bounded samples, identity mismatches, retained terminal lease
fields, infinite source holds and real read-only rejection of writes. It does
not contact production or any external provider.
