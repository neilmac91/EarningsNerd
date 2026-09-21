# Isolated Cloud SQL restore rehearsal

The copied 2026-09-20 [inventory](observations-2026-09-20.json) verifies PostgreSQL 15 instance `earningsnerd-db` in project `earnings-nerd`, seven daily backups, seven days of PITR logs and `deletionProtectionEnabled=false`. A successful backup is not restore evidence. This procedure is prepared; no clone, query, setting change or deletion has been performed.

## Scope and cost gate

Restore to a new, uniquely named instance in the **same project**, e.g. `earningsnerd-restore-drill-YYYYMMDD`, never onto `earningsnerd-db`. Select a UTC PITR timestamp within the verified seven-day window, preferably 15 minutes before drill start and after a known successful backup. Record source instance name, selected timestamp, clone name and project before the operation. Do not route production app traffic, Scheduler, jobs, webhooks or DNS to the clone. Use an existing authorized database reader via Cloud SQL Studio or IAM Auth Proxy; do not export or print `DATABASE_URL` or copy an application password. The clone can inherit users and connectivity, so inspect its network/service-account settings before connecting and keep the target outside every application configuration.

Before creation, read current source tier/edition, region, storage size, backup settings, disk growth and pricing. Define a numeric maximum **all-in USD amount** for clone compute, storage, backup/log side effects and network. Estimate `hourly compute rate × authorized maximum elapsed hours + allocated storage rate × storage GiB × elapsed fraction + backup/network allowance`; include a margin for provision/delete latency. The operator must supply the rates and ceiling from the current billing catalog; this repository has no verified price. Timebox to 4 hours after clone readiness and 6 hours wall-clock including provisioning and deletion. If the upper-bound estimate exceeds the approved ceiling or cannot be computed, stop before cloning. Record who is authorized to delete the clone and any backups it creates; deletion protection on the source must not be changed by this drill.

## Procedure after the production hold is released

1. Read back source settings, available backups and recovery window. Capture start UTC and the exact timestamp to restore. Check the selected timestamp against the actual earliest/latest recovery range; a seven-day setting alone does not prove any arbitrary timestamp is restorable.
2. Check the target name is unused. Run the documented PostgreSQL PITR clone command below with `--project=earnings-nerd`. This creates an independent billable instance. Capture the operation ID, start/finish UTC, result, target instance ID, effective tier/region/storage/network and source unchanged state.
3. Inspect clone settings. Verify no application or Scheduler points to it; connect only with an already authorized read-only identity. Confirm the connection target is the clone, then run [restore-integrity.sql](restore-integrity.sql) as one batch. Keep aggregate counts and the bounded latest-filing sample, not filing contents or user data. `to_regclass` must identify all four expected tables; orphan and missing-identity counts should be zero. A nonzero count needs investigation against source constraints; it is not silently repaired.
4. Run one application-read check against the clone using read-only SQL: the joined latest-filing rows in the integrity batch must return sensible ticker, accession and optional summary IDs. If available, compare a previously retained **stable** accession/summary ID to the clone. Do not call the live app with the clone database or generate summaries. Record SQL elapsed time and clone-ready-to-query duration; no RTO/RPO claim follows from one sample.
5. Record clone operation finish, integrity outcome, selected restore timestamp and lag from drill start, SQL timings, and every limitation. If any step fails, retain error/type and cleanup the clone; a failed rehearsal is a valid result.
6. Delete only the named rehearsal clone and its drill-owned residue under the scoped cleanup authority. Confirm `gcloud sql instances list` no longer contains it and record final elapsed/billing estimate. Do not delete the source or unrelated stopped `earningsnerd` instance. If inherited deletion protection blocks clone deletion, change that setting **on the clone only**, with the same scoped authority, then delete. Do not keep a billable clone because validation failed.

```bash
gcloud sql instances describe earningsnerd-db --project=earnings-nerd \
  --format='json(name,state,region,databaseVersion,settings.tier,settings.dataDiskSizeGb,settings.deletionProtectionEnabled,settings.backupConfiguration)'
gcloud sql backups list --instance=earningsnerd-db --project=earnings-nerd
gcloud sql instances list --project=earnings-nerd --format='table(name,state,region)'
# HELD: substitute the scoped target and verified UTC timestamp only after cost/cleanup authorization.
gcloud sql instances clone earningsnerd-db earningsnerd-restore-drill-YYYYMMDD \
  --point-in-time='YYYY-MM-DDTHH:MM:SSZ' --project=earnings-nerd
gcloud sql instances describe earningsnerd-restore-drill-YYYYMMDD --project=earnings-nerd --format=json
# HELD CLEANUP: this is irreversible and must be scoped to the named drill clone.
gcloud sql instances delete earningsnerd-restore-drill-YYYYMMDD --project=earnings-nerd
```

Use the [Google Cloud PostgreSQL PITR procedure](https://docs.cloud.google.com/sql/docs/postgres/backup-recovery/pitr) and [clone reference](https://docs.cloud.google.com/sdk/gcloud/reference/sql/instances/clone) to cross-check the command at execution time. `gcloud sql instances clone --help` was checked locally on 2026-09-21. The source [E09 read plan](../../review-evidence/fleet-2026-09-19/founder-readonly.sql) still requires an already authorized ledger reader. Do not retry the denied principal as a workaround. Deletion protection and monthly lifecycle-managed export need separate verify/apply-or-de-scope decisions after this drill.

For those separate decisions, read back `settings.deletionProtectionEnabled` (currently false) and inventory existing scheduled export jobs, buckets and lifecycle rules before adding anything. An authorized deletion-protection change would use `gcloud sql instances patch earningsnerd-db --deletion-protection --project=earnings-nerd`, followed by a settings readback and maintenance-window receipt; this command is **not** part of the drill. A monthly export, if retained, needs a verified scheduler, export destination, lifecycle expiry, restore use case, cost ceiling and owner. If it is retired, record an explicit decision; backups/PITR do not silently satisfy that older requirement.
