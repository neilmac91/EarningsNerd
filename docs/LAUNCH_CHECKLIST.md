# Launch Checklist — founder-only actions

Everything here needs your accounts/credentials or is a product/spend decision; none of it can
be done from the repo. Ordered by impact. Companion docs: `SEO_AUDIT.md`, `SEO_ROADMAP.md`.

## 1. Google Search Console — the single highest-impact action

1. https://search.google.com/search-console → Add property → **Domain** property
   `earningsnerd.io` (covers apex + www + http/https in one).
2. Verify via the DNS TXT record Google gives you (add it wherever your DNS is hosted —
   the record is `google-site-verification=...`).
3. After verification: **Sitemaps → submit `https://www.earningsnerd.io/sitemap.xml`**.
4. URL Inspection → paste `https://www.earningsnerd.io/` and one company page (e.g.
   `/company/AAPL`) and one summarized filing page → "Request indexing" on each. This kicks
   off crawling days before organic discovery would.
5. While you're there: Settings → confirm Googlebot sees the site (no manual actions).

## 2. Bing Webmaster Tools (10 minutes, also feeds DuckDuckGo/Ecosia)

1. https://www.bing.com/webmasters → "Import from Google Search Console" (fastest) or verify
   the same DNS TXT way.
2. Submit the same sitemap URL.

## 3. DNS / redirect config (Vercel dashboard)

- Vercel → Project → Settings → Domains: make `www.earningsnerd.io` the **primary** domain and
  set `earningsnerd.io` to **Redirect (308 Permanent)** to www. Today the apex answers with a
  **307 Temporary** (verified 2026-07-16), which tells Google the move is temporary and splits
  ranking signals across the two hosts.
- Sanity-check after: `curl -I https://earningsnerd.io/` → expect `308` + `location: https://www.earningsnerd.io/`.

## 4. Env vars to check/flip at launch (Vercel dashboard)

- **`WAITLIST_MODE`** — production is currently **not** gated: the homepage serves full
  content (verified live; `vercel.json` sets `WAITLIST_MODE=false`). If you believed the
  waitlist gate was on, it isn't — decide which state you want for the pre-beta window. For
  SEO, leave it off; if you turn it on, `/company/*`, `/filing/*` and `/pricing` stay
  crawlable and only `/` 307s to `/waitlist` (fine short-term; flip off at launch day).
- **`NEXT_PUBLIC_EXAMPLE_FILING_ID`** — confirm it's set in the Vercel dashboard to a filing
  whose summary is generated; it powers the homepage hero example (server-rendered, an SEO
  asset).
- **Backend `REGISTRATION_MODE=invite_only`** (Cloud Run env) — flip to open when beta opens.
  Until then, the signup gate that filing pages funnel organic visitors into dead-ends for
  anyone without an invite.
- After the branch deploys, verify ISR is live: `curl -sI https://www.earningsnerd.io/company/AAPL`
  twice — second response should show `x-vercel-cache: HIT` (or `STALE`), and the HTML title
  should contain "Apple Inc. (AAPL)".

## 5. Plan / billing decisions (roadmap Phases 1–3 reference these)

- **Vercel plan:** a commercial product on the Hobby plan violates Vercel's fair-use terms —
  budget Pro ($20/mo) or confirm current usage/plan status. This is the biggest single line
  item vs the $50 ceiling; the roadmap assumes you decide this consciously.
- **DeepSeek pregeneration budget:** approve the one-time ~$25–50 S&P-500 backfill
  (roadmap Phase 1) — it directly determines how many filing pages can be indexed.
- **Cloud SQL upgrade trigger:** pre-approve (or veto) the `db-custom-1-3840` (~+$25/mo) jump
  so it can happen fast if connection/CPU alerts fire during launch.

## 6. Dashboards to watch (launch week: daily; then weekly)

| Dashboard | Where | What matters |
|---|---|---|
| GSC Coverage + Performance | Search Console | indexed-page count rising; soft-404/duplicate warnings ~0; which queries get impressions (steers pregeneration coverage) |
| Vercel Usage + Observability | Vercel dashboard | function invocations (should stay near-flat thanks to ISR), ISR cache hit ratio, bandwidth |
| Cloud Run metrics | GCP console → earningsnerd-backend | instance count (should sit at 1, spike to 2), p95 latency, 429/5xx rates |
| Cloud SQL | GCP console → earningsnerd-db | active connections (<40), CPU (<70%) |
| Backend metrics | `GET /metrics` (admin JWT) | EDGAR circuit-breaker state, rate-limit hits |
| DeepSeek spend | provider console | monthly total vs ~$15 comfort line |
| PostHog funnel | PostHog | organic-landing → summary_viewed → signup conversion |
| Sentry | Sentry | new hydration/SSR errors after this branch deploys (watch the first day) |

## 7. Nice-to-have, not launch-blocking

- Set up a Slack/email alert on GSC "Coverage issues detected" emails (GSC sends these
  automatically once verified).
- Register the brand SERP: create/claim a Crunchbase page, LinkedIn company page, and X/Twitter
  handle linking to www.earningsnerd.io — the first backlinks, and they own the brand query.
- Submit to a handful of directories that link real tools (Product Hunt at beta, BetaList,
  fintech tool lists) — early backlinks matter disproportionately for a fresh domain.
