# SEO & Scaling Audit — 2026-07-16

Scope: why earningsnerd.io is invisible on Google, and what breaks first (or blows the ~$50/mo
budget) at 1,000–5,000 users. Companion docs: `SEO_ROADMAP.md` (phased plan),
`LAUNCH_CHECKLIST.md` (founder-only actions). Items marked **[FIXED]** were addressed on the
`seo-audit-quick-wins` branch; evidence lines cite the live site (checked 2026-07-16) or code.

## The headline

Google could crawl the site (robots/sitemap existed, waitlist gate exempts `/company` and
`/filing`), but the pages it found were **empty**: the entire programmatic-SEO surface rendered
as a spinner with a broken generic title. There was nothing to rank. On top of that, the domain
has never been verified in Google Search Console, so Google has never been told the sitemap
exists — a site this young with zero backlinks essentially doesn't get discovered on its own.

---

## Findings, ranked

### S1 — Company & filing pages served no content to crawlers **[FIXED]**
- **Evidence (live):** `curl https://www.earningsnerd.io/company/AAPL` returned 563 chars of
  visible text — header/footer chrome plus "Loading company…". No H1 with the company name, no
  filing links, no summary text.
- **Evidence (code):** `frontend/app/company/[ticker]/page.tsx` was `force-dynamic` returning a
  `'use client'` shell; all data arrived via React Query after hydration. Same for
  `frontend/app/filing/[id]/page.tsx`.
- **Impact: critical.** These are the pages meant to rank for "{ticker} 10-K summary". Googlebot
  does render JS, but JS-rendered pages are crawled slower, ranked from a degraded snapshot, and
  every crawl executed our client fetches against Cloud Run (worse for cost than serving HTML).
- **Fix shipped:** both routes are now server components with **on-demand ISR** (company 30 min,
  filing 60 min revalidate; `generateStaticParams` returns `[]` so CI builds never need the
  backend). Server-fetched data seeds the existing client page via React Query `initialData` —
  no UI rewrite. Verified against the built output: `/filing/3` (a summarized filing) now serves
  ~12,000 chars of crawler-visible HTML including the full summary; `/company/AAPL` serves the
  H1, stock quote, and 10 filing links. If the backend is down, pages degrade to the old
  client-shell behavior (HTTP 200), never a 500.
- **Cost note:** ISR *reduces* backend load — a crawl of N cached pages costs Vercel-edge hits
  only; misses cost ≤2–3 backend GETs per page per revalidation window, vs 3+ API calls per
  page view before.

### S2 — Metadata was broken or duplicated on every money page **[FIXED]**
- **Evidence (live):** the AAPL page's `<title>` was literally
  `Company SEC Filings & 10-K Summary | EarningsNerd`. Root cause: Next.js 16 passes `params`
  as a Promise; `company/[ticker]/metadata.ts` read it synchronously, so `ticker` was always
  undefined and fell back to the string "Company". Every filing page shared one static title
  (`filing/[id]/layout.tsx` never read the id).
- **Impact: critical.** Titles are the strongest on-page ranking signal; thousands of pages with
  identical/broken titles look like spam to Google.
- **Fix shipped:** real `generateMetadata` on both routes (awaiting `params`), fetching actual
  data: `Apple Inc. (AAPL) SEC Filings & AI Summaries`, `Apple Inc. (AAPL) 10-K 2025: AI
  Summary`, with the filing's meta description taken from its own summary's opening sentences
  (unique per page). Canonical URLs on both routes; `/pricing` got metadata (it had none).

### S3 — Soft-404s and duplicate URLs polluted the index **[FIXED]**
- **Evidence:** unknown tickers returned HTTP 200 with a "Company not found" card;
  `/company/aapl` and `/company/AAPL` were two 200-status copies of the same page;
  `/filing/AAPL` duplicated `/company/AAPL`.
- **Fix shipped:** unknown tickers/filings now return real 404s; lowercase ticker URLs 308 to
  uppercase; ticker-shaped filing URLs canonicalize to the company page; unsupported-foreign
  company stubs and summary-less filing pages are `noindex,follow` (they're signup-gate stubs;
  they flip to indexable automatically once a summary exists).

### S4 — Sitemap: dishonest lastmod, stub URLs, and a per-request DB scan **[FIXED]**
- **Evidence (live):** all 1,884 URLs carried `lastmod 2026-07-13` (the day the cache was
  built — refreshed to "today" on every regeneration). **Evidence (code):**
  `backend/app/routers/sitemap.py` stamped `datetime.now()` on static+company entries, listed
  every company and every filing regardless of content, and ran `db.query(Company).all()` +
  full filings scan **uncached on every request** against the shared-core `db-g1-small`
  Cloud SQL instance.
- **Impact: high (SEO)** — Google learns to ignore lastmod; crawl budget is spent on stubs.
  **Severity-one (cost)** — the API host's robots.txt allowed crawling `/sitemap.xml`, making
  it the cheapest anonymous way to hammer the database.
- **Fix shipped:** truthful lastmod (company = newest filing date; static pages emit none),
  companies listed only with ≥1 filing, filings only with a generated summary, column-only
  queries with a 45k cap, 1-hour in-process cache, `/terms` added. The API host's robots.txt is
  now `Disallow: /` (crawlers belong on www, which proxies the sitemap hourly). Frontend
  fallback sitemap synced to the same static list.

### S5 — Google has never been told the site exists **[FOUNDER ACTION]**
- No Search Console verification (your report), so: no sitemap submission, no index-coverage
  data, no manual-action visibility. A new domain with no backlinks and (previously) empty pages
  will simply not surface — even for the navigational query "Earnings Nerd".
- **This is the single highest-impact remaining action.** See `LAUNCH_CHECKLIST.md` §1.

### S6 — Apex → www redirect is temporary (307) **[FOUNDER ACTION]**
- **Evidence (live):** `curl -I https://earningsnerd.io/` → `HTTP/2 307` to www. A 307 tells
  Google "this move is temporary", splitting signals across two hosts. Vercel domain settings
  can issue a permanent 308. Checklist §3.

### S7 — Waitlist middleware: currently OFF in production (verify intent)
- **Evidence (live):** the homepage returns 200 with full prerendered content;
  `frontend/vercel.json` sets `WAITLIST_MODE: "false"`. You described the site as redirecting
  `/` → `/waitlist`, which is **not what production does today** — if you meant the gate to be
  on until beta, it isn't (a Vercel dashboard env var may have been removed at some point).
  SEO-wise the current state is the good one: the homepage is indexable, with server-rendered
  content and Organization/WebSite JSON-LD. If you re-enable the gate pre-launch, note the
  middleware exempts `/company/*`, `/filing/*`, `/pricing` etc., so the programmatic surface
  stays crawlable; `/` would 307 to `/waitlist` (acceptable short-term; flip it off at launch —
  checklist §4).

### S8 — Structured data was homepage-only **[PARTIALLY FIXED]**
- Homepage had Organization + WebSite + SearchAction JSON-LD (good). Company/filing pages had
  none. **Shipped:** BreadcrumbList on both; `Corporation` (name/ticker/SEC-EDGAR sameAs) on
  company pages. Deferred (roadmap): `Article`/FAQ markup on filing pages — needs a
  careful honesty pass, and Google's rich-result benefit for non-news articles is modest.

### S9 — Crawlable junk routes **[FIXED]**
- Auth/utility pages (`/login`, `/register`, `/verify-email`, …) were indexable with duplicate
  generic titles; `/admin`, `/profile`, `/settings` weren't disallowed. All added to
  `robots.ts` disallow. `/dashboard` was already disallowed.

---

## Cost & scaling findings (1,000–5,000 users, ~$50/mo ceiling)

**Configured today** (from `.github/workflows/ci.yml` deploy job + `docs/DEPLOYMENT.md`):
Cloud Run 1 vCPU / 1 GiB, min 1 / max 2 instances, concurrency 40, timeout 600s; Cloud SQL
`db-g1-small` (shared core, ~50 max connections); DB pool 12+8 overflow per instance; prod runs
Redis OFF (L1 in-process cache only, ADR-0004); Vercel functions in `iad1` (moved to `pdx1` on
this branch); DeepSeek `deepseek-v4-pro`.

**Estimated fixed baseline: ~$38–45/mo** — Cloud SQL db-g1-small ≈ $26 + storage; Cloud Run
min-instance idle ≈ $10–15; Vercel/Resend/PostHog/Sentry on free tiers. There is almost no
headroom for per-request costs; the budget survives only if marginal request cost ≈ 0. (All
$ figures here are estimates from public list prices; verify against your actual bills.)

### C1 — AI spend is well-guarded (verified, reassuring)
Generation is **auth-gated POST only** (`summaries.py:131`); the GET summary endpoint returns a
stub and never generates; anonymous visitors (and therefore Googlebot, even executing JS) hit a
signup gate — confirmed in `useSummaryGeneration.ts` (guests never auto-generate; backend 401s
them). One summary per filing (DB unique + in-flight dedup lock + existing-summary
short-circuit), 6-concurrent semaphore, Free 5/mo quota, Pro 300/mo fair-use cap, force-refresh
is Pro-only. **A crawler cannot spend a cent of DeepSeek money.** Per-summary marginal cost at
the configured prices (`config.py:485-487`, $0.435/M input miss, $0.87/M output) is roughly
**$0.02–0.05**; spend scales with *unique filings summarized*, not users.

### C2 — What breaks first, in order
1. **Cloud SQL connections (was: sitemap scans; now: pool math).** 2 instances × (12+8) = 40 of
   ~50 max connections, before the 6 Cloud Run jobs (pool 3+2 each) run. A traffic spike that
   holds both instances busy while the weekly pregenerate cron runs can exhaust connections.
   Cheapest mitigations, in order: keep max-instances at 2 (done), drop job pool sizes, then
   `db-custom-1-3840` (~$50/mo — a budget decision, roadmap Phase 3).
2. **SEC EDGAR budget.** One process-wide 10 req/s token bucket; the unauthenticated
   always-live-EDGAR endpoints (`/insiders`, `/search/full-text`) could let one anonymous IP
   starve every user's filing loads. **[FIXED]**: per-IP limits (30/min, 20/min). Remaining
   (roadmap): `/api/companies/search` also hits EDGAR live per search and is core UX — needs a
   generous per-IP limit + monitoring rather than a blind cap. Unknown-ticker page hits cost a
   live EDGAR search each (no negative cache) — bounded now by ISR caching of the 404, roadmap
   item for a proper negative cache.
3. **Cloud Run cold starts / concurrency.** Max 2×40 = 80 concurrent requests; instance #2
   starts cold (empty L1 cache → SEC fetch bursts). Fine to ~5k casual users; the SSE
   generation streams (up to 120s each) are the real concurrency eaters — 6-generation
   semaphore per process caps this. No change needed yet; watch p95 latency + instance count
   (checklist §6).
4. **Vercel.** ISR + static pages keep function invocations near zero for crawls and reads.
   Watch the plan limits; if the site is commercial, Vercel's Hobby plan terms require Pro
   ($20/mo) — that's a budget decision (roadmap Phase 2/3, checklist §5).
5. **Redis: not needed at this scale.** ADR-0004 stands. The costly cross-instance misses are
   already DB-backed (filing content cache) or now HTTP-cached at Vercel's edge (ISR).

### C3 — Latency geography **[FIXED]**
Vercel functions ran in `iad1` (Virginia) while Cloud Run is `us-west1` (Oregon): every ISR
render paid ~60–70ms × 2–3 backend calls cross-country. Moved to `pdx1` (same metro as
us-west1). User-facing TTFB is unaffected (ISR serves from the global edge cache).

### C4 — Misc cost holes **[FIXED]**
Anonymous `force_refresh=true` on `/api/hot_filings` bypassed its 15-min cache and forced a
full DB-aggregation + FMP/Finnhub recompute per request (unused by the frontend; removed).

---

## What was verified, and how

- Live site: homepage/apex headers, robots.txt, sitemap (1,884 URLs), AAPL page HTML (title +
  body text), all fetched 2026-07-16.
- Built output: `next build` + `next start`, then curl with no JS — real titles, canonicals,
  JSON-LD, filing links, 12k-char summary HTML, 308 ticker redirect, 404s for unknown
  ticker/filing, 200-with-shell when the API is dead.
- Gates: frontend `eslint` + `tsc` + `vitest` (409 passed) + `next build` + Playwright e2e
  (17 passed, CI parity: dead API); backend `ruff` + `bandit` + `pytest` (1,784 passed).
- Cost-path claims: traced in code (`summaries.py`, `summary_pipeline.py`, `companies.py`,
  `filings.py`, `insiders.py`, `search.py`, `hot_filings.py`, `sec_rate_limiter.py`,
  `ci.yml` deploy flags). Dollar figures are estimates, labeled as such.
