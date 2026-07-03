# Earnings Calendar Strategy — from a dead FMP dependency to an owned EDGAR-core pipeline

**Date:** 2026-07-03 · **Status:** Recommendation (no code changes in this PR)
**Scope:** How to deliver a best-in-class US earnings-date calendar (all ~6,000+ US-listed companies,
confirmed + estimated dates) on the existing FastAPI / Postgres / GCP stack, within ~CHF 10/month.

Every factual claim below was verified against live endpoints or live policy pages on 2026-07-03;
sources are cited inline. Live-test details are in the [Verification log](#appendix--verification-log).

---

## TL;DR — the recommendation

1. **Stop building on FMP for calendar data.** The integration is dead for any new API key: FMP cut
   off all legacy `/api/v3` endpoints (every endpoint `fmp.py` calls) for accounts without a paid
   subscription predating 2025-08-31 — they return `403 "Legacy Endpoint"`. Even paid FMP tiers
   prohibit displaying data on a multi-user website without a negotiated Data Display Agreement
   (ToS §2.2.2). This single root cause explains both the dark calendar and the
   `"No symbols passed FMP validation"` trending failures.
2. **Build a small, owned earnings-events engine with SEC EDGAR as the permanent core** — the only
   source in this entire space that is public-domain and commercially safe forever:
   - **Reported (ground truth):** 8-K Item 2.02 detection — machine-readable `items` field, filed
     same-day 96.9% of the time (measured, n=576).
   - **Estimated (owned):** prior-year same-quarter announcement date + 364 days — **92% within
     ±7 days** (measured, n=493). This is the same class of heuristic Nasdaq says powers its own
     estimated entries. No ML model needed; the high bar for building one is *not* met.
3. **Bridge the pre-revenue gap with Alpha Vantage's free bulk calendar** (one CSV call = the entire
   US market 3 months forward, 6,270 symbols, EPS estimates; verified live). It is the most robust
   free feed mechanically — but its free tier is licensed for personal, non-commercial use, so it is
   a **bridge only** and must be licensed (email Alpha Vantage) or dropped at launch. The
   architecture makes it removable: it only *enriches* rows the EDGAR engine can produce on its own.
4. **Persist everything in Postgres and serve only from Postgres.** Today every dashboard render
   hits FMP live. Provider outages become invisible; the calendar keeps serving from the last good
   snapshot; confirmed-vs-estimated becomes a first-class column instead of a guess.
5. Total incremental cost: **≈ CHF 0.1/month** (one more Cloud Scheduler job). Unblocks the roadmap
   item `ENABLE_CALENDAR → on` (docs/competitive-strategy-roadmap-2026.md, "NOW" tier) that was
   deferred on 2026-06-28 specifically because it needed a paid FMP key.

Two production bugs found during this audit, worth fixing regardless of this strategy:
- `earnings_whispers.py` calls `https://www.earningswhispers.com/api?type=hot`, which now returns
  `302 → /doh?statusCode=404`. The client fails soft to `{}`, so hot-filings silently lost that
  signal (verified live 2026-07-03).
- `fmp.py`'s base URL (`config.py:244`) is the legacy `/api/v3` — dead for new keys as above, so
  provisioning a key today would not revive the current code.

---

## 1. What exists today (audit)

Two UI surfaces, one data path, no persistence:

| Piece | Behaviour today |
|---|---|
| `backend/app/integrations/fmp.py` | Async client pinned to legacy `https://financialmodelingprep.com/api/v3`. `fetch_earnings_calendar()` pulls a date-range window; `_parse_earnings_list()` keeps only **one event per symbol** (closest to today), discarding multi-quarter data. |
| `backend/app/services/calendar_service.py` | Watchlist calendar: fetches the **entire market calendar live from FMP on every dashboard render**, filters to watched tickers in Python. No cache, no DB, swallows errors → `[]`. |
| `backend/app/services/reporting_this_week_service.py` | Homepage "Reporting This Week": FMP Mon–Fri window ∩ ~60 hardcoded large caps, 6h in-memory cache, hides itself under 4 matches. |
| `backend/app/routers/dashboard.py` | `GET /api/dashboard/calendar/upcoming?days=14` (auth-gated). |
| `backend/app/routers/reporting_this_week.py` | `GET /api/reporting_this_week` (public; frontend revalidates 6h). |
| Frontend | `EarningsCalendar.tsx` (behind `NEXT_PUBLIC_ENABLE_CALENDAR`, **off in prod**) and `ReportingThisWeek.tsx`. Both render nothing when empty — failure is invisible. |

**Assessment:** the UI layer is good and reusable; the data layer is the problem.
- **Single point of failure** on an API that no longer works for new accounts (and whose ToS
  prohibits this display use even on paid personal tiers).
- **No persistence** — a provider blip empties the calendar; there is no last-known-good.
- **No confirmed/estimated distinction** — FMP's legacy feed never flagged it, and the schema has
  nowhere to put it.
- **Coverage capped** at watchlist ∩ provider window + 60 curated tickers; there is no market-wide
  surface, although the roadmap wants the calendar as a discovery surface.
- Useful assets already in place to build on: full SEC ticker↔CIK universe
  (`edgar/compat.py` caches `company_tickers.json`, 10,415 entries), hourly 8-K scanning for
  watched companies (`filing_scan_service.py`), SEC rate limiter + circuit breaker, the
  `Cloud Scheduler → POST /internal/jobs/*` pattern (`internal.py`), and dated-SQL migrations.

**Keep / fix / replace verdict: replace the data layer, keep the surfaces.** The existing services
become thin readers over a new Postgres table; the FMP client leaves the calendar path entirely.

---

## 2. Options comparison

All facts verified 2026-07-03 (live calls and/or current policy pages; details + URLs in the
appendix). "Licence" uses the required classification: **(a) permanent** = safe for a public
commercial product indefinitely; **(b) bridge** = defensible only pre-revenue/personal-stage, must
be replaced or upgraded before launch.

| Option | Coverage (US) | Bulk forward calendar? | Estimated-date quality | Confirmed flag? | Licence | Breakage risk | Cost |
|---|---|---|---|---|---|---|---|
| **FMP legacy v3** (status quo) | — | — | — | — | — | **Already dead** for new keys (403 since 2025-08-31) | — |
| **FMP stable, free tier** | ~87 whitelisted tickers, 1-month window | No (toy) | n/a | No | (b) — free tier personal-only; display on a multi-user site prohibited (ToS §2.2.1/§2.2.2) | Low | $0 |
| **FMP stable, Starter** | US exchanges, 1-yr range | Yes | Good (analyst-fed) | No | **(b)** — display requires a separate "Data Display and Licensing Agreement" (pricing-page footer) | Low | $22/mo (annual) |
| **Alpha Vantage free** | Full US market — 6,270 symbols verified | **Yes — one CSV call**, 3/6/12-month horizons | Good near-term; no methodology docs; occasional staleness reported | No (only sparse `timeOfTheDay`, ~4%) | **(b)** — ToS §2.a: personal, non-commercial; commercial needs written agreement | Low (stable corporate API, no scraping) | $0 (25 req/day; we need 1–2) |
| **Finnhub free** | US, whole-market range queries | Yes (window depth unclear; "1 month + new updates") | Known uncorrected wrong dates (issue #528) | No | **(b)** — every self-serve plan incl. $3,500/mo is "Personal Use"; commercial = contact sales | Low-med | $0 |
| **Nasdaq api.nasdaq.com** (unofficial) | Full US market per-day | Yes (~55–70-day window, measured) | Good; has `lastYearRptDt`, analyst counts | No | **(b)** — nasdaq.com ToS: personal, non-commercial licence + anti-scraping clause | Med (browser-UA gating, Akamai; unofficial) | $0 |
| **EarningsWhispers `/api/caldata`** (unofficial) | Full US market per-day | Yes (~2-month window, measured) | Best free quality — explicit **`confirmDate`** field | **Yes** | **(b)** — personal, non-commercial, no redistribution | **High** — Referer-gated; EW already broke the other endpoint this repo uses | $0 |
| **yfinance** (Apache-2.0 lib) | Full US via new bulk `Calendars` API | Yes (paged, 100 rows/req) | OK | No | Code (a), **data (b)** — Yahoo ToS bans automated collection, commercial use, competing feeds | **High** — 2024–26 saw repeated 429/401/curl_cffi breakage waves | $0 |
| **OpenBB** (AGPL-3.0) | = its providers (fmp/nasdaq/seeking_alpha) | Via Nasdaq provider | = Nasdaq | No | Code AGPL (viral for SaaS backend); data = underlying ToS | Med | $0 |
| **DoltHub `post-no-preference/earnings`** | Broad US; updated ~daily | Yes (SQL; future dates verified to +5 wks) | Unknown methodology; provenance unstated (Zacks-like) | No | **(b)** at best — dataset licence/provenance unstated | Med (volunteer-run) | $0 |
| **SEC EDGAR (native engine)** | **All SEC filers** incl. every US-listed operating company | Reported: yes (daily sweep). Estimated: **own pattern rule** | **92% within ±7d** (measured, n=493); precise for stable reporters | **Reported = hard ground truth** (8-K Item 2.02, same-day 96.9%) | **(a) — public domain (17 U.S.C. §105), free, rate-limited 10 req/s** | **Lowest** — statutory disclosure infrastructure | $0 |
| Paid feeds ruled out for now | EODHD ($99.99/mo tier), Twelve Data (Grow $79/mo), Polygon/Benzinga (paid add-on; has `date_status` confirmed/projected) | — | — | Some | Mostly personal-use at these tiers too | Low | ≥ $79/mo — over budget |

**Verdict.** No free *or* affordable-paid provider is licence-clean for a public commercial product —
they are all bridges. The only permanent foundation available at this budget is **SEC EDGAR itself**,
which happens to be the one source EarningsNerd already has deep infrastructure for. Therefore:
build the thin EDGAR-native engine as the owned core (reported detection + pattern estimates), and
use **Alpha Vantage** — the mechanically cleanest bridge (one bulk CSV/day, corporate API, no
scraping, generous horizon) — to sharpen near-term estimates and EPS consensus until launch.
EarningsWhispers' `confirmDate` is the only free confirmed-flag anywhere, but it rides an unofficial,
Referer-gated endpoint from a vendor that already broke one integration in this repo — optional
cross-check at most, never a dependency. yfinance/OpenBB/Nasdaq-direct add ToS exposure and breakage
risk without adding anything the AV+EDGAR pair doesn't already provide.

---

## 3. Recommended architecture

### 3.1 Sources and roles

| Layer | Source | Role | Licence class |
|---|---|---|---|
| Ground truth | **EDGAR 8-K Item 2.02** (EFTS daily sweep + existing hourly `filing_scan` for watched companies) | Flip events to `reported` with the actual date, bmo/amc from `acceptanceDateTime`, and the accession number (deep-link the 8-K — on-brand "trace to source") | (a) permanent |
| History / own estimates | **EDGAR submissions API** (per-CIK `items` history) + existing `Filing.period_end_date` | Per-company announcement pattern → `event_date = prior-year same-quarter announcement + 364d`, clamped to 10-Q/10-K statutory due dates; fills tickers/quarters no provider covers | (a) permanent |
| Bridge enrichment | **Alpha Vantage `EARNINGS_CALENDAR`** (1 CSV/day, `horizon=3month`) | Sharper near-term dates, EPS consensus, company names, next-quarter `fiscalDateEnding` | (b) bridge — replace or license at launch |
| Optional cross-check (off by default) | EarningsWhispers `/api/caldata/{date}` | `confirmDate` boost for the next ~2 weeks of events | (b) bridge, fragile |

**Confirmed vs estimated, honestly:** free sources cannot tell you a company *announced* its date
(that news lives on paid wires; EDGAR itself carries advance notices for only ~2% of issuers —
measured). So the product ladder is:

- `reported` — 8-K Item 2.02 exists. Hard fact, linkable to the filing.
- `estimated` with a **confidence** derived from signals we can actually observe:
  date stability across daily snapshots (Wall Street Horizon sells exactly this signal), proximity,
  source agreement, and presence of provider `timeOfTheDay`/EPS estimate.
- `confirmed` — reserved for when a source with a real confirmation flag is wired in
  (EW cross-check now, or a licensed feed later). The schema supports it from day one; the UI can
  say "Est." vs "Confirmed" vs "Reported" without a migration later.

This is more honest than what FMP gave the app before (undifferentiated dates), and it matches the
site's "honest labeling" brand value.

### 3.2 Build vs reuse — and the fate of FMP

- **Reuse:** both UI components; both existing endpoints (response shapes extended, not broken);
  `internal.py` job-trigger pattern; SEC rate limiter/circuit breaker; `compat.py` ticker↔CIK map;
  hourly `filing_scan` (8-Ks already scanned for watched companies — add an `items` check);
  migrations convention.
- **Build (small):** one table, one ingest service (~300 lines), one internal job route, one
  Cloud Scheduler job.
- **FMP:** *remove from the calendar path entirely* (it is unusable there for any key the founder
  can obtain today, and display-prohibited even on paid tiers). The remaining FMP uses — trending
  validation, quotes — are equally dead on legacy v3 and out of scope here. Decide separately:
  either drop price display in trending (SEC tickers file can validate symbol existence for free) or
  accept another bridge. Don't let that decision block the calendar.
- **Do not adopt:** OpenBB (AGPL, adds no source), yfinance (hostile upstream), finance_calendars
  (abandoned 2021), OhEarningsCal (no licence).

### 3.3 Postgres data model

One row per company-quarter, mutated in place as knowledge improves:

```sql
-- migrations/2026xxxx_create_earnings_events.sql
CREATE TABLE IF NOT EXISTS earnings_events (
    id                BIGSERIAL PRIMARY KEY,
    ticker            VARCHAR(12) NOT NULL,          -- normalised upper-case
    cik               VARCHAR(10),                   -- zero-padded; NULL until mapped
    company_name      TEXT,
    fiscal_period_end DATE,                          -- quarter being reported (AV fiscalDateEnding / XBRL)
    event_date        DATE NOT NULL,                 -- the calendar date (US/Eastern calendar day)
    event_time        VARCHAR(3),                    -- 'bmo' | 'amc' | 'dmh' | NULL
    status            VARCHAR(10) NOT NULL DEFAULT 'estimated',  -- 'estimated' | 'confirmed' | 'reported'
    confidence        VARCHAR(6)  NOT NULL DEFAULT 'medium',     -- 'high' | 'medium' | 'low'
    eps_estimate      NUMERIC,
    eps_actual        NUMERIC,
    source            VARCHAR(20) NOT NULL,          -- 'alpha_vantage' | 'edgar_8k' | 'pattern' | ...
    accession_number  VARCHAR(25),                   -- set when status='reported' → deep-link the 8-K
    prior_event_date  DATE,                          -- previous value when the date moved
    date_changed_at   TIMESTAMPTZ,                   -- when it moved (stability = confidence input)
    first_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at      TIMESTAMPTZ NOT NULL DEFAULT now(),  -- snapshot liveness (delisting hygiene)
    reported_at       TIMESTAMPTZ,                   -- 8-K acceptanceDateTime
    CONSTRAINT uq_earnings_events_ticker_period UNIQUE (ticker, fiscal_period_end)
);
CREATE INDEX IF NOT EXISTS ix_earnings_events_event_date ON earnings_events (event_date);
CREATE INDEX IF NOT EXISTS ix_earnings_events_ticker     ON earnings_events (ticker);
```

Notes:
- `UNIQUE (ticker, fiscal_period_end)` is the upsert key. AV's CSV carries `fiscalDateEnding`
  per row; pattern-derived rows compute it from the company's fiscal calendar (`Filing.period_end_date`).
- Volume is trivial: ~6.5k companies × 4 quarters ≈ 26k rows/year.
- SQLAlchemy model added alongside (schema auto-created at startup per project convention;
  the SQL file documents the migration for prod).

### 3.4 Ingestion & refresh (GCP)

Reuses the exact operational pattern already in production for filing-scan/digest:

```
Cloud Scheduler (daily 06:00 UTC, before US pre-market releases)
  └─ POST /internal/jobs/earnings-calendar-refresh   (X-Internal-Token, 202 + background task)
       1. EDGAR sweep (yesterday, ~5–10 requests):
          EFTS q="Results of Operations and Financial Condition", forms=8-K, hits=100, paginate;
          keep hits whose _source.items contains "2.02" (client-side filter — the &items= request
          param is undocumented and flaky; do not rely on it);
          map CIK→ticker via cached company_tickers.json;
          upsert status='reported', event_date=file_date (event date), reported_at=acceptance,
          event_time from acceptance hour (accepted ≤ 13:30 UTC ≈ bmo; ≥ 20:00 UTC ≈ amc).
       2. Alpha Vantage snapshot (1 request):
          GET EARNINGS_CALENDAR&horizon=3month → CSV (~6.3k rows);
          upsert estimated rows on (ticker, fiscalDateEnding); never overwrite status='reported';
          if event_date changed → prior_event_date + date_changed_at.
       3. Recompute confidence for open rows; mark rows unseen for 14 snapshots as low/hidden.
Existing hourly filing_scan (watched companies): when an upserted 8-K has "2.02" in items,
  upsert the reported event immediately → intraday freshness where users actually look.
Quarterly (or one-off backfill) job: per-CIK submissions JSON for calendar tickers
  (~6k requests at ≤8 req/s ≈ 13 min, inside SEC fair-access) → historical 2.02 dates →
  pattern estimates for quarters beyond the provider horizon.
```

Serving: `GET /api/dashboard/calendar/upcoming` and `/api/reporting_this_week` become **DB reads**
(plus the future public `/api/calendar?from=&to=`). No provider call ever happens on a render path.

### 3.5 Reconciliation logic

Precedence (highest wins), applied at upsert time:

1. **`edgar_8k` reported** — terminal. Sets `status='reported'`, actual `event_date`,
   `accession_number`, `event_time` from acceptance hour. Nothing may override it.
2. **Provider (AV) date** for a not-yet-reported quarter — overwrite `pattern` dates; on
   AV-vs-previous-AV change, record `prior_event_date`/`date_changed_at`.
3. **`pattern` estimate** — only fills rows the provider doesn't cover (or post-launch, becomes the
   primary when AV is dropped/unlicensed).

Conflict & hygiene rules:
- Provider date in the past but no 8-K within 2 business days → treat as stale-provider case:
  keep `estimated`, drop confidence to `low` (do **not** show as reported; the 8-K is the only
  proof of reporting).
- AV disagrees with pattern by >14 days for an event >30 days out → prefer AV, confidence `medium`
  (analyst-informed beats arithmetic, but flag it).
- Confidence: `high` = reported, or ≤14 days out AND date unchanged ≥7 snapshots;
  `medium` = ≤45 days out, single source, stable; `low` = pattern-only, recently moved, or stale.
- A date that slips past its estimate is a mild bad-news signal (Bagnoli et al. 2002; deHaan et al.
  2015) — future product surface ("delayed vs usual schedule" chip), free differentiation.

### 3.6 Cost

| Item | Monthly |
|---|---|
| Alpha Vantage free tier (1–2 of 25 req/day) | CHF 0 |
| SEC EDGAR (fair-access limits, we use ~10–20 req/day + quarterly backfill) | CHF 0 |
| Cloud Scheduler 4th job | ≈ CHF 0.10 |
| Cloud Run/SQL delta (one light daily job, 26k rows/yr) | ≈ CHF 0 |
| **Total incremental** | **≈ CHF 0.1/month** |

At launch (licensing gate): either (i) written AV commercial agreement — email
`premium@alphavantage.co`, cost unknown; (ii) run EDGAR-only (pattern estimates + reported ground
truth) at CHF 0 — fully owned, slightly softer far-future dates; or (iii) a licensed feed
(e.g. Polygon/Benzinga earnings add-on with real `confirmed/projected` status) once revenue exists.
The schema and reconciliation don't change in any branch — that's the point of the design.

---

## 4. Minimal first version → full build

### MVP (ship in ~1 day)

1. **Migration + model:** `earnings_events` as above.
2. **`earnings_calendar_ingest.py` service:** (a) AV CSV fetch/parse/upsert; (b) EFTS yesterday-sweep
   → mark `reported`. Both behind the existing circuit-breaker/rate-limiter utilities where SEC is
   involved. ~300 lines incl. tests (parsers are pure functions — unit-test with fixture CSV/JSON).
3. **`POST /internal/jobs/earnings-calendar-refresh`** (copy the filing-scan trigger pattern) +
   Cloud Scheduler daily 06:00 UTC.
4. **Rewire reads:** `calendar_service.upcoming_for_user` and `reporting_this_week_service` query
   `earnings_events` (same response shapes + new `status`/`confidence` fields). Delete their FMP
   calls. `EarningsCalendar.tsx` gets an "Est." chip when `status != 'reported'`.
5. **Flip `NEXT_PUBLIC_ENABLE_CALENDAR=true`** after one manual job run seeds the table.

Result on day one: both existing surfaces work for every US-listed company, keep working through
provider outages, and honestly label estimates — already ahead of the FMP design, at CHF ~0.

### Enhancements (in order)

- **P2 — pattern estimator + backfill:** quarterly submissions backfill (historical 2.02 dates) →
  own estimates beyond AV's 3-month horizon and for AV-missing tickers; confidence scoring from
  snapshot stability; watched-company intraday `reported` via the existing hourly filing_scan.
- **P3 — the discovery surface:** public `/calendar` week view (`GET /api/calendar?from=&to=`),
  grouped by day with bmo/amc lanes, linking to company pages; per-day SEO pages. This is the
  roadmap's `ENABLE_CALENDAR` "NOW" item, fully unblocked.
- **P4 — launch licensing gate (before first paying customer):** decide AV-commercial vs
  EDGAR-only vs licensed feed (§3.6). Also fix/remove the dead EarningsWhispers hot endpoint and
  decide trending's post-FMP fate (separate issue).

---

## Appendix — verification log

Live tests run 2026-07-03 from this environment; research agents independently verified policy
pages the same day.

**Alpha Vantage** — `GET https://www.alphavantage.co/query?function=EARNINGS_CALENDAR&horizon=3month&apikey=demo`
returned CSV `symbol,name,reportDate,fiscalDateEnding,estimate,currency,timeOfTheDay`; 6,270 unique
symbols, dates 2026-07-03 → 2026-10-01; 60% rows with EPS estimate (81% within 21 days);
`timeOfTheDay` 4% (23% near-term); weekday-sane (4 weekend rows). Face-validity: JPM 7/14 bmo,
GOOGL/TSLA 7/22, MSFT/META 7/29, AAPL/AMZN 7/30, NVDA 8/26; LEVI 7/8 pre-market matches Nasdaq's
independent row exactly. Free tier = 25 req/day ([support](https://www.alphavantage.co/support/));
function not premium-gated ([docs](https://www.alphavantage.co/documentation/#earnings-calendar));
paid tiers $49.99–$249.99/mo ([premium](https://www.alphavantage.co/premium/)).
[ToS](https://www.alphavantage.co/terms_of_service/) §2.a grants "personal, non-commercial use,
unless … agreed otherwise in writing"; §2.a.iii defines display to third parties as commercial.
Known staleness example: META date off by one day
([QuantConnect thread](https://www.quantconnect.com/forum/discussion/16606/reliable-api-for-upcoming-earnings-calendar/)).

**SEC EDGAR** — EFTS: `https://efts.sec.gov/LATest/search-index?q=…&forms=8-K&startdt=…&enddt=…&hits=100`
→ every hit carries `_source.items`; phrase query `"Results of Operations and Financial Condition"`
narrows to Item-2.02 filers; the request-side `&items=` filter behaved inconsistently across
identical calls — filter client-side. ~1.4k Item-2.02 8-Ks in April 2026 (≈25.8% of 5,314 8-Ks;
ground-truthed on a 120-filing sample). Submissions API (`data.sec.gov/submissions/CIK##########.json`)
carries `items` + `acceptanceDateTime` per 8-K (AAPL earnings 8-K accepted 20:30:41 UTC, ~30 min
after the 16:30 ET release). Timing (n=576 Item-2.02 8-Ks, 20 companies): 96.9% filed same day;
acceptance clusters 44% pre-market / 53% after-close; post-17:30 ET submissions disseminate next
morning ([SEC filing-status guide](https://www.sec.gov/submit-filings/filer-support-resources/how-do-i-guides/determine-status-my-filing)).
Legal basis: [Form 8-K](https://www.sec.gov/files/form8-k.pdf) Item 2.02 (mandatory on public
announcement of completed-period results; 4-business-day outer deadline; furnished-not-filed
irrelevant to detection). Caveats: micro-caps that skip press releases have no 2.02; FPIs file 6-K
(no items). Advance notices of future dates on EDGAR ≈ 2% of issuers (8 hits for
"will report its financial results" in April 2026 vs ~1.4k 2.02s) — forward dates must come from
elsewhere. Estimation benchmark (n=493 pairs, 20 large/mid caps): prior-year same-quarter + 364d →
median error 0d, 56% ±1d, 65% ±3d, **92% ±7d**, 98% ±14d. Literature: deHaan et al. 2015 (mean
scheduling lead 15.7d; 81.6% of firms change EA weekday within a year → prefer day-count over
weekday-matching; [PDF](https://www.wallstreethorizon.com/upload/SSRN-id2545966_dehaan.pdf)),
Bagnoli et al. 2002 (delay ≈ bad news, [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=177209)),
Boulland & Dessaint 2017 ([SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2537184)),
Johnson & So 2018 ([SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2480662)).
[Nasdaq states](https://www.nasdaq.com/market-activity/earnings) its estimated entries use
"an algorithm based on a company's historical reporting dates" — same class of heuristic.
Access: free, [10 req/s + declared User-Agent](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data);
US-government work → public domain (17 U.S.C. §105). Prior art: same-approach commercial dataset
[sec-api.io Item 2.02, 2.28M records](https://sec-api.io/datasets/earnings-results-form-8-k-item-2-02);
[edgartools](https://github.com/dgunning/edgartools) (MIT, active) exposes `filing.items` if we
ever want a library instead of raw calls.

**FMP** — legacy cutoff: changelog "Legacy routes now auth-gated" 2025-08-27
([changelog](https://site.financialmodelingprep.com/developer/docs/changelog)); 403 body
"only available for legacy users who have valid subscriptions prior August 31, 2025" reproduced
across [FinanceToolkit #190](https://github.com/JerBouma/FinanceToolkit/issues/190) (2025-08-29),
[FinRobot #73](https://github.com/AI4Finance-Foundation/FinRobot/issues/73),
[firestocks #6](https://github.com/sthocs/firestocks/issues/6),
[how-to-stock #280](https://github.com/Abhiek187/how-to-stock/issues/280),
[claude-trading-skills #58](https://github.com/tradermonty/claude-trading-skills/issues/58) (403
even on a paid sub started 2026-04). Free tier: 250 calls/day; earnings calendar on free =
~87-ticker sample + 1-month window per the [pricing matrix](https://site.financialmodelingprep.com/developer/docs/pricing)
(FAQ says paid-only). Starter $22/mo annual. [ToS](https://site.financialmodelingprep.com/terms-of-service)
§2.2.2: "prohibited from showcasing FMP Services or Data on platforms including but not limited to
websites … designed for utilization by multiple individuals, irrespective of whether such usage is
complimentary or paid"; pricing footer: display/redistribution "requires a specific Data Display
and Licensing Agreement with FMP."

**Finnhub** — [docs](https://finnhub.io/docs/api/earnings-calendar): free tier note "1 month of
historical earnings and new updates", fields incl. `hour` bmo/amc/dmh; 60 calls/min; US-only on
free per pricing feature table. [ToS](https://finnhub.io/terms-of-service): "All plan listed on
Finnhub website is strictly for personal use … Personal plan can't be used by any business even
internally without a written approval." Data-quality:
[wrong forward date, uncorrected — issue #528](https://github.com/finnhubio/Finnhub-API/issues/528);
[fiscal-vs-calendar year gotcha #437](https://github.com/finnhubio/Finnhub-API/issues/437).

**Nasdaq (unofficial)** — `GET https://api.nasdaq.com/api/calendar/earnings?date=2026-07-08` →
200 with browser UA (connection reset for curl/requests UAs); rows incl. `epsForecast`, `noOfEsts`,
`lastYearRptDt`, `time-*`; forward window ~55–70 days (probes: 8/6 → 535 rows, 9/10 → 0; corroborated
by [finance_calendars #1](https://github.com/s-kerin/finance_calendars/issues)). No confirmed flag.
[nasdaq.com ToS](https://www.nasdaq.com/legal) (eff. 2026-05-11): §6 personal, non-commercial
licence; §7 anti-scraping/automated-capture. Wrapper
[finance_calendars](https://github.com/s-kerin/finance_calendars) abandoned (last push 2021-08-22).

**EarningsWhispers** — repo's `?type=hot` endpoint: `302 → /doh?statusCode=404` (dead).
`/api/caldata/{YYYYMMDD}` returns 200 with `Referer: https://www.earningswhispers.com/calendar`
(204 without): fields incl. **`confirmDate`** (7/21: 33/53 confirmed; 8/6: 23/420), ~2-month
horizon. [Usage terms](https://www.earningswhispers.com/usage): personal, non-commercial; no
redistribution without written consent.

**yfinance** — [repo](https://github.com/ranaroussi/yfinance) Apache-2.0, active (1.5.1,
2026-06-28); new bulk `Calendars.get_earnings_calendar` (Yahoo visualization endpoint, 100-row
pages). Breakage waves: [#2125](https://github.com/ranaroussi/yfinance/issues/2125) (429, 2024-11),
[#2422](https://github.com/ranaroussi/yfinance/issues/2422) (YFRateLimitError, 141 comments),
[#2533](https://github.com/ranaroussi/yfinance/issues/2533) (401 crumb wave, 71 comments),
mandatory `curl_cffi` ([#2449](https://github.com/ranaroussi/yfinance/issues/2449)).
[Yahoo ToS](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html) §2.4(i)/(j)/§2.5: no
automated collection, no competing data feed, no commercial use. yfinance's own disclaimer:
"personal use only … research and educational purposes."

**OpenBB** — [repo](https://github.com/OpenBB-finance/OpenBB) active (4.7.2, 2026-05-26) but
AGPL-3.0-only since 4.2.0; earnings-calendar providers = fmp / nasdaq / seeking_alpha / tmx —
[the Nasdaq fetcher calls the same api.nasdaq.com endpoint](https://github.com/OpenBB-finance/OpenBB/blob/develop/openbb_platform/providers/nasdaq/openbb_nasdaq/models/calendar_earnings.py);
adds no data source.

**Others** — EODHD: calendar in the $99.99/mo All-In-One tier ([pricing](https://eodhd.com/pricing));
Twelve Data: `/earnings_calendar` Grow $79/mo+, 40 credits/call, individual plans non-commercial
([docs](https://twelvedata.com/docs)); Polygon/Massive: Benzinga Earnings paid add-on — includes
`date_status` projected/confirmed ([docs](https://massive.com/docs/rest/partners/benzinga/earnings)) —
the natural licensed upgrade when revenue exists; Tiingo: no earnings-calendar product; Alpaca:
corporate-actions only. Open dataset: [DoltHub post-no-preference/earnings](https://www.dolthub.com/repositories/post-no-preference/earnings)
(daily-ish updates, future dates verified, provenance/licence unstated).
