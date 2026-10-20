# Fiscal-year label repair for filing-owned annual facts

An operator maintenance tool, not part of ingestion. Before P5 (#1364) the per-filing fact writer
named every annual (10-K, 20-F, 40-F) fact by the calendar year of its period end, while the
companyfacts writer names the same period by the issuer's fiscal year. They differ for a year
ending around 1 February that is named for the year it starts in (Target, Home Depot, Lowe's) and
for a 52-week year ending on 1 January (Johnson & Johnson). The fact identity leaves `fiscal_year`
out, so neither writer corrects the other's rows: Multi-Period Analysis loses or shifts a year and
the filing page's annual chart draws two bars for one year. P5 fixes new writes only.
`backend/scripts/relabel_filing_fy_facts.py` repairs the stored rows.

## What it changes

It targets `financial_fact` rows with `fiscal_period = 'FY'` and a filing owner, whatever their
source (a headline value the cross-check corrected is stored as `companyfacts` but keeps its
owner). It changes `fiscal_year` and nothing else: never `period_end`, `value`, `unit`,
`accession` or `is_latest`, never a quarter row, never a companyfacts, derived or reported-EPS row
without a filing owner, never a delete. Durations and balance-sheet instants are both relabelled,
because an annual balance closes the year that ends on its date. It only rewrites the defect's own
signature, a label equal to the calendar year of the period end; any other label (P5's annual
label, for example) is left alone.

The year comes from the stored companyfacts FY rows at the same company and period end (source
`companyfacts`, an XBRL tag, no filing owner, current or not, excluding rows a quarterly repair
retired as `validation: unavailable`) that the fiscal-year-window writer stored or a repair
corrected: `provenance.version = 1`. That writer and versioned provenance arrived together in
#1191 (10 October 2026). A row stored before it has NULL provenance and names every FY period by
the calendar year of its end, so it is not evidence. Each scanned row is counted once:

| Count | Meaning |
| --- | --- |
| `relabel_rows` / `relabels` | The rows that change, grouped by period end with the `from` and `to` years |
| `already_agrees` | The row already carries the trusted companyfacts year; left alone |
| `no_companyfacts_fy` | No companyfacts FY row at that period end; left alone |
| `legacy_companyfacts_only` | Only rows stored before #1191 (calendar labels) at that period end; left alone, never read as agreement |
| `companyfacts_disagree` | Current-writer rows at that period end name more than one year; left alone, never one picked |
| `untrusted_instant_only` | Only balance-sheet rows there. The companyfacts writer names its oldest opening balance by one report's fy or, failing that, by calendar year (for a January year, the next year's label), with no fiscal-year window behind it, so an instant-only label is never copied |
| `not_calendar_default` | The row's label is not the calendar year of its end, so a labeller set it (P5, or a NULL); a stored source never overwrites it |
| `label_collision` | The new label is one that another period end of the same filing and concept, or another current row of the concept, would carry; left alone so the chart and the annual datasets never get two period ends for one year |

`held` lists the period ends behind each non-agreeing skip, for spot checks. `partial_filings`
lists, on every run, the accessions of filings that keep calendar-default rows beside fiscal years
the run relabels or finds already agreeing (for example the newest year held as
`no_companyfacts_fy`): their annual chart may skip a year until the held rows are repaired. The
summary line totals every count, and `partial_filings` as a number.

**Where the writer that ran first owns the identity.** When the per-filing writer stored a period
before the company's first companyfacts sync under the same accession, the sync skipped that
identity and no companyfacts row exists there; those rows count as `no_companyfacts_fy`, and their
neighbours often as `label_collision`. A high share of these counts, or of
`legacy_companyfacts_only`, is a signal for a follow-up repair source, not a reason to widen the
trust rule.

## Run it

Run it only after P5 (#1364) is merged and deployed; before that, newly opened filings still write
calendar years. The database is reachable only from Cloud Run and through the Ops workflow's Cloud
SQL proxy, so run it through the backfill job image with execution-scoped arguments (see
`docs/DEPLOYMENT.md`, one-shot maintenance runs), or through the Ops workflow below.

Dry run (the default; writes nothing, and each company's read is rolled back):

```bash
gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \
  --args=scripts/relabel_filing_fy_facts.py --wait
```

Each company prints one JSON line, then one summary line (`"summary": true`) with the totals. A
company that fails prints `{"company_id", "ticker", "error"}` instead, and a refused run (an
unknown ticker) prints `{"failed": 1, "error"}`. Cloud Logging stores every line as
`jsonPayload`; read one execution's lines, errors included, by the execution name `--wait` prints:

```bash
gcloud logging read 'resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="<execution name>" AND jsonPayload:*' \
  --order=asc --format='value(jsonPayload)'
```

`--tickers TGT,JNJ` limits the run to a cohort (each named company gets a line, even with nothing
to scan) and `--limit N` to the first N companies by id.

The Ops workflow (`.github/workflows/ops.yml`, dispatched from main) runs the same script on its
runner through the Cloud SQL proxy, so every line lands in the workflow run's log instead of Cloud
Logging. Operation `relabel-fy-dry-run` runs the dry run in read-only transactions, so Postgres
refuses any write; `relabel-fy-apply` runs the apply below. Before the script, the run prints the
session's settings as Postgres reports them (`session read_only=on lock_timeout=10s
statement_timeout=2min` for a dry run, `read_only=off` for the apply) and stops unless they are the
step's own, so the log shows the guards took effect. Its `tickers` input passes `--tickers` (at most
50); there is no `--limit`. The workflow refuses to start while a CI run for a push to main is in
flight, so dispatch after that run finishes. A failed company fails the run once, with no automatic
retry: read its `error` line, then dispatch again. Dispatching the same apply again after such a
failure, up to three times (the retries Cloud Run would have made on its own), over the same tickers
or only the companies that failed, stands under the same sign-off; an apply over other tickers needs
its own. The repository is public, so anyone can read the run's log. Its lines carry company ids,
tickers, period ends and fiscal years, all public filing data, and an `error` line can quote the
failing SQL and its parameters. The proxy step masks the database URL and password, but a failed
connection's error names the database user and the database.

## Apply (founder sign-off required)

The apply rewrites stored financial data. Run it only after the founder has read the dry-run
counts and signed off, with the same arguments plus `--apply` (or the Ops workflow's
`relabel-fy-apply`). In the Ops workflow the run then waits for the founder's approval before any
step runs: GitHub shows it waiting on the `ops-apply` environment, and the founder approves it on
the run's page, promptly, since the run executes the commit main had at dispatch. The pre-flight
check for an in-flight main CI run happens after the approval, and a re-run of an approved apply
writes nothing, so each retry is a fresh dispatch and a fresh approval. A Claude Code session is
refused the approval call (`.claude/hooks/ops_approval_guard.py`).

```bash
gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \
  --args=scripts/relabel_filing_fy_facts.py,--apply --wait
```

The apply re-plans each company from the live rows, so the apply execution's own lines, not the
dry run's, are the record of what changed; compare them with the dry run before closing the
change. Each company is its own transaction, taken under the same company lock the fact writers
use. A failed company rolls back alone, prints an `error` line and makes the exit code non-zero.
A non-zero exit makes Cloud Run retry the task (no create command sets `--max-retries`, so the
default of three retries applies, `docs/OPERATIONS.md`): each attempt prints a new `run_id`, and
companies an earlier attempt committed then read as `already_agrees`. Every changed row is
journaled in `financial_fact_revision` (action `apply`, version `fy-relabel-v1`) under the `run_id`
on the company line that shows `revisions` above zero. To revert one company, preview and then
apply the audited rollback with that `run_id`. The rollback has no Ops operation, so it runs through
the job image:

```bash
gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \
  --args=scripts/repair_quarterly_facts.py,--tickers,TGT,--rollback-run,RUN_ID --wait
gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \
  --args=scripts/repair_quarterly_facts.py,--tickers,TGT,--rollback-run,RUN_ID,--apply --wait
```

## Re-running

The run is idempotent: a relabelled row counts as `already_agrees` next time, and a second apply
reports `relabel_rows: 0`. Re-run it (dry run first) after any backfill that re-extracts filings
from persisted `Filing.xbrl_data` snapshots taken before P5, because those snapshots carry no
annual labels and still write calendar years.

## What readers see

Readers that select annual facts by `fiscal_year` move with the repair: the filing page's annual
chart (`get_filing_fundamentals`), Multi-Period Analysis coverage and datasets, the peer panel's
year, Copilot `get_financial_fact` lookups and the data-quality coverage spans. A relabelled
row's value does not change, but the fiscal-year column it appears under does, now naming the
year that ends on its date; a filing listed in `partial_filings` keeps its held rows under their
calendar years, so its chart may skip a year. A changed Multi-Period dataset gets a new
fingerprint, so its narrative is regenerated when next requested. Readers that select by
`period_end`, such as quarterly balance reads, are unchanged.
