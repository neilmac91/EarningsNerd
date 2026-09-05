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

The scanner, persistence, API and frontend already exist. The last inspected production deploy
(run 33954400723, job 101275236022, 2026-09-05) printed:

```text
earningsnerd-notable-filings not found — create it once per DEPLOYMENT.md. Skipping.
```

- [ ] Founder: create the Cloud Run job and Scheduler using `docs/DEPLOYMENT.md` §12.
- [ ] Founder: smoke the job and seed `--days 7`; retain execution IDs, times and output counts.
- [ ] Founder: review one full week of subsequent output while serving remains dark; record
  representative accessions, reason accuracy, freshness, diversity and duplicate/noise findings.
- [ ] Founder: record retain/kill and the reviewed dates. A seed is not a week of observation.
- [ ] Engineering: if retained, add `NOTABLE_FILINGS_ENABLED=true` to the service deploy env in
  `.github/workflows/ci.yml`, with the review evidence in its PR. Complete backend and relevant
  frontend gates; merge with a freshly read head SHA, then verify deployment/migrations/health.
- [ ] Engineering: probe the API and homepage after ISR; if killed, leave the slot dark and
  record the decision in todo/dispatch log. No Notable serving flag is changed by this preparation.

## Evidence to retain

| Surface | Production flag evidence | Warm-up / seed execution | Review dates / observations | Flag PR / SHA | Deployment / smoke |
|---|---|---|---|---|---|
| Analysis | Pending founder | Pending prerequisites | Preview pending | Held | Pending |
| Notable | Repository default false; effective service override unconfirmed | Job absent in last inspected deploy | Not started | Held | Pending |

This checklist does not authorize Calendar or Insiders activation. Active residual FPI work
(6-K classifier/golden breadth, post-flip facts backfill, pregeneration job environment) stays in
`tasks/todo.md` and the WS-6/WS-7 briefs; archiving the historical FPI design is not completion
of those residuals.
