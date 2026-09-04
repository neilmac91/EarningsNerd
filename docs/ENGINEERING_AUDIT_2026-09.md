# Engineering audit — September 2026

**Date:** 2026-09-04 · **Repo state audited:** `main` @ `e8ea339` (2026-07-16) · **Production backend:** `4994360` (2026-07-13)
**Lens agreed with the founder:** invite-only beta; when two priorities are close, *product quality* wins.
**Mandate:** investigate, plan, and open PRs; the founder merges.

Six parallel workstreams (deploy pipeline, AI summary quality, data platform, frontend/UX,
security & ops, unfinished-work archaeology) each produced an evidence-backed report; they are the
appendices in `docs/audit-2026-09/`. This document is the synthesis: what is true today, the
three priorities, and the remediation plan (`tasks/todo.md` holds the checkable version).

---

## 1. Executive summary

1. **Production has been running a 7-week-old backend, and nobody was told.** The last merge to
   `main` (PR #634, 16 July) passed every test, built its image, then hung for six hours in
   "Apply database migrations" and was killed by GitHub's default job timeout. The Cloud Run
   deploy, all seven job-image updates and the health check were skipped. Root cause (confirmed
   from the job log): a *converged, idempotent* `ALTER TABLE filing_content_cache ADD COLUMN IF
   NOT EXISTS` — re-applied on every deploy — still takes an ACCESS EXCLUSIVE lock and waited
   behind one open transaction; there was no `lock_timeout`, no `statement_timeout`, and no job
   timeout. While it waited, every new read of that hot table queued behind it, so the API was
   probably degraded for most of that window (hypothesis — verify in Cloud Run metrics/Sentry).
   Nothing in the frontend depends on the undeployed backend, so the site is *up*, but the
   truthful sitemap, the API-host robots `Disallow`, and the per-IP limits on the two
   always-live-EDGAR endpoints never shipped.
2. **The next backend push would have gone red before it could deploy.** CI installs ruff
   unpinned; ruff 0.16 widened its default rule set and the same clean tree now reports 2,767
   findings. The tree is clean under the rules the repo actually chose. Fixed in this PR
   (explicit `select`, pinned toolchain, machine gate).
3. **Main is otherwise healthy.** All gates pass locally today under CI's environment: ruff,
   bandit, 1,785 backend tests, ESLint, `tsc`, 409 vitest tests, `next build`, and 17 Playwright
   end-to-end tests. Live public pages render server-side with correct titles, canonicals,
   structured data and summary text.
4. **The AI pipeline is well-engineered but under-measured.** One orchestrator, filing-only
   grounding, disciplined "measure-always, act-when-armed" guards. But the pinned eval bar is
   saturated (1.0/1.0/1.0/0.0) on dimensions that mostly verify deterministic XBRL plumbing; the
   LLM judge — the only faithfulness measure — is off in CI and in the baseline; the deterministic
   figure-trace exists only as a production log line. A prompt or provider change that increased
   causal fabrications would pass CI green. Three trust guards ship unarmed waiting on a "fleet
   readout" that has no dashboard. The retry chain still lists two Gemini models that are sent to
   DeepSeek and 404, so a transient provider error becomes a user-visible failure.
5. **Coverage is thin and user-driven.** 0 of 7 sampled recent filings have a summary; scheduled
   generation covers 8 tickers, 10-K only; 46 % of the S&P 500 ∪ Nasdaq 100 universe has no
   company row; 6-Ks are more than half of new filing rows, and although a 6-K summary path exists
   behind `ENABLE_FPI_FILINGS` (on in prod), it has no classifier, so governance and press-release
   6-Ks get the earnings prompt and the golden set contains no 6-K at all. The
   universe-refresh workflow has failed silently since August (Wikipedia removed the Nasdaq-100
   constituents table). The public sitemap advertises ~36k stub filing pages.
6. **The reading surface has three visible defects on the very first example a visitor opens:**
   five identical "Risk Factor" headings on `/filing/3`, a pricing page that server-renders no
   content (client-side bailout), and EDGAR-caps company names. The public sitemap has been a
   frozen 16 July snapshot for seven weeks and will not self-heal.
7. **Hygiene backlog is real but bounded.** Nine Dependabot PRs (six safe to merge, two to close,
   one to split; one would break the Vercel build as-is); Next.js 16.2.10 carries nine advisories
   including a middleware bypass and the middleware is the UX gate; `pandas` is pinned to a yanked
   release; nothing pages anyone when the API, a job, the SEC circuit breaker or the AI provider
   fails; Cloud SQL backups/PITR were never explicitly configured.
8. **Unfinished-work inventory: 55 items** (16 built-but-dark behind flags, 30 not started,
   5 partial, 4 blocked on the founder or a third party) and **10 items the docs call open that
   are actually done**. Two planning docs mislead: the FPI roadmap shows 34 unchecked boxes but
   Phases 0–5 are in code with the flag ON in prod; the homepage-sections review's 9 boxes were
   mostly resolved by PR #571. Eleven decision clusters need the founder, not engineering.

---

## 2. What this PR does (Phase 0 — lands with the audit)

| Change | Why | Where |
|---|---|---|
| Explicit ruff rule set `select = ["E4","E7","E9","F"]` | Tool upgrades can no longer change what CI enforces | `backend/ruff.toml` |
| Pinned lint toolchain `requirements-dev.txt` (ruff 0.16.6, bandit 1.9.4), installed by CI and the local gate | Unpinned `pip install ruff` caused the latent CI break | `backend/requirements-dev.txt`, `ci.yml`, `CLAUDE.md` |
| `timeout-minutes: 30` on `deploy-backend` | A stuck step can never hold the deploy group for 6 h again | `ci.yml` |
| `PGOPTIONS="-c lock_timeout=10s -c statement_timeout=120s"`, 5 bounded retries, `pg_stat_activity` dump on final failure | A lock becomes a fast, retried, diagnosable failure instead of a hang | `ci.yml` migration step |
| Gate test `test_migration_lock_safety.py` (6 tests) | Rule 12: the workflow knobs, the toolchain pin, the explicit rule set, the migration filename convention, and a frozen shrink-only allow-list of the 17 legacy files that still issue unguarded `ALTER TABLE`; new files must use the `DO $$ … IF NOT EXISTS … $$` guard | `backend/tests/unit/` |
| Two lessons + index entries | `ops-migrations-need-lock-timeout.md`, `ops-pin-ci-toolchain.md` | `lessons/` |
| Doc sync | `DEPLOYMENT.md` (7 jobs, `/health/detailed`, `pdx1`, migrations are automatic, "only a backend push deploys"), `CLAUDE.md` (7 jobs, rule-3 lock note, gate install line) | `docs/`, `CLAUDE.md` |
| `frontend/package.json` override `"postcss": "$postcss"` | Unblocks Dependabot's postcss security bump (override literal conflicted with the direct dep); lockfile-neutral | `frontend/package.json` |
| Finished SEO plan archived; this audit + appendices + new `tasks/todo.md` | Plan hygiene per `CLAUDE.md` | `tasks/`, `docs/` |

**Merging this PR deploys the backend** (the gate test lives under `backend/`, which is what
triggers CD; there is no other lever — `workflow_dispatch` never deploys and the 16 July run is
past GitHub's 30-day re-run window). The migrations are a pure no-op (no new files since #633).
Founder pre-flight before merging, in Cloud SQL Studio or `gcloud sql connect` (read-only):

```sql
SELECT pid, state, wait_event_type, backend_type, application_name, now() - xact_start AS xact_age
FROM pg_stat_activity
WHERE datname = current_database() AND xact_start IS NOT NULL
ORDER BY xact_start;
```

If a session shows an old `xact_start` (minutes or more) with `state = 'idle in transaction'`,
`SELECT pg_terminate_backend(<pid>)` before merging. With the new `lock_timeout` the worst case is
now a failed job that prints the blocker, not a hang. After the deploy: `robots.txt` on the API
host returns `Disallow: /`; `/health/detailed` is healthy; a 31-request burst to
`/api/companies/AAPL/insiders` returns 429.

---

## 3. The three priorities

Ranked for an invite-only beta where product quality wins ties. Effort is engineer-days of
agent work; founder time is separate and mostly decisions and merges.

### Priority 1 — Make releases safe and ship what is already merged (reliability floor)

*Why first even under a quality lens:* nothing in priorities 2 and 3 can reach users until the
pipeline works, and the same design that hung on 16 July probably degraded production for six
hours with no record. A quality fix that cannot ship is not a fix.

Scope (beyond this PR):
- Catch-up deploy via merge of this PR; verify the post-deploy checklist in §2. **(founder: 30 min)**
- Confirm the 16 July incident window in Cloud Run 5xx/latency and Sentry; record a lesson if
  confirmed. **(founder: 30 min)**
- Decide the durable migration design: **(a)** keep "re-apply all" and require the DO-block guard
  for new files (already gated), or **(b)** a `schema_migrations(filename, sha256, applied_at)`
  ledger so applied files are skipped and converged ALTERs take no lock. (b) supersedes rule 3's
  wording and needs an ADR. Recommendation: (b), ~0.5 day, plus a Cloud SQL
  `idle_in_transaction_session_timeout` flag as a DB-side backstop. **(founder decision)**
- Minimum alerting so a 7-week gap cannot recur: uptime check on `/health/detailed`; Cloud Run
  job-failure alert; log-based alerts for circuit-open and generation failures; GitHub Actions
  failure notifications for the scheduled workflows; a scheduled workflow that runs the existing
  `prod-smoke` Playwright spec against production so frontend/backend skew is caught in a day.
  ~1 day + founder GCP console time.
- Frontend observability holes: import the Sentry SDK in `GlobalErrorBoundary` (today a silent
  no-op), set the Sentry source-map upload variables in Vercel, delete the dead frontend
  `signup_completed` helper (the event is emitted server-side), decide a pre-consent PostHog
  strategy. ~0.5 day + **founder: Vercel env vars**.
- Pricing page server rendering (`useSearchParams` bailout) and the contact meta-description
  entity: two small fixes on public sales surfaces. ~0.5 day.
- Platform currency: Node 20 → 22 across `engines`, `.nvmrc`, CI and the Vercel project; add
  `typescript` to Dependabot's major-ignore list. ~0.5 day.
- Dependabot triage (details in appendix 05 §A): merge #635, #636, #639, #640, #641, #642; close
  #629 (TypeScript 7 breaks ESLint) and #570 (superseded draft); split #651 after this PR lands
  (pandas 3.0.5 and friends now; edgartools 5.40→5.51 alone through the eval gate); do the Next.js
  bump by hand to ≥16.3.4 after fixing `GlobalErrorBoundary.tsx:52` and `globals.css:408`, then
  recreate #652. ~1 day.
- Backup posture: enable PITR + deletion protection on `earningsnerd-db`; monthly export to a
  lifecycle-managed bucket; one-page rehearsed restore runbook. ~0.5 day + founder console time.
- Fix the universe refresh (Wikipedia source is gone): switch to `--source fmp` with a key, or
  another keyless Nasdaq-100 source; add a committed-list age gate so CI, not a silent monthly
  job, surfaces staleness. ~0.5 day; **founder: FMP key decision**.

### Priority 2 — Close the summary-fidelity measurement gap, then arm the trust guards (core product quality)

*Why:* the summary is the product. Today the eval gate cannot see the failure class the founder
cares most about (causal/prose fabrication), three ready trust guards sit unarmed for lack of a
readout, and provider hiccups surface as user-visible errors.

Scope:
- **Prose-fidelity signal in the gate:** pin `mean_untraceable_dollar_figures` (figure-trace) as
  an eval dimension (WARN first, then floor); add a scheduled judged run (8 filings, `--runs 3`)
  so faithfulness is measured weekly even though the judge stays off in PR CI. ~1 day.
- **Make the measure-only channels observable, then decide:** roll the five audit counters
  (figure-trace, forward-quote, evidence-snap, machine-sections-only, quality gate) into the
  weekly data-quality report from persisted `raw_summary` audits; then take the arming decisions.
  Evidence auto-snap first — measured +0.17 citation fidelity when armed. ~1 day + **founder
  decision per flag**.
- **Real retry + fallback + telemetry:** delete the dead Gemini chain, add bounded backoff on the
  primary and an env-configured fallback base URL/model, log `usage` and `response.model` per
  summary so silent provider-side model changes are detectable. ~1 day.
- **Eval ↔ prod parity:** set `USE_STATEMENT_FINANCIALS` in the eval env (prod runs it on
  out-of-band), restore the JPM bank-gate facts (G5 re-arm), exercise the streaming branch in
  the eval runner, re-pin; fix the `--runs 1` single-veto flakiness. ~1 day.
- **Copilot correctness on live FPI filings:** add the currency directive (never bare `$` for
  CNY/TWD/EUR issuers) and scope numeric tools to the filing being viewed (today `_query_fact`
  defaults to the company's most recent fact, so an older filing's page can cite a newer figure);
  grow the Copilot golden set from 2 unverified entries. ~1.5 days.
- **Golden-set breadth where prod already serves uncovered forms:** 6-Ks (0 in the set, >50 %
  of new rows), a REIT/utility/insurer, small caps. ~1 day + model spend (~$10).
- **Reading surface on the filing page:** real risk titles (frontend derives one from the first
  clause when the model emits none; backend emits `title`), a mobile section jump-nav, a live
  region for streaming progress, title-cased company names. All visible on `/filing/3` today.
  ~1.5 days; both-theme preview check required by the design system.
- Smaller: section-recovery grounding (raw HTML, 6,000-char cap), delete the latent
  `previous_filings` prompt path with an AST pin, drain cached v1 summaries to v2 (**founder
  spend call ≈$0.05/filing**), three stale docs.

### Priority 3 — Summary coverage and data integrity for the beta universe

*Why:* a beta user who clicks a filing and finds no summary, a bank with the wrong revenue tag,
or a thin governance-6-K summary has experienced a quality failure regardless of how good the pipeline is.

Scope:
- **Universe-wide pregeneration:** latest 10-K + 10-Q for the 515-name universe in batches via
  the existing precompute machinery; add 10-Q to the weekly pregenerate. **Founder spend call:
  ~$25–50 one-time, then ~$3–15/month.** ~1 day.
- **Coverage, freshness and job health in the weekly report:** summary coverage of the universe,
  stub ratio, universe-list age, last-success per job (a `job_runs` heartbeat table). ~1 day.
- **Data correctness items with user-visible effect:** SIC backfill (prod `Company.sic` is NULL
  everywhere; bank revenue-tag selection depends on it) and graduate `USE_STATEMENT_FINANCIALS`
  to default-on in code; ingest amendments (10-K/A, 10-Q/A) or at least mark superseded
  originals; derive `fiscal_period` for 10-Q per-filing facts. ~2 days.
- **Rule-5 and rule-10 gates:** route `facts_service._fetch_companyfacts_sync` through the SEC
  limiter (a scheduled job currently bypasses it); AST allow-list test for `sec.gov` importers;
  URL-format validation at the Filing boundary and remove the `cik=0` fallback fabrication; unit
  tests for the NOT NULL listeners. ~1.5 days.
- **Sitemap and stub containment:** deploy the truthful sitemap (Phase 0), make `app/sitemap.ts`
  stop fetch-caching the upstream document (`cache: 'no-store'` with the route-level revalidate,
  or a sitemap index past 45k URLs) so `www` regenerates instead of serving the 16 July snapshot,
  add a regression test and correct `docs/SEO_AUDIT.md`. 6-Ks already have a summary path behind
  the FPI flag; ship the 6-K classifier (earnings vs governance vs press release) so the majority
  of new rows get the right prompt, and add 6-K golden-set entries. ~1.5 days.
- Dead-integration teardown (Market Movers/FMP/Finnhub consumers still mounted on public routes,
  one endpoint fans out to FMP unauthenticated). ~0.5 day.

### Not in the top three, tracked

SEO phases 2–3, dashboard "later" tier, competitive roadmap items, legal
(Terms §7e counsel pass, DPAs), Turnstile keys, MFA, retention purge jobs, Alpha Vantage licence.
All are in the inventory (appendix 06) with evidence and size.

---

## 4. Findings by area (condensed; evidence and detail in the appendices)

### 4.1 Deploy pipeline and CI — appendix 01

- Hang timeline, blocking statement, lock semantics, and the collateral-impact hypothesis: §1.
- 17 of 32 migration files issue a top-level `ALTER TABLE` on a pre-existing table; ~43 plain
  `CREATE INDEX IF NOT EXISTS` (none `CONCURRENTLY`); only one file uses the lock-free DO-block
  guard. The loop re-applies all 32 every deploy; PR #634 added none.
- Production-vs-main backend drift is exactly 8 files: truthful sitemap (prod runs two uncached
  full scans per hit and advertises stubs the frontend marks `noindex`), API-host robots
  `Disallow: /`, anonymous `force_refresh` removal on hot filings, 30/min/IP on `/insiders`,
  20/min/IP on `/search/full-text`, three test files. No frontend@main call depends on
  backend@main.
- Only a push to `main` touching `backend/` deploys; `workflow_dispatch` runs tests only; a
  cancelled deploy is not retried; the deploy concurrency group has no cancel-in-progress.
- `refresh-index-membership.yml` failed on 1 Aug and 1 Sep: Wikipedia's Nasdaq-100 article no
  longer has a constituents table (verified live). `data-quality-weekly.yml` is 8/8 green.
  `ops.yml` is dormant and still carries a push trigger for a branch that no longer exists on
  origin (a dead trigger; remove it).
- Plain `CREATE INDEX IF NOT EXISTS` (SHARE lock before the existence check) is outside the new
  gate by design and bounded only by `lock_timeout`; extending the gate is tracked with the
  ledger decision. The re-run `UPDATE` in `20260706_demote_null_fiscal_period_duplicates.sql` is
  the most plausible `statement_timeout` trip as `financial_fact` grows.
- Docs drift fixed in this PR; remaining: `lessons/arch-migrations-no-alembic.md` equates
  idempotent with safe (update when the ledger decision lands).

### 4.2 AI summary quality — appendix 02

- Pipeline map (11 stages) and guard ledger with prod truth: `AI_QUALITY_GATE` on;
  figure-trace, forward-quote, evidence-snap measure-only; `STREAM_SECTION_REVEAL` and
  `ENABLE_FPI_FILINGS` on in prod via `ci.yml`; `USE_STATEMENT_FINANCIALS` on in prod by hand but
  default False in code and off in the eval env.
- Measured: gate_fail 0.0, precision 1.0, coverage 1.0, recall 1.0 (all HARD, zero variance),
  citation_fidelity 0.689 (WARN). Not measured anywhere in CI: faithfulness/hallucination
  (judge-only, off), untraceable dollar figures, %/ratio prose figures, risks evidence,
  6-K forms (0 in golden set), banks (G5 dormant), sector breadth.
- Robustness: `_fallback_models` = `[deepseek-v4-pro, gemini-2.5-pro, gemini-2.5-flash]` sent to
  the DeepSeek endpoint; `max_retries = 1`; no per-summary `usage`/`response.model` logging;
  enrichment timeout drops excerpt and XBRL and sends 15k chars of raw HTML with no grounding.
- Rule 2 holds: the only cross-filing prompt code (`previous_filings_context`) is dead but present.
  Copilot numeric tools are company-scoped, not filing-scoped (P1, user impact is a hypothesis).

### 4.3 Data platform — appendix 03

- Live coverage: API sitemap (old code) lists 635 companies / 36,140 filings; `www` sitemap is a
  frozen 510 / 1,429 snapshot dated 16 July. 278/515 universe members have a company row.
  0/7 sampled recent filings summarised. Last 50 filing rows: 27 6-K, 21 10-Q, 1 10-K, 1 8-K.
- Jobs: 7 Cloud Run jobs on the 13 July image; job code unchanged since, so behaviour matches
  HEAD. No job heartbeat or failure alert. Weekly data-quality report works and is the only
  proactive production signal; it does not measure coverage, freshness, universe age or deploy state.
- XBRL: period-selection lesson is in code and tested; FPI currency correct. Gaps: amendments
  never listed; no explicit scale handling (10× swing only flags); 10-Q per-filing facts carry
  `fiscal_period=None`; `_fetch_companyfacts_sync` uses raw httpx to sec.gov outside the limiter
  (rule 5) inside a scheduled job.
- Integrity: NOT NULL listeners exist but are untested and the insert fallback fabricates
  `…/edgar/data/0/{acc}/` when `company` isn't loaded.
- Alpha Vantage personal-use tier is live in prod on a public surface (licence gate open).
  Retention policy is DRAFT with unimplemented purge jobs; compliance doc still names Gemini.

### 4.4 Frontend and live UX — appendix 04

- Live public pages are healthy where it matters: `/`, `/company/AAPL`, `/filing/3` server-render
  real content with per-page title, description, canonical and JSON-LD; stubs are
  `noindex,follow`; unknown ticker/id return real 404s; lowercase tickers 308 to canonical; no
  error strings anywhere. No frontend call targets a backend@main-only endpoint or parameter.
- **Sitemap pipeline is broken end to end (P0 for SEO):** `www` serves a 1,945-URL snapshot frozen
  at 16 July (with noindex stubs, without `/terms`), while the prod API's old sitemap returns
  36,781 URLs / 6.35 MB stamped "today". Hypothesis: `app/sitemap.ts` fetch-caches a payload
  that outgrew Next's data-cache limit, so the stale entry can never be replaced. Deploying
  backend@main shrinks the payload; the frontend fetch should also stop caching.
  `docs/SEO_AUDIT.md` wrongly marks this fixed.
- **`/pricing` server-renders only header and footer** (492 chars: no H1, plans, prices or FAQ):
  the whole page body sits inside one Suspense boundary whose fallback is a spinner, and
  `useSearchParams()` inside it suspends on the server, so the spinner is what ships. The filing
  page avoided this with a post-hydration read. Re-verified live by the lead.
- **The hero example `/filing/3` shows five consecutive `<h4>Risk Factor</h4>`** — the fallback
  title when the model emits none. A reader cannot scan risks; the screen-reader heading list is
  useless. Re-verified live by the lead.
- Homepage shows no filings-discovery section: Market Movers is flag-hidden and Notable Filings
  self-omits because `NOTABLE_FILINGS_ENABLED` is off in prod. The product's own output is not
  shown to visitors.
- Smaller: EDGAR-caps company names in H1/title ("MICROSOFT CORP"); literal `&apos;` in the
  contact meta description; generic titles and no `noindex` on login/register; no skip link; no
  mobile section navigation for 10-section summaries; no live region for streaming progress.
- Observability holes: `GlobalErrorBoundary` reports through `window.Sentry`, which the SDK does
  not set (silent no-op); Sentry source-map upload has no org/project/token anywhere in repo or CI
  (hypothesis: not uploaded, `silent: true` hides the warning); the frontend `signup_completed`
  helper is dead code (the event is emitted server-side by `posthog_client.py`); PostHog drops all
  first-visit events until cookie consent; the `prod-smoke` spec has no workflow, and the
  filing-page e2e self-skips in CI.
- Code gates are clean: design-system legacy-color grep 0 hits; font-var gate passes; components
  allow-list and query-key ESLint rule exist and match `CLAUDE.md`; 0 `any`/`@ts-ignore` in prod
  code; AI markdown renders through `react-markdown` without raw HTML; citation hrefs are
  scheme-checked. Prose-only rule to gate: raw `fetch` outside the 5 sanctioned SSE/ISR sites.
- Platform: Node 20 (`engines`, `.nvmrc`, CI) is past EOL; React 18 pin (ADR-0005) remains valid;
  TypeScript 7 PR #629 breaks ESLint (peer range) and should be closed with a Dependabot ignore.

### 4.5 Security and operations — appendix 05

- Auth is sound (HS256 with enforced key strength and full claim checks; rotated single-use
  refresh tokens with reuse detection; hashed single-use reset/verify tokens; DB-backed login
  lockout; invite-only enforced server-side; all 16 admin and 9 internal routes gated; rule 4
  holds). Findings are P2/P3: rule-8 drift at `main.py:21-29` (Sentry) and `config.py:511,514`, a non-constant-time
  admin-token compare, per-process rate limiters across 2 instances, Turnstile fails open with
  unknown prod key state, e-mails in two log lines, client Sentry ships console logs.
- Anonymous cost holes are live *because the backend never redeployed*; plus
  `GET /api/trending_tickers/refresh-prices` is unauthenticated and fans out to FMP (not covered
  by the July fix).
- `npm audit`: 22 advisories (16 high). Runtime-exposed: Next 16.2.10 (9 advisories; middleware
  bypass matters because `middleware.ts` is the UX gate; `next/image` optimizer DoS), nested
  sharp. Build-time: postcss (blocked by the override conflict fixed here), nanoid, fast-uri,
  browserslist, brace-expansion. Backend: pyasn1 (PR #642), yanked pandas 3.0.4. No dependency
  audit gate in CI on either side.
- Nothing pages anyone. Cloud SQL created without backup/PITR/deletion-protection flags
  (hypothesis: PITR off); no restore runbook or drill.

### 4.6 Unfinished work — appendix 06

55 items with evidence, status and size. Counts by area: AI quality 14, data 8, frontend 11,
SEO/growth 5, ops 15, billing 2. Sixteen features are built but dark behind flags. Ten items the
docs imply are open are verified done (auth cookie domain, perf quick wins, IMPLEMENTATION_PLAN
phases 0–4, $39 pricing, homepage A1/B1/B6, streaming reveal, eval pin package, data-quality
P0/P1 items, architecture refactor waves 0–3, analysis remediation A–C).

---

## 5. Founder decisions required

Engineering cannot resolve these; each unblocks work above.

1. **Migration design:** DO-block guard only (status quo, gated) vs. `schema_migrations` ledger
   (recommended; supersedes rule 3 wording, needs ADR).
2. **Arm or keep advisory** each trust gate after the readout: `AI_EVIDENCE_SNAP` (recommend arm
   first), `AI_FIGURE_TRACE_GATE`, `AI_FORWARD_QUOTE_GATE`.
3. **Spend:** universe pregeneration (~$25–50 one-time); drain cached v1 summaries to v2
   (~$0.05/filing); golden-set expansion runs (~$10); FMP key for the universe refresh.
4. **Which dark surfaces go live for beta:** Multi-Period Analysis (Pro flagship; prod flag state
   unknown), Notable filings (needs one job + seed + flag), Calendar (+ Alpha Vantage licence),
   Insiders.
5. **Alpha Vantage licence** — request commercial terms or run EDGAR-only.
6. **Legal:** Terms §7e counsel pass; processor DPAs; legal entity / governing law.
7. **`WAITLIST_MODE` intent** and the LAUNCH_CHECKLIST founder-only actions (GSC, Bing, apex
   307→308, Vercel plan, `NEXT_PUBLIC_EXAMPLE_FILING_ID`).
8. **Pro trial timing** and whether to delete the retired reverse-trial code.
9. **`USE_STRUCTURED_OUTPUT`** — still wanted post-v2 cutover? (approve a bake-off or delete).
10. **Housekeeping approvals:** close #570 and #629; merge the six safe Dependabot PRs; approve
    the dead-integration teardown; archive the FPI roadmap with a status block.
11. **GCP console actions only you can take:** PITR + deletion protection; uptime check and alert
    policies; Turnstile keys; confirm `REGISTRATION_MODE`/flag state via `ops.yml describe-service`.

---

## 6. Verification record (2026-09-04, this environment)

| Gate | Result |
|---|---|
| `ruff check .` (0.16.6 with explicit select; 0.15.8 identical) | All checks passed |
| `bandit -r app -ll` (1.9.4) | clean |
| `pytest` (fast lane) | 1,785 passed on `main`; 1,791 passed after changes (6 new gate tests) |
| `npm run lint` / `tsc -p tsconfig.ci.json` | clean |
| `vitest --run` | 85 files, 409 tests passed |
| `next build` | success |
| Playwright e2e against `next start` with CI env (`NEXT_PUBLIC_API_BASE_URL`, `WAITLIST_MODE=false`) | 17 passed, 3 skipped (env-gated) |
| Live site (curl): `/`, `/company/AAPL`, `/filing/3`, `/sitemap.xml`, API `/health` | 200; correct title/canonical/H1/summary/JSON-LD; API healthy |
| Live `/pricing` server HTML | no `<h1>`, no plan prices, no FAQ — client-side bailout confirmed |
| Live `/filing/3` server HTML | five `<h4>Risk Factor</h4>` — confirmed |
| Live API `robots.txt` | still `Allow: /` — confirms backend@main never deployed |
| Postcss override change | lockfile-neutral (see PR body) |

Limits: the sandbox cannot open external sites in a browser (the repo's opt-in production smoke
spec could not run; the server-rendered HTML was checked with curl instead). No GCP, Vercel,
Stripe, Sentry or PostHog access — everything marked *hypothesis* needs a console check. The clone
is shallow (232 commits, 7–16 July), so git archaeology covers ten days.

## 7. Method

Six read-only workstream agents with file:line evidence requirements and explicit
hypothesis labelling; the lead verified the highest-impact claims independently (CI job log,
ruff behaviour across versions, live HTTP checks, the CONCURRENTLY claim, prod flag list in
`ci.yml`). Reports are reproduced as appendices with lead corrections noted inline.
