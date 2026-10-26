# Historical quarterly data repair

This is an operator maintenance tool, not part of normal ingestion. Normal companyfacts upserts
keep accession identities immutable. An explicit repair can correct previously stored calculated
quarterly facts and rebuild lineage for existing annual computed metrics (margins, free cash
flow and liquidity ratios). It keeps a before/after journal in `financial_fact_revision` in the
same transaction. It does not rewrite filing JSON or per-filing reported financial records, call AI,
change production flags, or delete facts. Annual repairs are restricted to the known computed
metric registry, source `derived`/`companyfacts`, no reported raw tag, and no filing owner; reported
annual numeric values and filing-owned metrics are preserved by the computed-metric repair.
A separate positive-evidence calendar correction can relabel companyfacts-owned reported rows:
the exact raw tag, start/end, accession, unit and concept must match the corrected normalizer.
Wrong fiscal years are corrected in place; wrong quarter labels are archived and replaced under
the canonical identity. A rolling twelve-month total is retired as FY only when the normalizer
provides explicit annual-calendar exclusion evidence. Missing candidates alone never authorize
these changes. Existing computed metrics at that exact old period are also retired when a
registered source operand is positively relabeled or excluded and no canonical calculation
exists for their identity. Their journal retains the corrected parent evidence. Every correction
and selection change is journaled and reversible.
Newly eligible filing-owned calculations
require an authoritative filing-scoped repair and are outside this tool: the lineage backfill
(`docs/filing-lineage-repair.md`) records their lineage, journaled in the same table and reverted by
this tool's rollback. New inserts remain
quarterly except for positively identified reported calendar replacements. Deploying the schema does not execute the repair.

## Prepare a bounded cohort

Deploy the provenance schema, journal schema and compatible readers first. Use the repository's
normal migration runner; never manually edit a recorded migration. Retain a database backup and
save the preview JSON with the intended environment, code revision and operator review. Run
against staging first. A production apply is a separate operational action.

A US-GAAP filer that reports in another currency (the CNY 20-F shape) normalizes into that
currency (`facts/currency.py`), so its repair plans native-currency identities. The repair does
not demote the USD convenience rows an older sync stored; only the companyfacts sync does that.
Sync such a company first (`POST /internal/jobs/sync-companyfacts` with `"force": true`), then
preview its repair. Otherwise, after the apply, both currencies are current for the same periods.
The sync leaves one thing for this repair: an annual ratio (a margin or the current ratio) that an
older sync computed from USD operands under the same filing as its native calculation. That
identity is occupied, so the sync keeps its USD operands; the repair's computed-metric correction
recomputes it from the native operands and journals the change. Apply the repair after the sync.

The CLI requires explicit tickers, defaults to a maximum of 10, and permits at most 50 per run.
Each company is its own transaction, bounded to 10,000 stored facts. Network reads complete before
the write transaction starts. Companies are serialized with the existing company-row lock used
by the fact writers; modified fact rows are locked as well. Failures are reported per company,
roll back that company's transaction, and cause a nonzero exit code. Earlier successful companies
in the same batch remain committed and can be rolled back independently. Before the first company,
the CLI prints one flushed JSON line that names the run:
`{"dry_run": …, "rollback_run": …, "run_id": "…", "started": true, "tickers": […]}`, where
`rollback_run` is the target run of a rollback and `null` otherwise. The full report follows only
once the batch ends, so a run cut short keeps its `run_id` in that line alone.

From `backend/`, preview without database writes:

```bash
python scripts/repair_quarterly_facts.py --tickers META --output /tmp/meta-quarterly-preview.json
```

For a repeatable offline companyfacts input, pass `--companyfacts-dir /path/to/snapshots`; the
selected company's filename is `CIK0001326801.json`. The payload CIK must match the selected
company. Inputs are limited to 32 MiB. No arbitrary remote URL is accepted.

Inspect `planned_updates`, `planned_inserts`, every changed value and provenance record, and the
coverage counters. `before` is actual current coverage. Dry-run `projected_after` includes
candidate additions before the standard writer resolves filing-date precedence, so it is a
preview rather than a guarantee of final selected-row counts. An apply returns actual `after`
coverage. Counts alone are not proof that financial figures are correct.

## Optional directly reported quarterly EPS

Calculated EPS from annual weighted shares is not an acceptable replacement for reported EPS.
Without a directly reported source, existing derived EPS stays present with `validation:
unavailable`, preserving its original value in the audit record while public readers withhold it.

To recover directly reported EPS, supply a local JSON array through `--eps-manifest`. Review the
exact filing accession, exhibit, fiscal quarter, currency and filing date first. For example:

```json
[
  {
    "ticker": "META",
    "cik": "1326801",
    "accession": "0001326801-25-000014",
    "filename": "meta-12312024xexhibit991.htm",
    "period_end": "2024-12-31",
    "fiscal_period": "Q4",
    "fiscal_year": 2024,
    "currency": "USD",
    "filed_at": "2025-01-29"
  }
]
```

The manifest has at most 200 entries, only for selected tickers. The helper fetches the exact
attachment through the existing filing transport and accepts an unambiguous reported GAAP
quarterly EPS pair from the dated income statement table. It preserves the source hash and table
evidence. The adapter checks CIK, checks USD against reconciled current company EPS units, and
checks the fiscal label against normalized company periods. Missing or ambiguous sources fail
the company before writes. The manifest's 8-K classification and filing date are operator-reviewed
metadata; the table parser does not independently resolve the cover filing. Do not manufacture
these fields from an arbitrary webpage.

A directly reported quarter explicitly supersedes unsupported derived EPS, even when the annual
10-K was filed later. The original calculated row remains in the database. Unsupported monetary
calculations are quarantined only with positive incompatibility/invalid-calculation evidence;
an incomplete payload or missing operand alone does not erase historical coverage.

## Apply and verify

Use the same snapshot and reviewed manifest for preview and apply when reproducibility matters:

```bash
python scripts/repair_quarterly_facts.py --tickers META --companyfacts-dir /path/to/snapshots --eps-manifest /path/to/eps-sources.json --apply --output /tmp/meta-quarterly-applied.json
```

Save the returned run ID. The audit table holds before/after states for corrected, inserted and
latest-demoted rows, the calculation version, and a hash of input payloads. Values are serialized
as decimal strings. A rerun against identical current state produces no new revisions. The public
analysis data fingerprint incorporates fact/provenance changes, so a corrected dataset cannot
reuse a narrative generated from the old inputs. Check the company's quarterly API, tables,
charts, narrative and exports before expanding to another small cohort.

## Run it through the Ops workflow

The production database is reachable only from Cloud Run and through the Ops workflow's Cloud SQL
proxy. The Ops workflow (`.github/workflows/ops.yml`, dispatched from main) runs this script on its
runner through that proxy, so the report lands in the run's log. Operation
`repair-quarterly-dry-run` runs the preview and `repair-quarterly-apply` runs the apply.

- **Tickers.** Both need the `tickers` input: an explicit comma-separated list of at most 50. The
  ops job's first step checks it, before the cloud sign-in and any database step, and a bad list
  stops the run there. For an apply that step runs after the founder's approval, so an apply with a
  bad list still asks for approval, then fails closed and writes nothing. An empty list is refused,
  never read as every company. The step passes `--tickers` and `--limit 50`, so the script's
  default of 10 does not refuse a longer list.
- **No other flags.** Ops passes no other flag, so it cannot pass `--companyfacts-dir`,
  `--eps-manifest` or `--rollback-run`. Each run reads companyfacts from SEC itself, one read per
  company under the shared limiter, at the one request a second every SEC-calling process is
  pinned to (`docs/OPERATIONS.md`, "SEC budgets per process").
- **Sync first, and wait for it.** A company that the section above says to sync first needs Ops'
  `sync-companyfacts` (which sends `"force": true`) to have finished before its preview, and a green
  `sync-companyfacts` run does not show that. When the Ops identity can read `INTERNAL_JOB_TOKEN`,
  the step posts to `/internal/jobs/sync-companyfacts`, which answers 202 once it has accepted the
  work, and prints `resync ACCEPTED via internal endpoint for: … (runs in the service background)`.
  The sync then runs on its own. With `DURABLE_TASKS_ENABLED` (on in production,
  `docs/OPERATIONS.md`) it runs as one queued task per ticker on `earningsnerd-task-worker`, and
  each task that finishes logs `Internal durable sync-companyfacts complete: …`; a ticker whose sync
  reports a failure logs no such line. With the flag off it runs as a background task in the API
  service, which logs `Companyfacts sync (internal trigger) complete: …` with the batch's counts
  once it ends, or `Companyfacts sync (internal trigger) failed` if it raised. Those lines are in
  Cloud Logging, which no Ops operation prints, so the founder confirms them before the preview is
  dispatched. Only when the token cannot be read does the step use the jobs channel instead:
  `--wait` holds it until the job execution ends, and it then prints
  `resync COMPLETED via jobs channel for: …`.
- **The apply re-plans.** The apply plans again from a fresh SEC read, so its own report is the
  record of what changed, not the preview's. Compare the two before closing the change.
- **Session guards.** Before the script, the step prints the session's settings as Postgres reports
  them: `session read_only=on lock_timeout=10s statement_timeout=2min` for the preview, and
  `read_only=off` for the apply. It stops unless they are the step's own. The preview's
  transactions are read-only, so Postgres refuses any write.
- **Approval.** The apply waits for the founder's approval on the `ops-apply` environment before any
  step runs (`docs/DEPLOYMENT.md`, "One-shot maintenance runs"). Approve it promptly, because the run
  executes the commit main had at dispatch. The workflow also refuses to start while a CI run for a
  push to main is in flight; for an apply, that check runs after the approval.
- **Failures and retries.** A failed company fails the run, and nothing retries it. The batch's other
  companies still run, each in its own transaction, and those that succeed stay committed. A re-run
  of an approved apply writes nothing and fails visibly, so a retry is a fresh dispatch with a fresh
  approval.
- **The run_id and the report.** The script's start line, in the log before the first company,
  names the run: an apply's reads `"dry_run": false` and carries its `run_id` and tickers. The JSON
  report follows once the batch ends. It is printed in the log and kept for 30 days as the run's
  artifact `quarterly-repair-<run id>`
  (`gh run download <run id> -R neilmac91/EarningsNerd -n quarterly-repair-<run id>`). Save the
  apply's `run_id`; the audited rollback needs it. A batch the script refuses as a whole (an
  unknown ticker, say) prints only its error, before any company, and writes no report file. A run
  stopped before its report writes none either. The artifact is then missing, and the log holds the
  error, or the start line.
- **An interrupted apply.** A cancel, or the step's 60-minute timeout, stops the script before its
  report, while each company it finished is already committed and journaled. Read the `run_id`
  from the start line. To undo what it committed, preview and then apply the audited rollback with
  that `run_id` over the same tickers, through the job image (below). Each company the apply
  committed rolls back. Each it did not has no journal under that run and fails its own line with
  `No bounded apply journal for this company/run`, so the rollback exits 1 while the others still
  roll back. That covers a company the apply never reached, the one whose transaction the stop
  rolled back, and one whose apply changed nothing. To finish the change instead, dispatch a fresh
  apply. It gets a new `run_id`, so undoing all of it later takes a rollback of each run, the later
  one first, since a rollback refuses a company whose rows changed after its run.
- **Both are public.** The repository is public, so anyone can read the log, and anyone signed in
  to GitHub can download the artifact. The report holds tickers, company ids, period ends, values and provenance, all public
  filing data. GitHub masks secrets in the log but not inside an artifact. The report carries no
  credential, but an `error` entry can quote the failing SQL and its parameters, and a failed
  connection's error names the database user and the database.

The deployment has no staging tier (`docs/DEPLOYMENT.md` lists production only), so the staging run
asked for above has no target. Instead, the founder reads the production preview before approving
the apply. The database backup is still the founder's to confirm or take before the first apply,
since only the founder has GCP credentials. The audited rollback below has no Ops operation; it runs
through the job image (`docs/fiscal-year-label-repair.md`, "Apply (founder sign-off required)").
Over more than one ticker, switch gcloud's `--args` delimiter so the list stays one value, and pass
`--limit` as the Ops step does once the list is longer than 10:

```bash
gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \
  --args="^;^scripts/repair_quarterly_facts.py;--tickers;TGT,JNJ;--limit;50;--rollback-run;RUN_ID" --wait
gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \
  --args="^;^scripts/repair_quarterly_facts.py;--tickers;TGT,JNJ;--limit;50;--rollback-run;RUN_ID;--apply" --wait
```

## Audited rollback

Preview first; then pass `--apply` to execute:

```bash
python scripts/repair_quarterly_facts.py --tickers META --rollback-run RUN_ID --output /tmp/meta-quarterly-rollback-preview.json
python scripts/repair_quarterly_facts.py --tickers META --rollback-run RUN_ID --apply --output /tmp/meta-quarterly-rollback.json
```

Rollback compares every affected row with the exact after-state recorded by the target apply.
Any intervening change refuses the entire company; inspect the conflict and prepare a new repair
rather than forcing it. Existing rows regain their original state. Inserted rows remain as
unavailable, non-current history rather than being deleted. Repeated rollback is rejected. Each
rollback adds its own journal entries and references the revisions it reverses. A selected company
with no journal under the target run fails its own line (`No bounded apply journal for this
company/run`) and makes the exit code nonzero; the other companies still roll back, each in its own
transaction.

Reapplication that encounters an identity inserted and subsequently rolled back is deliberately
rejected. This CLI does not reactivate those archived rows: inspect the reason for rollback and
prepare a separately reviewed repair if reactivation is needed. Do not delete audit rows or
financial history to force an upsert. Repeated applies before a rollback remain idempotent.
