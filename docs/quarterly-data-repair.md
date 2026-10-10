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
require an authoritative filing-scoped repair and are outside this tool. New inserts remain
quarterly except for positively identified reported calendar replacements. Deploying the schema does not execute the repair.

## Prepare a bounded cohort

Deploy the provenance schema, journal schema and compatible readers first. Use the repository's
normal migration runner; never manually edit a recorded migration. Retain a database backup and
save the preview JSON with the intended environment, code revision and operator review. Run
against staging first. A production apply is a separate operational action.

The CLI requires explicit tickers, defaults to a maximum of 10, and permits at most 50 per run.
Each company is its own transaction, bounded to 10,000 stored facts. Network reads complete before
the write transaction starts. Companies are serialized with the existing company-row lock used
by the fact writers; modified fact rows are locked as well. Failures are reported per company,
roll back that company's transaction, and cause a nonzero exit code. Earlier successful companies
in the same batch remain committed and can be rolled back independently.

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
rollback adds its own journal entries and references the revisions it reverses.

Reapplication that encounters an identity inserted and subsequently rolled back is deliberately
rejected. This CLI does not reactivate those archived rows: inspect the reason for rollback and
prepare a separately reviewed repair if reactivation is needed. Do not delete audit rows or
financial history to force an upsert. Repeated applies before a rollback remain idempotent.
