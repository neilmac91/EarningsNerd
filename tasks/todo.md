# SEO audit + quick wins (branch: seo-audit-quick-wins)

Goal: make the programmatic SEO surface (company + filing pages) real for crawlers without
architectural upheaval, fix sitemap/robots/metadata correctness, close crawler-driven cost
holes, and deliver the audit/roadmap/launch docs. Budget frame: ~$50/month at 1k–5k users.

Evidence base: live-site checks (www.earningsnerd.io HTML/titles/sitemap; apex 307) + code
audit of frontend rendering and backend cost paths (see docs/SEO_AUDIT.md).

## Frontend quick wins

- [ ] `/company/[ticker]`: convert to server component with on-demand ISR — server-fetch
      company + filings, seed the existing client page via React Query `initialData`, real
      `generateMetadata` (async params — the old sync read broke titles on Next 16), canonical,
      JSON-LD (Breadcrumb + Corporation), `notFound()` on unknown ticker (kills soft-404s),
      uppercase-ticker permanent redirect, noindex for unsupported-foreign stubs.
- [ ] `/filing/[id]`: same treatment — server-fetch filing + summary (read-only endpoints,
      never triggers generation), real metadata incl. summary excerpt description, canonical,
      Breadcrumb JSON-LD, noindex when no summary content exists yet, `notFound()` on unknown
      id, ticker-style ids (`/filing/AAPL`) get canonical→`/company/AAPL` + noindex.
      Replace `useSearchParams` in the filing client (demo/debug flags) with a post-hydration
      read so the page can statically render.
- [ ] `robots.ts`: disallow auth/utility routes (login, register, verify, reset, etc.).
- [ ] `sitemap.ts`: fallback entries synced with backend static list (+ /terms).
- [ ] `/pricing`: add layout metadata (title/description/canonical).
- [ ] `vercel.json`: region iad1 → pdx1 (co-locate SSR with Cloud Run us-west1).

## Backend quick wins

- [ ] `sitemap.py`: truthful lastmod (company = latest filing date; no fake "today"),
      only companies with filings, only filings with real summaries (noindex'd stubs must not
      be advertised), column-only queries, 1h in-process cache, 45k safety cap, add /terms.
- [ ] API host `robots.txt`: Disallow all (API JSON should never be crawled; sitemap lives on www).
- [ ] `hot_filings.py`: remove anonymous `force_refresh` cache-bypass param.
- [ ] Per-IP rate limits on the two always-live-EDGAR public endpoints that are product-flag-OFF
      (`/api/companies/{ticker}/insiders`, `/api/search/full-text`).
- [ ] Tests for all of the above; update robots smoke assertion.

## Docs

- [ ] `docs/SEO_AUDIT.md` — findings, evidence, impact/effort/cost ranking.
- [ ] `docs/SEO_ROADMAP.md` — phased plan with monthly cost per phase.
- [ ] `docs/LAUNCH_CHECKLIST.md` — founder-only actions (GSC, Bing, DNS 308, env flips, dashboards).

## Verification

- [ ] Frontend: lint + tsc + vitest + build all green.
- [ ] Crawler-eye check: `next build` + `next start` against a local mock API; curl
      `/company/AAPL` and `/filing/{id}` with no JS — confirm real title, canonical,
      H1, filings links, summary text in raw HTML.
- [ ] Backend: ruff + bandit + pytest green.

Deferred to roadmap (not in this diff): summary pregeneration scale-out, sitemap index files
past 45k URLs, per-IP limits on `/api/companies/search` (core UX — needs limit tuning),
negative-caching for unknown tickers, Cloud SQL/instance scaling, content/blog surface.
