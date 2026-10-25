# Lineage backfill for filing-owned legacy calculations

An operator maintenance tool, not part of ingestion. Before #1191 the per-filing fact writer stored
its calculated metrics (the gross, operating and net margins, free cash flow, working capital and
the current ratio) with no versioned provenance. Every reader projects such a row as a legacy
calculation (`fact_provenance.provenance_for_fact`): `validation: needs_review`, reason
`legacy_calculation`, so Multi-Period Analysis notes it and its growth figures as needing review.
Nothing gives these rows lineage later. Both writers skip an identity already stored
(`facts/upsert.py`), and the quarterly repair leaves filing-owned rows alone (`docs/quarterly-data-repair.md`).
`backend/scripts/repair_filing_lineage.py` writes the record, through
`backend/app/services/filing_lineage_repair.py`.

## What it changes

It changes `provenance` and `reconciled` on the rows it writes, and nothing else: never `value`,
`fiscal_year`, `fiscal_period`, `period_end`, `unit`, `accession` or `is_latest`, never another
row, never a delete. The record it writes is the one today's per-filing writer stores for the same
rows, recomputed by the same calculator (`facts/lineage.annotate_filing_calculations`), less that
writer's `checks.local_reconciliation`, the local gate's audit, which the stored row does not keep.

**Which rows.** A row is a target when it has a filing owner, its concept is one of the six
formulas (`fact_provenance.METRIC_FORMULAS`), its `raw_tag` is NULL, empty or the concept itself,
and its provenance is not a version-1 record. That is the reader's own legacy condition for a
calculation, limited to filing-owned rows. It covers every fiscal period, annual and quarterly, and
rows that are not current, since the filing page's annual chart reads every row a filing owns. A
formula concept with a tag of its own (`custom:NetMargin`) is reported, not calculated, and is
never a target. Companyfacts-owned legacy calculations belong to the quarterly repair.

**Which operands.** The calculator matches each input among every row of the company under the
target's accession, whatever its owner: the writer that stored an identity first owns it, so an
operand can be a companyfacts row. An input matches on company, accession, period end, fiscal year
and fiscal period, and must match exactly one row. The two inputs need the same unit and the same
start date, a flow (the margins, free cash flow) needs a start date, and the target's own start, if
it has one, must be the same. The recomputed value must agree with the stored one within a
relative and absolute tolerance of 1e-9. Each operand keeps its own record: a version-1 record as
stored, otherwise the reader's legacy projection, which passes a reported row whose `reconciled` is
true.

## What each row gets

Each target is decided in this order, and counted once:

| Count | Meaning |
| --- | --- |
| `held.legacy_flagged` | The row's `reconciled` is false: the old local gate flagged it for a reason the row does not keep. Held, never turned true. Its `rows` entry shows the verdict it would have had (`validation`) |
| `held.operand_withheld` | An operand's record is `unavailable` (a quarterly repair retired it), so the new record would be `unavailable` too and withhold a figure readers see today. Held |
| `held.inputs_not_found` | The calculator finds no operands. Held: an absent operand is no evidence against the figure, and writing `missing_calculation_inputs` would put a new concern on it. Its `diagnostic` names the first cause: `no_operand_row`, `ambiguous_operand` (more than one row for an input, such as revenue in two currencies), `unit_mismatch`, `duration_unknown` (a flow operand with no start date: the per-filing writer has stored one only since #831, 2026-09-13), `duration_mismatch`, else `other` |
| `held.operand_legacy_calculation` | An operand is itself a legacy calculation. Held: a version-1 record never carries a legacy reason |
| `outcomes.passed` | The operands are found, every one passes, and the value agrees. Written, `reconciled` true |
| `outcomes.needs_review` | A concern with positive evidence: the value disagrees with its operands (`calculation_mismatch`), or an operand is under review and passes on its reason (`source_check_needed`, `magnitude_vs_prior` and the like). Written, `reconciled` false. `reasons` counts each reason written |

A mismatch is what today's writer writes for the same rows. The legacy writer computed a margin
from the parsed revenue before the companyfacts cross-check could replace that revenue, so a
mismatch is a real inconsistency between the figure and its stored inputs.

Each company line carries `scanned` (its targets), `writes`, `outcomes`, `reasons`, `held`,
`diagnostics` (the causes behind `inputs_not_found`), `revisions` (zero in a dry run) and
`latest_fy`: for the current annual targets (`is_latest`, fiscal period `FY`) of the company's newest
fiscal year (its newest current annual row of any concept), how many the run clears (passes), marks
(concerns) and holds. That is the year whose review notes the Multi-Period Analysis baseline counts
(77 of 82 are `legacy_calculation`, #1610). `rows` lists every target with its id, concept,
fiscal year and period, period end, accession, `is_latest`, value, outcome, the calculator's
`validation` and `reasons`, and its `inputs` as `[concept, value]` pairs. The summary line totals
the counts. A company holding more than 10,000 facts is refused with an `error` line, because the
audited rollback below refuses it too.

## Run it

The database is reachable only from Cloud Run and through the Ops workflow's Cloud SQL proxy. The
script reads nothing from SEC and makes no network call.

The Ops workflow (`.github/workflows/ops.yml`, dispatched from main) runs it on its runner through
the proxy, so every line lands in the run's log. Operation `repair-lineage-dry-run` runs the dry run
and `repair-lineage-apply` the apply. Its `tickers` input passes `--tickers` (at most 50); empty
means every company with a filing-owned formula row, in company-id order. There is no `--limit`.
Before the script, the run prints the session's settings as Postgres reports them (`session
read_only=on lock_timeout=10s statement_timeout=2min` for a dry run, `read_only=off` for the apply)
and stops unless they are the step's own. The dry run's transactions are read-only, so Postgres
refuses any write. The workflow refuses to start while a CI run for a push to main is in flight,
so dispatch after that run finishes.

The script first lists the cohort in a short session and closes it. It then prints one flushed
start line, `{"dry_run": …, "run_id": "…", "started": true, "tickers": […] | null}`, and processes
each company in its own session and transaction: one JSON line per company, then one summary line
(`"summary": true`). A company that fails prints `{"company_id", "ticker", "error"}`, rolls back
alone and makes the exit code 1, and a refused run (an unknown ticker) prints
`{"failed": 1, "error"}` before any company. A failed company fails the run once, with no automatic
retry. The apply takes the company lock both fact writers take: a sync that holds it for more than
10 seconds fails that company with a lock timeout. Read its `error` line, then dispatch again.

The job image runs the same script with execution-scoped arguments (`docs/DEPLOYMENT.md`, one-shot
maintenance runs):

```bash
gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \
  --args=scripts/repair_filing_lineage.py --wait
```

The dry run stores nothing; the run's log is its record. The repository is public, so anyone can
read the run's log. Its lines carry company ids, tickers, period ends, values and accessions, all
public filing data, and an `error` line can quote the failing SQL and its parameters.

## Apply (founder sign-off required)

The apply rewrites stored provenance. Run it only after the founder has read the dry run's summary
and signed off, through the Ops workflow's `repair-lineage-apply`, which waits for the founder's
approval on the `ops-apply` environment before any step runs (`docs/DEPLOYMENT.md`, "One-shot
maintenance runs"). Approve it promptly, since the run executes the commit main had at dispatch. A
re-run of an approved apply writes nothing and fails visibly, so a retry is a fresh dispatch and a
fresh approval. A Claude Code session is refused the approval call (`.claude/hooks/ops_approval_guard.py`).

Order: apply after the quarterly repair's and the fiscal-year relabel's pending applies, then run the
dry run again before this apply. The relabel moves `fiscal_year` on filing-owned annual rows, which
the calculator's operand match and the journal's snapshot both read, so whichever runs second
closes the first one's rollback window, and a filing-owned margin beside companyfacts-owned
operands matches only once its year agrees. Apply one company first (REGN), read its line, confirm
that a dry run after it shows `writes: 0` for it, then apply the rest in one run.

The job-image form of the apply is `--args=scripts/repair_filing_lineage.py,--apply`.

The apply re-plans each company from the live rows, so the apply's own lines, not the dry run's, are
the record of what changed; compare them with the dry run before closing the change. Every written
row is journaled in `financial_fact_revision` (action `apply`, version `lineage-backfill-v1`), with
its state before and after, under the `run_id` on the company line.

## Audited rollback

The quarterly repair's rollback reverts one company's run, as it does for the relabel. Preview it,
then apply it, with the `run_id` of a company line that shows `revisions` above zero; a company
whose line shows none has no journal under that run, and its rollback line reads
`No bounded apply journal for this company/run`. The rollback has no Ops operation, so it runs
through the job image:

```bash
gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \
  --args=scripts/repair_quarterly_facts.py,--tickers,REGN,--rollback-run,RUN_ID --wait
gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \
  --args=scripts/repair_quarterly_facts.py,--tickers,REGN,--rollback-run,RUN_ID,--apply --wait
```

It compares every row the run wrote with its journaled after-state and refuses the whole company if
any has changed since, so a later write closes the window: a newer filing demoting a row's
`is_latest`, or a relabel moving its year. A restored row's provenance is stored as JSON `null`,
which every reader treats as no record, and it is a target again.

## Re-running

The run is idempotent: a written row carries a version-1 record and is no longer a target, so a
second apply reports `writes: 0` for it. Held rows are counted again on every run and never
written.

## What readers see

- **A passed row** loses its review note in Multi-Period Analysis, and a growth figure built on it
  passes when the figure it is compared with passes too.
- **A concern** keeps a review note, now under its own reason rather than `legacy_calculation`, and
  its `reconciled` flag on the filing page's fundamentals turns false. `calculation_mismatch` has
  no words of its own in either reason map yet (`trend_analysis/data_notes.py`,
  `frontend/features/analysis/lib/provenance.ts`), so it reads the generic note.
- **Every changed dataset** gets a new fingerprint (`trend_analysis/dataset.py`,
  `dataset_fingerprint`), so its narrative is regenerated when next requested, as after the other
  repairs.
- **A held row** stays a legacy calculation, as before.
- **A ratio of an issuer that also reports in another currency** can change which row is current at
  the next companyfacts sync. A ratio with no record never counts as computed from USD operands
  (`facts/currency._usd_derived`); once its record names USD operands it does, so a sync that stores
  the native-currency calculation for the same period demotes it and promotes that one, as #1365
  intended for every ratio with recorded operands. One whose record names native operands can be
  the row such a sync promotes. The `is_latest` change is the sync's, never the backfill's, and, as
  any later write does, it closes that company's rollback window ("Audited rollback"). A USD-only
  issuer is unaffected.

The reconciliation-flag audit (`scripts/audit_reconciliation_flags.py`) can still rewrite a written
row's `reconciled` alone, leaving its provenance.
