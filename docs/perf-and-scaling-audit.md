# Filing-Load Performance & Scaling Audit

**Date:** 2026-07-06 (audit) · 2026-07-07 (fixes implemented) · **Scope:** why `/company/{ticker}`
is slow for filing-heavy companies and fails outright for Morgan Stanley (`/company/MS`), plus
scaling/cost posture for beta (tens of users) through thousands of users. Every claim cites the
file/line it was read from, or is labeled as measured/inferred. SEC filing counts were measured
live against `data.sec.gov` on 2026-07-06.

> **Implementation status (this PR).** The Quick-wins are now implemented and tested:
> **QW2** — `EdgarClient.get_filings_multi` (one `EdgarCompany`, all forms in one
> `trigger_full_load=False` recent-window fetch) + `_transform_filing` now reads the cheap
> `report_date` instead of the network-triggering `period_of_report` (see the correction in §2.1);
> **QW1** — DB-first serving with a bounded `BackgroundTasks` refresh in `routers/filings.py`;
> **QW3** — CORS headers on the timeout 504 (`main.py`); **QW5** — compliant `EDGAR_IDENTITY`
> default (`edgar/config.py`); **PS1** — composite `filings(company_id, filing_type, filing_date)`
> index (model + migration). Also a latent-bug fix: the edgar thread pool now auto-recreates after
> shutdown (`async_executor.py`). **QW4** — the CI deploy step now pins the Cloud Run sizing flags
> and sets `--min-instances=1` (one warm instance; ~$8–12/mo) so cold starts end and per-process
> caches survive (`.github/workflows/ci.yml`, docs updated to match). **Still live-GCP / not code:**
> setting the prod `EDGAR_IDENTITY` env value to the compliant string (the default is now compliant,
> but prod should set it explicitly — see §6).

---

## 1. Executive summary

**Root cause.** The filings-list endpoint does a live SEC fetch on most loads, and the way it
calls the edgartools library forces edgartools to download a company's **entire lifetime filing
history** before filtering to the handful of forms we show — and it does this **once per
requested form type** (5 form types in production). The cost therefore scales with a company's
*total* filing count, not the ~20 filings displayed. Morgan Stanley has **105,377 lifetime
filings across 44 SEC submissions files (~25–45 MB)**; Apple has 2,236 across 2. An MS load
means up to ~220 rate-limited SEC fetches plus five parses of a 105k-row table on a 1 vCPU /
1 GiB Cloud Run instance. It can never finish inside any of the timeouts in the path, the
abandoned work cannot be cancelled and piles up in a 4-thread pool, memory pressure builds, and
the browser ends up seeing a dropped connection or a CORS-stripped error — which the frontend
renders as the exact reported message, "Unable to connect to the server…".

The hypothesis in the brief ("per-filing work in the load path") is **confirmed in spirit,
refuted in detail**: per-filing DB work is already batched and LLM generation is *not* in the
load path. The scaling term is the *company's total filing history × form types*, hidden inside
the edgartools call.

**Top actions, in priority order:**

| # | Action | Expected impact | Effort | Monthly cost |
|---|--------|-----------------|--------|--------------|
| 1 | Serve the filings list **DB-first** and refresh from SEC in the background (stale-while-revalidate). The endpoint already persists every fetched filing — flip the order. | Filing loads become ~10–50 ms for every previously-seen company, on every instance, regardless of filer size. Biggest reliability win available. | ~1 day | $0 |
| 2 | **Bound the SEC fetch**: one submissions-JSON fetch per company serving *all* form types (the JSON already contains every form — filter locally), never the full paginated history. | Fixes mega-filers outright: MS drops from ~220 fetches to 1–2. First-ever loads complete in 1–3 s. | ~0.5–1 day | $0 |
| 3 | **Fix the CORS-less 504** in `request_timeout_middleware` (`backend/main.py:320-331`). | Slow requests surface as a readable "timed out" error instead of the masked "Unable to connect". | ~15 min | $0 |
| 4 | Set **`--min-instances=1`** and pin all Cloud Run sizing flags in the CI deploy step. | No cold starts at beta; the in-memory caches (filings-list TTL, XBRL L1, tickers) stop evaporating; sizing can't silently drift. | ~1 h | ~$8–12 |
| 5 | Set **`EDGAR_IDENTITY`** in prod to SEC's recommended `Company Name contact@domain` form (default is a bare email, `backend/app/services/edgar/config.py:14`). | Removes an easy reason for SEC to classify traffic as an undeclared automated tool. | minutes | $0 |

Items 1–3 are the pre-beta set. Together they make every company page fast and make the failure
mode (if anything else ever fails) legible instead of "backend down".

---

## 2. Root-cause analysis

### 2.1 The traced request path

**Frontend** (`frontend/app/company/[ticker]/page-client.tsx`):

1. `useQuery(queryKeys.company)` → `GET /api/companies/{ticker}` (page-client.tsx:46-51).
2. Only after the company resolves (`enabled: !!company`), `useQuery(queryKeys.companyFilings)` →
   `GET /api/filings/company/{ticker}` with `retry: 1` (page-client.tsx:53-58). **This is the
   slow/failing call.** Auth/watchlist queries are light; the summary prefetch
   (page-client.tsx:200-210) is a read-only GET that never triggers generation. The optional
   peer/insider panels are feature-flagged off by default.
3. All requests go through the shared axios client with a **30 s timeout**
   (`frontend/lib/api/client.ts:57`). The exact reported string — *"Unable to connect to the
   server. Please ensure the backend API is running on …"* — is produced **only** by the
   `Network Error`/`ECONNREFUSED` branch (`client.ts:165-166`), i.e. when the browser received
   **no readable HTTP response at all**. A plain timeout renders "The request timed out."
   (client.ts:167-168) and an app-level 503 renders the backend's message (client.ts:154-156).
   This is the key forensic fact: the failure is connection-level, not a clean error response.

**Backend** (`backend/app/routers/filings.py:93-276`, `async def get_company_filings`):

4. Company row lookup (filings.py:104; `companies.ticker` is indexed).
5. Form list: prod deploys with `ENABLE_FPI_FILINGS=true` (`.github/workflows/ci.yml:378`;
   default is `False`, `backend/app/config.py:314`), so `types_list =
   ["10-K","10-Q","20-F","6-K","40-F"]` — **5 form types** (filings.py:135-140).
6. Fast path: an **in-memory, per-process** freshness stamp with a 3 h TTL
   (`_filings_synced_at`, filings.py:30-45,153-156). If fresh AND the DB has rows, serve up to
   20 DB rows. This map is empty after every cold start/deploy and is not shared between the
   two Cloud Run instances — so "cold" is the common case at beta traffic with
   `min-instances=0`.
7. Cold path: `await asyncio.wait_for(sec_edgar_service.get_filings(cik, types_list),
   timeout=20.0)` (filings.py:160-163) — a **live SEC fetch on the request path**.
8. On success: one batched existing-rows prefetch (filings.py:170-178, an intentional N+1 fix),
   one commit (filings.py:235-239), respond. On `TimeoutError`/`EdgarError`: roll back and fall
   back to DB rows if any exist, else **503** (filings.py:247-266).

**The SEC call chain** — where the scaling term lives:

9. `SECEdgarServiceCompat.get_filings` loops **once per form type** and calls
   `edgar_client.get_filings(cik, ft, limit=None, ...)` each iteration
   (`backend/app/services/edgar/compat.py:263-276`).
10. Each `edgar_client.get_filings` constructs a **fresh** `EdgarCompany(cik)` and calls
    `edgar_company.get_filings(form=ft, amendments=…)`
    (`backend/app/services/edgar/client.py:200-231`). The `islice(…, per_form_limit=20)` at
    client.py:225-230 caps how many results are *materialized* — it does **not** bound the
    network cost, because the filtering happens after the data is loaded.
11. **edgartools 5.40.1** (`backend/requirements.txt`): `Company.get_filings()` defaults to
    `trigger_full_load=True` (verified in the installed-package source:
    `edgar/entity/core.py:396-409` and `edgar/entity/data.py:409,424-426`). Before filtering by
    form, `_load_older_filings()` (`edgar/entity/data.py:353-382`) downloads **every**
    paginated submissions file (`data.sec.gov/submissions/CIK…-submissions-NNN.json`) and
    concatenates all rows into a pyarrow table. The app never passes
    `trigger_full_load=False`.
12. These edgartools HTTP calls **bypass the app's `sec_rate_limiter`** entirely; edgartools
    self-throttles at **8 req/s** (`edgar/httprequests.py:52`, `max_requests_per_second = 8`)
    and HTTP-caches submissions responses for only **30 seconds**
    (`edgar/httpclient.py:63`, `MAX_SUBMISSIONS_AGE_SECONDS = 30`) in a file cache that, on
    Cloud Run, lives on the RAM-backed tmpfs.
13. All of this runs synchronously inside a **dedicated 4-thread pool**
    (`EDGAR_THREAD_POOL_SIZE = 4`, `backend/app/services/edgar/config.py:165`;
    `backend/app/services/edgar/async_executor.py:39-42`), wrapped by a per-operation **15 s**
    timeout (`EDGAR_DEFAULT_TIMEOUT_SECONDS`, edgar/config.py:167) and the shared circuit
    breaker.
14. **Second, per-filing scaling cost (correction to the first-pass audit).** The first pass said
    `_transform_filing` was "metadata-only" because it avoids edgartools' `filing_url`. That was
    incomplete: it read `edgar_filing.period_of_report`, which on `EntityFiling` is **not** a plain
    attribute — it is a base-class `@property` (`edgar/_filings.py:1560`) that calls `self.sgml()`, a
    **live per-filing full-submission download from sec.gov** (even `hasattr` evaluates it). So the
    listing did up to `per_form_limit × forms` extra SGML downloads on top of the submissions
    history — a second term that also scales with the number of filings shown. The fix reads the
    cheap `report_date` attribute that `EntityFiling` populates from the submissions JSON
    (`edgar/entity/filings.py:70`), same value, zero network. **Implemented** in this PR
    (`client.py::_transform_filing`).

### 2.2 Why MS fails while small companies succeed (measured)

Measured live from `data.sec.gov` on 2026-07-06:

| Company | CIK | Lifetime filings | Submissions files | Main JSON size | "Recent" window |
|---|---|---|---|---|---|
| Morgan Stanley | 895421 | **105,377** | 1 main + **43** pages | 3.8 MB (19,171 entries) | ~12 months (mostly 424B2/FWP — the structured-notes desk) |
| Apple | 320193 | 2,236 | 1 main + 1 page | ~1 MB | ~10+ years |

For Apple, "load the full history" is 2 fetches per form type — a couple of seconds total; the
request completes, rows persist, and the 3 h fast path takes over. That is the observed
"companies with few filings load fine".

For Morgan Stanley, one cold load implies:

- Up to **5 × 44 = 220 SEC fetches** (5 form types × 44 submissions files). The 30 s
  edgartools HTTP cache dedupes the 2nd–5th form types *within* one request, so best case is
  ~44 fetches + 4 × 44 cache revalidations-or-hits — but the parse/concat of a **105k-row**
  pyarrow table still happens **5 times per request**, on 1 vCPU.
- At edgartools' 8 req/s self-throttle, 44 fetches ≥ 5.5 s of token waits alone, plus
  ~25–45 MB of download and JSON→arrow parsing. Realistic wall clock: **20–60 s+**, versus the
  **15 s** per-operation timeout — so the very first `get_filings(form="10-K")` call times out
  **deterministically**. MS can never complete a sync, its `filings` DB rows never get
  populated, so the fallback at filings.py:251-258 finds nothing and the endpoint 503s — every
  time, forever. (Whether prod's DB actually has zero MS rows is listed in §6 to verify.)

### 2.3 The failure mode: why "no response" instead of a clean 503

Confirmed mechanics, in escalating order:

1. **Un-cancellable zombie work.** `asyncio.wait_for` can cancel the *awaiting coroutine*, but
   `loop.run_in_executor` threads are not cancellable
   (`backend/app/services/edgar/async_executor.py:67-78`) — each timed-out MS attempt keeps
   downloading and parsing all 44 files to completion inside the 4-thread pool. The frontend's
   `retry: 1` (page-client.tsx:57) plus user reloads multiply attempts. A handful of MS-page
   views fills the pool with long-running orphans, and **every** Edgar operation for every
   company then queues behind them.
2. **Circuit-breaker blast radius.** Each timeout is a trip-exception; **5 consecutive failures
   open the breaker for 30 s** (`backend/app/services/edgar/circuit_breaker.py:63-70,367-375`),
   during which *all* companies' cold filings loads fail fast with 503. One mega-filer page view
   can briefly take the feature down site-wide. (These 503s do carry CORS headers via the
   handler at `backend/main.py:369-385`, so they render readably — they are not the
   "Unable to connect" case.)
3. **Memory pressure → instance death.** Concurrent/zombie full-history loads each hold tens of
   MB (JSON buffers + pyarrow tables + the tmpfs HTTP cache, which is RAM on Cloud Run) against
   a **1 GiB** instance (`docs/DEPLOYMENT.md:120`). An OOM-killed or wedged instance produces
   **connection resets**, and Cloud Run's "no available instance" 503 is emitted by Google's
   frontend **without CORS headers**. Both are exactly what the browser reports as a network
   error → axios's `Network Error` branch → *"Unable to connect to the server…"*
   (client.ts:165-166). This is the best-supported explanation for the reported symptom.
   (Confirming OOM vs. no-instance requires Cloud Run logs — see §6.)
4. **A confirmed code-level producer of the same masked error:** the request-timeout
   middleware's hand-built 504 (`backend/main.py:306-331`, 60 s for `/api/filings/`) **omits**
   `_error_response_cors_headers`. The middleware is registered *after* `CORSMiddleware`
   (main.py:233 vs 306), which makes it the **outermost** layer in Starlette's stack, so its
   504 never passes through CORSMiddleware and the browser blocks it. The codebase already
   fixed this exact bug for the `CircuitOpenError` handler (main.py:380) and the global
   exception handler (main.py:418) — this one site was missed. (Note: axios usually aborts at
   30 s before this 60 s middleware fires for the filings call, but it applies to every
   30 s-default endpoint and to any client without the axios timeout.)

**Verdict:** the failure is **not a cold start** and **not an LLM problem**; it is a
request-path SEC fetch whose cost is unbounded in company size, which then converts into
thread-pool exhaustion, breaker trips, and instance-level failure (timeout/OOM), all surfaced to
the user as a connection error because the error paths lose their CORS headers or never produce
a response at all.

### 2.4 Explicitly cleared

- **LLM generation is not in the load path.** List endpoints never generate. Generation happens
  only via the user-initiated SSE endpoint and the background/cron path, both through the single
  orchestrator (`backend/app/services/summary_pipeline.py`), with results persisted in the
  `summaries` table under a per-filing unique constraint and an in-process in-flight dedup
  (summary_pipeline.py:184-223). Cost profile in §5.
- **Per-filing DB work is already batched** — one `IN`-query prefetch + one commit
  (filings.py:170-239). Remaining nits (per-new-filing `db.refresh`, sync SQLAlchemy calls on
  the event loop in `async def` handlers, `Filing.company_id`/`filing_type`/`filing_date`
  having **no index** — `backend/app/models/__init__.py:198-201`) are secondary costs, listed
  in §3.

---

## 3. Prioritised recommendations

### Quick wins (before beta)

**QW1 — DB-first filings list with background refresh.** *Impact: very high · Effort: ~1 day ·
Cost: $0 · Risk: low.*
In `get_company_filings`, if the DB has *any* rows for the company, return them immediately and
kick the SEC sync as a background task (`fastapi.BackgroundTasks` or `asyncio.create_task`)
guarded by the existing `_filings_synced_at` stamp; only block on SEC when the DB is empty
(first-ever view). The endpoint already persists everything it fetches, so this is a reordering,
not new machinery. Staleness is bounded by the same 3 h TTL that exists today, and the
new-filing *alert* path (filing-scan job) is independent, as the comment at filings.py:25-29
already notes. Seed popular tickers once via the existing filing-scan/precompute paths so
day-one loads are warm.

**QW2 — One bounded submissions fetch per company, serving all form types.** *Impact: very high
(fixes MS-class filers outright) · Effort: 0.5–1 day · Risk: low-medium (changes the fetch
path; contract-test the response shape).*
The submissions JSON's `recent` block already contains **every** form with `form`,
`accessionNumber`, `filingDate`, `reportDate`, and `primaryDocument` — everything
`_transform_filing` needs (client.py:389-444 builds URLs from exactly these fields). Replace the
per-form-type × per-`EdgarCompany` loop (compat.py:263-276) with **one** rate-limited direct GET
of `https://data.sec.gov/submissions/CIK{cik}.json` through the existing `sec_rate_limiter` +
circuit breaker (the pattern already used for `company_tickers.json` at compat.py:75-94),
filtered locally to the requested forms. For mega-filers whose `recent` window (~1 year) holds
too few 10-K/10-Qs, page backward through the additional files **only until N matches are
found, capped at a handful of pages** — never the full history. Alternative (smaller diff,
weaker): keep edgartools but construct a single `EdgarCompany` per request and call
`get_filings(..., trigger_full_load=False)`; this relies on edgartools' lazy-load flag and
still parses per call. The direct-fetch version also removes the second, uncoordinated
egress path (§4).

**QW3 — Add CORS headers to the middleware 504.** *Impact: medium (diagnosability) · Effort:
~15 min · Cost: $0 · Risk: none.*
`backend/main.py:320-331`: build the 504 `JSONResponse` with
`headers=_error_response_cors_headers(request)`, matching main.py:380 and main.py:418. Every
future slow request becomes a readable error instead of "Unable to connect".

**QW4 — `--min-instances=1` and pin sizing flags in CI.** *Impact: medium · Effort: ~1 h ·
Cost: ~$8–12/mo · Risk: none.*
`min-instances=0` (docs/DEPLOYMENT.md:120) means cold starts and cold in-memory caches at beta
traffic. One warm instance removes both. At the same time, add
`--memory/--cpu/--concurrency/--timeout/--min-instances/--max-instances` to the CI deploy step
(`.github/workflows/ci.yml:374-379` currently asserts none of them), so live sizing can't drift
from the documented values — this repo already has a lesson to this effect
(`lessons/arch-per-process-state-on-cloud-run.md`, `tasks/architecture-refactor-plan.md`).

**QW5 — Fix `EDGAR_IDENTITY` in prod.** *Impact: compliance/risk · Effort: minutes · Cost: $0.*
Default is a bare email (`edgar/config.py:14`); SEC's fair-access policy asks for
`Sample Company Name AdminContact@sample.com`. The compliant string already exists as
`SEC_USER_AGENT` (`backend/app/config.py:32`) but edgartools uses `EDGAR_IDENTITY`. Set the env
var on the Cloud Run service (and jobs) to the same product+contact form.

### Pre-scale hardening (before real growth)

| Rec | Detail | Impact / Effort / Cost / Risk |
|---|---|---|
| **PS1 — Composite index on `filings`** | New idempotent migration: index on `(company_id, filing_type, filing_date DESC)`. The hot fallback query (filings.py:144-147) and trending join (companies.py:276-291) currently walk an unindexed FK (`models/__init__.py:198-201`). | Med / 30 min / $0 / none |
| **PS2 — Move sync DB off the event loop in hot handlers** | `get_company_filings`, `get_company`, trending run `db.query(...)` directly inside `async def` (filings.py:104,144; companies.py:404), blocking the loop under load. Either convert pure-DB read endpoints to `def` (FastAPI threadpools them) or use the `run_sync_db` helper that already exists in `summary_pipeline.py:159-161`. | Med at 100s of users / 0.5 day / $0 / low |
| **PS3 — Global cap on concurrent summary generations** | Per-filing dedup + per-user 5/min exist (summaries.py:42,146), but nothing bounds *distinct-filing* generations per instance; each holds a DB session + LLM stream. A simple `asyncio.Semaphore(4–6)` in the pipeline bounds memory, DB sessions, and worst-case LLM spend. | Med / 2–3 h / $0 / low |
| **PS4 — Consolidate the SEC egress budget** | Today: app limiter 10/s (`config.py:33`) **plus** edgartools 8/s per process, **plus** `facts_service._fetch_companyfacts_sync` bypassing both at ~5/s (`facts_service.py:443-469`), × instances × 7 Cloud Run jobs. Route facts_service through `sec_rate_limiter`; lower per-process rates so worst-case aggregate ≤ ~8/s (see §4). | High at scale / 0.5 day / $0 / low |
| **PS5 — Read back persisted XBRL** | `get_xbrl_data` checks L1 → (prod-disabled) L2 → live SEC, never the `Filing.xbrl_data` column the pipeline already persists (xbrl_service; summary_pipeline.py:299-323). Reading the DB copy first eliminates repeat SEC fetches after every deploy/scale event. | Med / 2–4 h / $0 / low |
| **PS6 — Ops guardrails** | Alert on Cloud Run memory >80 %, instance restarts, and 5xx rate (Sentry is already wired); keep `max-instances × (pool 5+5)` + job pools under Cloud SQL `max_connections` (~50 on db-g1-small; Dockerfile:45-46) when raising `max-instances`. | Med / 2 h / $0 / none |

### Later (only when growth demands)

- **Shared cache tier.** ADR-0004 deliberately runs L1-only in prod. DB-first serving (QW1)
  removes most of the need; revisit Memorystore (~$35/mo) or a Postgres-backed cache table only
  when >2 instances make per-process caches visibly redundant against SEC quota.
- **Static egress IP (VPC connector + Cloud NAT)** — only if SEC throttling is actually
  observed; it concentrates all traffic on one IP, which cuts both ways (§4).
- **Move all SEC list-refresh to the hourly filing-scan job** so user requests *never* touch
  SEC synchronously; the request path becomes pure DB reads.
- **Async SQLAlchemy migration** — large effort; unnecessary if PS2 is done and traffic is
  within a few hundred concurrent users.

---

## 4. SEC EDGAR compliance & scaling risk

**The rules (current, per SEC's developer/fair-access guidance):** declare a `User-Agent` of the
form `Sample Company Name AdminContact@sample.com`; stay at or below **10 requests/second** per
IP; violators get HTTP 403 "Undeclared Automated Tool" or temporary IP blocks (typically ~10
minutes, longer for repeat offenders).

**Current posture, from code:**

- **Identity:** two strings in play. `SEC_USER_AGENT = "EarningsNerd/1.0
  (contact@earningsnerd.io)"` (config.py:32) — compliant — is used by the EFTS client and
  facts sync. But edgartools and the compat layer's direct calls use `EDGAR_IDENTITY`, whose
  default is the bare `neil@earningsnerd.io` (edgar/config.py:14). Whether prod overrides it is
  not verifiable from the repo (§6). → QW5.
- **Rate limiting is per-process and duplicated.** The app's token bucket (10/s,
  `sec_rate_limiter.py:52,238`) governs only the direct httpx calls; edgartools throttles
  itself separately at 8/s (`edgar/httprequests.py:52`); `_fetch_companyfacts_sync` bypasses
  both with a 0.2 s sleep (~5/s, facts_service.py:460-469). One busy instance can therefore
  emit ~18–23 req/s; with `max-instances=2` plus overlapping Cloud Run jobs (7 exist —
  filing-scan hourly, digest, backfill-facts, calendar ×2, notable-filings, pregenerate), the
  theoretical aggregate is **>40 req/s** from processes that each believe they're compliant.
- **Egress IPs:** no VPC connector/NAT is configured (docs/DEPLOYMENT.md deploy flags), so
  Cloud Run uses Google's shared egress pool. This diffuses per-IP pressure (bursts spread
  across pool IPs) but is not a guarantee, and it also means an SEC block would be
  unpredictable and shared.
- **Hidden request amplification:** edgartools' 30 s submissions cache TTL means every page
  reload >30 s apart re-**validates** all 44 MS files — and revalidations consume rate-limit
  budget even on 304s (noted in `edgar/httpclient.py`'s cache-rule comments). QW2 eliminates
  this class of traffic.

**Risk by tier:** at tens of users the aggregate stays comfortably under 10/s *except* during a
mega-filer load (which is its own DoS). At hundreds of users with cold caches, concurrent
company loads × 2 instances can sustainably exceed 10/s and draw 403s — which the breaker then
converts into site-wide 503 windows. At thousands, without consolidation SEC throttling is
**likely**, and it is the one dependency that cannot be bought out of.

**Mitigations (mostly already in §3):** QW2 (one fetch per company, no history walk), PS4
(single egress budget: e.g. app limiter 3/s + edgartools 3/s per process, facts through the
limiter, stagger job schedules — most already are), QW5 (identity), and DB-first serving (QW1)
so user traffic stops translating 1:1 into SEC traffic at all. With those, thousands of users
generate *less* SEC traffic than tens do today.

---

## 5. Scaling & cost model

### What breaks first, by tier

- **Tens of users (beta, now):** mega-filer pages fail deterministically (§2.2); any MS-class
  view degrades the whole instance (thread pool, breaker, memory) for everyone; cold starts +
  cold caches make even healthy companies take 3–8 s on first view. *Fixes: QW1–QW4.*
- **Hundreds of users:** concurrent cold loads trip the breaker regularly; per-process caches ×
  2 instances double SEC traffic; sync-DB-on-event-loop (PS2) inflates tail latency; unindexed
  `filings` scans start to show (PS1); SEC 403s begin if PS4 is skipped. Cloud SQL connections
  remain fine (2 × 10 pool max vs ~50).
- **Thousands of users:** SEC egress is the hard wall without PS4/QW1; raising `max-instances`
  beyond ~4 without pool math (PS6) risks Postgres connection exhaustion on db-g1-small;
  2 × 1 vCPU instances saturate on CPU (JSON/markdown serialization, XBRL parses) → need
  min 2 / max 4–6 instances and possibly 2 vCPU; per-process rate limiters (per-user 5/min
  etc.) become per-instance approximations — acceptable, but document it.

### Cost model (us-west1 list prices, approximate)

**LLM unit economics** (from configured pricing, `config.py:401-403` — DeepSeek-equivalent):
a fresh 10-K summary ≈ 25–30k input tokens (≤ $0.013 at the cache-miss rate, ~120× cheaper on
cache hits) + 8–12k output tokens (≈ $0.007–0.010) → **~$0.02–0.03 per fresh summary**, and
summaries are generated **once per filing ever** (DB-unique + dedup), so LLM cost scales with
*newly-viewed filings*, not with users.

| | Today (pre-fix) | Beta, tens of users (with QW1–QW5) | Hundreds of users | Thousands of users |
|---|---|---|---|---|
| Cloud Run service | ~$0–5 (scale-to-zero) | **+$8–12** (min-instances=1) | $15–40 (1 warm + bursts) | $50–150 (2 warm, maybe 2 vCPU) |
| Cloud SQL | ~$25–35 (db-g1-small) | same | same | $50–100 (db-custom-1-3840 when connections/CPU demand) |
| Cloud Run jobs / Scheduler | <$5 | same | same | <$10 |
| LLM (DeepSeek) | pennies | <$5 (few hundred fresh summaries) | $20–90 (1–3k fresh/mo; catalogue effect saturates) | $100–300 (5–10k fresh/mo; Pro users are the unbounded term — PS3 caps burst) |
| Redis / NAT / etc. | $0 | $0 (deliberately deferred) | $0 | optional: Memorystore ~$35, NAT ~$10–65 — only on observed need |
| **Total infra** | **~$30–45** | **~$40–55** (**increment ≈ $10** — under the $50 cap) | ~$60–140 | ~$200–500 |

**Cost step-up points to watch:** (1) sustained concurrency >~40 → a 2nd warm instance;
(2) DB connections approaching ~50 or DB CPU >70 % → next Cloud SQL tier; (3) fresh-summary
volume — the free tier (5/mo, `entitlements.py`) and guest quota (3/day, config.py:363) bound
abuse, Pro is uncapped by design (PS3 bounds the burst rate); (4) SEC 403s → PS4/NAT decision.

Notably, **none of the recommended pre-beta fixes add meaningful cost** — they *reduce* SEC and
compute work per user. The only new spend is the ~$10/mo warm instance.

---

## 6. Assumptions & unverified items

| Item | Why it matters | How to check |
|---|---|---|
| **Live Cloud Run sizing** (memory/cpu/concurrency/timeouts/min-max instances) | CI never re-asserts sizing flags (ci.yml:374-383); all values here come from the bootstrap doc (docs/DEPLOYMENT.md:120) and may have drifted. | `gcloud run services describe earningsnerd-backend --region=us-west1` |
| **Which mechanism produced the observed "Unable to connect"** (OOM vs no-instance 503 vs reset) | §2.3 ranks OOM/no-instance as best-supported; confirming changes nothing about the fix priority but validates the memory sizing. | Cloud Run logs: filter for `Memory limit … exceeded`, `The request was aborted because there was no available instance`; Sentry for the same window |
| **Prod `EDGAR_IDENTITY` env value** | Default is a bare email; compliance item QW5. | `gcloud run services describe earningsnerd-backend --region=us-west1 --format='value(spec.template.spec.containers[0].env)'` |
| **Whether MS has any `filings` rows in prod** | Determines whether MS 503s (empty fallback) or would serve stale rows today. | `SELECT count(*) FROM filings f JOIN companies c ON c.id=f.company_id WHERE c.ticker='MS';` |
| **Live Cloud SQL tier / `max_connections`** | Pool math in PS6 assumes db-g1-small ≈ 50. | `gcloud sql instances describe earningsnerd-db` |
| **Egress IP arrangement** | §4 assumes shared Google egress pool (no NAT configured in repo). | GCP console → Cloud Run networking / VPC connectors |
| **edgartools cache growth on tmpfs** | Assumed to count against instance memory (Cloud Run filesystems are in-memory); affects memory headroom. | Cloud Run memory metrics before/after a mega-filer load in staging |
| **SEC fair-access specifics** | 10 req/s + declared UA taken from SEC's published guidance as of the audit date; re-confirm before building PS4. | https://www.sec.gov/os/webmaster-faq#developers |
| **Filing counts** | MS = 105,377 / 44 files; AAPL = 2,236 / 2 files — measured live 2026-07-06; counts grow daily (MS ≈ +19k/yr). | `curl -H 'User-Agent: …' https://data.sec.gov/submissions/CIK0000895421.json` |
