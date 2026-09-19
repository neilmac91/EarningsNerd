# E9 current evidence and protection receipt

The [fleet proposal](../../fleet-coordination-proposal-2026-09-19.md) separates database ownership and fleet SEC admission; neither is implemented or activated here.

The founder-approved database protection operation completed. Initial backup `1789845398872`: **SUCCESSFUL**, completed `2026-09-19T19:18:10.104Z`. PITR update completed2026-09-19T19:16:01.014Z; settings receipt shows seven-day PITR, daily16:00 UTC backups, seven retained copies. No restore or history deletion occurred.

Independent detailed health timestamp `1789845779.3615158`: **healthy**, database latency `7.04`ms. Traffic receipt records the same production revision at100%. Operation/settings/backup/health JSONs are primary read results, not inferred from CLI exit codes. A completed backup is not proof of a tested restore.

Current service/job/scheduler settings are in `e9-live-runtime.json`. Measured database max_connections25 and exact missing SELECT error are in [IAM read evidence](iam-read-evidence.md). The bounded [SQL handoff](founder-readonly.sql) requires an existing identity already able to SELECT the job-outcome table; the current IAM login connects but lacks that privilege. No grants or application-secret access were used.
