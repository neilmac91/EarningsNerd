# Homepage sections review — Trending Filings & Market Movers

**Date:** 2026-07-06 · **Reviewer:** Claude (fractional product/staff-eng review, session `claude/homepage-sections-review-7k2120`)
**Scope:** keep/fix/kill for the two sections + their plumbing. No code changed in this session.
**Method:** live prod GETs (read-only), line-level code verification, in-repo prior research (`tasks/earnings-calendar-strategy.md`, 2026-07-03), two parallel web-research subagents (cited), adversarial fresh-context passes per verdict.

---

## TL;DR verdict table

| Section | Verdict | Confidence | One-line why |
|---|---|---|---|
| **Market Movers** (`TrendingTickers` → `/api/trending_tickers`) | **HIDE now — permanent for the current concept** (flag-gated removal; retire backend in follow-up) | **High** | Its data path is unrevivable as built (FMP legacy API dead since 2025-08-31; display use prohibited even on paid tiers), every candidate replacement source is license-gray at $0, and a hype-ticker strip contradicts the roadmap's own "calm signal, never casino" posture on what is now a Pro sales surface. |
| **Trending Filings** (`HotFilings` → `/api/hot_filings`) | **FIX — minimal honest fix now (~1 day), EDGAR-wide rebuild only if 30-day metrics earn it** | **Medium-high** | The concept (fresh, notable filings → one-click AI summary) is the product's core discovery loop and roadmap item A3's hook; the failure is mechanical (no dedupe, no freshness floor, dead paid signals, dishonest badges) and cheap to fix honestly; coverage stays own-DB until engagement data justifies the market-wide EDGAR rebuild. |

Both verdicts ship with instrumentation (Phase A) so the 30-day keep/kill call is data-driven — today CTR is unknowable.

---

## 1. The bar (written before researching fixes)

Judged against what the hero search, Popular Companies banner, QuickAccessBar, and the calendar surfaces (ReportingThisWeek + `/calendar`) already provide. Overlap counts **against** a section.

**Trending Filings** earns its slot only if it shows:
- **Content:** filings selected by a signal that plausibly proxies "notable" — high-signal form types (10-K/10-Q, 8-K 2.02/5.02/1.01, S-1, 13D/G), real demand (searches, news), or market breadth — with **at most one card per company**.
- **Freshness:** filed today / this week. A "trending" card about a 28-day-old routine 6-K is worse than no card.
- **Honesty:** every badge and label describes the actual selection mechanism; the section title matches what the algorithm does.
- **Distinct value:** push-discovery of "what just hit EDGAR that matters" with a one-click AI summary — the only homepage section that surfaces the *product's actual output* for new filings. Hero search is pull (you must know the company); Popular Companies is static curation; the calendar is *upcoming earnings*, not filed documents. So a genuinely fresh, honest version has a real, non-overlapping job.

**Market Movers** earns its slot only if it shows:
- **Content:** actual same-day price/volume movers (gainers/losers/actives) or genuine social trending, with live prices, from a source licensed for display on a commercial multi-user site.
- **Freshness:** intraday; "today" in the subtitle must mean today.
- **Honesty:** the source label matches the source actually serving the data; no internal error strings; a Refresh button that refreshes.
- **Distinct value — and this is where it structurally struggles:** EarningsNerd's product is filing analysis, not quotes. The link from "NVDA is up 3%" to "read an AI filing summary" is one hop weaker than every other section's link. The roadmap (D3, and `pulse_service.py`'s own docstring) explicitly rejects the "Stocktwits casino" framing: *"calm signal, never casino."* A price-hype strip must clear both the data bar **and** the brand bar. Overlap: Popular Companies + QuickAccessBar already give one-click access to the mega-caps that dominate any movers list.

---

## 2. Current state — verified live, 2026-07-06 (~16:40 UTC)

All read-only GETs; response files preserved in session scratchpad.

### 2.1 Symptoms still hold — exactly

- `GET https://api.earningsnerd.io/api/hot_filings?limit=4` → **four BABA 6-K cards** (filed 2026-06-26, 06-18 ×2, 06-09), each `buzz_score 3.5`, components `filing_velocity 2.0 / filing_type_bonus 1.5` → PULSE shares **57% / 43%**, `sources: ["recency", "filing_velocity"]` with `recency: 0.0`. [FACT]
- `GET https://api.earningsnerd.io/api/trending_tickers` → `source: "curated"`, `status: "fallback"`, all five tickers (NVDA/TSLA/AAPL/MSFT/AMZN) with `price: null`, and `message: "Showing curated fallback trending tickers. Last error: No symbols passed FMP validation"`. [FACT]
- `GET https://www.earningsnerd.io/` → the fallback banner **including the internal error string is server-rendered into the public homepage HTML** (ISR prefetch), visible to logged-out visitors and crawlers. "Alibaba" appears 14× in the page source. [FACT]

### 2.2 Dishonest labeling, itemized

| Claim on screen | Reality | Where |
|---|---|---|
| "🔥 Trending Filings" | 20 most recent rows of our own DB re-sorted; no demand/market signal survives in prod | `hot_filings.py:124-131`, live payload |
| "Recent" badge on every card | `sources` always starts with `"recency"` regardless of score — badge appears by construction, incl. on a 27-day-old filing | `hot_filings.py:274`, live payload (`recency: 0.0` + badge) |
| "Active Filer" badge | ≥2 filings in 30 days *among ingested filings* — trivially true for any FPI filing 6-Ks | `hot_filings.py:157-168` |
| "What's moving in the market today" | Hardcoded 5-ticker list, no prices | `trending_service.py:473-480`, live payload |
| "SOURCE: CURATED" + raw `Last error: …` | Internal diagnostics printed to end users | `trending_service.py:140-142` → `TrendingTickers.tsx:285-289` |
| Footer "Data from Stocktwits & FMP" | Rendered unconditionally, even when `source: "curated"` | `TrendingTickers.tsx:303-323` |
| Refresh button (Market Movers) | Re-reads the same ≤10-min backend cache; router never passes `force_refresh` | `trending.py:33`, `TrendingTickers.tsx:276` |
| Analytics `source: 'stocktwits'` on `market_mover_clicked` | Hardcoded — click data is mislabeled even when serving the curated fallback | `TrendingTickers.tsx:94-102` |
| Empty state "No major filings in the last 24 hours" | The query has no 24h window at all | `HotFilings.tsx:101` |

Corrections/additions to the prior code map found during verification:
- `/api/hot_filings` **does** expose `force_refresh` publicly (`hot_filings.py:15`) — the frontend just never sends it. (Minor abuse surface: unauthenticated cache-busting triggers the external fan-out.)
- The router also has a zero-score "recent filings" fallback (`hot_filings.py:20-52`) that contradicts any future self-omission behavior.
- **Alpha Vantage is NOT unused** — `earnings_calendar_service.py:438` consumes it for the calendar engine (bridge source per strategy doc). It is unused *by these two sections* only.

### 2.3 Root causes — confirmed, and they reproduce the screenshots

**Market Movers.** Hypothesis (b) — FMP-side breakage — is confirmed; (c) is refuted.
- Live Stocktwits trending (fetched this session): 30 symbols, **27 legitimate US common stocks** on NASDAQ/NYSE (rank 1 = WULF/TeraWulf), 1 ETF, 1 crypto, 1 OTC ADR. The upstream source is healthy, so symbols are not "legitimately failing validation." [FACT]
- In-repo prior research, verified live 2026-07-03 (`tasks/earnings-calendar-strategy.md`): **FMP cut off all legacy `/api/v3` endpoints — every endpoint `fmp.py` calls — for accounts without a paid subscription predating 2025-08-31; they return `403 "Legacy Endpoint"`.** The doc names our exact symptom: *"This single root cause explains both the dark calendar and the `No symbols passed FMP validation` trending failures."* [FACT — prior verified research; consistent with everything observed]
- Mechanism (verified in code): `fmp.py:get_profiles` catches the HTTP error per batch and returns `{}` (fmp.py:206-212) → `_validate_symbols_with_fmp` treats every symbol as `profile None` → **caches `is_valid: False` for 6h per symbol** (trending_service.py:393-399) → returns `[]` → `_last_error = "No symbols passed FMP validation"` (trending_service.py:239). The error message is therefore *itself misleading*: symbols didn't fail validation, the validator's upstream is dead. Fresh fetch → None; in-memory cache empty (Cloud Run instance never had a success); persistent cache lives in `/tmp` in prod (trending_service.py:55) — ephemeral and only written on success → **curated fallback**, exactly as observed. Prices null because the fallback carries none and `refresh_prices` also rides dead FMP. Exchange-naming hypothesis (d) is moot (requests 403 before any exchange comparison); key-expiry (a) vs. account-class cutoff (b) can't be distinguished without prod secrets, but both are FMP-side and both are unfixable *within FMP's ToS* — even paid tiers prohibit multi-user display without a negotiated Data Display Agreement (ToS §2.2.2, per strategy doc). [FACT + one UNVERIFIED sub-detail: which exact FMP account state prod has]
- Note: even the FMP-unconfigured path would have "worked" (symbols pass through unvalidated, trending_service.py:317-326) — so prod definitely has a (dead) key configured. [INFERENCE, high confidence]
- ETF-set Redis tier is a no-op in prod (ADR-0004, no Redis) — L1-only, harmless here since FMP ETF fetch also 403s to an empty set. Every process restart re-runs the whole doomed pipeline. [FACT]

**Trending Filings.** All mapped root causes confirmed; the arithmetic reproduces the screenshot exactly.
- Candidate pool = 20 most recent `Filing` rows **of our own DB** (hot_filings.py:124-131) — and rows are ingested only by the hourly scan of *watched* companies (`filing_scan_service.py`) plus on-demand views. A watched, prolific FPI filer (Alibaba, frequent 6-Ks) floods the pool. [FACT]
- Live signal status: `recency` = 0 for anything >72h (nothing fresh ingested); `search_activity` = 0 (no searches for these companies in 7d); `earnings_calendar` = **dead** (FMP 403, above; the comment "replaces EarningsWhispers" is itself a tombstone — EW died earlier, verified 2026-07-03); `news_*` = **dead or unlicensed** (Finnhub `/news-sentiment` is a premium endpoint, finnhub.py:86; all Finnhub self-serve plans are personal-use-only per strategy doc; live components all 0.0). Which exact Finnhub failure mode (no key / free key on premium endpoint / rate limit) is UNVERIFIED without prod env — but all paths produce the observed zeros.
- Surviving signals: `filing_velocity` (normalized, BABA = max → 2.0 on every BABA filing) + `filing_type_bonus` (6-K → 1.5). Every BABA filing scores 3.5 > everything else → **four identical BABA cards, 2.0/(3.5)=57% / 1.5/3.5=43%**, tier "On the radar" (3.5 ≥ 3.0). No company dedupe exists anywhere in the chain (hot_filings.py:315-332). `sources` seeded with `"recency"` unconditionally (hot_filings.py:274) → "Recent" badge always. **Mechanism fully predicts all observed details.** [FACT]
- Ops: lazy 15-min in-memory cache per `limit` value; no scheduler. [FACT]

### 2.4 Licensing reality (from in-repo verified research, 2026-07-03 + this session's web research §4)

The homepage is now a sales surface for a paid product; this stops being pedantry:
- **FMP:** free tier personal-use-only; display on a multi-user site prohibited (§2.2.1/§2.2.2); legacy API dead anyway. Currently credited in the section footer. 
- **Finnhub:** every self-serve plan including $3,500/mo is "Personal Use"; commercial = contact sales. Feeds (nominally) Trending Filings.
- **Alpha Vantage:** free tier personal, non-commercial (ToS §2.a) — already accepted repo-wide as a *bridge only* for the calendar, "must be licensed or dropped at launch."
- **Stocktwits:** see §4 (research). The section title credits it today while serving a hardcoded list.
- **SEC EDGAR:** public domain (17 U.S.C. §105) — the only permanently license-clean source in this space, and the one this product already has deep infrastructure for (rate limiter, circuit breaker, ticker↔CIK cache, EFTS sweep in `earnings_calendar_service.py`).

---

## 3. Engagement evidence — what is and isn't knowable (Q4)

**Knowable today:** raw click counts and clickers for exactly two events — `hot_filing_summary_clicked` (HotFilings.tsx:160-164) and `market_mover_clicked` (TrendingTickers.tsx:94-102) — plus homepage `$pageview` as a weak denominator.

**Not knowable:** impressions (no section-view events) → **CTR is uncomputable**; scroll depth to these below-fold sections; whether Market Movers clicks were on real data or the curated fallback (the event's `source` property is hardcoded `'stocktwits'`); Refresh usage (untracked). **The gap is itself a finding:** both sections shipped without the instrumentation needed to ever evaluate them.

**PostHog queries for Neil to run** (all last 90 days unless noted):

| # | Query (Insights) | Question it answers |
|---|---|---|
| P1 | Trend: `hot_filing_summary_clicked`, weekly, total count + unique users | Does anyone use Trending Filings at all? Is it one power user or breadth? |
| P2 | Trend: `market_mover_clicked`, weekly, total + uniques | Same for Market Movers |
| P3 | Trend: `$pageview` where `pathname = '/'`, weekly | Denominator: pseudo-CTR = P1/P3, P2/P3 (undercounts real CTR — below-fold, but bounds it) |
| P4 | Breakdown: `market_mover_clicked` by `symbol` | If clicks are ≈ only NVDA/TSLA/AAPL/MSFT/AMZN, users have been clicking the *hardcoded fallback* (the `source` property can't tell you — it lies) |
| P5 | Funnel: `hot_filing_summary_clicked` → `$pageview` matching `/filing/.*` → summary-view/generation event | Does the section convert to actual product usage? |
| P6 | Breakdown: `hot_filing_summary_clicked` by `symbol` | Concentration check (expect ~all BABA lately — corroborates the degeneration window) |

Run P1–P4 before approving Phase B if you want to overrule either verdict with data; the verdicts below don't depend on them (both sections are indefensible *as shipped* regardless of clicks), but P1/P5 calibrate how much to invest in the Trending Filings rebuild.

---

## 4. External landscape (web research, cited)

All URLs accessed 2026-07-06 by a fresh-context research subagent unless marked otherwise; `[curl]` = raw API response inspected live from this environment; "strategy doc" = `tasks/earnings-calendar-strategy.md`, whose claims were live-verified 2026-07-03.

### 4.1 Trending Filings candidates

| Source | What it enables | Cost / limits | License | Effort | Verdict |
|---|---|---|---|---|---|
| **EDGAR full-text search API** (`efts.sec.gov/LATEST/search-index`) [curl] | All filings by form + date across **all** companies, JSON, same-day fresh; hits carry ticker, 8-K `items` codes, SIC. `q` is optional — `?forms=8-K&startdt=2026-07-06&enddt=2026-07-06` returned all 80 8-Ks filed today | Free, keyless; SEC 10 req/s + declared User-Agent | Public domain (17 U.S.C. §105) | **S** (2–4h, one method in `app/services/edgar/`) | ✅ Core candidate. Caveats observed live: `from=` pagination 500s; exhibits are separate hits (dedupe on `adsh`); undocumented endpoint, shape change-prone |
| **EDGAR `getcurrent` Atom feed** [curl] | Freshest firehose — top entry observed **~14 min** after acceptance; form filter, 8-K item codes in entries; 100/page (hard cap verified) | Free, keyless; same SEC policy ([fair access](https://www.sec.gov/os/accessing-edgar-data), acc. 2026-07-06) | Public domain | **S** (2–4h) | ✅ Core candidate (freshest) |
| **edgartools** `get_current_filings()` (already a dependency; docs acc. 2026-07-06: [current-filings guide](https://dgunning.github.io/edgartools/guides/current-filings/); v5.40.1 released 2026-06-29) | Typed wrapper over the above with pagination; also parses Form 4s and 8-K items | Free | OSS; repo already depends on it | **S** (2–4h) | ✅ Easiest path. Caution: its HTTP calls bypass the repo's per-process SEC limiter — budget poll cadence (5–10 min cron, 1–3 req/poll) per CLAUDE.md rule 5 |
| **EDGAR daily/full index files** [curl] | Complete daily filing lists | Free | Public domain | S | ⚠️ Written ~10 PM ET — backfill only, not intraday |
| **8-K item-code materiality** (from the feeds above + `data.sec.gov` submissions [curl]) | Free "notable" ranking: 2.02 results, 1.01 material agreements, 5.02 exec departures, 2.01 M&A, 4.02 restatements, 1.03 bankruptcy; plus SC 13D, S-1, Form 4 cluster-buys | Free | Public domain | **S** (2–3h scoring layer) | ✅ This is the real fix for "notable" — the signal is *in the filing metadata*, no third party needed |
| **EDGAR log file data sets** ([page](https://www.sec.gov/about/data/edgar-log-file-data-sets), acc. 2026-07-06) | Actual EDGAR view counts — newest published data ends **2025-06-30** (~1-yr lag) | Free | Public | M | ❌ Discarded for live use: no free, current, public EDGAR demand signal exists (searched; only paid streamers like sec-api.io). Internal `UserSearch` counts remain the only first-party demand signal |
| **GDELT DOC 2.0 API** ([docs](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/), [terms](https://www.gdeltproject.org/about.html), acc. 2026-07-06) [curl] | News-volume buzz per company, 15-min updates, 3-month window | Free, keyless; **1 req/5 s** (observed live) — fine for a 10-min cron over candidates, not per-request | "unlimited and unrestricted use for any … commercial … use", attribution required | M (6–12h; company-name matching is the hard part) | ✅ Best free, license-clean external news signal (optional enrichment) |
| **Wikipedia pageviews API** [curl] | Attention proxy per company, daily, ~24h lag | Free, generous | Open | S–M (4–8h) | ⚠️ Optional tie-breaker only — too slow to lead |
| **Stocktwits trending** [curl this session] | `trending_score`, `watchlist_count`, sector per ticker | Free, keyless today; limits undocumented | **Gray** — commercial API permission unverifiable; partner program effectively closed (see §4.2) | S (already integrated) | ⚠️ Non-critical enrichment at most; must be able to vanish without breaking the module |
| **Finnhub news sentiment** (current pipeline) ([ToS](https://finnhub.io/terms-of-service), acc. 2026-07-06) | Buzz/sentiment | Free tier 60/min | ❌ "All plan[s] … strictly for personal use"; no redistribution of "data or derived results" | — | ❌ Discarded: current use in a commercial product appears to violate ToS — flag independent of this review |
| **Paid** (sec-api.io, Benzinga, FMP paid) | Real-time filing streams | $ | varies | — | ❌ Discarded: $0 rule; adds nothing essential — EDGAR itself is real-time enough |

**Synthesis:** a genuinely real "notable filings today" module is buildable entirely on free, keyless, public-domain SEC infrastructure this repo already has plumbing for (EFTS sweep exists in `earnings_calendar_service.py`; ticker↔CIK cache exists in `edgar/compat.py`; cron pattern exists in `internal.py`). Missing ingredient is the *universe* (all of EDGAR, not our own DB) + item-code materiality — not a cleverer score.

### 4.2 Market Movers candidates

| Source | What it enables | Cost / limits | License | Effort | Verdict |
|---|---|---|---|---|---|
| **FMP (status quo)** | — | Legacy v3 **dead** for this account class (403 "Legacy Endpoint", cutoff 2025-08-31; strategy doc, verified 2026-07-03; error shape re-probed [curl] 2026-07-06) | ❌ Display on a multi-user site prohibited even on paid tiers without a negotiated Data Display Agreement (ToS §2.2.2) | — | ❌ Unrevivable as built |
| **Stocktwits-only rebuild** (drop FMP; the payload's own `instrument_class`/`exchange` fields replace validation) [curl this session] | Real social trending, honestly labeled; watchlist counts; no reliable prices | Free, keyless; limits undocumented | See §4.2.1 below | S/M (4–8h) | ⚠️ Technically easy; license-gray + brand-conflicting (roadmap D3) |
| **Alpha Vantage `TOP_GAINERS_LOSERS`** | Real gainers/losers/most-active with prices | Free 25 req/day (1 call cached hourly fits) | ❌/⚠️ AV ToS §2.a: personal, non-commercial (strategy doc; classified "(b) bridge" repo-wide) | M (6–10h; client exists) | ⚠️ See §4.2.1 — most viable *data*, but it would put a third personal-use-tier dependency on a commercial homepage |
| **Finnhub** | Quotes; no free movers endpoint of note | Free 60/min | ❌ Personal use only (ToS acc. 2026-07-06) | — | ❌ Discarded |
| **yfinance** (Yahoo screeners) | Day gainers/losers/actives | Free | ❌ Yahoo ToS bans automated collection & commercial use; repeated breakage waves 2024–26 (strategy doc) | M | ❌ Discarded |
| **Tiingo / Twelve Data / Polygon free tiers** | Quotes/movers | Free tiers | See §4.2.1 | M | See §4.2.1 |

**§4.2.1 — completed by follow-up research (retried subagent), see Validation log:** Stocktwits current ToS posture; AV TOP_GAINERS_LOSERS live verification; Tiingo/Twelve Data/Polygon free-tier commercial terms; whether any exchange publishes an official free movers feed.

**Bottom line (consistent with the repo's own 2026-07-03 research):** for *earnings-calendar* data the verdict was "no free or affordable-paid provider is license-clean; only EDGAR is" — and for *market price/movement* data the situation is strictly worse, because there is no public-domain source at all: every free quote/movers feed found is personal-use-tier. Unlike Trending Filings, Market Movers has **no license-clean $0 rebuild path**.

---

## 5. Options and recommendation per section

### 5.1 Market Movers

| Option | Value vs bar | Effort | Ongoing cost/ops | Risk |
|---|---|---|---|---|
| Keep as-is | **Negative** — hardcoded list + internal error string on a sales surface | 0 | Dead FMP calls per cache-miss | Credibility damage compounding daily |
| Minimal honest fix (suppress error string, honest footer/labels, drop "today" claim) | Near-zero — the honest version is "here are 5 famous tickers", which fails the bar outright | S (3–6h) | Same dead pipeline underneath | Polishing a section with no content |
| Rebuild on Stocktwits-only | Partial — real social trending, no license-clean prices, so the "moving today" promise still can't be kept | S/M (4–8h) | Keyless dependency that can vanish; undocumented limits | ToS gray; contradicts roadmap D3 ("calm signal, never casino") on the Pro homepage |
| Rebuild on Alpha Vantage TOP_GAINERS_LOSERS | Good data (real movers + prices) | M (6–10h) | 1 call/hr fits 25/day free | ❌ Personal-use free tier on a commercial homepage — repo already classifies AV as bridge-only that "must be licensed or dropped at launch"; this *adds* launch debt |
| Merge | Fold the social-attention idea into Filing Pulse components later (roadmap B4 sentiment snapshots) — no homepage section | 0 now | — | None |
| **HIDE now (recommended)** | Frees the slot; removes a live credibility leak | S (1–2h flag/removal) + M (4–6h follow-up deletion) | Negative — retires dead FMP/Stocktwits calls and 6h-poison caching | Near-zero: reversible via git; no evidence of user demand (and none *can* exist — no impression data) |

**RECOMMENDATION: HIDE — now, permanent for the current concept. Confidence: HIGH.**
Decisive reasons:
1. **Unrevivable as built, and no license-clean $0 rebuild exists** (§4.2). Every candidate source is personal-use-tier or ToS-gray; the only honest free versions can't show price movement, which is the section's entire promise.
2. **It is actively damaging a sales surface today**: an internal error string, a fabricated source attribution, and null-price mega-cap cards are server-rendered into the public homepage HTML.
3. **Off-mission and off-brand by the company's own written strategy** (roadmap D3, `pulse_service.py` docstring): the product's differentiation is calm, filing-grounded analysis — not a quote-ticker strip whose value users already get from their broker.

Disposition of parts: frontend section + prefetch removed (flag-gated for a release if reversibility is wanted); backend router/service/Stocktwits+FMP integrations and `test_stocktwits_fmp.py` deleted in a follow-up PR after one deploy cycle; nothing preserved for rebuild except a roadmap note that social-attention data may later feed Filing Pulse (B4) — from a licensed source, on company pages, not the homepage.
**30-day success criteria** (measurable with Phase A instrumentation + existing funnels): homepage → search/signup conversion does not degrade vs the prior 30 days (PostHog funnel); zero user complaints referencing the section. **Revisit trigger** (not a kill criterion — the default is it stays gone): a licensed data source arrives (e.g., a negotiated AV/Stocktwits agreement) *and* Pro-user interviews actually surface demand for market data on the homepage.

### 5.2 Trending Filings

| Option | Value vs bar | Effort | Ongoing cost/ops | Risk |
|---|---|---|---|---|
| Keep as-is | Negative — four stale cards for one company under a "Trending 🔥" banner | 0 | Dead FMP/Finnhub calls | Credibility + quiet ToS exposure (Finnhub) |
| **Minimal honest fix (recommended now)** | Moderate — honest "latest notable filings we cover", deduped, fresh-only, self-omitting when thin; keeps the one homepage surface that showcases the core product on new filings | M (~1 day total) | Removes dead/unlicensed calls → simpler + cheaper | Inventory may be thin off-season → section absent some days (acceptable; ReportingThisWeek precedent) |
| Rebuild on EDGAR current filings + item materiality | High — actually delivers "notable filings today, market-wide"; license-clean forever; $0 | L (~2–3 days: poller/cron, scoring, persistence, tests) | One more cron job (~CHF 0.1/mo pattern); SEC rate budget | Building before knowing anyone clicks — that's why it's gated on 30-day data |
| Merge into calendar surfaces | Poor fit — calendar = *upcoming earnings*; this = *filed documents*; merging loses the AI-summary hook | M | — | Dilutes both |
| Hide | Frees the slot | S | — | Kills the core-mission discovery loop for a fixable mechanical failure; over-correction on a section whose concept the evidence supports |

**RECOMMENDATION: FIX (minimal honest fix now) + instrument; EDGAR rebuild only if 30-day data earns it. Confidence: MEDIUM-HIGH.**
Decisive reasons:
1. **The concept is the product**: fresh filing → one-click AI summary is EarningsNerd's core loop, and this is the only homepage section that demonstrates it on new filings. Hero search is pull; Popular Companies is static; the calendar is future-looking. A working version has a non-overlapping job (the bar, §1).
2. **The failure is mechanical and cheap to fix honestly**: dedupe + freshness floor + truthful badges + deleting dead/unlicensed signal calls is ~a day, and each piece is independently verifiable.
3. **The expensive version isn't justified yet**: with zero impression data, spending 2–3 days on a market-wide EDGAR rebuild would repeat the original sin (shipping unmeasured). The fix makes the section honest; the instrumentation makes the rebuild decision data-driven.

**30-day criteria** (from Phase A instrumentation, evaluated ~2026-08-05):
- **Kill →HIDE** if section CTR (`hot_filing_summary_clicked` / `homepage_section_viewed[trending_filings]`) < 0.5% *and* < 15 clicks/week — the honest version demonstrably doesn't earn its slot.
- **Invest → EDGAR rebuild** if CTR ≥ ~1% *or* the section self-omits >50% of days while clicks-when-present are healthy (demand exists, inventory is the constraint).
- Otherwise: keep the fixed version, re-evaluate at 90 days.

---

## 6. Remediation plan

Approval gate: Neil picks a verdict per section (§5); then Phase A + the chosen Phase B items become the implementation PR(s). Estimates include running the full local gates.

### Phase A — zero-risk prep (do under ANY verdict)

- [ ] **A1. Section impression instrumentation** — S, ~2–3h. New `useSectionImpression` hook (IntersectionObserver, fire-once `homepage_section_viewed` with `section` prop) applied to both sections (+ ReportingThisWeek for a baseline); fix `market_mover_clicked`'s hardcoded `source: 'stocktwits'` → actual `data.source`. Files: `frontend/lib/useSectionImpression.ts` (new), `frontend/features/filings/components/HotFilings.tsx`, `frontend/features/companies/components/TrendingTickers.tsx` (skip if hidden first), `frontend/tests/unit/`.
- [ ] **A2. Stop rendering internal error strings** — S, ~1–2h. Strip `Last error: …` from all user-facing `message` fields (keep in logs). Files: `backend/app/services/trending_service.py:74,110-113,119-121,141-142`; assertion added in `backend/tests/unit/test_stocktwits_fmp.py`. *(Moot if Market Movers is hidden in the same deploy — do whichever ships first.)*
- [ ] **A3. Neil runs PostHog queries P1–P6** (§3) — 30 min, no code.

### Phase B-MM — Market Movers: HIDE (recommended)

- [ ] **B1. Hide the section** — S, ~1–2h + gates. Remove the section block `frontend/app/page.tsx:224-230` and the `fetchTrendingInitial` prefetch (`frontend/lib/serverApi.ts:143` + its call site in `page.tsx`); *or* flag-gate via a new `NEXT_PUBLIC_ENABLE_MARKET_MOVERS` (default off) in `frontend/lib/featureFlags.ts` if Neil wants one-env-var reversibility. Verify: build + e2e (specs must tolerate the absent section), both themes on preview.
- [ ] **B2. Retire the backend (follow-up PR, ≥1 deploy later)** — M, ~4–6h. Delete `backend/app/routers/trending.py` (+ router mount in `main.py`), `backend/app/services/trending_service.py`, `backend/app/integrations/stocktwits.py`, `backend/tests/unit/test_stocktwits_fmp.py`; frontend `TrendingTickers.tsx`, its `companies-api` functions, `queryKeys.trendingTickers`. Endpoints simply disappear (public, unauthenticated, no contract-test coverage — verified; contract-test lock untouched).
- [ ] **B3. Retire FMP entirely** (pairs with B-TF below, which removes the last consumer) — S, ~2h. Delete `backend/app/integrations/fmp.py`, `FMP_*` settings in `app/config.py`, doc rows in `docs/CONFIGURATION.md`; update `docs/ARCHITECTURE.md` + router docstrings still describing Stocktwits+FMP. Add the `lessons/` entry (§8) — machine gate: a unit test asserting tombstoned integration modules have no importers.

### Phase B-TF — Trending Filings: minimal honest fix (recommended)

- [ ] **B4. Backend honesty fix** — M, ~4–6h. In `backend/app/services/hot_filings.py`: dedupe to one filing per company (keep highest-scoring, then most recent); freshness floor `filing_date >= now-14d`; `sources` includes `recency` only when `recency_score > 0`; delete the dead FMP-earnings and Finnhub calls + their components (also resolves the Finnhub ToS exposure). In `backend/app/routers/hot_filings.py`: remove the zero-score "recent filings" fallback (contradicts self-omission); drop public `force_refresh` (admin refresh endpoint already exists). Files above + new `backend/tests/unit/test_hot_filings_ranking.py` (dedupe, floor, badge honesty), update `test_hot_filings_tz.py`/`test_pulse_service.py` for the reduced component set.
- [ ] **B5. Frontend self-omission + honest copy** — S, ~2–3h. Empty payload → render nothing (move the section wrapper into `HotFilings` or conditional in `page.tsx:187-198`, ReportingThisWeek precedent `page.tsx:180-182`); retitle "🔥 Trending Filings" → "Latest notable filings" (`page.tsx:191`); fix the false "last 24 hours" empty-state (`HotFilings.tsx:101`). Files: `frontend/app/page.tsx`, `frontend/features/filings/components/HotFilings.tsx`, render test in `frontend/tests/unit/`.
- [ ] **B6. (Conditional — only on 30-day trigger, ~2026-08-05)** EDGAR-wide rebuild — L, ~2–3 days. New `notable_filings` service: 5–10-min poll of EDGAR current filings (edgartools `get_current_filings` / Atom feed, routed per rule 5), 8-K item-code materiality scoring, one-per-company, persist candidates, lazy-ingest on click; wire the existing `/internal/jobs/*` cron pattern. Frontend unchanged. Not in scope for the first PR.

Sequencing: one PR = A1 + A2 + B1 + B4 + B5 (they touch disjoint files; ~1.5 days total), follow-up PR = B2 + B3 a deploy later. B6 waits for data.

---

## 7. Validation log

**Claim audit (all load-bearing claims re-verified this session):**
- Live prod: `hot_filings?limit=4`, `trending_tickers`, homepage HTML — captured 2026-07-06 ~16:40 UTC (scratchpad). ✔
- Code claims: every `file:line` cited in §2 read directly this session (hot_filings.py, trending_service.py, fmp.py, stocktwits.py, finnhub.py, pulse_service.py, both routers, both components, page.tsx, featureFlags.ts, serverApi.ts, filing_scan_service.py, alpha_vantage.py, earnings_calendar_service.py). ✔
- Map corrections found: `force_refresh` IS exposed on the hot-filings GET; router has a zero-score fallback; **Alpha Vantage is used** (by the calendar engine); footer attribution + analytics `source` dishonesty; Finnhub endpoint is premium-tier.
- External claims: EDGAR endpoints, GDELT, Finnhub ToS, edgartools docs — fetched/curled 2026-07-06 by the research subagent (URLs in §4). FMP death + FMP/AV/yfinance ToS — `tasks/earnings-calendar-strategy.md`, live-verified 2026-07-03 (accepted as recent primary research; FMP error shape independently re-probed today).

**Symptom reproduction:** §2.3 mechanisms predict the screenshots exactly — (a) with FMP+Finnhub dead and nothing filed <72h or searched <7d, every BABA filing scores velocity 2.0 (normalized max) + type 1.5 = 3.5 → top-4 sweep, 57%/43% PULSE, tier "On the radar" (3.5 ≥ 3.0 threshold); `sources` seeded `"recency"` unconditionally → "Recent" on every card. (b) FMP 403 → `get_profiles` returns `{}` → all symbols cached invalid 6h → exact error string → fresh-fetch None → empty caches on an ephemeral instance → curated fallback with null prices + verbatim banner + unconditional "Data from Stocktwits & FMP" footer. No unexplained residue in either screenshot.

**Adversarial pass:** see §7.1 below (fresh-context devil's-advocate subagents, one per verdict).

**UNVERIFIED (kept, labeled):**
- Which exact FMP account state prod has (expired key vs post-cutoff account) — indistinguishable without prod secrets; both imply the same verdict.
- Which Finnhub failure mode produces the zeros (no key / free key on premium endpoint / rate limit) — all paths yield the observed zeros; ToS problem holds regardless.
- Stocktwits current ToS clause for keyless commercial API use — first research agent hit a session limit mid-task; classified **gray** pending the retried agent (§4.2.1). Verdict does not hinge on it (Stocktwits-only rebuild is rejected on brand/price-data grounds too).
- Alpha Vantage TOP_GAINERS_LOSERS live response shape/limits — pending same retry; its ToS class (personal-use) is already established and is what the verdict rests on.
- Actual engagement numbers — only Neil can run the PostHog queries (P1–P6).
- edgartools full-text-search wrapper function name — package not importable in the research sandbox; the raw EFTS endpoint is verified regardless.

**Estimate audit:** every Phase A/B item enumerates its files (see §6); estimates assume the repo's existing patterns (httpx integration clients, `/internal/jobs` cron, ReportingThisWeek self-omission precedent) and include running the full local gates. B6's L estimate is the least certain (new service + cron + persistence); it is deliberately deferred behind a data gate.

### 7.1 Adversarial pass results

> PLACEHOLDER — filled after the fresh-context devil's-advocate subagents return.

---

## 8. Appendix — research notes & out-of-scope observations

- **Out-of-scope but material:** none found beyond what the strategy doc already documents (EarningsWhispers endpoint dead; FMP dead). The calendar surfaces are already off FMP.
- **These two sections are the last FMP consumers** in the codebase (`grep fmp_client` → only `hot_filings.py`, `trending_service.py`, `integrations/__init__`). Killing/fixing them per the recommendations lets `fmp.py` (426 LOC) + `FMP_*` config retire entirely.
- **Durable lesson candidate** (for `lessons/` in the implementation PR): when an integration is declared dead (as FMP was, in writing, on 2026-07-03), sweep **all** of its consumers in the same pass — the calendar was rewired off FMP while trending/hot-filings were left running on the corpse for three more days, printing the failure to the public homepage. Machine-enforceable version: a CI grep/test asserting no imports of a tombstoned integration module.
- Doc contradictions to fix in the implementation PR: `docs/ARCHITECTURE.md:156-157` still credits `fmp` with "symbol validation, prices, earnings calendar" (the calendar role moved to `alpha_vantage`/EDGAR on 2026-07-03; the rest is dead), and the trending router docstring (`trending.py:27-31`) still promises "Stocktwits with FMP validation" — code truth diverges (curated fallback, dead FMP). Update alongside B2/B3.
