# Homepage sections review — Trending Filings & Market Movers

**Date:** 2026-07-06 · **Reviewer:** Claude (fractional product/staff-eng review, session `claude/homepage-sections-review-7k2120`)
**Scope:** keep/fix/kill for the two sections + their plumbing. No code changed during the investigation.
**DECISION (Neil, 2026-07-06):** Market Movers → HIDE approved. Trending Filings → **option B (the runner-up): hide + immediate EDGAR rebuild** — implemented on this branch (see `tasks/todo.md` status block and DEPLOYMENT.md §12 for rollout).
**Method:** live prod GETs (read-only), line-level code verification, in-repo prior research (`tasks/earnings-calendar-strategy.md`, 2026-07-03), two parallel web-research subagents (cited), adversarial fresh-context passes per verdict.

---

## TL;DR verdict table

| Section | Verdict | Confidence | One-line why |
|---|---|---|---|
| **Market Movers** (`TrendingTickers` → `/api/trending_tickers`) | **HIDE now via default-off flag** (backend retired in the follow-up PR regardless — it's unlicensable; only the *slot's* future is data-gated at day 30; `stocktwits.py` may stay, but future use needs a license) | **High** (on hiding now) | Its data path is unrevivable as built (FMP legacy API dead since 2025-08-31; display use prohibited even on paid tiers), no license-clean $0 source of price movement exists to rebuild on, and it is server-rendering an internal error string onto the Pro sales surface today. |
| **Trending Filings** (`HotFilings` → `/api/hot_filings`) | **FIX — minimal honest fix now (~1 day: dedupe, freshness floor, min-3-or-omit, muzzled PULSE, honest copy) + instrument; EDGAR rebuild decision at 30-day checkpoint** (runner-up: hide + rebuild immediately, if Neil can commit 2–3 days this month) | **Medium** | The concept (fresh filings → one-click AI summary) is the product's core discovery loop with a non-overlapping homepage job; the fix buys an honest interim at seasonal peak (10-Q season) while the market-wide EDGAR rebuild — verified viable at $0 — waits for a capacity/engagement decision rather than shipping unmeasured. |

Both verdicts ship with instrumentation (Phase A) so the 30-day keep/kill call is data-driven — today CTR is unknowable.

---

## 1. The bar (written before researching fixes)

Judged against what the hero search, Popular Companies banner, QuickAccessBar, and the calendar surfaces (ReportingThisWeek + `/calendar`) already provide. Overlap counts **against** a section.

**Trending Filings** earns its slot only if it shows:
- **Content:** filings selected by a signal that plausibly proxies "notable" — high-signal form types (10-K/10-Q, 8-K 2.02/5.02/1.01, S-1, 13D/G), real demand (searches, news), or market breadth — with **at most one card per company**.
- **Freshness:** filed today / this week. A "trending" card about a 27-day-old routine 6-K is worse than no card.
- **Honesty:** every badge and label describes the actual selection mechanism; the section title matches what the algorithm does.
- **Distinct value:** push-discovery of "what just hit EDGAR that matters" with a one-click AI summary — the only homepage section that surfaces the *product's actual output* for new filings. Hero search is pull (you must know the company); Popular Companies is static curation; the calendar is *upcoming earnings*, not filed documents. So a genuinely fresh, honest version has a real, non-overlapping job.

**Market Movers** earns its slot only if it shows:
- **Content:** actual same-day price/volume movers (gainers/losers/actives) or genuine social trending, with live prices, from a source licensed for display on a commercial multi-user site.
- **Freshness:** intraday; "today" in the subtitle must mean today.
- **Honesty:** the source label matches the source actually serving the data; no internal error strings; a Refresh button that refreshes.
- **Distinct value — and this is where it structurally struggles:** EarningsNerd's product is filing analysis, not quotes. The link from "NVDA is up 3%" to "read an AI filing summary" is one hop weaker than every other section's link. The roadmap (D3, and `pulse_service.py`'s own docstring) explicitly rejects the "Stocktwits casino" framing: *"calm signal, never casino."* A price-hype strip must clear both the data bar **and** the brand bar. Overlap: Popular Companies + QuickAccessBar already give one-click access to the mega-caps. *(Post-hoc correction, §7.1: this overlap holds for the current hardcoded fallback list, not for genuine trending data — the live feed's rank 1 was WULF, a name no static surface here would show.)*

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

**Market Movers.** FMP-side breakage — the (a)/(b) hypothesis class — is confirmed; (c) is refuted; (d) is moot.
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
| **Stocktwits trending** [curl this session] | `trending_score`, `watchlist_count`, sector per ticker | Free, keyless today; limits undocumented | ❌ **unless licensed** — Apr 2026 ToS §5 bars automated extraction; approval channel closed (see §4.2/§4.2.1) | S (already integrated) | ❌ Not usable even as enrichment without written authorization or a commercial deal |
| **Finnhub news sentiment** (current pipeline) ([ToS](https://finnhub.io/terms-of-service), acc. 2026-07-06) | Buzz/sentiment | Free tier 60/min | ❌ "All plan[s] … strictly for personal use"; no redistribution of "data or derived results" | — | ❌ Discarded: current use in a commercial product appears to violate ToS — flag independent of this review |
| **Paid** (sec-api.io, Benzinga, FMP paid) | Real-time filing streams | $ | varies | — | ❌ Discarded: $0 rule; adds nothing essential — EDGAR itself is real-time enough |

**Synthesis:** a genuinely real "notable filings today" module is buildable entirely on free, keyless, public-domain SEC infrastructure this repo already has plumbing for (EFTS sweep exists in `earnings_calendar_service.py`; ticker↔CIK cache exists in `edgar/compat.py`; cron pattern exists in `internal.py`). Missing ingredient is the *universe* (all of EDGAR, not our own DB) + item-code materiality — not a cleverer score.

### 4.2 Market Movers candidates

| Source | What it enables | Cost / limits | License | Effort | Verdict |
|---|---|---|---|---|---|
| **FMP (status quo)** | — | Legacy v3 **dead** for this account class (403 "Legacy Endpoint", cutoff 2025-08-31; strategy doc, verified 2026-07-03; error shape re-probed [curl] 2026-07-06) | ❌ Display on a multi-user site prohibited even on paid tiers without a negotiated Data Display Agreement (ToS §2.2.2) | — | ❌ Unrevivable as built |
| **Stocktwits-only rebuild** (drop FMP; the payload's own `instrument_class`/`exchange` fields replace validation) [curl this session] | Real social trending, honestly labeled; watchlist counts; **no prices** (would reintroduce the licensing problem) | Free, keyless today; limits undocumented | ❌ **Gray-to-prohibited** — current ToS ([Apr 9, 2026 revision](https://stocktwits.com/about/legal/terms/), acc. 2026-07-06) §5 bars automated extraction "except as expressly authorized … or through an approved API", and the [developer program](https://api.stocktwits.com/developers) has been closed to new registrations since ~2021 (page still says so; developers.stocktwits.com dead). Stocktwits now sells data commercially (Messages API via Databricks) | S/M (4–8h) | ❌ Discarded: unlicensable in practice, no prices, vanish-anytime |
| **Alpha Vantage `TOP_GAINERS_LOSERS`** [live-verified 2026-07-06: JSON with 20 top_gainers + 20 top_losers + 20 most_actively_traded, each ticker/price/change/volume; EOD-updated on free tier; junk-heavy (sub-$1 warrants) needing filters] | Real gainers/losers/actives with prices — the best *technical* fit found | Free 25 req/day ([support page](https://www.alphavantage.co/support/), acc. 2026-07-06); section needs ~1 call/day | ❌ **Prohibited** — [docs page itself](https://www.alphavantage.co/documentation/) (acc. 2026-07-06): premium plans are "for your personal use. **For commercial use, please contact sales.**" Even paid self-serve is personal-use | S (3–4h) | ❌ Discarded on licensing alone; the blocker is purely legal, not technical |
| **Finnhub** | Quotes; no free movers endpoint of note | Free 60/min | ❌ Personal use only (ToS acc. 2026-07-06) | — | ❌ Discarded |
| **yfinance** (Yahoo screeners) | Day gainers/losers/actives | Free | ❌ Yahoo ToS bans automated collection & commercial use; repeated breakage waves 2024–26 (strategy doc) | M | ❌ Discarded |
| **Tiingo** ([ToS](https://app.tiingo.com/tos), acc. 2026-07-06) | No movers endpoint documented | ~1k req/day free (marketing; exact figures UNVERIFIED) | ❌ "All data via the API is for internal consumption only… Redistribution … comes with additional fees" | — | ❌ Discarded |
| **Twelve Data** ([ToS](https://twelvedata.com/terms) rev. 2026-01-01, acc. 2026-07-06) | Movers endpoint exists (paid tier) | Free 800 credits/day | ❌ §2.3(l): free tier bars commercial use; external display needs a "Redistribution Rights Add-On" | — | ❌ Discarded |
| **Polygon.io / "Massive"** (rebranded 2025-10; [movers docs](https://polygon.io/docs/rest/stocks/snapshots/top-market-movers) + [pricing](https://massive.com/pricing), acc. 2026-07-06) | Top-20 movers snapshot — "Not included" on free; Starter $29/mo is 15-min delayed | Free 5 calls/min, EOD | ❌ Basic/Starter/Developer all `license_type: "personal"`; display = Business tier (custom pricing) | — | ❌ Discarded |
| **Exchanges/regulators** (Nasdaq/NYSE/SEC/FINRA) | Exchange sites show movers but publish **no documented, licensed, free movers API**; `api.nasdaq.com` is an undocumented internal API (unlicensed-scraping class of risk); SEC/FINRA publish filings/short-volume data, not intraday movers | — | ❌/gray | — | ❌ Discarded |

**§4.2.1 — follow-up research results (retried subagent, all fetched live 2026-07-06; detail merged into the table above).** Headline: **no source verified today is both $0 and license-clean for displaying gainers/losers/actives on a commercial website.** Two corollaries: (1) the *current live pipeline is itself a ToS violation* — trending_service's server-side automated extraction of Stocktwits is unauthorized under the Apr 2026 §5 language, one more reason to retire it promptly rather than let it idle behind a flag; (2) the only $0-and-clean "what's moving" signal available to this product is EDGAR-derived filing activity — which is the Trending Filings concept, not this section.

**Bottom line (now fully verified, no longer partly inferred):** for *earnings-calendar* data the repo's 2026-07-03 verdict was "no free or affordable-paid provider is license-clean; only EDGAR is" — and for *market price/movement* data the situation is strictly worse: five providers + the exchanges checked, zero license-clean $0 paths, and the cheapest display-legal route anywhere is a negotiated commercial license. Unlike Trending Filings, Market Movers has **no license-clean $0 rebuild path**.

---

## 5. Options and recommendation per section

### 5.1 Market Movers

| Option | Value vs bar | Effort | Ongoing cost/ops | Risk |
|---|---|---|---|---|
| Keep as-is | **Negative** — hardcoded list + internal error string on a sales surface | 0 | Dead FMP calls per cache-miss | Credibility damage compounding daily |
| Minimal honest fix (suppress error string, honest footer/labels, drop "today" claim) | Near-zero — the honest version is "here are 5 famous tickers", which fails the bar outright | S (3–6h) | Same dead pipeline underneath | Polishing a section with no content |
| Rebuild on Stocktwits-only | Partial — real social trending, no license-clean prices, so the "moving today" promise still can't be kept | S/M (4–8h) | Keyless dependency that can vanish; undocumented limits | ❌ Apr 2026 ToS §5 bars automated extraction and the approval channel is closed (§4.2.1) — unlicensable in practice, on top of the brand-placement conflict |
| Rebuild on Alpha Vantage TOP_GAINERS_LOSERS | Good data (real movers + prices; live-verified) | S (3–4h) | 1 call/day fits 25/day free | ❌ Prohibited — AV's own docs: commercial use = "contact sales"; even paid self-serve tiers are personal-use (§4.2.1) |
| Merge | Fold the social-attention idea into Filing Pulse components later (roadmap B4 sentiment snapshots) — no homepage section | 0 now | — | None |
| **HIDE now (recommended)** | Frees the slot; removes a live credibility leak | S (1–2h flag/removal) + M (4–6h follow-up deletion) | Negative — retires dead FMP/Stocktwits calls and 6h-poison caching | Near-zero: reversible via git; no evidence of user demand (and none *can* exist — no impression data) |

**RECOMMENDATION: HIDE — now, via flag; permanence ratified at 30 days. Confidence: HIGH on hiding now; the "permanent" stamp is data-gated (see below).**
Decisive reasons:
1. **Unrevivable as built, and no license-clean $0 rebuild exists — now fully verified** (§4.2/§4.2.1: five providers + exchanges checked live, zero clean paths; the cheapest display-legal route anywhere is a negotiated commercial license). This is the load-bearing reason — and it means no amount of engagement data could justify *reviving* the section at $0; data can only ratify the kill.
2. **It is actively damaging a sales surface today, and its pipeline is a live ToS violation**: an internal error string, a fabricated source attribution, and null-price mega-cap cards are server-rendered into the public homepage HTML — while the server-side Stocktwits extraction behind it is unauthorized under Stocktwits' Apr 2026 terms (§4.2.1).
3. **Off-mission *for the homepage*** (amended after the adversarial pass, §7.1): the roadmap does value social-attention signal — but its sanctioned home is Filing Pulse on company/filing pages (roadmap items A3/B4, not this plan's A3/B4), rendered calmly, not a homepage ticker strip. What D3 rejects is the casino *rendering*; what this review rejects is the *placement and promise* — a "what's moving today" strip that cannot show licensed price movement. The residual value routes to the Merge row, not to a fix.

Disposition of parts (amended after §7.1, re-amended after §4.2.1): frontend section + prefetch behind `NEXT_PUBLIC_ENABLE_MARKET_MOVERS` default-off (one-env-var reversible) — hiding stops essentially all Stocktwits extraction immediately (nothing calls the endpoint but direct API hits, served from cache/fallback). The backend pipeline (`routers/trending.py`, `services/trending_service.py`, `test_stocktwits_fmp.py`, the frontend component) is deleted in the follow-up PR *regardless of engagement data* — §4.2.1 established it is unlicensable, so any future revival would be a rebuild on a licensed source, never a re-enable; what stays data-gated at day 30 is only whether the *slot* deserves a future replacement. **`integrations/stocktwits.py`** (~140 self-contained LOC) may be kept as the §7.1 pass argued (roadmap A3/B4 names the signal) — but with the new caveat that any future use requires written authorization or a commercial deal under the Apr 2026 ToS §5; keeping the file is free, using it is not. `fmp.py` is deleted with no regrets once B4 removes its last consumer.
Honest cost accounting (from §7.1): the full hide path (B1+B2+B3 ≈ 7–10h) costs about the same as the Stocktwits-only rebuild (4–8h) — the choice is which end-state you buy, not cheap-vs-expensive. The end-state argument (license wall, no prices, gray keyless dependency on the revenue homepage) still decides it.
**30-day criteria** (evaluated ~2026-08-05, with A3's PostHog numbers in hand): permanence ratified if P2 shows <~30 clicks/week pre-hide *or* P4 shows clicks concentrated on the five fallback tickers, and no licensed source has materialized; homepage → search/signup conversion must not degrade vs the prior 30 days (PostHog funnel over existing events — UNVERIFIED whether such a funnel is already configured; A3 sets it up if not). **Revisit trigger:** a licensed data source (negotiated AV/Stocktwits agreement) *and* actual Pro-user demand for homepage market data.

### 5.2 Trending Filings

| Option | Value vs bar | Effort | Ongoing cost/ops | Risk |
|---|---|---|---|---|
| Keep as-is | Negative — four stale cards for one company under a "Trending 🔥" banner | 0 | Dead FMP/Finnhub calls | Credibility + quiet ToS exposure (Finnhub) |
| **Minimal honest fix (recommended now)** | Moderate — honest "latest filings from covered companies", deduped, fresh-only, self-omitting when thin; keeps the one homepage surface that showcases the core product on new filings | M (~1 day total) | Removes dead/unlicensed calls → simpler + cheaper | Inventory may be thin off-season → section absent some days (acceptable; ReportingThisWeek precedent) |
| Rebuild on EDGAR current filings + item materiality | High — actually delivers "notable filings today, market-wide"; license-clean forever; $0 | L (~2–3 days: poller/cron, scoring, persistence, tests) | One more cron job (~CHF 0.1/mo, per the strategy doc's Cloud Scheduler costing); SEC rate budget | Building before knowing anyone clicks — that's why it's gated on the 30-day checkpoint |
| Merge into calendar surfaces | Poor fit — calendar = *upcoming earnings*; this = *filed documents*; merging loses the AI-summary hook | M | — | Dilutes both |
| Hide | Frees the slot | S | — | Kills the core-mission discovery loop for a fixable mechanical failure; over-correction on a section whose concept the evidence supports |

**RECOMMENDATION (amended after the adversarial pass, §7.1): FIX — minimal honest fix now + instrument, with a hard self-omission threshold and the PULSE breakdown muzzled; EDGAR rebuild decision at the 30-day checkpoint. Confidence: MEDIUM** (downgraded from medium-high — the adversarial pass established that the fixed version clears only the honesty prong of the bar, not the "notable, market-wide" content prong; it is an honest interim, not the destination).
Decisive reasons:
1. **The concept is the product**: fresh filing → one-click AI summary is EarningsNerd's core loop, and this is the only homepage section that demonstrates it on new filings. Hero search is pull; Popular Companies is static; the calendar is future-looking. A working version has a non-overlapping job (the bar, §1) — and hiding-now risks the hide-forever pattern for an on-mission concept (a solo-founder tendency both adversarial passes treated as real; judgment, not documented fact).
2. **Timing favors the fix**: the next 30 days are peak 10-Q season — the fixed version's best case (fresh 10-Qs from recognizable covered companies, deduped, one-click summaries). Its frontend half (self-omission, honest copy, instrumentation) is shared with the rebuild, so little is thrown away.
3. **The rebuild is verified-viable but not risk-free** (§7.1): market-wide 8-K streams are junk-heavy, item-code scoring is an editorial problem, and lazy-ingest-on-click adds first-experience latency for unknown companies — 2–3 days is the *optimistic* case. Committing it before any engagement signal, in the same week as the credibility cleanup, is the larger unmeasured bet.

**Runner-up, explicitly** (the adversarial pass's convergent position): HIDE now + schedule the EDGAR rebuild as the next roadmap slice + re-show only when it meets the bar. **Neil should pick this instead if he can commit the 2–3 rebuild days within ~a month** — it keeps the sales surface pristine during the Pro launch window and skips the interim entirely. The fix wins only under realistic solo-founder capacity assumptions; the adversary itself conceded that "if the founder won't get to the rebuild within ~a month, the fix beats an indefinite hide."

**30-day checkpoint** (~2026-08-05 — honestly labeled: this is a decision checkpoint on imperfect data, not a powered experiment; homepage traffic likely cannot distinguish 0.5% from 1% CTR in 30 days):
- Compute CTR **only over days the section rendered** (self-omission would otherwise train absence and corrupt the denominator), alongside absolute clicks/week and the P5 funnel (clicks → filing page → summary view).
- **HIDE** if clicks are negligible in absolute terms (< ~15/week during peak 10-Q season) — the concept's best month couldn't earn the slot.
- **REBUILD (B6)** if clicks-when-present are healthy but the section self-omits often — demand exists, inventory (own-DB universe) is the constraint, which is precisely what B6 fixes.
- Otherwise: keep the fixed version, re-evaluate at 90 days with post-season data.

---

## 6. Remediation plan

Approval gate: Neil picks a verdict per section (§5); then Phase A + the chosen Phase B items become the implementation PR(s). Estimates include running the full local gates.

### Phase A — zero-risk prep (do under ANY verdict)

- [ ] **A1. Section impression instrumentation** — S, ~2–3h. New `useSectionImpression` hook (IntersectionObserver, fire-once `homepage_section_viewed` with `section` prop) applied to both sections (+ ReportingThisWeek for a baseline); fix `market_mover_clicked`'s hardcoded `source: 'stocktwits'` → actual `data.source`. Files: `frontend/lib/useSectionImpression.ts` (new), `frontend/features/filings/components/HotFilings.tsx`, `frontend/features/companies/components/TrendingTickers.tsx` (skip if hidden first), `frontend/tests/unit/`.
- [ ] **A2. Stop rendering internal error strings** — S, ~1–2h. Strip `Last error: …` from all user-facing `message` fields (keep in logs). Files: `backend/app/services/trending_service.py:74,110-113,119-121,141-142`; assertion added in `backend/tests/unit/test_stocktwits_fmp.py`. *(Moot if Market Movers is hidden in the same deploy — do whichever ships first.)*
- [ ] **A3. Neil runs PostHog queries P1–P6** (§3) — 30 min, no code.

### Phase B-MM — Market Movers: HIDE (recommended)

- [ ] **B1. Hide the section (flag-gated, per §7.1 amendment)** — S, ~1–2h + gates. New `NEXT_PUBLIC_ENABLE_MARKET_MOVERS` (default off) in `frontend/lib/featureFlags.ts`; conditional render of the section block `frontend/app/page.tsx:224-230` and skip the `fetchTrendingInitial` prefetch (`frontend/lib/serverApi.ts:143` + its call site in `page.tsx`) when off. Verify: build + e2e (specs must tolerate the absent section), both themes on preview.
- [ ] **B2. Retire the backend (follow-up PR, ≥1 deploy later — not data-gated; the pipeline is unlicensable per §4.2.1, only the slot's future replacement is a day-30 question)** — M, ~4–6h. Delete `backend/app/routers/trending.py` (+ router mount in `main.py`), `backend/app/services/trending_service.py`, `backend/tests/unit/test_stocktwits_fmp.py`; frontend `TrendingTickers.tsx`, its `companies-api` functions, `queryKeys.trendingTickers`, and the B1 flag. **Keep `backend/app/integrations/stocktwits.py`** (roadmap names the signal for Filing Pulse) with the §4.2.1 caveat: any future use requires written authorization or a commercial deal. Endpoints simply disappear (public, unauthenticated, no contract-test coverage — verified; contract-test lock untouched).
- [ ] **B3. Retire FMP entirely** (pairs with B-TF below, which removes the last consumer) — S, ~2h. Delete `backend/app/integrations/fmp.py`, `FMP_*` settings in `app/config.py`, doc rows in `docs/CONFIGURATION.md`; update `docs/ARCHITECTURE.md` + router docstrings still describing Stocktwits+FMP. Add the `lessons/` entry (§8) — machine gate: a unit test asserting tombstoned integration modules have no importers.

### Phase B-TF — Trending Filings: minimal honest fix (recommended)

- [ ] **B4. Backend honesty fix** — M, ~4–6h (amended per §7.1). In `backend/app/services/hot_filings.py`: dedupe to one filing per company (keep highest-scoring, then most recent); freshness floor `filing_date >= now-7d` (matches the §1 bar and B5's "this week" title; tunable — self-omission is the safety valve if inventory runs thin); **return an empty list below 3 qualifying companies** (a one-card section is worse than absence); `sources` includes `recency` only when `recency_score > 0`; delete the dead FMP-earnings and Finnhub calls + their components (also resolves the Finnhub ToS exposure). In `backend/app/services/pulse_service.py` (or at composition): **suppress the component breakdown when only structural signals (`filing_velocity`/`filing_type_bonus`) are active** — show the tier alone; the "Filing cadence 57% / Filing type 43%" gauge is the photographed embarrassment and must not survive the fix. In `backend/app/routers/hot_filings.py`: remove the zero-score "recent filings" fallback (contradicts self-omission); drop public `force_refresh` (admin refresh endpoint already exists). Files above + new `backend/tests/unit/test_hot_filings_ranking.py` (dedupe, floor, min-count, badge honesty, pulse suppression), update `test_hot_filings_tz.py`/`test_pulse_service.py`.
- [ ] **B5. Frontend self-omission + honest copy** — S, ~2–3h. Empty payload → render nothing, header included (move the section wrapper into `HotFilings` or conditional in `page.tsx:187-198`, ReportingThisWeek precedent `page.tsx:180-182`); retitle "🔥 Trending Filings" → **"New filings this week"** with a subtitle naming the coverage honestly ("from companies EarningsNerd tracks") — per §7.1, "notable" would still overclaim; fix the false "last 24 hours" empty-state (`HotFilings.tsx:101`). Files: `frontend/app/page.tsx`, `frontend/features/filings/components/HotFilings.tsx`, render test in `frontend/tests/unit/`.
- [ ] **B6. (Decision at the 30-day checkpoint, ~2026-08-05 — or immediately, if Neil picks the runner-up)** EDGAR-wide rebuild — L, ~2–3 days *optimistic* (§7.1 risk notes: market-wide 8-K noise filtering is an editorial problem, not just a parser; microcap junk needs a recognizability filter or the rebuilt section has its own credibility failure mode; lazy-ingest-on-click means cold-start latency on first click for unknown companies — mitigate by linking to `/company/{ticker}` rather than a filing page). New `notable_filings` service: 5–10-min poll of EDGAR current filings (edgartools `get_current_filings` / Atom feed, routed per rule 5), 8-K item-code materiality scoring, one-per-company, persist candidates; wire the existing `/internal/jobs/*` cron pattern. Frontend mostly unchanged. Not in scope for the first PR.

Sequencing: one PR = A1 + B1 + B4 + B5 (~1.5 days total; A2 becomes moot once B1 hides the section in the same deploy — include A2 only if the hide is deferred), follow-up PR = B2 + B3 a deploy later. B6 waits for the checkpoint.

---

## 7. Validation log

**Claim audit (all load-bearing claims re-verified this session):**
- Live prod: `hot_filings?limit=4`, `trending_tickers`, homepage HTML — captured 2026-07-06 ~16:40 UTC (scratchpad). ✔
- Code claims: every `file:line` cited in §2 read directly this session (hot_filings.py, trending_service.py, fmp.py, stocktwits.py, finnhub.py, pulse_service.py, both routers, both components, page.tsx, featureFlags.ts, serverApi.ts, filing_scan_service.py, alpha_vantage.py, earnings_calendar_service.py). ✔
- Map corrections found: `force_refresh` IS exposed on the hot-filings GET; router has a zero-score fallback; **Alpha Vantage is used** (by the calendar engine); footer attribution + analytics `source` dishonesty; Finnhub endpoint is premium-tier.
- External claims: EDGAR endpoints, GDELT, Finnhub ToS, edgartools docs — fetched/curled 2026-07-06 by the research subagent (URLs in §4). FMP death + FMP/AV/yfinance ToS — `tasks/earnings-calendar-strategy.md`, live-verified 2026-07-03 (accepted as recent primary research; FMP error shape independently re-probed today).

**Symptom reproduction:** §2.3 mechanisms predict the screenshots exactly — (a) with FMP+Finnhub dead and nothing filed <72h or searched <7d, every BABA filing scores velocity 2.0 (normalized max) + type 1.5 = 3.5 → top-4 sweep, 57%/43% PULSE, tier "On the radar" (3.5 ≥ 3.0 threshold); `sources` seeded `"recency"` unconditionally → "Recent" on every card. (b) FMP 403 → `get_profiles` returns `{}` → all symbols cached invalid 6h → exact error string → fresh-fetch None → empty caches on an ephemeral instance → curated fallback with null prices + verbatim banner + unconditional "Data from Stocktwits & FMP" footer. No unexplained residue in either screenshot.

**Adversarial pass:** see §7.1 below (fresh-context devil's-advocate subagents, one per verdict).

**Final consistency pass:** after all amendments were merged, a fresh-context critic reviewed the assembled document end-to-end and found 15 defects — mostly §6/§1 text lagging later amendments (the flag-only hide, the stocktwits.py keep-decision, the un-gated backend teardown), plus a hypothesis-label contradiction in §2.3, a "this week" title sitting over a 14-day floor (resolved to a 7-day floor), an unlabeled "documented" claim, and an identifier collision between roadmap items and this plan's item IDs. All 15 were fixed; none changed a verdict.

**Resolved by the retried research agent (2026-07-06, was UNVERIFIED at the first commit):**
- Stocktwits ToS: Apr 9, 2026 revision, §5 quoted in §4.2.1 — automated extraction unauthorized; developer program closed since ~2021. (The older content.stocktwits.com PDF is a stale 2019 version.)
- Alpha Vantage TOP_GAINERS_LOSERS: live-verified (20/20/20 entries, EOD on free, 25 req/day) — and prohibited for commercial display per AV's own docs page.
- Tiingo / Twelve Data / Polygon-Massive free tiers: all prohibit commercial/external display (clauses in §4.2 table). No exchange/regulator free movers feed exists.

**UNVERIFIED (kept, labeled):**
- Which exact FMP account state prod has (expired key vs post-cutoff account) — indistinguishable without prod secrets; both imply the same verdict.
- Which Finnhub failure mode produces the zeros (no key / free key on premium endpoint / rate limit) — all paths yield the observed zeros; ToS problem holds regardless.
- Actual engagement numbers — only Neil can run the PostHog queries (P1–P6).
- edgartools full-text-search wrapper function name — package not importable in the research sandbox; the raw EFTS endpoint is verified regardless.
- Minor: Tiingo's exact free-tier numeric limits (pricing page is a JS shell); Twelve Data's movers-endpoint plan level; whether Tiingo has any movers endpoint at all — all moot given their display-licensing verdicts.

**Estimate audit:** every Phase A/B item enumerates its files (see §6); estimates assume the repo's existing patterns (httpx integration clients, `/internal/jobs` cron, ReportingThisWeek self-omission precedent) and include running the full local gates. B6's L estimate is the least certain (new service + cron + persistence); it is deliberately deferred behind a data gate.

### 7.1 Adversarial pass results

Two fresh-context subagents, each given only the evidence summary and instructed to argue the opposite of the draft verdict as strongly as the evidence allows (both also had read access to the repo to check citations).

**Pass 1 — against "HIDE Market Movers permanently."** Changed the report:
- *Survived → adopted:* (a) the **permanence** stamp was under-evidenced relative to the standard applied to the sibling section — amended to hide-now-via-flag with the *slot's future* ratified at day 30 after the PostHog P2/P4 queries (note: §4.2.1 later narrowed this — the pipeline itself is unlicensable, so only the slot question stays data-gated, not the pipeline's survival); (b) **backend teardown over-reach** — `integrations/stocktwits.py` is a healthy, live-verified integration that roadmap A3/B4 explicitly names as a Filing Pulse input; excluded from deletion (later caveated by §4.2.1: keeping the file is free, but any future *use* requires a license under the Apr 2026 ToS §5); (c) my **brand argument was overstated** — roadmap D3 rejects the casino *rendering*, not attention data (Phase-3 item 3 explicitly plans to use social signal); decisive reason 3 reworded to "off-mission for the homepage — the sanctioned home is Filing Pulse on company pages" (which is the Merge row); (d) the **overlap claim was wrong for real trending data** (live rank 1 was WULF, not a mega-cap — it's the *fallback* that overlaps with QuickAccessBar); (e) honest **cost accounting** added: full hide path ≈ rebuild cost (~a day either way); the end-state argument decides, not price.
- *Did not survive (verdict holds):* the licensing wall — no license-clean $0 source of price movement exists, so the section's headline promise ("what's moving today") is unkeepable; the honest Stocktwits-only variant is a different, weaker concept on a gray, vanish-anytime dependency; and the AV "bridge" argument backfires (Pro just launched — the bridge class is at its stated expiry). The adversary conceded this leg is unanswerable.

**Pass 2 — against "FIX Trending Filings now, rebuild maybe later."** Changed the report materially:
- *Survived → adopted:* (a) the **internal contradiction** — §4.1's diagnosis ("missing ingredient is the universe + materiality, not a cleverer score") means the fixed version clears only the *honesty* prong of the §1 bar, never the *content* prong; the recommendation now says so and confidence dropped medium-high → **medium**; (b) **PULSE display unchanged** — post-fix cards would still show the ridiculed "Filing cadence / Filing type" gauge; B4 now suppresses the component breakdown when only structural signals are active; (c) **a one-card section is worse than absence** — B4 now self-omits below 3 qualifying companies (live data implies launch week might otherwise render a single stale BABA card); (d) **the 30-day gate was decision theater as written** — reframed as an explicitly imperfect checkpoint: CTR computed only over rendered days, absolute clicks + P5 funnel alongside, no pretense of statistical power; (e) **"notable" in the retitle still overclaims** — retitle changed to "New filings this week" + honest coverage subtitle; (f) **rebuild risk notes added to B6** (8-K junk filtering is editorial work; microcap credibility failure mode; cold-ingest click latency).
- *Weighed and rejected (with the adversary's own concessions):* the convergent counter-proposal — HIDE now + rebuild as the next slice — **is recorded as the explicit runner-up**, preferable if Neil can commit the rebuild within ~a month. The fix wins on: solo-founder hide-forever risk for an on-mission concept (the adversary granted this), peak 10-Q season making the interim's best month (the adversary granted this — "a seasonal-best fixed section … is better than a permanently empty slot"), and the fix's frontend half being shared with the rebuild. The final call is a capacity judgment, and it is Neil's — both paths are specified in §6.

---

## 8. Appendix — research notes & out-of-scope observations

- **Out-of-scope but material:** none found beyond what the strategy doc already documents (EarningsWhispers endpoint dead; FMP dead). The calendar surfaces are already off FMP.
- **These two sections are the last FMP consumers** in the codebase (`grep fmp_client` → only `hot_filings.py`, `trending_service.py`, `integrations/__init__`). Killing/fixing them per the recommendations lets `fmp.py` (426 LOC) + `FMP_*` config retire entirely.
- **Durable lesson candidate** (for `lessons/` in the implementation PR): when an integration is declared dead (as FMP was, in writing, on 2026-07-03), sweep **all** of its consumers in the same pass — the calendar was rewired off FMP while trending/hot-filings were left running on the corpse for three more days, printing the failure to the public homepage. Machine-enforceable version: a CI grep/test asserting no imports of a tombstoned integration module.
- Doc contradictions to fix in the implementation PR: `docs/ARCHITECTURE.md:156-157` still credits `fmp` with "symbol validation, prices, earnings calendar" (the calendar role moved to `alpha_vantage`/EDGAR on 2026-07-03; the rest is dead), and the trending router docstring (`trending.py:27-31`) still promises "Stocktwits with FMP validation" — code truth diverges (curated fallback, dead FMP). Update alongside B2/B3.
