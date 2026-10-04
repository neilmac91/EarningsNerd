# Production configuration observation — read-only Ops reads (chief, 2026-10-04)

Two `workflow_dispatch` runs of `.github/workflows/ops.yml`, dispatched by the chief as the founder's
GitHub account at 2026-10-04T17:32Z; both read-only `gcloud … describe` operations, both `success`.
Values the workflow withholds stay withheld here; no secret value, env value or egress address was read.

| Operation | Run | Job | Result |
|---|---|---|---|
| `describe-service` | 37220896634 | 111490845621 | success |
| `describe-jobs` | 37220898225 | 111490914263 | success |

## Service (`earningsnerd-backend`, us-west1)

- Serving revision `earningsnerd-backend-00443-n58`, 100 % traffic, latest revision. Image digest
  `sha256:444f06cf88369ae327dc7ec22f945b0d8b2d4c9e7610d6344c3f4937999a3b52`;
  `SENTRY_RELEASE = 100fb7d6bdaf62590af19964d39c2ed732062210` (= main at takeover).
- Service maxScale 2, revision maxScale 2; `containerConcurrency` 40; request timeout 600 s; ingress
  `all`; no VPC connector, no direct-VPC annotation, `vpc-access-egress` unset → dynamic egress IP
  (handback B37 observation; compliance consequence in `DECISIONS-02.md` D8).
- Container command: image default (no override); `WEB_CONCURRENCY` / `UVICORN_WORKERS` not set; no
  gunicorn args → one uvicorn process per instance (`backend/Dockerfile:60`), now observed.
- Plain env confirmed: `REGISTRATION_MODE=invite_only`, `DB_POOL_SIZE=4`, `DB_MAX_OVERFLOW=0`,
  `AI_DEFAULT_MODEL=deepseek-flash`, `OPENAI_BASE_URL=https://api.deepseek.com/v1`, AI gates as in
  `ci.yml:620`; `AI_FALLBACK_MODEL` / `AI_FALLBACK_BASE_URL` not set (Settings default `''`).
- **`SEC_RATE_LIMIT_PER_SECOND` is not set** → code default 10 req/s per process (`config.py:33`);
  **`EDGAR_RATE_LIMIT_PER_SEC` is not set** → edgartools default 9 req/s per process (second bucket).

## Jobs (eight expected Cloud Run jobs)

All eight on image tag `backend:100fb7d`, `taskCount` 1, pools as the workflow requires
(pregenerate 3+0; the other seven 1+0), commands `python scripts/<job>.py` with the expected arguments
(`filing_scan.py` / `--digest`, `backfill_facts.py --only-new`, `earnings_calendar_job.py` /
`--alerts`, `notable_filings_job.py`, `retention_purge.py`, `pregenerate_examples.py`).
**None sets `SEC_RATE_LIMIT_PER_SECOND` or `EDGAR_RATE_LIMIT_PER_SEC`** → 10 + 9 req/s configured per job process.

## Consequences for the operating-envelope handback (next revision owner: CTO)

- B36 refinement: each process holds two independent SEC buckets — the app singleton (10 req/s,
  `SEC_RATE_LIMIT_PER_SECOND`) and edgartools' own (9 req/s, `EDGAR_RATE_LIMIT_PER_SEC`, neither set in
  any deploy) — so the configured sustained ceiling is 19 req/s per process, 190 with every process
  active (2 instances + 8 jobs) and 95 in the Monday 07:00 UTC scheduled overlap (two instances +
  pregenerate + filing-scan + backfill-facts), with a first-second ceiling of 29 per process (the app
  bucket starts full; edgartools' is a sliding window); realised demand remains unmeasured (B39). Only
  lower per-process budgets on both buckets change this (`DECISIONS-02.md` D3).
- B37: egress identity observed as dynamic (no fixed egress); moot for the SEC cap (D8).
- B07/B08: `WEB_CONCURRENCY` and `UVICORN_WORKERS` are not set and the command is the image default, so
  with `backend/Dockerfile:60` (`uvicorn main:app`, no `--workers`) one serving process per instance is
  now observed rather than assumed (the assumptions refuter named `$WEB_CONCURRENCY` as the hidden input;
  uvicorn honours it only when `--workers` is absent). Rollout overlap stays unknown.
- B21: taskCount 1 re-observed today; retries/timeouts not printed by this operation.

## Hygiene observations (not acted on; routed to the existing product owners, no PR opened)

- `ENABLE_GUEST_DAILY_QUOTA` is removed at every deploy (`ci.yml:619`) although no Settings field or
  code reads it (assumptions refuter): dead deploy config for the owner of the next `ci.yml` change.
- The service still carries env entries for integrations torn down in #657 (names withheld here per
  `DECISIONS-02.md` D5; visible in the Ops run above); removal is a deploy-config change for the next
  backend PR by its owner, not for this session.
- The `notable-filings` job sets neither `EDGAR_IDENTITY` nor `SEC_EDGAR_BASE_URL`; it falls back to
  the compliant default identity in `backend/app/services/edgar/config.py:16`. Compliant; worth
  aligning with the other SEC-calling jobs when that job is next touched.
