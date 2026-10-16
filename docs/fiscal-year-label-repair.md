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

It copies the companyfacts fiscal year onto `financial_fact` rows with `source = 'edgar_xbrl'`,
`fiscal_period = 'FY'` and a filing owner. It changes `fiscal_year` and nothing else: never
`period_end`, `value`, `unit`, `accession` or `is_latest`, never a quarter row, never a
companyfacts, derived or reported-EPS row, never a delete. Durations and balance-sheet instants are
both relabelled, because an annual balance closes the year that ends on its date.

The year comes from the stored companyfacts FY rows at the same company and period end
(source `companyfacts`, an XBRL tag, no filing owner, current or not, excluding rows a quarterly
repair retired as `validation: unavailable`). It is used only when it can be trusted. Each scanned
row is counted once:

| Count | Meaning |
| --- | --- |
| `relabel_rows` / `relabels` | The rows that change, grouped by period end with the `from` and `to` years |
| `already_agrees` | The row already carries the trusted companyfacts year; left alone |
| `no_companyfacts_fy` | No companyfacts FY row at that period end; left alone |
| `companyfacts_disagree` | Companyfacts rows at that period end name more than one year; left alone, never one picked |
| `untrusted_instant_only` | Companyfacts holds only balance-sheet rows there. The companyfacts writer names its oldest opening balance (older than every fiscal year it knows) by calendar year, which for a January year is the next year's label, so an instant-only label is never copied |

`held` lists the period ends behind each non-agreeing skip, for spot checks.

**Where the writer that ran first owns the identity.** When the per-filing writer stored a period
before the company's first companyfacts sync under the same accession, the sync skipped that
identity and no companyfacts row exists there; those rows count as `no_companyfacts_fy`. A high
share of that count is a signal for a follow-up repair source, not a reason to widen the trust rule.

## Run it

Run it only after P5 (#1364) is merged and deployed; before that, newly opened filings still write
calendar years. The database is only reachable from Cloud Run, so run it through the backfill job
image with execution-scoped arguments (see `docs/DEPLOYMENT.md`, one-shot maintenance runs).

Dry run (the default; writes nothing, and each company's read is rolled back):

```bash
gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \
  --args=scripts/relabel_filing_fy_facts.py --wait
```

Each company scanned prints one JSON line, then one summary line (`"summary": true`) with the
totals. Cloud Logging stores them as `jsonPayload`:

```bash
gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="earningsnerd-backfill-facts" AND jsonPayload.relabel_rows:*' \
  --freshness=3h --format=json
```

`--tickers TGT,JNJ` limits the run to a cohort and `--limit N` to the first N companies by id.

## Apply (founder sign-off required)

The apply rewrites stored financial data. Run it only after the founder has read the dry-run
counts and signed off, with the same arguments plus `--apply`:

```bash
gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \
  --args=scripts/relabel_filing_fy_facts.py,--apply --wait
```

Each company is its own transaction, taken under the same company lock the fact writers use. A
failed company rolls back alone, prints an `error` line and makes the exit code non-zero. Every
changed row is journaled in `financial_fact_revision` (action `apply`, version `fy-relabel-v1`)
under the printed `run_id`. To revert one company, preview and then apply the audited rollback:

```bash
python scripts/repair_quarterly_facts.py --tickers TGT --rollback-run RUN_ID
python scripts/repair_quarterly_facts.py --tickers TGT --rollback-run RUN_ID --apply
```

## Re-running

The run is idempotent: a relabelled row counts as `already_agrees` next time, and a second apply
reports `relabel_rows: 0`. Re-run it (dry run first) after any backfill that re-extracts filings
from persisted `Filing.xbrl_data` snapshots taken before P5, because those snapshots carry no
annual labels and still write calendar years.

## What readers see

Readers that select annual facts by `fiscal_year` move with the repair: the filing page's annual
chart (`get_filing_fundamentals`), Multi-Period Analysis coverage and datasets, the peer panel's
year, Copilot `get_financial_fact` lookups and the data-quality coverage spans. A changed
Multi-Period dataset gets a new fingerprint, so its narrative is regenerated when next requested.
Readers that select by `period_end`, such as quarterly balance reads, are unchanged.
