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
because an annual balance closes the year that ends on its date. It rewrites the defect's own
signature, a label equal to the calendar year of the period end. A label a labeller set (P5's annual
label) moves only with its whole filing, as the per-filing writer's own adoption (#1364) moves it:
every row of the filing that has a trusted year gives the same offset, this run's SEC read names the
same year at the row's period end, and no other labelled row of the filing is held, for any reason
(a collision included), so a filing is never left on two offsets. That repairs a 10-K whose DEI focus
lags, opened before companyfacts stored any year for the company (Salesforce's fiscal 2026 report,
focus 2025, stored one year low). Such a filing whose company synced its next annual report before
the relabel ran is held whole, one year low as before: that report's equity statement opens at the
filing's oldest end, the only companyfacts row stored there (the filing owns the rest), so the end
holds as `untrusted_instant_only`. A NULL label is never filled.

The year comes from the stored companyfacts FY rows at the same company and period end (source
`companyfacts`, an XBRL tag, no filing owner, current or not, excluding rows a quarterly repair
retired as `validation: unavailable`) that the fiscal-year-window writer stored or a repair
corrected: `provenance.version = 1`. That writer and versioned provenance arrived together in
#1191 (10 October 2026). A row stored before it has NULL provenance and names every FY period by
the calendar year of its end, so it is not evidence.

Where no stored row is evidence at a period end, the year comes from the company's companyfacts as
read from SEC on this run. The script reads each company's companyfacts once, through the shared
SEC limiter and backoff (`facts/transport`), before the company's session opens. It names their FY
periods with the writer a sync uses, judges them by the same rule, and stores nothing it read.
Where a stored row vouches for a period end, its year is the one used; the read can still clear,
or cause, a neighbour's `label_collision`. A resync rarely fills these gaps: a sync skips every
identity already stored, whichever writer stored it, and never rewrites a stored row's label or
provenance. So a pre-#1191 row, or a period the per-filing writer stored first, gains a current
companyfacts row only when a later report re-reports the period under an accession not yet stored.
A failed read, or one with no `facts` object, fails that company with an `error` line and changes
nothing; for a failed read the transport's warning on standard error gives the cause (in the Ops run log, or as a `textPayload` line in Cloud
Logging, outside the `jsonPayload:*` filter below). Each scanned row is counted once:

| Count | Meaning |
| --- | --- |
| `relabel_rows` / `relabels` | The rows that change, grouped by period end with the `from` and `to` years |
| `already_agrees` | The row already carries the trusted companyfacts year; left alone |
| `no_companyfacts_fy` | No companyfacts FY row at that period end, stored or read from SEC; left alone |
| `legacy_companyfacts_only` | Only rows stored before #1191 (calendar labels) at that period end, and either none read from SEC or a current one that readers still pick, beside which a relabel would split the period end across fiscal years; left alone, never read as agreement |
| `companyfacts_disagree` | Current-writer rows at that period end name more than one year; left alone, never one picked |
| `untrusted_instant_only` | Only balance-sheet rows there. Until 2026-10-23 the companyfacts writer named its oldest opening balance by one report's fy or, failing that, by calendar year (for a January year, the next year's label), with no fiscal-year window behind it; rows it stored then carry the same provenance as later ones, so an instant-only label is never copied |
| `not_calendar_default` | The row's label is not the calendar year of its end, so a labeller set it (P5, or a NULL), and it cannot move with its whole filing: the filing's trusted years give more than one offset, or this run's SEC read does not name the same year there, or another labelled row of the filing is held, or the label is NULL |
| `label_collision` | The new label is one that another period end of the same filing and concept, or another current row of the concept, would carry; the whole period end is left alone, every concept and filing at it, so the chart and the annual datasets never get two period ends for one year and no period end gets two years |

`held` lists the period ends behind each non-agreeing skip, for spot checks. `partial_filings`
lists, on every run, the accessions of filings that keep calendar-default rows beside fiscal years
the run relabels or finds already agreeing (for example a year held as `no_companyfacts_fy` because
SEC's companyfacts has no FY row there either): their annual chart may skip a year until the held
rows are repaired.
`sec_evidence` counts the scanned rows judged on the SEC read, whatever the outcome. The summary
line totals every count, and `partial_filings` as a number.

**Where the writer that ran first owns the identity.** When the per-filing writer stored a period
before the company's first companyfacts sync under the same accession, the sync skipped that
identity and no companyfacts row is stored there. The SEC read names that period, so its rows and
their neighbours relabel together instead of holding as `no_companyfacts_fy` and
`label_collision`. The first dry run, before the read existed (Ops run 39306000050, 2026-10-19),
held all 1,892 scanned rows for want of stored evidence: 1,153 as `no_companyfacts_fy` and 739 as
`legacy_companyfacts_only`.

## Run it

Run it only after P5 (#1364) is merged and deployed; before that, newly opened filings still write
calendar years. The database is reachable only from Cloud Run and through the Ops workflow's Cloud
SQL proxy, so run it through the backfill job image with execution-scoped arguments (see
`docs/DEPLOYMENT.md`, one-shot maintenance runs), or through the Ops workflow below.

Dry run (the default; writes nothing, and each company's transaction is rolled back):

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
refuses any write; `relabel-fy-apply` runs the apply below. Either way the runner reads each
company's companyfacts from SEC itself, one read per company under the shared limiter (its backoff
may retry a 429), at the one request a second every SEC-calling process is pinned to
(`docs/OPERATIONS.md`, "SEC budgets per process"), with the app's SEC user agent. Before the script, the run prints the
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
writes nothing and fails visibly, so each retry is a fresh dispatch and a fresh approval. A Claude
Code session is refused the approval call (`.claude/hooks/ops_approval_guard.py`).

```bash
gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \
  --args=scripts/relabel_filing_fy_facts.py,--apply --wait
```

The apply re-plans each company from the live rows and a fresh SEC read, so the apply execution's
own lines, not the dry run's, are the record of what changed; compare them with the dry run before
closing the change. Each company is its own transaction, taken under the same company lock the fact writers
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
annual labels and still write calendar years. Re-run the dry run, too, after the companyfacts
year-naming fix of 2026-10-23 deploys, before any apply: from then on the SEC read names an equity
statement's oldest opening balance, and a delinquent filer's year chain with no timely annual
report, by their fiscal years, and a labeller-set filing can move by its one offset, so an earlier
dry run no longer shows what an apply would do. A 10-K whose focus lags, opened before the
company's first sync, is still stored one year low, so later runs find such filings too.

**Companyfacts rows the relabel never touches.** The companyfacts writer's rows from before that fix
keep their labels, since a sync is insert-only: an oldest opening balance one year high (Target,
Home Depot, J&J), and a delinquent filer's late chain under calendar years, where its next annual
report's sync stores the re-reported years under fiscal labels beside the older calendar ones. The
audited quarterly repair, `scripts/repair_quarterly_facts.py --tickers ...` (preview, then
`--apply` with sign-off), relabels a current companyfacts row, journaled, only where the writer,
reading SEC now, still picks that row's own report for its period end. That holds for an oldest
opening balance, which only its own report carries. It does not hold for a delinquent filer whose
newer annual report a reader opened between two syncs: at the ends that report re-reports, the
current rows come from the older report, while the writer now picks the newer one, whose rows the
filing owns. The repair then moves, concept by concept, only the years the newer report does not
re-report, so a chain one year off everywhere gains a missing year and a period end on two years
(Target-shaped, pinned in `test_annual_fact_fiscal_labels.py`: revenue's 2022, 2023, 2024, 2025
became 2021, 2023, 2024, 2025, while the assets at fiscal 2022's end became 2022; in a review probe
the relabel then held the filing's newest end as `label_collision`). Run the preview for such a
cohort before the relabel, apply it only where it relabels every calendar-labelled year of a late
chain, and leave a chain it would repair in part as it is; no tool repairs that part yet. A current opening balance one year high holds the filing's
next year-end balance as `label_collision`, so repair those first.

## What readers see

Readers that select annual facts by `fiscal_year` move with the repair: the filing page's annual
chart (`get_filing_fundamentals`), Multi-Period Analysis coverage and datasets, the peer panel's
year, Copilot `get_financial_fact` lookups and the data-quality coverage spans. A relabelled
row's value does not change, but the fiscal-year column it appears under does, now naming the
year that ends on its date; a filing listed in `partial_filings` keeps its held rows under their
calendar years, so its chart may skip a year. A changed Multi-Period dataset gets a new
fingerprint, so its narrative is regenerated when next requested. Readers that select by
`period_end`, such as quarterly balance reads, are unchanged.
