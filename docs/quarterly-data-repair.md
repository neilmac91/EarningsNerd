# Historical quarterly data repair

This is an operator maintenance tool, not part of normal ingestion. Normal companyfacts upserts
keep accession identities immutable. An explicit repair can correct previously stored calculated
quarterly facts and rebuild lineage for existing annual computed metrics (margins, free cash
flow and liquidity ratios). It keeps a before/after journal in `financial_fact_revision` in the
same transaction. It does not rewrite filing JSON, call AI, change production flags, or delete facts.
Per-filing reported records change only through the proxy step (below, "Proxy-statement values
(E211)"): it promotes one that agrees with the 10-K's winner (`is_latest` only), restores one the old
cross-check replaced with a proxy's figure, records again a check confirmed against one, and
re-annotates the filing calculations over those rows. Annual computed-metric repairs are restricted
to the known computed metric registry, source `derived`/`companyfacts`, no reported raw tag, and no
filing owner; reported annual numeric values and filing-owned metrics are preserved by the
computed-metric repair.
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
quarterly except for positively identified reported calendar replacements and the 10-K winners the
proxy step admits. Deploying the schema does not execute the repair.

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

## Proxy-statement values (E211)

Before #1622 a proxy or information statement's pay-versus-performance figure could win a
companyfacts period, and the backfill's cross-check could take it as the authority over a filing's
parse (`facts/currency.is_proxy_form` keeps both out now). Ingestion never rewrites a stored identity,
so those rows stay until this repair's proxy step (`backend/app/services/proxy_fact_repair.py`) repairs
them. It runs in every preview and apply, with no flag, after the calendar correction and before the
computed-metric correction, reading only the payload the repair already fetched. A company with no proxy
row and no filing row a proxy figure replaced or confirmed passes through it unchanged.

It runs these passes, in this order; the sets are those of `ops/detection/proxy_form_winners.sql`.

1. **Set 4: filing rows the old cross-check replaced with a proxy's figure** (a filing owner and source
   `companyfacts`, whose value a proxy figure holds: a stored proxy-form row, current or not, or a proxy
   item in the payload; relative 1e-6). Left alone when a stored report row holds the value, or when the
   value is 1,000 or 1,000,000 times the recorded original (the authority scaling up a parse read in
   units, the replacement the check exists for). Kept, and counted `filing_rows_kept`, when it already
   holds today's authority's figure, the 10-K's. Otherwise restored (`filing_rows_restored`) to its
   recorded `original_value` and passed through today's cross-check, as the backfill stores it now
   (source `edgar_xbrl`, its check recorded against the 10-K's figure), when that original is within 1%
   of the 10-K's figure; where the
   payload gives no figure (a year only a proxy tags), restored to the original with the local gate's
   verdict and no authoritative check, as the backfill stores it with no authority. Refused when no
   original was recorded (a replacement before #1191), or when the original is more than 1% off the
   10-K's figure.
2. **Set 5: filing rows the old cross-check confirmed against a proxy's figure** (a filing row of
   another source whose recorded check confirmed it against an `authoritative_value` a proxy figure
   holds). Left alone when a stored report row holds that figure (the confirmation may have come from
   it). Kept, and counted `filing_rows_kept` (`kept_confirmed_by_10k`), when that figure is today's
   authority's, the 10-K's: the proxy quoted the 10-K exactly, as CRM's, META's, NVDA's and REGN's do,
   so the row and its record are right. Otherwise its value and source stay, and its check is recorded
   again against today's authority, or, where the payload gives no figure, replaced by the local gate's
   verdict (`filing_rows_reconfirmed`). Refused when the 10-K's figure is more than 1% off the row's
   value: FedEx's proxy, in dollars, confirmed a parse that read millions as units.
3. **Re-annotation.** Once both passes have run, each filing's calculations over a row they rewrote are
   recomputed once per filing scope by the per-filing writer's calculator (`facts/lineage.py`), so each
   operand's record in them is the operand's own record now (`filing_calculations_reannotated`, one per
   calculation). It writes `provenance` and `reconciled` only, and only on a filing-owned calculation of
   a rewritten concept that has a version-1 record and whose operands the calculator finds. A
   calculation whose new record would read `unavailable` where its stored record does not (an operand
   in its scope is withheld, such as a companyfacts row a correction retired with the filing's labels)
   is held as it is, with the lineage backfill's `operand_withheld` hold (`docs/filing-lineage-repair.md`):
   counted `filing_calculations_held`, with a `reannotation_held` entry in `rows` that names the new
   record's reasons. So the step never withholds a figure readers see today by re-annotating it. A
   calculation with no record, which is that backfill's, and every other record stay as they are.
4. **Set 2: current proxy-form rows.** Each is retired: `is_latest` and `reconciled` false, provenance
   `validation: unavailable` with reason `proxy_statement_value`, and `replacement` naming what took its
   key. The fresh winner at its key (concept, period end, fiscal period, unit) is then admitted. It is
   inserted when no stored row holds its identity; corrected and promoted when a companyfacts-owned row
   holds it (a stored 10-K row a proxy demoted); promoted, `is_latest` only, when a filing-owned row
   holds it and agrees with it. A key with no fresh winner in any unit keeps no current row
   (`retired_without_winner`): the fixed ingestion's own result for a period only a proxy tags.
5. **Set 3: current rows built on a proxy figure** (provenance that quotes a proxy row's accession,
   other than `companyfacts`, the name a sync gives an item that carries none, which every
   cross-checked filing row quotes as its check's method; the detection file skips it too).
   A calculation the computed-metric correction can recompute, its identity among the payload's
   candidates, is left to it (`dependents_recomputed`). Otherwise it is retired with reason
   `proxy_statement_operand` and the fresh fact at its key admitted as in set 2 (`dependents_retired`).

**The agreement test.** A filing-owned row at the winner's identity is promoted only when its value is
within 1% of the winner's (the cross-check's own tolerance for one filing's parse against companyfacts'
figure for that filing), its start equals the winner's or it has none, and its fiscal year equals the
winner's. A missing start counts as agreement (founder, 2026-10-26): the per-filing writer stored rows
without one before #831, and the identity already names the filing and the period. The promoted row's
value, provenance and labels never change.

**Refusals.** The step refuses the whole company before any write when it cannot settle a case on
positive evidence, with every reason in one error: `Proxy repair refused for this company (N):
<concept> <fiscal period> <period end> (fact <id>): <reason>; …`.

| Reason | Meaning |
|---|---|
| `a filing row holds a proxy's figure, not the 10-K's, and records no original value` | set 4: a replacement from before #1191 |
| `the 10-K's figure disagrees with the recorded original value by more than 1%, and the filing row holds neither` | set 4: the parse and the 10-K disagree |
| `the old cross-check confirmed this filing row against a proxy's figure, and the 10-K's figure disagrees with it by more than 1%` | set 5 |
| `a row with a filing owner carries a proxy form, which no writer stores` | set 2: an anomaly |
| `another row is current at this key (fact N)` | two current rows at one key: an anomaly |
| `the payload holds more than one winner at this key` | an ambiguous winner |
| `the payload's winner for this period is in <unit>; sync the company first` | a native-currency filer: sync it first (above), then preview again |
| `a stored report row (fact N) has no fresh winner to agree with` | no fresh winner, but a stored report gives a figure |
| `the winner's row (fact N) was rolled back; a reviewed reapplication is required` | as for any rolled-back identity (below) |
| `the filing row holding the 10-K's identity (fact N) disagrees with the 10-K on: …` | the agreement test, naming each failing clause: `value`, `start`, `fiscal year` |
| `a row outside the repair's scope is built on a proxy figure` | set 3: a filing's calculation or a reported row |

A postcondition then holds on the plan, before any write, and again on the apply's rows after its
writes: no current row is proxy-form, no current row quotes a proxy accession, and each key the step
settled holds the current rows it planned (one, or none after `retired_without_winner`). At a quarter
key, a current row with no fiscal period at the key's period counts beside it: on the plan where the
step makes a stored row current in place (a promotion or correction, or a calculation left to the
computed-metric correction), since no upsert demotes it there, and on the apply's rows at every key, since
only the apply shows where the upsert lands an insert. It fails with `Proxy repair would leave rows for
detection: {…}` or `Proxy repair left rows for detection: {…}`; after the writes the company's
transaction then rolls back, journal included.

While the step lives, a refusal blocks every quarterly repair of that company, not only its proxy
repair. Dispatch the apply without a refused ticker, give it its own `tasks/todo.md` line with the
reason, and decide each refused row from its filing (founder, 2026-10-26).

**Reading the preview.** Each company's report carries a `proxy` block:

- The counters above, each pass's, at zero when unused. `inserted`, `promoted`, `corrected` and
  `retired_without_winner` count once per key; `retired` counts rows.
- The counter `filing_rows_kept` counts both kept kinds: a set-4 row that already holds the 10-K's
  figure and a set-5 row already confirmed against it. A kept row is counted on every run while a
  proxy figure, a stored proxy-form row or a proxy item in the payload, holds its figure (set 4: its
  value; set 5: the figure its check confirmed it against) and no other stored report row does.
  Detection lists it where a stored proxy-form row is that witness or, in set 4, where its value is
  within 1% of 1/1,000 or 1/1,000,000 of its recorded original, with the same sign (the file's "scale"
  listing); a row kept against a payload item alone is otherwise counted on every run and never listed
  (below).
- `rows`: one entry per row the step settles, with its `action` (`inserted`, `promoted`, `corrected`,
  `retired_without_winner`, `dependent_<outcome>`, `restored`, `reannotated`, `reannotation_held`,
  `kept_agrees_with_authority`, `kept_confirmed_by_10k` or `reconfirmed`), its own and its winner's
  accession and value, `gap`
  (`|a - b| / max(|a|, |b|)`; 1.0 is a figure at another scale), the winner's form and filing date
  (`winner_form`, `winner_filed`), and `twin_fact_id` where a current row with no fiscal period sits at
  a quarter key's period end (at an inserted winner the apply decides it, by the upsert's filing dates;
  at a promoted or corrected one the plan refuses).
- `other_planned_updates`, `other_planned_inserts`, `other_updates_by_kind` (`made_unavailable`,
  `is_latest`, `value`, `label`, `provenance_only`) and `other_inserts_by_concept`: the company's other
  pending corrections, which the same approval applies.
- `projected_residual`, and on an apply `residual`: the postcondition's counts, all zero.
- `detection_listed`: each filing row that detection sets 4 and 5 will still list once the plan is
  applied, by the file's own rules and in its exact arithmetic (a witness within 1e-6, a scale band of
  1%, compared as PostgreSQL's numeric compares them, not as floats), as `{fact_id, set, verdict}`; on
  an apply it is computed from the rows as written. The verdict is the step's:
  `kept_agrees_with_authority` or `kept_confirmed_by_10k` (right as it is, and listed because no other
  stored report row holds its figure), `no_proxy_figure` (a set-4 "scale" row: a parse 1,000 or
  1,000,000 times too large that the 10-K's own figure corrected; outside the step), `restored` or
  `reconfirmed` (its new figure, the 10-K's, is also a proxy row's, as where a later proxy quotes the
  10-K exactly), or `report_backed` (a report row held its figure before the apply, and another
  correction of the same run changed that row). `unclassified` would be a defect of the step: report it.

The CLI's report adds `proxy_totals`, each counter and each `other_*` entry summed over the companies
that succeeded. Read each company's block this way: `inserted + promoted + corrected +
retired_without_winner` equals `retired` (one proxy row per key, as the writers leave it);
`retired_without_winner`, `dependents_retired` and `filing_calculations_held` are expected to be zero,
and any other value is read row by row. A held calculation keeps its stored record, whose operand
record still carries the old check against the proxy's figure, and nothing rewrites it later: a sync
or backfill skips a stored identity, the lineage backfill records only a calculation with no record,
and the step's later runs leave its operand as the apply wrote it, so only this preview and its apply
name it. Give each company with a held calculation one `tasks/todo.md` line, as a refused company
gets, naming its held calculations by fact id, and decide each from its filing by a reviewed repair
(one line per company keeps the file within its 120 lines). Every `winner_form` is `10-K` (a 10-K/A
that carries the pay-versus-performance table is a report, and admitted); `gap` measures each retired
figure against its winner, the first measure for rows with no stored report behind them. Read
`made_unavailable` row by row in `changes`: each such figure leaves the public pages. Read the other
corrections against a baseline: a plain preview of the same tickers on the commit before the step,
saved before it merged. A company only set 5 names is first known after the merge (set 5 is new with
the step), so it has no baseline: read its `other_*` corrections row by row in `changes` instead.

**The journal.** The apply journals the step's rows with the rest of the run, under
`calculation_version` `proxy-repair-v1`: the rows it wrote or left to the computed-metric correction,
its inserts, and every row that is or quotes a proxy row. The run's other rows keep `quarterly-v2`, so
one query lists the proxy repair alone:

```sql
SELECT fact_id, before_state, after_state FROM financial_fact_revision
WHERE run_id = :run_id AND calculation_version = 'proxy-repair-v1' ORDER BY id;
```

A retired row is non-current and `unavailable`, so no reader shows it: the public pages, the Copilot's
accession scope and the fiscal-year evidence all withhold an unavailable figure. The audited rollback
(below) reverts the step's rows with the rest of the run.

**Done.** Right after the apply, before any companyfacts sync or facts backfill reaches a repaired
company, dispatch `detection-sql`. For every company the apply repaired, `proxy_form_winners.sql`
must read no rows in sets 2 and 3, and in sets 4 and 5 exactly the rows its apply report lists in
`proxy.detection_listed`: compare their `fact_id`s. The comparison is exact only on the rows as the
apply wrote them, and a sync or backfill in between can change them: a sync can store a later 10-K's
comparative, a report row that takes a kept row off set 5. For a company one of them reached first,
run its dry run again and compare the file with that preview's `proxy.detection_listed`, which reads
the rows as they stand. Each set stops at 200 rows and carries its full count (`of_n`): where a set's
`of_n` exceeds the rows it shows, that run cannot establish the criterion, and the set's limit is raised
in a reviewed change before the run is repeated. Record the listed rows, with their verdicts, in the
records change. A company the apply refused
stays listed in every set until its own follow-up line closes, by a reviewed repair or by recording why
its rows stand.

The step is temporary. Once that run holds for every repaired company and every refused company's
line is closed, a records change deletes the detection file and its test, and a later change removes
the step. Removing it earlier would remove the only repair for a refused company's current proxy rows.

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
- **The proxy step.** Both operations run it with no flag ("Proxy-statement values (E211)", above).
  One approval applies each company's whole plan: its proxy repair and its other pending corrections
  (`other_*` in its `proxy` block).
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

The proxy step's rows roll back like any other. Its inserted 10-K winners then stay as rolled-back
history, so the company's every later repair refuses, and no sync heals those keys, since their
identities are taken: roll a proxy repair back only to stop a harmful apply.

Reapplication that encounters an identity inserted and subsequently rolled back is deliberately
rejected. This CLI does not reactivate those archived rows: inspect the reason for rollback and
prepare a separately reviewed repair if reactivation is needed. Do not delete audit rows or
financial history to force an upsert. Repeated applies before a rollback remain idempotent.
