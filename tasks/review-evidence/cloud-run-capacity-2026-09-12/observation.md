# Production capacity observation — September 12, 2026

Read-only inspection of the authenticated Google Cloud console in project `earnings-nerd`, service `earningsnerd-backend`, region `us-west1`. No values were entered, saved or deployed. The service configuration tour was dismissed and revision-scaling controls expanded for inspection. Browser extension interactions timed out; native Chrome accessibility controls completed the reads.

The Revision History page shows `earningsnerd-backend-00333-56s` receiving **100% (to latest)**. Its predecessor `00332-p9k` receives 0%. This independently agrees with the #823 deploy record. The Containers page shows image tag `backend:d2c176f`.

| Setting | Observed value |
| --- | --- |
| Service scaling | Automatic; minimum 0, maximum 20 |
| Revision scaling overrides | Minimum 1, maximum 2 |
| Billing | Instance-based; CPU available throughout instance lifetime |
| CPU / memory | 1 vCPU / 1 GiB |
| Request timeout / concurrency | 600 seconds / 40 requests per instance |
| Database pool / overflow | 12 / 8 |
| Startup CPU boost | Enabled |
| Outbound VPC connection | Unchecked |
| Ingress | All |

The revision limits agree with the repository's deployment settings; the separate service-level limits must not be reported as identical to those revision overrides. With one serving revision, a simple two-instance, one-process-per-instance pool calculation is 40 potential database connections (2 × (12 + 8)); this excludes jobs, old revisions and other services and is not measured database headroom.

The overview also listed another service, `earningsnerd` in `us-central1`, with a displayed instance-count legend value of 1. Its ownership, purpose, traffic, configuration and costs were not inspected. It must be included in fleet reconciliation before any capacity or cost conclusion; no deletion is proposed from this observation alone.

Recent service charts showed CPU utilization values up to 18.92% and memory utilization up to 32.99% in the displayed prior-day window. These aggregate chart ranges are not a load test, a peak-demand guarantee or proof of sufficient fleet capacity. Job parallelism/task limits, scheduler overlap, database headroom, outbound IP identity, and budget remain to be reconciled. An unchecked outbound VPC control does not establish a stable shared egress IP.

The EarningsNerd website's account menu also confirmed the existing admin session. No credential entry or live account test was needed. No authentication URLs or credentials are retained here.

Next: fold these observations into the E09 proposal and reconcile the remaining fleet before requesting any activation/capacity/budget change. Universe-wide pregeneration and historical replay remain held on the founder's quality condition.
