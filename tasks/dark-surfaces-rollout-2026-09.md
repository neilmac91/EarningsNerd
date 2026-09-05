# Dark-surface rollout — September 2026 (D3)

Status: engineering preparation; production flips are held at the stated prerequisites.
Owner: chief engineer; founder executes console, job setup and spend actions.
Accepted decision: Analysis on after prerequisites; Notable after a week of job output;
Calendar off until the Alpha Vantage licence decision; Insiders off.

## Analysis

- [ ] Founder: record the effective production Vercel `NEXT_PUBLIC_ENABLE_ANALYSIS` value
  and deployment identifier. `frontend/vercel.json` does not currently set it; source defaults
  to false in `frontend/lib/featureFlags.ts`. The repository cannot establish a console value.
- [ ] Engineering: prepare the committed universe cohort after WS-7 Company seeding and SIC
  prerequisites. `scripts/sync_companyfacts.py` accepts `--tickers`, `--watchlist-only`, `--limit`
  and `--force`; default scans stored companies, so it does not prove coverage of missing members.
- [ ] Founder: execute companyfacts warm-up on the backfill job; retain the execution identifier,
  exact cohort, success/error counts, and remaining gaps. Do not infer success from process exit
  alone: `sync_companyfacts_batch` returns counters and the wrapper logs them.
- [ ] Engineering: after confirmed flag state and warmed universe evidence, add
  `NEXT_PUBLIC_ENABLE_ANALYSIS=true` to `frontend/vercel.json` in a reviewed flag PR.
  Run full frontend gates and Playwright with no backend; verify the resulting preview in
  light/dark themes and production Analysis with a Pro account after deployment.

## Notable filings

The scanner, persistence, API and frontend already exist. W3-1 observed the serving flag
absent on the verified #704 image, whose default is false. W3-2 explicitly pins
`NOTABLE_FILINGS_ENABLED=false` in the service and pregenerate deploy env; merge/deployment
verification remains pending at this source checkpoint. Activation prerequisites are unchanged. The earlier production observation
(run 33954400723, job 101275236022, 2026-09-05) printed the message below. Latest verified
[#704 deployment](https://github.com/neilmac91/EarningsNerd/actions/runs/33988401306), job
101366418068, still reports the job absent; it has not been created by this programme:

```text
earningsnerd-notable-filings not found — create it once per DEPLOYMENT.md. Skipping.
```

- [ ] Founder: create the Cloud Run job and Scheduler using `docs/DEPLOYMENT.md` §12.
- [ ] Founder: smoke the job and seed `--days 7`; retain execution IDs, times and output counts.
- [ ] Founder: review one full week of subsequent output while serving remains dark; record
  representative accessions, reason accuracy, freshness, diversity and duplicate/noise findings.
- [ ] Founder: record retain/kill and the reviewed dates. A seed is not a week of observation.
- [ ] Engineering: if retained, add `NOTABLE_FILINGS_ENABLED=true` to the service deploy env in
  `.github/workflows/ci.yml`, with the review evidence in a PR that also contains an independently
  required `backend/` change. The current deploy filter skips workflow/docs-only pushes; if no
  backend change is ready, hold the flip. Complete backend and relevant
  frontend gates; merge with a freshly read head SHA, then verify that the service deployment
  step actually ran, the migration summary, and detailed health.
- [ ] Engineering: probe the API and homepage after ISR; if killed, leave the slot dark and
  record the decision in todo/dispatch log. No Notable serving flag is changed by this preparation.

## Evidence to retain

| Surface | Production flag evidence | Warm-up / seed execution | Review dates / observations | Flag PR / SHA | Deployment / smoke |
|---|---|---|---|---|---|
| Analysis | Pending founder | Pending prerequisites | Preview pending | Held | Pending |
| Notable | W3-1 verified image default false; W3-2 explicit false pin awaiting deployment | Job absent in last inspected deploy | Not started | Held | Pending |

The founder-approved calendar universe filter is service=true / pregenerate=false; W3-2
records this existing override explicitly. This checklist does not authorize Calendar UI or
Insiders activation. Active residual FPI work
(6-K classifier/golden breadth and founder data backfill) stays in
`tasks/todo.md` and the WS-6/WS-7 briefs; archiving the historical FPI design is not completion
of those residuals.

Pregenerate FPI/10-Q job environment shipped in #697; this does not prove actual founder
generation. See the [consolidated founder interfaces](handover-wave2-2026-09.md#6-founder-only-items-outstanding-do-not-do-these-yourself-keep-them-visible).
