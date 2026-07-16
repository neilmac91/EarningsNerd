# SEO Roadmap — programmatic SEO within ~$50/mo

Goal: rank for "{ticker} 10-K summary / earnings / SEC filings" queries the way Investing.com
or Public.com do, with thousands of indexable company and filing-summary pages — without the
infra bill escaping the ~$50/mo ceiling. Phases are ordered so each one only spends money after
the previous one proved demand. Baseline today: ~$38–45/mo fixed (Cloud SQL + Cloud Run min
instance); every phase lists its *delta*.

**Prerequisite for everything: `LAUNCH_CHECKLIST.md` §1–3 (Search Console, sitemap submission,
permanent apex redirect). No phase matters until Google is actually reading the sitemap.**

---

## Phase 0 — shipped on `seo-audit-quick-wins` (delta: $0/mo)

Server-rendered company + filing pages (on-demand ISR), real per-page metadata + canonicals,
honest 404s/redirects/noindex, truthful content-only cached sitemap, API-host crawl-off,
per-IP limits on live-EDGAR endpoints, Vercel functions co-located with Cloud Run.

What to expect: indexed pages go from ~0 usable to (sitemap size) over 2–6 weeks after GSC
submission. Rankings for long-tail "{small-cap ticker} 10-K summary" queries come first;
head terms take months and backlinks.

## Phase 1 — widen the indexable surface with pregeneration (delta: ~$3–15/mo, elastic)

The sitemap now only advertises filings that have summaries; the surface is therefore capped by
how many summaries exist. The pregenerate cron already exists (weekly, Cloud Run job) — the
lever is its ticker × form coverage:

1. Expand pregeneration to the S&P 500's latest 10-K + latest 10-Q (~1,000 summaries). At
   ~$0.02–0.05/summary that's a **one-time ~$25–50** DeepSeek spend, then ~$5–10/quarter to
   keep current (only new filings get summarized; dedup means nothing is ever paid twice).
2. Then Russell-1000 / full coverage as search impressions justify it — check GSC queries
   first, spend second. Full 8,000-ticker × 2-form coverage would be a one-time ~$300–800;
   don't do it speculatively.
3. Quality gate awareness: partial-quality summaries persist with real content today, so they
   are sitemap-listed and indexable. That's fine to start; if GSC flags thin content, tighten
   the sitemap filter to full-quality tiers only (`raw_summary.quality.tier`).
4. Watch the 45k-URL sitemap cap; move to a sitemap *index* (split by type: companies /
   filings-by-year) when the filing count approaches it. The frontend proxy
   (`app/sitemap.ts`) needs `generateSitemaps()` support at that point — small, known change.

Guardrails already in place: generation runs through the one orchestrator with the 6-concurrent
semaphore and EDGAR token bucket, so a big pregenerate batch is a slow drip, not a stampede.

## Phase 2 — content depth & internal linking (delta: $0–20/mo)

What makes programmatic pages rank is being *less* thin than competitors:

1. **Company page enrichment (server-rendered):** last-N summarized filings with one-line
   excerpts, latest revenue/net-income deltas from the XBRL facts already in Postgres
   (financial_fact) — no new data sources, no AI spend, pure templating.
2. **Filing page FAQ block:** render 3–5 Q&A pairs derived from the existing summary sections
   ("What did {TICKER} report for revenue?"). Honest `FAQPage`/`Article` JSON-LD only where the
   answers are real. This is the highest-leverage rich-result play; needs an eval-gated prompt
   or pure section-templating (prefer templating: $0).
3. **Cross-linking:** peers (already in DB) → "Compare with {peer}" links; filing → prior
   filing; company → sector hub pages. Crawl depth and PageRank flow, $0.
4. **Earnings-calendar pages** (`/calendar` exists, flag-gated): "{TICKER} earnings date"
   queries are huge; a server-rendered weekly calendar page + per-company earnings row is
   nearly free from the existing earnings engine.
5. Optional: a small blog/changelog for backlink bait (Vercel static, $0 infra; your time is
   the cost). If the product is commercial on Vercel, budget Pro ($20/mo) here — decision item.

## Phase 3 — scale hardening, spend only when metrics demand (delta: $0 → +$25–45/mo)

Trigger-based, not calendar-based. Watch the dashboards in `LAUNCH_CHECKLIST.md` §6:

| Trigger (sustained) | Action | Cost delta |
|---|---|---|
| Cloud SQL connections >80% or CPU >70% | `db-custom-1-3840` tier | +~$25/mo |
| Cloud Run p95 >1.5s or frequent 2-instance saturation | max-instances 3 (check pool math: 3×20 conns needs the DB upgrade first) | +$0–10/mo |
| `/api/companies/search` abuse in logs | generous per-IP limit (e.g. 120/min) + negative cache for unknown tickers (24h TTL in DB or L1) | $0 |
| GSC crawl-stats show heavy bot traffic on ISR misses | lengthen revalidate windows (company 30→60min) | $0 |
| DeepSeek monthly spend >$15 | check PRO_SUMMARY_MONTHLY_CAP / batch sizes before paying more | $0 |

Explicitly **not** planned: Redis in prod (ADR-0004 holds — ISR + DB caches cover the misses),
multi-region, queues, or any second generation path (CLAUDE.md rule 1).

## Ongoing hygiene

- GSC weekly during launch quarter: Coverage (soft-404s, duplicates), Performance (which
  queries actually land — steer Phase 1 coverage by this), Enhancements (structured-data
  errors).
- Keep `lastmod` honest: if summaries get regenerated in bulk (prompt upgrades), consider
  surfacing `summary.updated_at` as the filing-page lastmod.
- Every new public page ships with: server-rendered content, unique title/description,
  canonical, and a sitemap decision (in or out) — this is now the repo convention; the
  no-em-dash-style structural gates culture applies (CLAUDE.md rule 12) if regressions appear.
