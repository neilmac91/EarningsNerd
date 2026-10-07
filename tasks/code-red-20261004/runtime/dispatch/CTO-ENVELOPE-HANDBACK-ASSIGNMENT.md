# CTO assignment — current-beta operating-envelope handback (dispatch `CTO-ENVELOPE-HANDBACK-01`)

Issued by the chief/CEO (session `01GWYV7WXWstgVGQG43YcSM8`) on 2026-10-04 under
`control/CEO-DIRECTIVE.md` ("CTO: … Own … required current-cohort E09 input to the COO") and the COO's
`FIRST-DELIVERABLE.md` section "C1 — one capacity admission, still HOLD", which names this handback as
the next owner action. Manifest: `dispatch/CTO-ENVELOPE-HANDBACK-01.json` (input hashes, stop
conditions, USD 0). This is engineering management support for wave R3. It is not R5, not E09
implementation, not a capacity admission and not cohort entry authority.

## Role and boundaries

You are the single CTO-designated author of this handback. You are an engineering/management context:
excluded from source A/B authorship, source reconciliation, semantic financial review and blind
financial judging; you never open source packets, candidate outputs, judge material, customer data,
credentials or private participant records. No code change, test run, server, container, `git`
command, `gcloud`/`gh`/network call, production or Cloud Console read, provider call, measurement,
load or job is permitted. Passive repository reads at main `100fb7d6bdaf62590af19964d39c2ed732062210`
are the only new evidence you may gather; everything else is reused from the inputs in the manifest.
Record what you could not observe as **unknown**; never fill it with a default, an inference from light
HTTP traffic, or a number taken from the four-slot arithmetic (`25 − 3 − 18 = 4`) or the 110/120-second
request controls.

## The five required components (verbatim from the COO)

1. Effective service-instance/worker/engine/pool and simultaneous job-execution bounds, including
   rollout overlap and other clients; distinguish observed, configured, assumed and unknown.
2. An evidenced DB operating reserve and connection/latency/cleanup/wait allowance that covers the
   proposed current-beta useful workload. Do not choose policy numbers from the four-slot arithmetic or
   110/120-second existing request controls.
3. Effective aggregate SEC egress/rate/burst/headroom and provider
   concurrency/recovery/chat/queue/retry/cancellation bounds, their enforcement scope and unresolved
   uncertainty. Process-local settings are insufficient fleet evidence.
4. Proposed current-beta demand envelope and stop/rollback conditions supported by retained
   useful-work evidence and recorded policy, with CFO/CEO provenance for provider spend authority. The
   shared USD15 ceiling alone is not concurrency, capacity or runtime-budget admission.
5. A specific determination whether existing controls demonstrably suffice or a named E09 subset is
   necessary for current-beta safety. If a subset is necessary, preserve its existing
   implementation/policy decision; give evidence and exact missing decision. Do not preselect a fleet
   build, assume egress identity is a prerequisite for separate Slice A ownership, or treat dormant
   code as exempt from the hold.

## Evidence classification rules

Every bound you state carries exactly one classification and one evidence identity:

| Class | Meaning | Acceptable evidence |
|---|---|---|
| `observed` | Measured in production/retained observation | COO FIRST-DELIVERABLE C1 bullets (dated windows, SQL snapshot), package documents; cite section |
| `configured-deploy` | Set by the deploy workflow / Cloud Run flags / job env | `.github/workflows/ci.yml` deploy block, `ops.yml`, `docs/DEPLOYMENT.md`; cite `file:line` |
| `configured-code-default` | Code/Settings default that production may override | `backend/app/config.py`, `backend/app/database.py`, service modules; cite `file:line`; say whether the deploy overrides it |
| `assumed` | A stated modelling assumption | state it as such and why |
| `unknown` | Not observable from this session | say what observation would establish it and who can make it |

Byte limits, connection counts, request/second rates, seconds and token counts are different units;
never interchange them. Process-local limits (semaphores, token buckets, in-flight dedup, L1 caches)
are per process: the fleet bound is the sum over serving processes and concurrently executing jobs,
and only if the per-instance process count is known. Say explicitly whether the SEC limiter, the
generation semaphore, chat admission and the in-flight dedup are process-local, and what that implies
when two service instances and one or more jobs run at once.

## Where to look (pointers, not a complete list; verify each before citing)

- Cloud Run sizing and job env: `.github/workflows/ci.yml` deploy step (`--cpu --memory --min-instances
  --max --max-instances --concurrency --timeout`, `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` for the service,
  pregenerate and the seven other jobs; the comment on the 18-connection budget and Cloud Run briefly
  exceeding a maximum), `.github/workflows/ops.yml`, `docs/DEPLOYMENT.md` (Cloud SQL tier, job
  creation/schedules, connection budgeting guidance), `backend/Dockerfile` (uvicorn workers per
  instance).
- Database engine and pool: `backend/app/database.py` (pool size/overflow defaults, `pool_timeout`,
  `pool_recycle`, pre-ping, connector); `backend/app/config.py` (`USAGE_COUNTER_LOCK_TIMEOUT_MS`,
  `STARTUP_SCHEMA_DEADLINE_SECONDS`, `USAGE_RESERVATION_TTL_SECONDS`); E03 connection release before AI
  waits (`app/services/summary_pipeline.py`, health endpoints); request timeout middleware
  (`docs/OPERATIONS.md` "Request Timeout Configuration"); `docs/OPERATIONS.md` "Performance Tuning",
  "Monitoring Alerts", saturation visibility (E12) and `/metrics` fields.
- SEC: `backend/app/services/sec_rate_limiter.py` and `SEC_RATE_LIMIT_PER_SECOND`
  (`docs/CONFIGURATION.md`), breaker coverage (`lessons/sec-edgar-resilience-layer.md`,
  `app/services/edgar/`), job schedules that generate SEC traffic (filing-scan, backfill-facts,
  calendar refresh, pregenerate), egress identity (NAT/static IP: find evidence or mark unknown).
- Provider: `MAX_CONCURRENT_GENERATIONS`, `RECOVERY_MAX_CONCURRENCY`, `AI_CHAT_MAX_INFLIGHT`
  (`backend/app/config.py`), in-flight dedup and generation ownership (`app/services/summary_pipeline.py`,
  `generate_summary_background`), cancellation/drain on client disconnect (`docs/DEPLOYMENT.md` around
  the "Timeout/disconnect cancels and drains" note), provider retry/backoff (`app/services/ai/`,
  `openai_service.py`), metering at provider start and refund rules (PR1069, `tasks/todo.md` 2026-10-02
  entry), usage reservations (E07).
- Fleet/E09 history and holds: `tasks/fleet-coordination-proposal-2026-09-19.md`,
  `tasks/e09-fleet-coordination-proposal-2026-09-08.md`, `tasks/e09-proposal-next-2026-09-13.md`,
  `ops/capacity/readout.py` and `ops/capacity/snapshot.sql` (what the retained read-only receipts can
  and cannot show), `tasks/readiness-2026-09-21/beta/` (readout and support files only; do not open
  anything under `tasks/readiness-2026-09-21/acceptance/`).
- Retained production observations: COO FIRST-DELIVERABLE C1 bullets only (max_connections 25,
  superuser_reserved 3, reserved null, six client backends including the observer; 29 HTTP 200s in the
  Oct 3 19:45–20:00 UTC window; Oct 4 02:30–04:30 UTC window with 318 requests and three one-task
  executions, 11.657177 s execution overlap, no DB sample inside it; non-overlapping recorded business
  phases). These are light-traffic observations: they establish neither spare capacity nor a safe
  participant count. Say so.
- Spend-authority provenance for component 4: CFO FIRST-DELIVERABLE (shared USD 15 future DeepSeek
  authority; USD 12.570771 conditionally unreserved as of the snapshot; not concurrency or runtime
  admission) and the chief's `control/LEDGER-ACCESS.md` (live ledger inaccessible; paid dispatch held).
  Do not propose spending; record provenance and the HOLD.

## Deliverables (write exactly these two files; no other writes)

1. `tasks/code-red-20261004/runtime/handbacks/cto/envelope/CURRENT-BETA-OPERATING-ENVELOPE-HANDBACK.md`
   Sections, in order: (0) identity, dispatch id, inputs read with SHA-256 for package inputs and
   `path:line` for repository reads, observation date, limits of what was read; (1)–(5) one section per
   component, each with a table whose columns are bound · value and unit · classification ·
   enforcement scope · evidence · uncertainty/implication; (6) determination for component 5 with the
   evidence chain, the exact missing decision if a subset is necessary, and what remains the founder's
   retained E09 decision; (7) limitations and unknowns, each with the observation that would resolve it
   and the owner who can make it; (8) return contract: counts unchanged (3/30 dossiers, 0/2 readouts,
   5 reporting groups + 1 capacity decision), zero new calls/spend/reservations/external mutations,
   next owner (COO disposition worker) and stop condition. Target length: what the content needs, no
   padding; prefer tables to prose.
2. `tasks/code-red-20261004/runtime/handbacks/cto/envelope/CURRENT-BETA-OPERATING-ENVELOPE-BOUNDS.json`
   `{"schema_version":1,"dispatch_id":"CTO-ENVELOPE-HANDBACK-01","observed_at":<UTC>,"repository_commit":"100fb7d6…","bounds":[{"id":"B01","component":1..5,"bound":"…","value":<number|string|null>,"unit":"…","classification":"observed|configured-deploy|configured-code-default|assumed|unknown","enforcement_scope":"process|instance|service|fleet|external","evidence":"…","uncertainty":"…"}],"determination":{"existing_controls_suffice":true|false|"undetermined","necessary_e09_subset":null|"…","missing_decision":null|"…","evidence_ids":[…]},"spend":{"new_calls":0,"new_spend_usd":"0.000000","reservations":0},"external_mutations":0}`.
   Every bound in the Markdown appears here with the same id and classification. `null` means unknown,
   never zero.

## Pass, fail and stop

Pass: all five components covered; every bound classified and evidenced; process-local versus fleet
scope explicit; the light-traffic observations are not promoted to capacity; the determination follows
from cited evidence; the two files agree. Fail: any invented value, default silently presented as
production, policy number derived from the forbidden arithmetic, fleet claim from a process-local
setting, E09 build preselected, dormant code treated as exempt, or a read outside the allowed scope.
Stop immediately and report the exact dependency if the task would require a production read, a
measurement, code, source material or a spend action.

Return to the chief (as your final message, not in the files): the two output paths with SHA-256,
pass/incomplete, the determination in one sentence, the list of unknowns, and confirmation of zero
calls/spend/mutations.
