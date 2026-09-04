# EarningsNerd frontend audit — 2026-09-04

> Appendix 04 of `docs/ENGINEERING_AUDIT_2026-09.md`. Written by the frontend workstream; live claims on `/pricing` and `/filing/3` re-verified by the lead.

Scope: read-only audit of `frontend/` at `main` (e8ea339, PR #634) plus live public-site GETs. Lens: product
quality of the filing-summary reading experience; invite-only beta. Production frontend IS at main (verified:
`/company/aapl` -> 308, new robots disallow list, noindex stubs). Production backend is at 4994360 (PR #633);
the only routers that differ from main are `sitemap.py`, `hot_filings.py`, `insiders.py`, `search.py`
(`git diff --stat 4994360..HEAD -- backend/app/routers`).

Method notes
- 21 read-only HTTP GETs total (www + api hosts). No POSTs, no auth, no generation.
- Playwright: preconditions were met (`frontend/node_modules/@playwright/test` 1.61.1, `npm-ci-done` marker,
  `/opt/pw-browsers/chromium`), a Playwright script was written, but every Chromium navigation failed with
  `net::ERR_CONNECTION_RESET` both with Playwright's `proxy` option and `--proxy-server`. The agent proxy status
  endpoint attributes it to the egress side closing the tunnel mid-TLS-handshake (`ws_closed_mid_exchange`, 39 B
  received) for every host, and its README says not to work around that. So: NO screenshots / console / theme
  captures; all live findings below are from raw HTML (curl). Both-theme visual verification remains outstanding
  (DESIGN_SYSTEM.md section 12.4).
- Lead's local gate: lint 0, tsc 0, vitest 85 files / 409 tests green.

---

## (A) Live public-site findings

| Page | Check | Result | Severity |
|---|---|---|---|
| `/` | Status / title / desc / canonical / H1 / JSON-LD | 200 · "EarningsNerd \| Understand any SEC filing in minutes" · desc present · canonical `https://www.earningsnerd.io` · H1 "Understand any SEC filing in minutes" · 2 JSON-LD blocks (Organization+WebSite graph) · no error strings | OK |
| `/` | og:title | Inherits root default "EarningsNerd \| AI-powered SEC filing analysis" (`app/layout.tsx:47`) — differs from the page `<title>` | Low |
| `/` | Sections rendered server-side | Only "Reporting this week" present. NO filings-discovery section at all: Market Movers flag-hidden (`app/page.tsx:226`), and Notable Filings self-omits because prod `GET /api/notable_filings?limit=8` returns `{"filings":[],"status":"empty"}` — `NOTABLE_FILINGS_ENABLED` defaults False (`backend/app/config.py:410`) | Medium (product) |
| `/pricing` | Status / metadata | 200 · "Pricing \| EarningsNerd" · desc · canonical (from `app/pricing/layout.tsx`) | OK |
| `/pricing` | SSR content | Body text is 492 chars = header + footer chrome only. No H1, no plan names, no prices, no FAQ in HTML. Cause: `useSearchParams()` at `app/pricing/page.tsx:42` in a `'use client'` page -> CSR bailout behind the Suspense wrapper (`:457`). The filing page explicitly avoided this (`app/filing/[id]/page-client.tsx:47-58`); pricing was not fixed. Also `<h2>Pricing</h2>` at `:241` duplicates the SecondaryHeader `<h1>Pricing</h1>` once hydrated | Medium (SEO of the sales page; Lighthouse SEO job asserts on it) |
| `/pricing` | JSON-LD | None (no Product/Offer schema) | Low |
| `/contact` | Meta description | `We&amp;apos;re` in raw HTML -> crawlers read the literal text "We&apos;re". Source: an HTML entity inside a JS string, `app/contact/page.tsx:6` | Low (1-line fix) |
| `/contact` | Canonical | Missing | Low |
| `/login`, `/register` | Title / canonical / robots | Generic root title "EarningsNerd \| AI-powered SEC filing analysis", no canonical, no `noindex` meta (pages are `'use client'` with no layout metadata). robots.txt Disallow covers crawl but not indexing of the bare URL | Low |
| `/company/AAPL` | All checks | 200 · "Apple Inc. (AAPL) SEC Filings & AI Summaries \| EarningsNerd" · canonical `/company/AAPL` · H1 "Apple Inc." · 2 JSON-LD (Breadcrumb+Corporation) · filings list SSR'd (90 KB) · no error strings | OK |
| `/company/MSFT` | Display name | H1/title "MICROSOFT CORP" — raw EDGAR uppercase name in the H1, `<title>` and meta description (`app/company/[ticker]/page.tsx:27-33`, `page-client.tsx:399`). Reads unpolished next to "Apple Inc." | Low (cosmetic, but on every non-Apple company page) |
| `/company/ZZZZ9` | Unknown ticker | 404 with `<meta name="robots" content="noindex">`, generic title. Took 3.08 s (cold path — likely a live EDGAR lookup before 404; SEO audit defers "negative-caching for unknown tickers") | OK / Low perf |
| `/company/aapl` | Lowercase -> canonical | 308 `location: /company/AAPL` | OK |
| `https://earningsnerd.io/` | Apex redirect | 307 -> `https://www.earningsnerd.io/` (checklist expects 308). Founder action in `docs/LAUNCH_CHECKLIST.md:27-30` (Vercel domain setting), not code | Low |
| `/filing/3` (AAPL 10-K, the hero example) | SSR of summary | 200 · title "Apple Inc. (AAPL) 10-K 2025: AI Summary \| EarningsNerd" · description is the summary's own first sentences · canonical · 2 JSON-LD · summary text IS in raw HTML ("Services growth" x5, "iPhone" x11, "416.2" x7 in body outside scripts; 12 131 visible chars). Sections SSR'd: Executive Assessment, Financial Highlights, Investment Risks & Concerns, Management Strategy, Segments, Liquidity, Outlook, Notable Footnotes, 3-Year Perspective, "Ask AAPL's 10-K anything" | OK |
| `/filing/3` | Heading quality | Five consecutive `<h4>Risk Factor</h4>` with identical text (fallback at `features/summaries/components/SummaryRisks.tsx:40` when the model emits no `title`). Reader sees five cards all titled "Risk Factor" | Medium (core reading surface) |
| `/filing/3` | Error strings / undefined / NaN | None | OK |
| `/filing/3` | Buttons / a11y | 23 buttons, 2 icon-only without text — both carry `aria-label` (15 labelled total); 0 `<img>` without alt; 1 `<main>`; no skip-to-content link (none app-wide: `components/Header.tsx`, `components/SiteChrome.tsx`) | Low (a11y) |
| `/filing/1369` (AAPL 10-Q 2008, no summary) | Stub handling | 200, honest template description, `robots: noindex, follow`, 610 chars visible (header + sign-up gate) | OK |
| `/filing/999999` | Unknown id | 404 + noindex | OK |
| `/robots.txt` | Content | Matches `app/robots.ts` (auth/utility disallows, sitemap pointer) | OK |
| `/sitemap.xml` (www) | Freshness / honesty | 200, 1 945 URLs, 516 entries stamped `lastmod 2026-07-16`, includes summary-less noindex stubs (e.g. `/filing/1369`), lacks `/terms`. Response headers: `last-modified: 02 Sep 2026`, `age: 211394`, `x-vercel-cache: HIT`. Meanwhile `GET https://api.earningsnerd.io/sitemap.xml` answers in 1.6 s with 36 781 URLs (6.35 MB), lastmod stamped today — i.e. the prod backend is still the OLD sitemap (all filings, fake "today"), and the www copy is a frozen 7-week-old snapshot. Hypothesis (strong): Next's fetch data cache refuses entries > 2 MB, so the `fetch(..., { next: { revalidate: 3600 } })` in `app/sitemap.ts:44` can never replace the stale <2 MB entry it cached on 07-16 and stale-while-revalidate serves it forever. Two compounding defects: backend `sitemap.py` fix (main) not deployed; frontend caches a payload that outgrew the cache | HIGH (SEO: Google is fed stale, dishonest lastmod + 1 400 noindex URLs; `docs/SEO_AUDIT.md:63` marks S4 "[FIXED]" which is not true in prod) |
| `api.earningsnerd.io/robots.txt` | API host | Prod still `Disallow: /api/` + `Allow: /` (main's `Disallow: /` not deployed) -> crawlers may fetch the 6 MB API sitemap directly | Low (cost) |
| Frontend -> backend@main drift | SSR fetches vs 4994360 routers | All SSR endpoints exist at 4994360: `/api/companies/{t}`, `/api/filings/company/{t}`, `/api/filings/{id}`, `/api/summaries/filing/{id}`, `/api/notable_filings`, `/api/reporting_this_week`, `/sitemap.xml` (`lib/serverApi.ts:150-261`). Frontend never sends `force_refresh` (grep: 0). No live call to a main-only endpoint/param. Only contract drift is the sitemap payload shape (lastmod/stubs), handled above | OK |

---

## (B) Code-gate findings

| Gate | Result | Evidence |
|---|---|---|
| DESIGN_SYSTEM 12.2 legacy-color grep | 0 hits (clean) | `grep -rnE '\b(mint-[0-9]\|...\|#92A0E2)' app components features` -> exit 1 |
| 12.2 motion grep (raw ms / bezier) | Clean except sanctioned token homes (`app/globals.css:63-64`) and comments. Borderline JS constants: `CLOSE_DELAY_MS = 120` in `features/filings/components/copilot/CitationChip.tsx:27` and `features/filings/components/SourceTrace.tsx:47` (hover-close delay, duplicated in two files); `PROGRESS_POLL_INTERVAL_MS = 1000` (`features/summaries/hooks/useSummaryGeneration.ts:38`) is polling, not motion | Low |
| 12.3 font-var gate | Pass — every `fontFamily` stack leads with its `var(--font-*)` (`tailwind.config.js:165-174`, `globals.css:29-33`) | OK |
| `componentsAllowlist.spec.ts` | Exists and does what CLAUDE.md claims: fails on any unexpected entry in `components/` and on a missing allowlisted file (`tests/unit/componentsAllowlist.spec.ts:16-31`). Note: `SentryTestButton.tsx` is allowlisted but has zero importers (dead chrome) | OK / Low |
| queryKeys ESLint rule | Exists: three `no-restricted-syntax` selectors (object-form `queryKey: [...]`, `getQueryData([...])`, `setQueryData([...])`) scoped to prod code (`eslint.config.mjs:43-75`). Grep confirms 0 inline arrays in `app components features lib` | OK |
| Raw `fetch(` outside sanctioned sites | 5 call sites, all sanctioned: ISR (`app/sitemap.ts:44`, `lib/serverApi.ts:28,214`), SSE (`features/summaries/api/summaries-api.ts:260`, `features/filings/api/copilot-api.ts:177`, `features/analysis/api/analysis-api.ts:280`). But this rule is prose-only — no ESLint gate bans `fetch` outside those files (CLAUDE.md rule 12 says rules become gates) | Low (add a `no-restricted-globals`/syntax rule with a file allowlist) |
| `any` in prod code | 0 (`: any`, `as any`, `<any>` grep over app/components/features/lib); 8 in tests (allowed by `eslint.config.mjs:24-35`) | OK |
| `@ts-ignore` / `@ts-expect-error` | 0 in prod, 0 in tests | OK |
| `// eslint-disable` | 38 in prod code, 36 with an inline justification (mostly `react-hooks/set-state-in-effect` from eslint-config-next 16's compiler rules). Two bare, unjustified: `features/companies/components/TrendingTickers.tsx:185` and `features/filings/components/copilot/useSheetFocusTrap.ts:112` (`react-hooks/exhaustive-deps`) | Low |
| `dangerouslySetInnerHTML` | 4 sites, none render AI output: JSON-LD via `JSON.stringify` (`app/page.tsx:107`, `app/company/[ticker]/page.tsx:113`, `app/filing/[id]/page.tsx:152`) and the static theme bootstrap (`app/layout.tsx:106`). JSON-LD strings are not `<`-escaped (`</script>` in an EDGAR company name would break out) — theoretical | Low |
| AI output sanitization | All AI markdown goes through `react-markdown` (7 sites, no `rehype-raw`), which escapes inline HTML and drops `javascript:` URLs by default. No DOMPurify usage anywhere in app code; `dompurify@3.4.11` is a transitive dep of `posthog-js` only -> PR #640 is a lockfile-only patch, safe/low-urgency. Citation hrefs are scheme-checked (`CitationChip.tsx:13`, `SourceTrace.tsx:19`) | OK |
| Skeleton a11y rule (DS section 4) | Followed: `SkeletonText` owns `role="status"` (`components/ui/Skeleton.tsx:40,52`), wrappers role-less (`StreamingSummaryDisplay.tsx:245`) | OK |

---

## (C) Unfinished frontend work

> **Lead correction (PR #653 review, 2026-09-04):** `signup_completed` is emitted server-side (`backend/app/services/posthog_client.py:46`, covered by `test_beta_funnel_events.py`); the frontend helper at `lib/analytics.ts:50-57` is dead code to delete, not an event to wire. The `/pricing` finding stands, but the mechanism is that the whole page body sits inside one Suspense boundary (`page.tsx:458-464`) whose spinner fallback is what the server ships.


### C.1 Homepage sections review — the 9 unchecked items (`tasks/homepage-sections-review-findings.md` section 6)

Decision recorded 2026-07-06: Market Movers -> hide; Trending Filings -> hide + immediate EDGAR rebuild. Code state today:

| Item | Evidence | Status | Size | User impact |
|---|---|---|---|---|
| A1 Section impression instrumentation | `features/marketing/components/SectionImpression.tsx:36` -> `homepage_section_viewed`; wired in `NotableFilings.tsx:23`, `ReportingThisWeek.tsx:42`; `tests/unit/section-impression.spec.tsx`. Hardcoded `source: 'stocktwits'` still at `TrendingTickers.tsx:100` (moot, hidden) | Done (box unchecked) | — | Enables the 30-day CTR call |
| A2 Stop rendering internal error strings | `backend/app/services/trending_service.py:74,112,121,142` still build "Last error: ..." into `message`; endpoint `/api/trending_tickers` still public (`backend/main.py:355`) | Not done (moot on the homepage while B1 hides it; still leaks diagnostics to anyone hitting the API) | S | None on-site; API hygiene |
| A3 Neil runs PostHog queries P1-P6 | Founder action, no code signal | Unknown | — | Needed for the 30-day keep/kill call (deadline was ~2026-08-05, now passed) |
| B1 Hide Market Movers behind default-off flag | `lib/featureFlags.ts` `ENABLE_MARKET_MOVERS`; `app/page.tsx:96-101,226-234`; `tests/unit/market-movers-hidden.spec.tsx` | Done (box unchecked) | — | Error-string banner gone from the sales surface |
| B2 Retire trending backend + `TrendingTickers.tsx` | `backend/app/routers/trending.py`, `services/trending_service.py`, `tests/unit/test_stocktwits_fmp.py`, `frontend/features/companies/components/TrendingTickers.tsx` all exist; mounted at `main.py:355` | Not done | M | Dead code + a public endpoint calling dead FMP paths |
| B3 Retire FMP integration | `backend/app/integrations/fmp.py` exists; consumers `hot_filings.py`, `trending_service.py` (calendar_service only keeps a compat kwarg, `:27`) | Not done | S-M | — |
| B4 hot_filings honesty fix | Superseded by the rebuild, BUT `/api/hot_filings` is still mounted (`main.py:353`) with zero frontend consumers (grep `hot_filings` in frontend: 0). Its DB aggregation + FMP/Finnhub calls run for any anonymous caller; the `force_refresh` removal (#634) is not deployed | Superseded -> should be deleted | S | Cost/abuse surface only |
| B5 Frontend self-omission + honest copy | `NotableFilings.tsx:17` returns null on empty; `HotFilings.tsx` deleted | Done via rebuild | — | No dishonest "Trending" cards |
| B6 EDGAR-wide rebuild ("Notable filings") | Router `backend/app/routers/notable_filings.py`, card + section components, `NotableFilings.spec.tsx`; mounted at 4994360 so prod has it. BUT `NOTABLE_FILINGS_ENABLED=False` by default (`config.py:405-410`) and prod returns `status:"empty"` -> section never renders | Built, not switched on | S (ops) + quality review | Homepage currently has NO "what just hit EDGAR" surface — the product's own output is not shown to visitors |

Decision needed from the founder: (1) flip `NOTABLE_FILINGS_ENABLED` + schedule `scripts/notable_filings_job.py` after eyeballing one week of its output for the credibility failure modes the review warned about (microcap junk, 8-K noise); (2) approve the teardown PR (B2 + B3 + delete `hot_filings`); (3) doc hygiene — check the boxes / archive the findings file, fix the dangling "DEPLOYMENT.md section 12" pointer (`findings.md:5`; DEPLOYMENT.md has 4 sections).

### C.2 Other unfinished / debt items

| Item | Evidence | Status | Size | User impact |
|---|---|---|---|---|
| Pricing page server-renders nothing | `app/pricing/page.tsx:42` `useSearchParams()`; live body = chrome only | Open | S (move `useSearchParams` into a tiny Suspense-wrapped child or read `window.location` post-hydration as the filing page does) | Sales page invisible to crawlers/preview scrapers; Lighthouse SEO warn |
| Risk cards all titled "Risk Factor" | `SummaryRisks.tsx:40`; live `/filing/3` has 5x `<h4>Risk Factor</h4>` | Open | S (frontend: derive title from first clause of `summary` or drop the h4 when no title; backend: emit `title`) | Reader can't scan risks; screen-reader heading list is useless |
| Company display names in EDGAR caps | `company/[ticker]/page.tsx:27-33`, `page-client.tsx:399`; live "MICROSOFT CORP" | Open | S (title-case helper with an exceptions list, or backend `display_name`) | Every non-Apple company page looks unpolished |
| Contact meta description entity | `app/contact/page.tsx:6` | Open | XS | Crawler-visible "&apos;" |
| `GlobalErrorBoundary` never reports to Sentry | `components/GlobalErrorBoundary.tsx:38-44` reads `window.Sentry`, which `@sentry/nextjs` does not set -> `captureException` is a silent no-op; `app/error.tsx:17` / `global-error.tsx:18` import the SDK correctly | Open (bug) | XS | Client render errors caught by this boundary are invisible in Sentry |
| `signup_completed` never fires | `lib/analytics.ts:51` defined, 0 call sites; register only fires `signup_started`/`signup_submitted` (`app/register/page.tsx:61,68`); `app/verify-email/page.tsx` fires nothing | Open | S | No activation event for "account verified" — the funnel has a hole between submit and first login |
| Mobile has no in-page section nav | TOC is `hidden lg:block` (`SummaryBlocks.tsx:104`); 10 sections per summary | Open | M | Phone readers must scroll the whole summary |
| Streaming progress not announced | `StreamingSummaryDisplay.tsx:270-300` progressbar has `aria-label` but no live region for stage changes; whimsy is `aria-hidden` | Open | S | SR users get no progress feedback during 30-60 s generation |
| `lodash` + webpack alias hack are dead | `package.json` `lodash ^4.18.1` has 0 imports in app code and no other requirer in `package-lock.json` (only root line 19); `next.config.js:66-86` aliases lodash for a recharts-2-era issue (recharts is 3.9.2) | Hypothesis (verify with `npm ls lodash`) | XS | Build config noise |
| prod-smoke e2e never runs | `tests/e2e/prod-smoke.spec.ts` needs `SMOKE_BASE_URL`; no workflow sets it (grep `.github/`: 0) | Open | S (scheduled workflow) | The stale-deploy class it was written for went unnoticed for 7 weeks |
| Filing-page e2e self-skips in CI | `tests/e2e/filing-page-renders.spec.ts:27` `test.skip(!hasHeading)` because CI has no backend | Open | M (route-mock the 3 read endpoints via `page.route`) | Core journey has no automated browser coverage |
| `SentryTestButton.tsx` dead chrome | 0 importers; allowlisted in `componentsAllowlist.spec.ts` | Open | XS | — |

Reading-experience notes that are fine as built (verified in code): loading/empty/error states exist for the viewer
(`FilingViewer.tsx:116-143`), summary (`SummaryDisplay.tsx:139-151`, `SectionEmpty.tsx`), copilot (`CopilotMessage.tsx:356-380`,
role="alert"); wide tables scroll inside their own container (`DataTable.tsx:159`, `SummaryBlocks.tsx:221`); the only fixed
px widths are lg+ pane widths (`AskCopilotRail.tsx:56`, `FilingViewer.tsx:184`); direction never rides on color alone
(`FinancialMetricsTable.tsx:129-135`, `WhatChanged.tsx:54-63`); Change Report renders only when `has_changes`
(`SummaryDisplay.tsx:200`); Trace-to-Source degrades from in-app highlight -> popover -> EDGAR link with touch bottom-sheet
(`SourceTrace.tsx:254-327`); SSE readers share the 401 refresh dance (`lib/api/streamRefresh.ts`) and retry once only before
first content (`summaries-api.ts:173-200`), idle timeout 120 s (`:75`).

---

## (D) Risks

| Risk | Evidence | Severity | Mitigation |
|---|---|---|---|
| Stale, dishonest sitemap served to Google for 7+ weeks — 1 400 noindex stub URLs advertised, `lastmod` frozen at 2026-07-16, `/terms` missing; will not self-heal | Live www sitemap vs API sitemap (A); `app/sitemap.ts:44` fetch-cache + 6.35 MB payload; backend fix undeployed | P0 (SEO) — highest-leverage fix in this audit | Deploy backend@main (shrinks payload to summarized filings only); in `app/sitemap.ts` use `cache: 'no-store'` and rely on the route-level `revalidate = 3600`, or stream/paginate into a sitemap index; add a unit test that the proxied entry count/lastmod is not from a cached body; correct `docs/SEO_AUDIT.md:63` "[FIXED]" |
| Production backend 7 weeks behind main with the frontend already on main | `git log 4994360..HEAD`; deploy-backend gates on e2e (`ci.yml:289`) whose Playwright install is flaky (`ci.yml:228-245`) | P0 (process) | Re-run/repair the 07-16 deploy; add the prod-smoke spec as a scheduled workflow so frontend/backend skew is detected within a day |
| Pricing page invisible to crawlers | (A) `/pricing` row; `pricing/page.tsx:42` | P1 | Suspense-scope `useSearchParams`; add Product/Offer JSON-LD while there |
| Node 20 runtime past EOL (2026-04-30) | `package.json` `engines.node 20.x`, `.nvmrc 20.19.0`, `ci.yml:51,91,219` | P1 (platform deprecation on Vercel/GitHub runners) | Bump to Node 22 LTS in engines/.nvmrc/CI/Vercel project settings; run full gate |
| Sentry source maps probably not uploaded -> minified prod stack traces | `next.config.js:89-93` `withSentryConfig(nextConfig, { silent: true })` with no org/project/authToken; no `SENTRY_AUTH_TOKEN`/`SENTRY_ORG`/`SENTRY_PROJECT` anywhere in repo, docs or CI (grep) — hypothesis: unless set in the Vercel dashboard, the plugin silently skips upload (`silent: true` hides the warning) | P1 (observability) | Set the three env vars in Vercel; drop `silent`, add `widenClientFileUpload: true`; confirm a release with artifacts in Sentry. `instrumentation-client.ts` also has no `tracesSampleRate` (no perf data — acceptable for now) |
| Client-side error reporting hole | `GlobalErrorBoundary.tsx:38-44` (`window.Sentry` no-op) | P1 | Import the SDK and call `Sentry.captureException(error, { extra: errorInfo })` |
| PostHog is blind until cookie consent | `app/posthog-provider.tsx:60-75` returns before `init` when no preference stored; `posthog.capture` before init is a no-op, so `signup_gate_shown`, `example_cta_clicked`, `$pageview` on first visit are lost for every visitor who hasn't clicked the banner | P1 (funnel measurement) | Cookieless/memory persistence pre-consent (`persistence: 'memory'`, no recording) or explicitly track banner acceptance rate so denominators are known |
| Copilot / summary SSE: automatic retry only before first content; no resume | `summaries-api.ts:173-200` (MAX_ATTEMPTS 2, never retries after `deliveredContent`), idle timeout 120 s (`:75`); copilot mirrors (`copilot-api.ts:6`) | P2 (behaviour is honest: user gets "Generation interrupted" + Retry, and the backend serves cached progress) | Acceptable; consider surfacing "resume" copy when the backend persisted a partial |
| Public dead endpoints from the homepage review still live | `/api/hot_filings` (DB aggregation + FMP/Finnhub per anonymous call; `force_refresh` removal undeployed), `/api/trending_tickers` (leaks "Last error" diagnostics) | P2 (cost/abuse) | Teardown PR (C.1 B2-B4) |
| TypeScript 7 bump (PR #629) would break lint and the Vercel build | CI on #629: `frontend-tests`, `e2e-tests`, `lighthouse` failed; log: ESLint crashes `TypeError: Cannot read properties of undefined (reading 'Cjs')` in `@typescript-eslint/typescript-estree` (peer `typescript >=4.8.4 <6.1.0`); Vercel preview deployment errored | P2 (only if merged) | Close with `@dependabot ignore this major version` and add `typescript` to the semver-major ignore list in `.github/dependabot.yml` alongside next/react; revisit when `eslint-config-next`/typescript-eslint declare TS 7 support |
| Justified body text on narrow phones | `SummaryBlocks.tsx:134` `text-justify [hyphens:auto]`, `.markdown-body p` (DS section 3 acknowledges rivers risk) | P2 (unverified — no screenshots possible here) | Verify on a 360-390 px device; consider `sm:text-justify` (ragged on phones) |
| Deprecated transitive packages | `glob@7/10`, `rimraf@3`, `inflight` via `@lhci/cli`/`chrome-launcher` devDeps (`package-lock.json` `"deprecated"` x4) | P2 (dev-only) | Track `@lhci/cli` upgrade; overrides already in place |

Dependency currency snapshot (lockfile): next 16.2.10 · react/react-dom 18.3.1 (ADR-0005 pin still valid — Next 16.2.10 peer
range includes ^18.2, no React-19-only need) · typescript 6.0.3 · @sentry/nextjs 10.63.0 · posthog-js 1.396.7 · recharts 3.9.2 ·
react-markdown 10.1.0 · tailwindcss 3.4.19 · @typescript-eslint/parser 8.62.0 · dompurify 3.4.11 (transitive, posthog-js).
Open Dependabot PRs touching frontend: #652 (17 minor updates, 2026-08-31), #641 (fast-uri), #640 (dompurify), #629 (TS 7 — failing).

---

## (E) Ranked top-5 frontend investments

1. Fix the sitemap pipeline end-to-end (P0, S). Deploy backend@main, switch `app/sitemap.ts` to `cache: 'no-store'` (or a sitemap index), add a regression test, and correct `docs/SEO_AUDIT.md`. This is the single biggest SEO defect and it is silent.
2. Make the reading surface scannable (product core, S-M). Real risk titles instead of five "Risk Factor" h4s; a mobile section jump-nav (sticky select or collapsible TOC); title-cased company names in H1/title. All three are visible on the very first example a visitor opens.
3. Close the observability holes (P1, S). Sentry source-map upload env + `GlobalErrorBoundary` SDK import; `signup_completed`/verify-email event; PostHog pre-consent strategy; a scheduled `prod-smoke` workflow so frontend/backend skew is caught in a day, not 7 weeks.
4. Ship the "Notable filings" decision (product, S ops + review). The homepage currently shows none of the product's output. Either flip `NOTABLE_FILINGS_ENABLED` after a one-week quality look, or explicitly kill the slot; then land the trending/hot_filings/FMP teardown PR and close the review doc.
5. Platform currency (P1, S). Node 20 -> 22 across engines/.nvmrc/CI/Vercel; close TS 7 PR #629 and add `typescript` to the Dependabot major-ignore list; merge lockfile-only #640; remove dead `lodash` + the recharts webpack alias (after `npm ls lodash` confirms).

Deferred/OK as-is: React 18 pin (ADR-0005); design-system grep gates all clean; query-key and components-allowlist gates exist and
match CLAUDE.md; AI output rendering is sanitized by construction (react-markdown, scheme-checked citation links).
