# SEC Data Expansion — Strategic Master Plan

> **Status:** Proposal / awaiting approval
> **Author:** Architecture pass (autonomous discovery → evaluation → planning)
> **Date:** 2026-06-19
> **Scope:** Backend (`/backend`) + Frontend (`/frontend`)
> **North Star:** Make financial discovery seamless, fast, accurate, and beautifully presented in a minimalist dark UI.

---

## 0. Executive Summary (TL;DR)

The premise of this engagement — "should we adopt EdgarTools?" — is already settled. **`edgartools==5.36.0` is a core dependency** (`backend/requirements.txt:55`) and the SEC integration layer was rebuilt around it (issue #244 removed the legacy `sec-edgar-downloader` + `arelle` + `sec-parser` stack — see `backend/app/services/edgar/__init__.py:6-8`). The legacy architecture doc `backend/docs/plan_sec_pipeline.md` is **stale** and describes a `sec-parser`/`markdown_serializer` pipeline that no longer exists.

So this is **not an adoption decision; it is a depth-and-expansion decision.** The strategic findings:

1. **We are under-using an engine we already pay for.** EdgarTools `5.37.0` (released today, 2026-06-19; we are one minor behind) natively provides XBRL *standardization* (≈2,900 tags → ≈95 comparable concepts with Fama-French industry overrides), **Form 3/4/5 ownership parsing with automatic Rule 10b5-1 detection**, **13F holdings**, **EDGAR-wide full-text search**, a **near-real-time current-filings feed**, and multi-period statement *stitching* (`XBRLS.from_filings`). Today we call almost none of this — `FilingType` already enumerates `FORM_8K`, `FORM_3/4/5`, `FORM_13F` (`edgar/config.py`) but **zero extraction logic exists for any of them.**

2. **The four highest-ROI features are almost free.** Full-text "mention search", real-time filing alerts, peer/cross-company comparison, and insider/institutional signals can all be built on (a) capabilities already in our dependency tree and (b) free, keyless SEC endpoints — **with no new heavyweight dependency and no GPL/AGPL contamination.**

3. **The one true architectural gap is the data shape.** `Filing.xbrl_data` is a per-filing **JSON blob** (`backend/app/models/__init__.py:128-156`), not a normalized facts table. Cross-company, peer, and time-series queries are structurally impossible until we add a `financial_fact` table. This is the single schema change that unlocks the most product surface.

4. **The dominant risk is data trust, not availability.** EdgarTools' most common failure mode is a **silent wrong value** (scale/sign/period/standardization bugs — the maintainer attributes ~65% of issues to data quality), and it is **maintained by one person.** The mitigation is a **reconciliation gate** that cross-checks the parsed/standardized layer against the authoritative `data.sec.gov` `companyfacts` JSON for headline figures — not blind trust.

**Recommended sequencing (value-to-cost):** ① EDGAR full-text search → ② real-time filing alerts (the `NotificationPreferences` rails already exist, unfed) → ③ peer comparison via Frames API + a `financial_fact` table → ④ insider/13F signals → ⑤ fundamentals time-series charts. Detail in §2–§3.

---

## 1. Open-Source Landscape & Deep Technical Audit

### 1.1 Current state (grounded in the repository)

| Layer | What exists today | Reference |
|---|---|---|
| Engine | `edgartools==5.36.0`, wrapped behind a clean typed facade | `requirements.txt:55`, `edgar/__init__.py` |
| Client | `EdgarClient` — `get_company`, `search_company` (exact + fuzzy `find`), `get_filings` (amendment-aware, `islice`-bounded), `get_filing_html/markdown` (2× timeout) | `edgar/client.py` |
| XBRL | `EdgarXBRLService` — 3-tier extraction (filing's own `filing.xbrl()` → `companyfacts` API → `get_financials()`), accession-aware since #240, two-tier L1+L2 cache | `edgar/xbrl_service.py` |
| Extraction helpers | `instance_extractor.py` (`DURATION_CONCEPTS`, `INSTANT_CONCEPTS`, duration-window filtering), `statement_parser.py` (DataFrame → metric series) | `edgar/instance_extractor.py`, `edgar/statement_parser.py` |
| Resilience | Circuit breaker (5-fail → open, 30 s recovery), dedicated thread pool (`run_with_circuit_breaker`), per-process token-bucket rate limiter | `edgar/circuit_breaker.py`, `edgar/async_executor.py`, `services/sec_rate_limiter.py` |
| Identity | `set_identity(EDGAR_IDENTITY)` at import time | `edgar/client.py:47`, `edgar/xbrl_service.py:46` |
| Storage | `Filing.xbrl_data` = JSON blob; `FilingContentCache` = markdown/sections; `SummaryGenerationProgress` | `models/__init__.py` |
| Alert rails (built, unfed) | `Watchlist.last_alerted_accession`, `NotificationLog` (unique `user_id+filing_id+channel`), `NotificationPreferences` (`notify_8k`, `realtime` already modeled as Pro) | `models/__init__.py:112-126`, `models/notifications.py:30-64` |

**What we already extract** (richer than a first glance suggests — `xbrl_service.py:850-995`): revenue, net income, EPS basic/diluted, gross profit, operating income, operating cash flow, capex, total assets/liabilities, cash, shareholders' equity, long-term debt — plus *derived* free cash flow, gross/operating/net margin, and ROE/ROA.

**What the UI surfaces** (`frontend/app/filing/[id]/`, `company/[ticker]/`): AI narrative sections (executive snapshot, risks, MD&A, guidance, liquidity, trends), a financial metrics table, optional bar charts (flag-gated), stock quotes, hot/trending tickers. It is deliberately **narrative-first**, not a data-grid explorer.

**The gap between "extracted" and "surfaced" and "available upstream":**

- *Available in EdgarTools, never called:* 8-K event parsing, Form 4 insider trades, 13F holdings, full-text search, current-filings feed, multi-year stitched statements, segment/dimensional facts.
- *Structurally blocked:* anything cross-company or time-series, because `xbrl_data` is a per-filing blob with no queryable facts table.

### 1.2 EdgarTools — deep audit of the engine we already own

`edgartools` · MIT · **v5.37.0 (2026-06-19)** · Python ≥3.10 · docs at `edgartools.readthedocs.io` · **single maintainer (Dwight Gunning).**

**API surface that matters for expansion (verified against docs + source):**

| Capability | Call | Returns |
|---|---|---|
| Company entry | `Company("AAPL")` | props: `name, cik, tickers, sic, industry, shares_outstanding, public_float` |
| Typed filing object | `filing.obj()` | polymorphic: `TenK`, `TenQ`, `EightK`, `Form4`, `ThirteenF`, `Schedule13D/G`, `ProxyStatement`, … |
| 10-K object | `TenK` | `.business`, `.risk_factors`, `.mda`, `.financials`, `tenk["Item 1A"]` |
| 8-K object | `EightK` | `.items` (event codes), `.press_releases`, `.date_of_report` |
| Insider | `Form4` (`edgar.ownership`) | `.market_trades`, `.derivative_trades`, `.get_net_shares_traded()`, `.to_dataframe()`, **10b5-1 detection** |
| Institutional | `ThirteenF` | `.infotable`, `.holdings`, `.total_value` |
| Multi-period stitch | `XBRLS.from_filings([...]).statements.income_statement().to_dataframe()` | multi-year columns, concept-change handling |
| Standardization | `xbrl.standardization` / `get_default_mapper()` | adds `standard_concept` column; preserves as-filed labels |
| Full-text search | module-level FTS fn (name unverified: `find_filings`/`search_filings_full_text`) | filings matching free text, 2001→present |
| Real-time feed | `get_current_filings(form='', owner='include', page_size=100)` | `CurrentFilings`, paginate `.next()` |
| Fact query | `xbrl.facts.query().by_concept(...).by_period(...).to_dataframe()` | chainable fact view |

**Operational truths (source-verified, production-critical):**

- **Rate limiting is built in at ~9 req/s** (`pyrate-limiter`, deliberate margin under SEC's 10), overridable via `EDGAR_RATE_LIMIT_PER_SEC`. **It is per-process / in-memory only.** We *also* run `sec_rate_limiter.py` → two stacked limiters. **More importantly: with multiple Cloud Run instances, each has its own limiter and the *aggregate* can exceed SEC's 10 req/s → IP block.**
- **`set_identity()` is mandatory or it hangs.** Without an identity, EdgarTools calls `ask_for_identity()` which blocks on interactive `input()` — it would freeze a server worker. We correctly set it at import. ✅ It also mutates `os.environ` and calls `close_clients()`, so it must be set **once at startup, never per-request.**
- **Sync library.** No stable public async API; must be thread-pooled. We do this via `async_executor.py`. ✅
- **Caching:** HTTP response cache in `~/.edgar/_tcache` (submissions ~30 s, archives indefinitely); opt-in bulk local storage off by default. **Cloud Run's `~/.edgar` is ephemeral** → cold-start re-fetch of reference data on every new container.
- **Memory (#705):** an empty `Company` is ~100 bytes, but first property access loads 1–3 MB and **accumulates progressively** in long-lived processes. Bound any in-process company cache.

**Reliability profile:** hundreds of releases (multiple/week), two recent ground-up rewrites (XBRL engine in 4.0, HTML parser in 5.0). Reacts fast to SEC changes (when SEC rewrote index files back to 2002 on 2024-12-20 and broke `get_filings()`, it was fixed in ~a week). But PyPI status is still "Beta," and the **single-maintainer bus factor is the dominant structural risk.**

**The headline gotcha — silent wrong values (not exceptions):** the maintainer states ~65% of open issues are data-quality bugs. Concrete, verified-and-since-fixed examples (meaning the *class* recurs on new filers):
- Scale: ABNB rendered `1` and XOM EPS `0.00` from narrow "$ in millions" matching.
- Sign/weight: AAPL cash-flow AR shown `-6,682` vs filed `+6,682` (#712).
- Standardization drop: MRVL D&A ($348.6M) vanished from the standardized cash-flow (#839).
- Period/stitching (notably unreliable on 2013–2019 filings): MU returned **+$2M for a −$284M loss** (#814); ADI returned quarterly data for an annual 10-K (#812).
- **Section extraction:** a GS 10-K returned 669 KB of MD&A under `.business` because the parser misclassified the form — **silent, confidence 0.95, empty warnings** (#821). This matters because we feed extracted section text to the LLM.

**Action:** treat the standardized/stitched layer as *convenient but not authoritative*. For any number we display as fact, reconcile against `data.sec.gov` `companyfacts`/`companyconcept`. (§3.5, §5.)

### 1.3 Supplementary engines evaluated

| Tool | License | Status (2026) | Verdict for us |
|---|---|---|---|
| **SEC raw JSON APIs** (`companyfacts`, `companyconcept`, **`frames`**, `submissions`) | Public, keyless | Live, real-time | **ADOPT (direct `httpx`).** `frames` is the *only* cross-company-one-concept primitive. Authoritative cross-check for EdgarTools. |
| **SEC EDGAR Full-Text Search (EFTS)** `efts.sec.gov/LATEST/search-index` | Public, keyless | Live (2001→present) | **ADOPT.** Best ROI in the survey. No copyleft. |
| **SEC `getcurrent` Atom firehose** + per-company Atom | Public, keyless | Live | **ADOPT** for real-time alerts. Accession-keyed → trivial dedupe. |
| **SEC Financial Statement Data Sets** (quarterly `sub/num/tag/pre` TSV) | Public domain | Q1-2009→present, ~4–6 wk lag | **ADOPT for backfill.** `COPY` into Postgres staging → facts table. Sidesteps rate limit. |
| **Bulk `companyfacts.zip` / `submissions.zip`** (nightly ~3am ET, ~1.4/1.6 GB) | Public | Live | **OPTIONAL** nightly full refresh; reuses our XBRL JSON parser. |
| **Arelle** (`arelle-release`) | Apache-2.0 | v2.41.5, very active | **OPTIONAL, out-of-band only.** Only tool with real SEC **EFM validation**. Heavy/stateful — never in a request path. |
| **SimFin** (`simfin`) | MIT | v1.0.2 (2026-04-30) | **CANDIDATE** for pre-standardized fundamentals if we'd rather consume than compute. Free tier reduced coverage. |
| **datamule** | MIT | active | **CANDIDATE** — `monitor_submissions()` (free poller) / `stream_submissions()` (push, $5/mo) if we don't hand-roll the poller. |
| `sec-edgar-downloader` | MIT | v5.1.0, active | **SKIP** — download-only, overlaps EdgarTools. |
| `secedgar` | Apache-2.0 | v0.6.0, pre-1.0, light | **SKIP** — `core.rest` relevant but worse-maintained than going direct. |
| markdownify | MIT | active | **MINOR** — ad-hoc HTML fragment → markdown only. |
| **OpenBB** | **AGPL-3.0** | active | **REJECT** — SaaS source-disclosure landmine. |
| **py-xbrl**, **html2text**, **edgar-tool** (bellingcat) | **GPL-3.0** | active | **REJECT** — copyleft incompatible with closed-source SaaS. |
| **docling** | MIT | active | **REJECT for now** — multi-GB torch image; only if scanned PDFs enter scope. |
| **yfinance / yahooquery** | Apache/MIT | active | **FALLBACK ONLY** — Yahoo commercial-ToS risk; keep Finnhub/FMP primary. |
| `sec-parser`, `trafilatura`, `finsec`, `SECurityTr8Ker` | mixed | dormant/wrong-job | **SKIP.** |

**Licensing guardrail (non-negotiable):** no GPL/AGPL in the runtime dependency closure. That hard-excludes OpenBB, py-xbrl, html2text, and edgar-tool. EdgarTools (MIT) + raw SEC endpoints keep us clean.

### 1.4 Exact integration points in the repo

- **New SEC endpoints** → a thin `app/integrations/sec_api.py` (mirrors `integrations/finnhub.py` patterns) for EFTS + Frames + Atom, routed through `sec_rate_limiter.py` and a centralized User-Agent. *Do not* funnel these through EdgarTools.
- **Insider/13F/8-K extraction** → extend `EdgarClient` with `get_filing_object()` returning the `.obj()` typed object, plus `services/edgar/ownership_extractor.py` and `eightk_extractor.py` mirroring `instance_extractor.py`.
- **Facts table** → new model in `app/models/`, populated by a backfill job in `backend/scripts/` + the existing weekly Cloud Run cron.
- **Routers** → new `routers/search.py` (`/api/search/full-text`), `routers/peers.py` (`/api/companies/{ticker}/peers`), `routers/insiders.py` (`/api/companies/{ticker}/insiders`); extend `routers/filings.py` for stitched multi-period.
- **Alerts** → a poller service feeding the existing `NotificationLog` / `email_service.py` / Resend path; flip on `NotificationPreferences.notify_8k` / `realtime`.

---

## 2. UX-First Product Roadmap

Design language: minimalist dark, zero layout shift (reserve skeletons sized to final content), instant filtering (client-side where data is already loaded), progressive disclosure. Every feature below degrades gracefully — a failed SEC call yields a quiet empty-state, never a broken page (the existing fallback ethos).

### F1 — Filing Full-Text Search ("find every filing that mentions…")
- **User value:** "Show me every filing mentioning *going concern*, *material weakness*, *FDA approval*, or a competitor's name." A marquee capability competitors paywall.
- **Source:** EFTS (`efts.sec.gov`), keyless.
- **UX:** A command-palette-style search bar (⌘K) over the dark canvas; results stream as compact rows (ticker · form · date · highlighted snippet). Filters as pill toggles (form type, date range) that re-query without layout shift. Snippet highlights use the existing accent color.
- **Performance:** debounced input, server-side rate-limited + cached (EFTS shares the 10 req/s budget), 10 k deep-pagination cap respected with "refine your query" guidance.

### F2 — Real-Time Filing Alerts (light up the dormant rails)
- **User value:** "Tell me the moment a company on my watchlist files a 10-K/10-Q/8-K." The schema for this **already exists and is unused.**
- **Source:** SEC `getcurrent` Atom firehose (global) + per-company submissions JSON (watchlist-scoped).
- **UX:** Toggle in dashboard settings maps to `NotificationPreferences` (`notify_10k/10q/8k`, `digest`, `realtime`). In-app: an unobtrusive bell with a count; email via existing Resend templates. 8-K and `realtime` gated to Pro (already modeled).
- **Performance:** background poller (mirrors weekly cron pattern), accession-keyed dedupe via `NotificationLog` unique constraint — guaranteed idempotent under retries.

### F3 — Peer / Cross-Company Comparison
- **User value:** "How does this company's revenue growth / margins / ROE compare to its sector peers?" The most-requested capability the current blob schema cannot serve.
- **Source:** SEC **Frames API** (one concept across all filers) + EdgarTools **standardization** (so line items are comparable) + a new `financial_fact` table.
- **UX:** On the company page, a "vs Peers" panel — a small-multiples sparkline grid or a single normalized bar set (revenue growth %, gross/operating/net margin, ROE) with the subject company highlighted. Peers derived from SIC/industry (already on `Company`). Recharts, consistent with `FinancialCharts.tsx`.
- **Performance:** peer metrics precomputed into the facts table (no live fan-out on the request path); the page reads one indexed query.

### F4 — Insider & Institutional Signals
- **User value:** "Are insiders buying or selling? What are the big funds holding?" High perceived value, near-zero new data cost.
- **Source:** EdgarTools `Form4` (with **10b5-1 filtering** to suppress low-signal automated trades) and `ThirteenF` — **already in our dependency.**
- **UX:** A compact "Insider Activity" strip on the company page — net shares bought/sold over trailing 90 days, color-coded, with a "discretionary vs 10b5-1" toggle. A "Top Institutional Holders" mini-table from the latest 13F.
- **Performance:** extracted off-request and cached (Form 4 live throughput is only ~2–3 obj/s under the rate cap, so it must be background-populated).

### F5 — Fundamentals Time-Series Charts
- **User value:** "Show me 5 years of revenue, margins, FCF, and EPS at a glance."
- **Source:** EdgarTools `XBRLS.from_filings([...])` multi-period stitching → facts table.
- **UX:** Replaces the current/prior two-bar chart with a clean multi-year trend (area/line), with a quality badge when stitching confidence is low (honesty over false precision — extends the existing `ENABLE_QUALITY_BADGE` pattern).
- **Performance:** precomputed series in the facts table; chart reads one query, renders with no refetch.

---

## 3. Detailed Implementation Plan

### 3.1 Database changes

**New: `financial_fact` (the unlock).** Normalizes XBRL into a queryable shape — the prerequisite for F3 and F5.

```
financial_fact
  id              PK
  company_id      FK companies.id   (indexed)
  filing_id       FK filings.id     (nullable; backfill rows may precede a Filing row)
  concept         String  -- standardized concept, e.g. "Revenue", "NetIncome"
  raw_tag         String  -- as-reported us-gaap tag (audit trail)
  unit            String  -- USD, USD/shares, shares, pure
  period_start    Date    (nullable for instant facts)
  period_end      Date    (indexed)        -- duration end / instant date
  fiscal_year     Integer
  fiscal_period   String  -- FY, Q1..Q4
  value           Numeric
  form            String  -- 10-K, 10-Q
  accession       String  (indexed)
  source          String  -- 'edgar_xbrl' | 'companyfacts' | 'frames' | 'fsds'
  reconciled      Boolean -- passed the cross-check gate (§3.5)
  created_at      DateTime
  UNIQUE(company_id, concept, period_end, fiscal_period, unit)
  INDEX(concept, period_end)   -- peer queries
  INDEX(company_id, concept, period_end)  -- time-series
```

- **Migration:** add SQL to `backend/migrations/` (manual convention — no Alembic). Schema also auto-creates via `Base.metadata.create_all()` at startup, so the model addition is sufficient for new envs; the migration is for existing prod.
- `Filing.xbrl_data` JSON blob **stays** (back-compat for the summary path); the facts table is additive.

**New: `insider_transaction`** (for F4) — `company_id, accession, filed_date, insider_name, role, transaction_code, shares, price, value, is_10b51, acquired_disposed`.

**New: `institutional_holding`** (for F4) — `company_id, holder_cik, holder_name, accession, period, shares, value`.

**Extend `Filing`:** add `processed_facts_at` (nullable DateTime) to track which filings have been normalized into `financial_fact`.

No change required to the alert tables — `NotificationPreferences` / `NotificationLog` / `Watchlist` already suffice for F2.

### 3.2 New API endpoints

| Method · Path | Purpose | Notes |
|---|---|---|
| `GET /api/search/full-text` | EFTS query | params `q, forms, startdt, enddt, ciks`; cached; rate-limited |
| `GET /api/companies/{ticker}/peers` | F3 peer metrics | reads `financial_fact`; peers by SIC |
| `GET /api/companies/{ticker}/fundamentals` | F5 multi-year series | reads `financial_fact` |
| `GET /api/companies/{ticker}/insiders` | F4 insider activity | reads `insider_transaction` |
| `GET /api/companies/{ticker}/institutional` | F4 13F holders | reads `institutional_holding` |
| `POST /api/alerts/poll` | internal/cron — scan firehose, enqueue notifications | admin-token gated like `hot_filings/refresh` |

All follow existing conventions: `/api/` prefix, Pydantic response models in `app/schemas/`, JWT where user-scoped, Pro gating via the existing `require_entitlement` dependency for `realtime`/8-K/peer-export.

### 3.3 New backend modules

- `app/integrations/sec_api.py` — EFTS + Frames + Atom client (async `httpx`, centralized UA, via `sec_rate_limiter`).
- `app/services/edgar/ownership_extractor.py` — `Form4`/`13F` → typed rows (mirrors `instance_extractor.py`).
- `app/services/edgar/eightk_extractor.py` — `EightK.items` → event records.
- `app/services/facts_service.py` — normalize XBRL/Frames/FSDS → `financial_fact`, owns the reconciliation gate.
- `app/services/filing_alert_service.py` — poll firehose, dedupe, dispatch via `email_service`.
- `backend/scripts/backfill_financial_facts.py` — one-off + cron backfill (FSDS `COPY` or `companyfacts.zip`).

### 3.4 Security & rate-limiting protocol

- **Single rate-limit authority.** Today we have *two* limiters (ours + EdgarTools' internal 9/s). Reconcile: keep `sec_rate_limiter.py` as the authority for our *direct* `httpx` calls (EFTS/Frames/Atom); leave EdgarTools' internal limiter for *its* calls. Document that both are **per-instance**.
- **Cross-instance ceiling.** With N Cloud Run instances the aggregate SEC rate is N × limit. Either (a) cap `EDGAR_RATE_LIMIT_PER_SEC` and our limiter to `floor(10/expected_instances)`, or (b) front all SEC traffic through the single weekly-cron worker for bulk/poll workloads (preferred for backfill/alerts). Live request-path calls stay rare and cached.
- **User-Agent** is mandatory and centralized (`EDGAR_IDENTITY`) — already enforced; extend to the new direct-`httpx` client.
- **Set all `EDGAR_*` env vars before importing `edgar`** — config is read at import time.
- **Admin/cron endpoints** reuse the `X-Admin-Token` / `HOT_FILINGS_REFRESH_TOKEN` pattern.
- **No PII to external services**; EFTS/Frames calls carry only public tickers/CIKs/queries.

### 3.5 Reconciliation gate (the trust layer)

Because EdgarTools can return silent wrong values, `facts_service.py` enforces, before `reconciled=True`:
1. **Sign/scale sanity:** revenue ≥ 0; assets ≥ liabilities is *not* assumed but flagged; EPS within plausible bounds; magnitude vs. prior period within an order of magnitude (catches the ABNB/XOM scale bugs).
2. **Cross-source check for headline figures:** compare EdgarTools-parsed revenue/net income/assets against `data.sec.gov` `companyconcept` for the same accession; mismatch beyond tolerance → mark `reconciled=False`, prefer the authoritative API value, log a structured `fact_reconciliation_mismatch` event.
3. **Period correctness:** verify `period_end` aligns with `period_of_report` for the form (catches the MU/ADI period bugs).
Unreconciled facts are excluded from peer comparisons and flagged in the UI quality badge.

### 3.6 Edge cases

- Pre-2009 filings lack XBRL → `.xbrl()` is `None`; fall back to text, exclude from facts.
- `Schedule13D/G.obj()` can return `None` (#840) — null-check.
- EFTS deep-pagination cap ~10 k → guide refinement, don't silently truncate.
- 8-K event codes vary; map only the high-signal items (1.01, 2.02, 5.02, 8.01) initially.
- Form 4 throughput is rate-bound (~2–3/s) → strictly background.
- Cloud Run ephemeral `~/.edgar` → set `EDGAR_LOCAL_DATA_DIR` to a persistent path or warm reference data at startup to cut cold-start latency.

### 3.7 Phased rollout

- **P0 — Foundations (1 sprint):** bump `5.36.0 → 5.37.0` *with regression tests* (5.37 carries the NullHandler logging fix + Form 4/5 + section-detection regression fixes); silence `edgar` logger; reconcile rate-limit authority; set `EDGAR_LOCAL_DATA_DIR`; add reconciliation gate scaffolding.
- **P1 — Full-text search (F1):** `sec_api.py` EFTS + `/api/search/full-text` + ⌘K UI. Highest ROI, no schema change.
- **P2 — Real-time alerts (F2):** poller + dispatch on existing rails + dashboard toggles.
- **P3 — Facts table + peers + fundamentals (F3, F5):** `financial_fact`, backfill via FSDS, Frames-powered peers, stitched series, charts.
- **P4 — Insider/13F (F4):** ownership/13F extractors + tables + UI strips.

---

## 4. Agent Execution Strategy

How subsequent build sessions will be decomposed across specialized subagents to maximize parallelism and isolate risk. Each agent gets one focused mandate; the primary agent integrates, reviews diffs against `main`, and owns the reconciliation/quality bar.

**Wave A — parallel, independent (no shared files):**
- **`schema-migration` agent** → `financial_fact`, `insider_transaction`, `institutional_holding` models + `migrations/` SQL + model unit tests. Isolated to `app/models/` and `migrations/`.
- **`sec-api-integration` agent** → `app/integrations/sec_api.py` (EFTS/Frames/Atom) + integration tests with mocked SEC responses. Isolated to `integrations/`.
- **`extraction` agent** → `ownership_extractor.py` + `eightk_extractor.py` mirroring `instance_extractor.py`, with golden-file fixtures (real filings). Isolated to `services/edgar/`.

**Wave B — depends on Wave A:**
- **`facts-service` agent** → `facts_service.py` + reconciliation gate + `backfill_financial_facts.py`. Depends on schema + sec-api.
- **`api-router` agent** → new routers + Pydantic schemas. Depends on schema + services.

**Wave C — frontend, parallelizable per feature:**
- **`frontend-search` agent** (⌘K + results), **`frontend-peers` agent** (peer panel + charts), **`frontend-alerts` agent** (settings toggles + bell). Each scoped to its `features/` domain + components, behind a feature flag.

**Wave D — quality, run last and continuously:**
- **`edge-case-test` agent** → adversarial unit tests for silent-value classes (scale/sign/period), null-returns, pagination caps. Read-mostly; writes only `tests/`.
- **`security-review` agent** → run `/security-review` on the diff (rate-limit ceilings, admin-token gating, no-PII egress).

**Guardrails for every agent:** one task per agent; touch only the files in its mandate to avoid collisions; never bump a dependency without regression tests; prove behavior (tests/logs) before marking done; surface any silent-value or licensing surprise to the primary agent rather than working around it. The primary agent verifies each PR against the reconciliation gate and the "would a staff engineer approve this?" bar before merge.

---

## 5. Risk & Resilience Analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **EdgarTools silent wrong value** (scale/sign/period/standardization) | High (recurs per-filer) | High (wrong numbers shown as fact) | **Reconciliation gate (§3.5)**; prefer authoritative `companyconcept`/`companyfacts` for headline figures; quality badge on unreconciled data; never trust stitched/standardized layer blindly. |
| **EdgarTools single-maintainer / abandonment** | Low-Med | High | Pin exact version; vendor-lock isolated behind our `edgar/` facade (already done) so a swap touches one module; raw SEC JSON APIs are a documented fallback for every critical read; sponsor the project. |
| **SEC EDGAR layout/endpoint change** (e.g., the 2024-12-20 index rewrite) | Med | High | Favor stable JSON APIs over HTML scraping; circuit breaker already isolates failures; fall back to cached DB filings (existing pattern); monitor EdgarTools releases for fixes (historically ~1 week). |
| **Aggregate rate-limit breach across Cloud Run instances → IP block** | Med | High | Route bulk/poll traffic through the single cron worker; cap per-instance limits to `floor(10/instances)`; honor `Retry-After`; circuit breaker on 429. |
| **EdgarTools major-version breaking change** (4.0/5.0-class rewrites) | Med | Med | Pin exactly; gate upgrades behind the regression suite + golden-file fixtures; budget migration time. |
| **Cloud Run ephemeral storage → cold-start latency** | High | Low-Med | `EDGAR_LOCAL_DATA_DIR` on a persistent path or startup warm-up of reference data. |
| **Memory accumulation in long-lived workers (#705)** | Med | Med | Bound in-process `Company` cache; generator-based sequential processing; delete references after use. |
| **Licensing contamination (GPL/AGPL)** | Low (if disciplined) | High (legal) | Hard policy: no GPL/AGPL in runtime closure; EdgarTools (MIT) + raw SEC endpoints only; Arelle (Apache) out-of-band if needed. |
| **Yahoo ToS exposure (if yfinance used commercially)** | — | Med-High (legal) | Keep Finnhub/FMP primary; yfinance fallback-only, off-request, counsel review before any commercial reliance. |
| **Section misclassification feeding the LLM bad text (#821)** | Med | Med | Validate extracted section length/labels against expected form structure; the existing `QualityGate` can reject implausible inputs. |

**Resilience principles to encode:** (1) every external read has a cached fallback; (2) every displayed number is reconciled or visibly flagged; (3) the SEC integration is swappable behind one facade; (4) bulk/scheduled traffic is centralized to respect the global rate ceiling; (5) silent failure is the enemy — prefer loud structured logs and honest empty-states.

---

## Appendix — Stale documentation to retire

`backend/docs/plan_sec_pipeline.md` describes a `sec-parser` / `sec_edgar.py` / `markdown_serializer.py` pipeline that **no longer exists** (removed in #244). It should be archived or rewritten to reflect the EdgarTools-based architecture before it misleads a future contributor.
