# CTO handback — current-beta operating envelope (dispatch `CTO-ENVELOPE-HANDBACK-01`)

Observed 2026-10-04T15:20:16Z (revision 3: revision 2 corrected three unrendered placeholder fields reported by the COO worker, `CORRECTION-01.md`; revision 3 corrects four imprecise anchors and one attribution reported by the independent PR reviewer, `CORRECTION-02.md`). Repository commit `100fb7d6bdaf62590af19964d39c2ed732062210` (main). This is the named
CTO handback the COO's first deliverable requires before its C1 capacity disposition. It records
bounds and evidence; it is not a capacity admission, a safe participant count, an E09 implementation
decision, a release or cohort-entry authority.

## 0. Identity, inputs and limits of this handback

- **Author:** the receiving Fable chief (session `01GWYV7WXWstgVGQG43YcSM8`, runtime-reported model
  `claude-fable-5-1`) acting as CTO under `control/CEO-DIRECTIVE.md`. **Isolation limitation:** the
  dispatch manifest requested an isolated author plus three independent adversarial lenses; the
  platform's auto-mode classifier denied that workflow launch, so this handback was authored in the
  chief context from first-hand repository reads and **no isolated adversarial review ran**. Every
  `file:line` anchor below was resolved programmatically against the checked-out commit at
  generation time (a missing anchor aborts generation); the interpretation of each value is the
  author's and has not been independently refuted. The COO disposition should treat `assumed` and
  derived rows accordingly.
- **Dispatch manifest:** `dispatch/CTO-ENVELOPE-HANDBACK-01.json`, SHA-256 `681a3526575f4e6e5abddde2f788d48215579d2467e59d81d6c20852ac41f58d` (lists every
  package input with its SHA-256; all verified at dispatch time).
- **Package inputs used:** COO FIRST-DELIVERABLE (`c8277395…`, C1 section), CTO FIRST-DELIVERABLE
  (`bdca249d…`), CEO-DIRECTIVE (`5008dbbc…`), CHIEF-TRANSFER-POLICY (`c6b8dc3a…`), WAVE-REGISTER
  (`55a602df…`), HANDBACK-CONTRACT (`cc4d5b74…`), MASTERPLAN-REVIEW (`0c946f93…`), CFO FIRST-DELIVERABLE
  (`925fcc6b…`, spend provenance only), `control/LEDGER-ACCESS.md`, `control/REPOSITORY-SNAPSHOT.json`.
- **Repository reads (read-only):** `.github/workflows/ci.yml` (deploy block), `.github/workflows/ops.yml`
  (operation list, capacity-readout step), `backend/Dockerfile`, `backend/main.py` (timeout table),
  `backend/app/config.py`, `backend/app/database.py`, `backend/app/services/sec_rate_limiter.py`,
  `backend/app/services/summary_pipeline.py` (control constants and docstrings),
  `backend/app/services/ai/provider_requests.py`, `provider_admission.py`, `section_recovery.py`,
  `backend/app/services/openai_service.py` (client construction), `backend/app/services/edgar/config.py`,
  `backend/app/services/entitlements.py`, `backend/scripts/pregenerate_examples.py`,
  `ops/capacity/readout.py`, `ops/capacity/snapshot.sql`, `docs/OPERATIONS.md`, `docs/DEPLOYMENT.md`
  (sections cited; two job-schedule sections were not re-read after a classifier denial and are cited
  from an earlier line-level search only), `tasks/fleet-coordination-proposal-2026-09-19.md`,
  `lessons/sec-edgar-resilience-layer.md`, `tasks/todo.md` (2026-10-02 entry).
- **Not read, by rule:** anything under `tasks/readiness-2026-09-21/acceptance/`, source packets,
  candidate outputs, customer or participant data, credentials. **No** production, Cloud Console,
  gcloud, network, provider or GitHub call; no test, server, code change or git command.
- **Classification key:** `observed` (dated retained observation) · `configured-deploy` (deploy
  workflow / Cloud Run flags / job env) · `configured-code-default` (code, Settings or image default;
  production-effective unless the row says the deploy overrides it) · `assumed` (stated modelling
  assumption or arithmetic on cited values) · `unknown` (not observable from here; the row names the
  resolving observation and owner). Byte, connection, request-rate, second and token units are never
  interchanged. Process-local limits are per process; fleet figures are sums over serving processes
  and concurrently executing jobs and are marked `assumed`.

## 1. Service, worker, engine, pool and job-execution bounds

| ID | Bound | Value (unit) | Class | Scope | Evidence | Uncertainty / implication |
|---|---|---|---|---|---|---|
| B01 | Cloud Run service vCPU per instance | 1 (vCPU) | `configured-deploy` | instance | `.github/workflows/ci.yml:616` (`--cpu=1 --cpu-boost`); mirrored `docs/DEPLOYMENT.md:201` | Re-asserted on every backend deploy; current live value not re-read from Cloud Run here. |
| B02 | Cloud Run memory per instance | 1 (GiB) | `configured-deploy` | instance | `.github/workflows/ci.yml:616` (`--memory=1Gi`) | As B01. |
| B03 | Cloud Run minimum instances | 1 (instances) | `configured-deploy` | service | `.github/workflows/ci.yml:617` (`--min-instances=1`) | One warm instance; per-process caches survive between requests. |
| B04 | Cloud Run maximum instances (service-level and per-revision) | 2 (instances) | `configured-deploy` | service | `.github/workflows/ci.yml:617` (`--max=2 --max-instances=2`); `.github/workflows/ci.yml:612` (comment) | Cloud Run can briefly exceed a configured maximum during scaling/rollout (vendor behaviour recorded in the workflow comment; magnitude unknown). Jobs are outside this limit. |
| B05 | HTTP request concurrency per instance | 40 (requests) | `configured-deploy` | instance | `.github/workflows/ci.yml:617` (`--concurrency=40`) | Upper bound on simultaneous requests per instance; generation concurrency is bounded separately (B41). |
| B06 | Cloud Run request timeout / stream timeout | 600 (seconds) | `configured-deploy` | instance | `.github/workflows/ci.yml:617` (`--timeout=600`); `STREAM_TIMEOUT` `backend/app/config.py:546` | Streaming endpoints are excluded from the application timeout middleware (B27); the platform timeout is the outer bound. |
| B07 | Serving processes per instance | 1 (processes) | `configured-code-default` | instance | `backend/Dockerfile:60` (`uvicorn main:app` without `--workers`); tasks/fleet-coordination-proposal-2026-09-19.md:26 (no container command/argument override returned in the 2026-09-19 live read) | Current live container command not re-read from Cloud Run; treated as one process per instance. |
| B08 | Fleet serving processes (steady / rollout) | steady_max=2; rollout_overlap_extra=unknown (processes) | `assumed` | fleet | Derived: B04 × B07. Rollout overlap: a draining revision's instances add processes for an unknown interval (ci.yml comment at B04). | Overlap count and duration unknown; no observation in allowed inputs. |
| B09 | SQLAlchemy engines per process | 1 (engine) | `configured-code-default` | process | `backend/app/database.py:32`–39 (module-level `create_engine`, PostgreSQL branch); tasks/fleet-coordination-proposal-2026-09-19.md:25 | One sync engine per importing process (API instance or job). |
| B10 | Service DB pool per process (pool_size / max_overflow) | pool_size=4; max_overflow=0; max_connections_per_process=4 (connections) | `configured-deploy` | process | `.github/workflows/ci.yml:620` (`DB_POOL_SIZE=4,DB_MAX_OVERFLOW=0`) overrides image ENV 5/5 (`backend/Dockerfile:45`–46) and code defaults 20/10 (`backend/app/database.py:12`–13) | Production-effective values are the deploy values. Local/ad-hoc runs of the same code use 20/10 unless the environment sets them. |
| B11 | Pool checkout wait before fail-fast | 10 (seconds) | `configured-code-default` | process | `backend/app/database.py:22` (`DB_POOL_TIMEOUT` default 10; not set by deploy `.github/workflows/ci.yml:620` or image ENV) | Effective 10 s unless a runtime env override exists (none in the workflow). Saturation surfaces as a fast error, not a hang. |
| B12 | Pool connection recycle | 1800 (seconds) | `configured-code-default` | process | `backend/Dockerfile:47` (image ENV 1800) overriding code default 3600 (`backend/app/database.py:15`); deploy does not set it | Effective 1800 s assuming no runtime override. |
| B13 | DB connect timeout / pre-ping | connect_timeout_seconds=10; pool_pre_ping=yes (seconds / flag) | `configured-code-default` | process | `backend/Dockerfile:48`; `backend/app/database.py:17`; `pool_pre_ping=True` `backend/app/database.py:32`–39 (PostgreSQL branch) | — |
| B14 | Cloud Run jobs: count and per-process pools | jobs=8; pregenerate_pool=3; pregenerate_overflow=0; other_seven_pool=1; other_seven_overflow=0 (connections) | `configured-deploy` | job process | `.github/workflows/ci.yml:637` (pregenerate `DB_POOL_SIZE=3`); `.github/workflows/ci.yml:651` (six jobs `DB_POOL_SIZE=1`); backfill-facts same values in its own step | Env is re-asserted only for jobs that exist (CI skips missing jobs); operator `--args` overrides are outside this source audit. |
| B15 | Configured maximum application DB demand (2 instances + pregenerate + one execution of each other job) | 18 (connections) | `configured-deploy` | fleet | `.github/workflows/ci.yml:609` (comment: 2×4 + 3 + 7×1 = 18); `docs/DEPLOYMENT.md:664` | Excludes rollout-overlap instances (+4 each), repeated concurrent executions of one job, and non-application clients (Ops proxy sessions, Cloud SQL Studio, monthly export, observers). This is configured demand, not measured load. |
| B16 | Cloud SQL tier | bootstrap=db-g1-small; current=unknown (tier) | `configured-deploy` | external | `docs/DEPLOYMENT.md:157` (bootstrap runbook) | Current tier not verified from this session (no cloud read). |
| B17 | PostgreSQL max_connections | 25 (connections) | `observed` | external | COO FIRST-DELIVERABLE §“C1 — one capacity admission, still HOLD” (package `c8277395…`) (read-only SQL snapshot 2026-10-04 07:02:47 UTC); also measured 2026-09-19 (tasks/fleet-coordination-proposal-2026-09-19.md:28) | Observed value; not a reserve policy. |
| B18 | superuser_reserved_connections / reserved_connections | superuser_reserved_connections=3; reserved_connections=unknown (connections) | `observed` | external | COO FIRST-DELIVERABLE §“C1 — one capacity admission, still HOLD” (package `c8277395…`) (same snapshot; `reserved_connections=null`) | Null is unknown, not zero. |
| B19 | Usable non-superuser connections | 22 (connections) | `assumed` | external | Arithmetic on B17 − B18 (25 − 3). Not an operating reserve and not a policy number. | Any non-null `reserved_connections` would lower it. |
| B20 | Client backends observed at the snapshot | 6 (backends) | `observed` | external | COO FIRST-DELIVERABLE §“C1 — one capacity admission, still HOLD” (package `c8277395…`) (six client backends including the observer, 2026-10-04 07:02:47 UTC) | A single light-traffic instant; not a peak and not evidence of spare capacity. |
| B21 | Job task configuration (taskCount / maxRetries / timeout) | taskCount=1; maxRetries=3; timeout_seconds_range=900–3600; parallelism=unknown (tasks / retries / seconds) | `observed` | job | tasks/fleet-coordination-proposal-2026-09-19.md:27 (live inventory 2026-09-19) | Dated observation; parallelism omitted in that listing (not zero); current values not re-read. |
| B22 | Simultaneous job executions | observed_overlap_seconds=11.657177; same_job_concurrent_executions=unknown (seconds) | `observed` | fleet | COO FIRST-DELIVERABLE §“C1 — one capacity admission, still HOLD” (package `c8277395…`) (two execution lifetimes overlapped in the 2026-10-04 02:30–04:30 UTC window; recorded business phases did not overlap, 0.694726 s gap) | Whether one job can run two executions concurrently (Scheduler re-trigger while running) is unknown; no DB sample lies inside the observed overlap. |
| B23 | Job schedules (SEC- and DB-relevant) | pregenerate=Mon 06:00 UTC; filing-scan=hourly 0 * * * *; filing-digest=daily 08:00 UTC; backfill-facts=runbook: Mon 07:00 UTC; 2026-09-19 inventory: unscheduled; earnings-calendar-refresh=daily 05:30 America/New_York; earnings-day-alerts=daily 06:00 America/New_York; retention-purge=Sun 03:00 UTC; notable-filings=08:30 and 18:30 America/New_York per docs/DEPLOYMENT.md:623–624 as reported by the independent PR reviewer; not read by the chief (classifier denial) (cron) | `configured-deploy` | external | `docs/DEPLOYMENT.md:222`, `:275`, `:280`, `:285`, `:344`, `:351`, `:381` (runbook); `docs/OPERATIONS.md:93` (Monday 06:00–07:00 UTC overlap of pregenerate, filing-scan and backfill-facts with the service); tasks/fleet-coordination-proposal-2026-09-19.md:27 | Runbook values are creation-time commands, not a live Scheduler read; backfill-facts scheduling conflicts between sources → unknown; notable-filings schedule not read by the chief; the independent reviewer reports it from docs/DEPLOYMENT.md:623–624 (recorded with that attribution, not verified here). |
| B24 | Default worker-thread limiter per event loop (shared by health probes and summary DB units) | 40 (threads) | `assumed` | process | `docs/OPERATIONS.md:75` (anyio default limiter; the documented numbers are illustrative) | Library default assumed; not observed. |
| B25 | EDGAR thread pool per process / EDGAR default timeout | threads=4; default_timeout_seconds=15.0 (threads / seconds) | `configured-code-default` | process | `backend/app/services/edgar/config.py:167`–169 | Env-overridable; deploy does not set them. |

**Reading of component 1.** Steady state is two single-process instances (B04, B07), each holding
at most 4 database connections (B10), plus up to eight job processes with pools of 3 or 1 (B14). The
configured application maximum is 18 connections (B15) against 22 usable (B19); one draining revision
instance during a rollout adds 4 and reaches 22 with nothing left for Ops proxy sessions, Studio or
observers. This is configured arithmetic, not an operating reserve (component 2). Job overlap is
observed to happen (B22); whether the same job can overlap itself is unknown.

## 2. Database operating reserve and connection / latency / cleanup / wait allowance

| ID | Bound | Value (unit) | Class | Scope | Evidence | Uncertainty / implication |
|---|---|---|---|---|---|---|
| B26 | Request-level timeouts by path | /api/summaries/=120; /api/filings/=60; /health=5; default=30; */insiders=75; streaming_and_progress=excluded (seconds) | `configured-code-default` | process | `backend/main.py:330`–344; `docs/OPERATIONS.md:315` | Recorded as existing controls only; not used to derive any reserve or policy. |
| B27 | Pipeline backstop timeout / follower wait cap | pipeline_timeout_seconds=120; follower_wait_cap_seconds=110; context_enrichment_timeout_seconds=18 (seconds) | `configured-code-default` | process | `backend/app/services/summary_pipeline.py:353`; `backend/app/services/summary_pipeline.py:91`; `backend/app/services/summary_pipeline.py:359` | Back-pressure: excess generations queue on the semaphore inside this timeout (`backend/app/services/summary_pipeline.py:673`). Not used to choose policy numbers. |
| B28 | Provider budgets (summary / attempt / attempts / recovery) | summary_budget_seconds=75; attempt_cap_seconds=45; max_summary_attempts=3; recovery_attempt_timeout_seconds=12 (seconds / attempts) | `configured-code-default` | process | `backend/app/services/ai/provider_requests.py:22`–24; `backend/app/services/ai/section_recovery.py:122`; `docs/DEPLOYMENT.md:762` | — |
| B29 | DB session released before admission/provider waits (E03) | yes (design property) | `configured-code-default` | process | `backend/app/services/summary_pipeline.py:384` (docstring: router releases its session before streaming; no ORM result survives into an admission or provider wait); MASTERPLAN-REVIEW E03 “delivered and subsequently strengthened” | A design property of the code path, not a load-tested measurement; connection hold time per DB unit is not measured here. |
| B30 | Transactional lock waits (usage counters) / reservation TTL | usage_counter_lock_timeout_ms=3000; usage_reservation_ttl_seconds=300 (ms / seconds) | `configured-code-default` | process | `backend/app/config.py:464`; `backend/app/config.py:473` | Per-transaction waits, not total deadlines. |
| B31 | Startup schema deadline / additive DDL lock timeout | startup_schema_deadline_seconds=60; additive_lock_timeout_ms=5000 (seconds / ms) | `configured-code-default` | process | `backend/app/config.py:469`; `backend/app/database.py:59` | Startup only; a start that exceeds the deadline fails fast so Cloud Run keeps the last healthy revision. |
| B32 | DB operating reserve and wait/cleanup allowance under concurrent useful generation | unknown (connections / seconds) | `unknown` | fleet | No retained observation ties pool `checked_out`, waits or pool-timeout log signatures to a window with concurrent generation; the COO windows carried light HTTP traffic and single-task jobs (COO FIRST-DELIVERABLE §“C1 — one capacity admission, still HOLD” (package `c8277395…`)); no DB sample lies inside the 11.66 s job overlap (B22). | Resolving observation: one bounded read-only Ops `capacity-readout` run (`.github/workflows/ops.yml:477`–483; ≤2 h window per `ops/capacity/readout.py:38`) over a window that contains actual concurrent generation, such as the Monday 06:00–07:00 UTC job-overlap window, reporting backend counts by state, the job ledger and the pool-timeout log signature (`ops/capacity/readout.py:128`). Owner: COO/CEO decision; not dispatched by this handback; no new load. |
| B33 | Pool-saturation failure mode and alert thresholds | behaviour=fail-fast after 10 s wait; documented_warning=checked_out > 8; documented_critical=checked_out = pool_size (—) | `configured-code-default` | process | B11; `docs/OPERATIONS.md:305`–313 | The documented warning threshold (> 8) is unreachable with pool 4 / overflow 0; only the critical threshold (= 4) can fire. Docs-vs-config inconsistency; code/deploy are truth (fix the doc separately). |

**Reading of component 2.** The code bounds how long a request can hold or wait for a connection
(B11, B26–B31) and releases sessions before provider waits (B29). None of this measures the reserve
under the proposed current-beta workload: **the operating reserve is unknown (B32)**. The four-slot
nominal margin and the 110/120-second controls are recorded as facts and deliberately not converted
into a policy number. The smallest permitted next observation is one bounded read-only Ops
`capacity-readout` over a window that actually contains concurrent generation; it is named, not
dispatched.

## 3. Aggregate SEC and provider bounds

| ID | Bound | Value (unit) | Class | Scope | Evidence | Uncertainty / implication |
|---|---|---|---|---|---|---|
| B34 | SEC per-process token bucket / retries / backoff / Retry-After cap | requests_per_second=10; max_retries=5; base_backoff_seconds=1.0; max_retry_after_seconds=120 (req/s / retries / seconds) | `configured-code-default` | process | `backend/app/config.py:33`–35; `backend/app/services/sec_rate_limiter.py:57`; `backend/app/services/sec_rate_limiter.py:29` | Deploy does not override `SEC_RATE_LIMIT_PER_SECOND`; every process (instance or job) carries its own full bucket. |
| B35 | SEC external cap | 10 (req/s per IP) | `observed` | external | `backend/app/services/sec_rate_limiter.py:4`; CLAUDE.md rule 5 | Exceeding it risks SEC IP blocking, which would fail filing fetches for every user behind that IP. |
| B36 | Fleet SEC configured ceiling | steady_two_instances=20; monday_overlap_two_instances_plus_pregenerate_filing_scan=40; plus_backfill_facts_if_scheduled=50 (req/s) | `assumed` | fleet | Derived: B34 × (B08 steady processes + concurrently running SEC-calling job processes per B23); `docs/OPERATIONS.md:96` (aggregate budget exceeded while a job runs; only lower per-process budgets fix it) | Configured ceiling, not realised demand; actual aggregate rate unknown (B39). Assumes all processes share one egress IP (B37). |
| B37 | Egress identity (shared public IP across instances and jobs) | unknown (—) | `unknown` | external | tasks/fleet-coordination-proposal-2026-09-19.md:29 (no fixed egress arrangement observed 2026-09-15; dynamic egress does not prove independent IPs) | Do not assume independent IPs. A Cloud Run egress/NAT configuration read would resolve it; not performed here. |
| B38 | SEC breaker/limiter coverage by path | edgartools_and_compat_fetches=limiter + breaker; efts_full_text_and_companyfacts=limiter only; local_parsing=breaker-exempt; user_facing_wait=single token (`execute`); jobs=may use backoff ladder (—) | `configured-code-default` | process | `lessons/sec-edgar-resilience-layer.md:22`; CLAUDE.md rule 5 | The allowlist gate bounds `sec.gov` literals; it does not prove every call's routing. |
| B39 | Observed aggregate SEC rate / 429 / IP-block incidents | unknown (req/s / incidents) | `unknown` | fleet | No retained aggregate measurement or incident in the allowed inputs. Observation route: per-process `/metrics.sec_rate_limiter` (`total_requests`, `rate_limit_hits`) `docs/OPERATIONS.md:85`; jobs need their logs. | Admin-authenticated and per process; a fleet figure needs every instance and job in the window. |
| B40 | Provider stream ceilings per process | MAX_CONCURRENT_GENERATIONS=6; RECOVERY_MAX_CONCURRENCY=3; AI_CHAT_MAX_INFLIGHT=8; max_streams_per_process=17 (streams) | `configured-code-default` | process | `backend/app/config.py:489`; `backend/app/config.py:492`; `backend/app/config.py:501`; `backend/app/services/ai/provider_admission.py:1` (docstring) | Not overridden by the deploy env (`.github/workflows/ci.yml:620`); effective as coded. |
| B41 | Fleet provider stream ceiling | two_instances=34; plus_pregenerate_process=43 (streams) | `assumed` | fleet | Derived: 2 × B40 + pregenerate (6 generation + 3 recovery; no chat). Other jobs' provider use not verified. | Configured upper bound; realised concurrency unknown; provider account limits unknown (B46). |
| B42 | Provider retry policy | sdk_max_retries=0; application_attempts=3; retry_after_cap_seconds=5; deadline_extended_by_retry=no (—) | `configured-code-default` | process | `backend/app/services/openai_service.py:121`; `backend/app/services/ai/provider_requests.py:172`; `backend/app/services/ai/provider_requests.py:135`; B28 | — |
| B43 | Cancellation and drain on timeout/disconnect | yes (design property) | `configured-code-default` | process | `backend/app/services/ai/provider_requests.py:95` (outcome `cancelled`, settled); `docs/DEPLOYMENT.md:767` | Design property; provider-side billing for a cancelled stream is provider behaviour (unknown). |
| B44 | Chat admission queue semantics | waits_only_within_own_budget=yes; rejected_counter=provider_admission.rejected (—) | `configured-code-default` | process | `backend/app/services/ai/provider_admission.py:1`; `docs/OPERATIONS.md:85` | Slot, not rate; summary path never queues behind chat. |
| B45 | In-flight generation dedup / ownership | scope=process-local dict; cross_instance_duplicate_generation_possible=yes (—) | `configured-code-default` | process | `backend/app/services/summary_pipeline.py:90`; tasks/fleet-coordination-proposal-2026-09-19.md:25 (process-local leaders); Slice A proposal tasks/fleet-coordination-proposal-2026-09-19.md:125 | With two instances the same filing can be generated twice; keep-better/accepted-publisher behaviour per the proposal; E09 Slice A implementation remains held. |
| B46 | Provider account quota / rate limits (DeepSeek) | unknown (—) | `unknown` | external | Not in the allowed inputs. | Would need provider account documentation/observation; no provider call is authorized here. |
| B47 | Metering and refund rule | metered_at=provider call start; refund_on=provider-side failure, timeout, partial verdict; refund_on_client_cancellation=no (—) | `configured-code-default` | process | `tasks/todo.md:6147` (PR1069 package); summary_pipeline comments near the lease/refund paths | — |
| B48 | Pregenerate job provider concurrency | generations_at_a_time=1; loop=sequential per ticker and form (streams) | `configured-code-default` | job process | `backend/scripts/pregenerate_examples.py:86`–91 (awaited per ticker/form inside one loop; the `await pregenerate_for_ticker` is the last line of the range) | Section recovery inside each generation may add up to 3 streams (B40). |

**Reading of component 3.** Every limiter and semaphore here is process-local (B34, B40, B44, B45).
The SEC fleet ceiling by configuration is 20 req/s with two instances and 40–50 req/s in the Monday
06:00–07:00 UTC job-overlap window (B36), against an external cap of 10 req/s per IP (B35), with
egress identity unknown (B37) and no retained measurement of the realised aggregate rate (B39). The
repository's own operations guide states that only lower per-process budgets on the service and jobs
can fix an exceeded aggregate budget. Provider streams are bounded at 17 per process and 43 for the
configured fleet (B40–B41); provider account limits are unknown (B46). Duplicate generation of one
filing across instances is possible by design today (B45).

## 4. Proposed current-beta demand envelope and stop / rollback conditions

| ID | Bound | Value (unit) | Class | Scope | Evidence | Uncertainty / implication |
|---|---|---|---|---|---|---|
| B49 | Registration mode | REGISTRATION_MODE=invite_only (—) | `configured-deploy` | service | `.github/workflows/ci.yml:620` | Accounts are bounded by issued invites; invitations remain separately controlled (no invitations under CODE RED). |
| B50 | Per-user monthly caps | free_summaries=5; pro_summaries_guardrail=300; pro_copilot_questions=1000; pro_analysis_fresh_generations=100 (per user per month) | `configured-code-default` | account | `backend/app/services/entitlements.py:32`; `backend/app/config.py:462`; `backend/app/config.py:513`; `backend/app/config.py:526` | Plan truth lives in `entitlements.py`; values not changed by the deploy env. |
| B51 | Per-account burst limiters | unknown (—) | `unknown` | process | Exist since PR1069 (keyed on the account alone; `tasks/todo.md:6147` entry); limiter key cardinality `backend/app/config.py:171` | Burst values not read in this handback; process-local. |
| B52 | Guest (unauthenticated) generation path | unknown (—) | `unknown` | service | `.github/workflows/ci.yml:619` removes `ENABLE_GUEST_DAILY_QUOTA` at deploy | Effective guest behaviour not read here. |
| B53 | Intended cohort size (settled, not enrolled or consented) | 10–20 (participants) | `observed` | — | COO FIRST-DELIVERABLE §“C1 — one capacity admission, still HOLD” (package `c8277395…`); CEO-DIRECTIVE | Not enrollment, consent or a safe participant count. |
| B54 | Configured permitted monthly demand ceiling if all 20 were Pro at guardrail | summaries=6000; copilot_questions=20000; analysis_generations=2000 (per month) | `assumed` | fleet | Arithmetic on B50 × 20. | A ceiling of permitted demand; expected useful demand unknown (B56). |
| B55 | Instantaneous demand bounds and back-pressure | http_per_instance=40; generations_per_process=6; excess_generations=queue inside the 120 s pipeline timeout (—) | `configured-code-default` | process | B05; B40; `backend/app/services/summary_pipeline.py:673` | Overload becomes timeouts/503s, not process crashes; user-visible failure rate under overload unknown. |
| B56 | Retained useful-work (generation) evidence under concurrency | unknown (—) | `unknown` | fleet | None in the allowed inputs. CI eval-baseline runs at `EVAL_CONCURRENCY=2` (`.github/workflows/ci.yml:400`) are CI measurements, not production; COO windows are light HTTP traffic and single-task jobs. | Resolving observation: as B32, plus `/metrics.provider_admission` peaks in the same window. |
| B57 | Existing stop / rollback signals and levers | health=/health/detailed (database healthy + latency, breaker state); metrics=/metrics: database.checked_out, provider_admission.in_flight/rejected/peak_in_flight, sec_rate_limiter.rate_limit_hits, thread_pool.anyio.tasks_waiting; logs=pool-timeout signature (QueuePool limit / connection pool exhausted); rollback=Ops `rollback-traffic` operation; deploy routes traffic --to-latest (—) | `configured-code-default` | service | `docs/OPERATIONS.md:85`; `ops/capacity/readout.py:128`; `.github/workflows/ops.yml:641`; `.github/workflows/ci.yml:628` | Thresholds for a beta are not evidenced; the documented suggestions are partly stale (B33). |
| B58 | Provider spend authority provenance | shared_future_authority_usd=15.000000; conditional_unreserved_at_snapshot_usd=12.570771; retained_holds_usd=1.881713; live_ledger=inaccessible from this session; paid dispatch HELD (USD) | `observed` | — | CFO FIRST-DELIVERABLE (package `925fcc6b…`); `control/LEDGER-ACCESS.md` | Authority is not concurrency, capacity or runtime-budget admission; no spend is proposed. |

**Envelope proposal (conservative, evidence-bound).** No numeric participant or throughput envelope
can be supported by retained useful-work evidence (B56). The envelope this handback can support is
the configured one, with nothing new:

1. Cohort: the settled intended 10–20 invite-only participants (B49, B53), enrolled only through the
   separately controlled invitation/consent process; no new accounts beyond issued invites.
2. Demand: existing per-user caps unchanged (B50–B51); no production flag, pricing, registration or
   job/schedule change; no additional load, probe or warm-up.
3. Capacity controls unchanged: max 2 instances (B04), pools 4/0 and 3/0 and 1/0 (B10, B14),
   per-process SEC and provider ceilings (B34, B40).
4. Stop conditions (existing signals, B57): `/health/detailed` database unhealthy or latency rising;
   `/metrics.database.checked_out` at pool size on any instance; pool-timeout log signature present;
   `sec_rate_limiter.rate_limit_hits` rising on the service while a job runs; `provider_admission.rejected`
   rising; SEC breaker `half_open`/`open`. Numeric thresholds for a beta are **not** evidenced and are
   not set here; the documented suggestions are partly stale (B33).
5. Rollback lever: the existing Ops `rollback-traffic` operation to the previous revision (B57).
6. Spend authority provenance: the shared USD 15 future DeepSeek authority (CFO reconciliation,
   USD 12.570771 conditionally unreserved at the snapshot) is recorded as provenance only; the live
   ledger is inaccessible from this session, so the provider operating-spend field stays **HOLD**
   (B58). The ceiling is not concurrency, capacity or runtime admission.

## 5. Determination: do existing controls demonstrably suffice, or is a named E09 subset necessary?

**Determination: undetermined, with no E09 code subset demonstrated necessary for current-beta
safety.**

What the evidence shows existing controls *do* bound: per-process generation, recovery and chat
streams (B40); request, pipeline and provider time budgets with retries that never extend a deadline
(B26–B28, B42); fail-fast behaviour when a pool saturates (B11); session release before provider
waits (B29); cancellation and drain on disconnect (B43); metering that refunds only provider-side
failures (B47); invite-only registration and per-user monthly caps (B49–B50); a two-instance cap
(B04); configured database demand of 18 within 22 usable at steady state (B15, B19).

What the evidence shows existing controls do *not* demonstrably bound:

| Gap | Evidence | User-visible failure mode | Route that is not E09 code | Retained decision / owner |
|---|---|---|---|---|
| (a) Aggregate SEC request rate across instances and jobs (B36 vs B35; B37, B39 unknown) | configured ceilings 20–50 req/s vs 10 req/s external cap; no incident retained; realised rate unknown | SEC IP block → filing fetches fail for every user behind the IP, mostly risked in the Monday job-overlap window rather than by cohort traffic | lower per-process SEC budgets on the service and jobs so the fleet sum fits under 10 req/s with headroom (the repository's documented fix; configuration, no new code) | the founder's retained Slice B policy numbers (aggregate rate, burst/headroom, wait/error tolerance), `tasks/fleet-coordination-proposal-2026-09-19.md:127`; this handback proposes no numbers |
| (b) DB operating reserve under concurrent generation plus rollout overlap (B15, B19, B32) | configured 18 + 4 overlap = 22 usable; six backends at one light instant; no saturation observed or excluded | pool wait → 10 s fail-fast errors on summaries/health during overlap windows | one bounded read-only capacity-readout observation (B32); Cloud SQL sizing is a separate, non-E09 decision | COO/CEO decision to run the existing read-only Ops operation; not dispatched here |
| (c) Cross-instance duplicate generation of one filing (B45) | by design; two instances | duplicate provider spend; keep-better publication avoids wrong results per the proposal | none without Slice A | founder's retained Slice A decision, `tasks/fleet-coordination-proposal-2026-09-19.md:125`; not demonstrated necessary for 10–20 participants' safety |
| (d) Provider account quota (B46) | unknown | provider 429s → retries inside fixed budgets → timeouts | observe account limits | CTO/CEO observation; no provider call authorized here |

Because gap (a) has a configuration-only mitigation and gaps (b) and (d) are missing observations
rather than missing code, **no E09 subset is named as necessary for current-beta safety**. The E09
implementation hold, including inactive lease/schema/runtime code, is unchanged; no fleet build is
preselected; Slice A ownership is not made dependent on SEC egress identity; the dormant code is not
treated as exempt. The exact missing decision is the founder's Slice B policy allocation if the chief
and COO choose to close gap (a) by configuration before cohort entry; the exact missing observations
are B32, B39 and B37.

## 6. Limitations and unknowns (each with the resolving observation and owner)

| Unknown | Resolving observation | Owner |
|---|---|---|
| B08 rollout-overlap process count and duration | Cloud Run revision/instance timeline read for one deploy (read-only) | CTO via CEO-approved read; not dispatched |
| B16 current Cloud SQL tier | `gcloud sql instances describe` (read-only) | same |
| B21 current job task configuration / parallelism | Ops `describe-jobs` operation (read-only, exists in `ops.yml`) | COO/CEO decision |
| B22 same-job concurrent executions | job ledger + executions over a 14-day window (fleet proposal SQL / capacity-readout) | COO/CEO decision |
| B23 backfill-facts and notable-filings schedules | Scheduler list (read-only) | same |
| B32 DB operating reserve | one bounded read-only capacity-readout over a job-overlap window | COO/CEO decision |
| B37 egress identity | Cloud Run egress / NAT configuration read | CTO via CEO-approved read |
| B39 realised aggregate SEC rate | per-process `/metrics.sec_rate_limiter` on every instance + job logs in one window | same |
| B46 provider account limits | provider account documentation / dashboard read; no call | CTO/CEO |
| B51–B52 burst limiter values; guest path | code read (not performed here to keep the handback bounded) | CTO |
| B56 useful-work evidence under concurrency | the B32 observation plus `/metrics.provider_admission` peaks | COO/CEO decision |

Docs-vs-config note (not fixed here): `docs/OPERATIONS.md` alert threshold `database.checked_out > 8`
cannot fire with the deployed pool 4 / overflow 0 (B33); the deploy values are truth.

## 7. Return contract

- **Outcome:** handback complete as a bounded evidence record; `pass` for the administrative
  assignment with the isolation limitation stated in §0. Capacity remains **unadmitted**.
- **Deliverables:** this file and `CURRENT-BETA-OPERATING-ENVELOPE-BOUNDS.json` (same bounds, same
  ids and classifications; hashes recorded by the chief in the checkpoint).
- **Counts unchanged:** 3/30 dossiers; 0/2 actual weekly readouts; 5 reporting groups + 1 capacity
  decision; candidate HOLD; E7 90+30 not admitted.
- **Spend and mutations:** 0 new provider/DeepSeek calls; USD 0.000000; 0 reservations; 0 external
  mutations (no GitHub, cloud, production or provider action).
- **Next owner and action:** COO R3 operating-envelope disposition worker, dispatched by the chief
  with a manifest binding this handback's SHA-256, the CFO/CEO spend statement (HOLD) and the current
  exclusion successor. **Stop condition for that worker:** hash mismatch, missing field, or any
  request for a production read, measurement, invitation, flag, pricing or E09 code.
