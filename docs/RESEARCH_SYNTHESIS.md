# Research Synthesis & Value Thesis

**Date:** 2026-06-17 · **Inputs:** 3 parallel research streams (competitive scan, freemium/monetisation, YC operating principles), live-web-verified mid-June 2026. This is a synthesis, not a link dump — key sources cited inline.

---

## Executive summary (read this first)

1. **There is open white space at $10–20/mo.** Among *live* specialist competitors, only Simply Wall St Premium (~$11/mo) and Quartr Core (~$20/mo) sit in the band; Koyfin and Fiscal.ai start paid at **$39/mo**, and Atom Finance exited the consumer market (acquired by Toggle AI, 2024). EarningsNerd can anchor a polished retail tier here.
2. **The real threats are free, not paid.** [Public.com's Alpha](https://help.public.com/en/articles/9354354-what-is-alpha) does AI over SEC filings + earnings calls **free**, bundled with a brokerage; **PublicView.ai** (identical positioning) was acquired by Aether Holdings (NASDAQ: ATHR, Feb 2026) and is now capitalised. We do not out-feature them — we out-**trust** and out-**craft** them.
3. **Source-grounding is now table stakes, and under-delivered at retail.** [Fiscal.ai](https://www.matchmybroker.com/tools/fiscal-ai-review) and [Quill AI](https://www.quillai.com/) ($250/mo) cite every claim back to the filing; free retail tools' grounding is undocumented. Our wedge: **institutional-grade, source-cited, plain-English, "what-changed" summaries at a sub-$20 price with a clean UX** — academically validated as a real need (["Bloated Disclosures: Can ChatGPT Help Investors Process Information?"](https://arxiv.org/html/2306.10224v4); MD&A readability has declined 26 years running).
4. **Copy Simply Wall St's freemium *shape*:** unlimited free watchlists (drives word-of-mouth) + **meter the core unit** (summaries/month). Gate depth, export, history, real-time alerts, 8-K, and advanced comparison to Pro.
5. **Monetise with a reverse trial, not a hard wall:** new users get full-Pro depth for ~7 days (no card), then drop to Free — so they paywall *after* feeling the ceiling. Reverse trials convert ~8–12% vs ~3–5% plain freemium ([Growth Unhinged, 2026](https://www.growthunhinged.com/p/free-to-paid-conversion-report)).
6. **Price:** **Pro $14/mo or $140/yr** ("2 months free", ~16.7% — the norm per [Recurly benchmarks](https://recurly.com/research/saas-benchmarks-for-subscription-plans/)). Single tier now; model entitlements as named flags so a future **Team** tier is a config row, not a rewrite.

---

## Competitive landscape (live, mid-2026)

| Product | Free tier | Paid (in/near $10–20) | What's gated | Why it matters to us |
|---|---|---|---|---|
| **Simply Wall St** (closest analog) | **Unlimited watchlists**, **5 reports/mo**, 1 portfolio/10 holdings | Premium ~$11/mo ($120/yr); Unlimited ~$21.50/mo | Report volume, portfolio breadth, Excel/PDF export (Unlimited), brokerage sync | The freemium *shape* to copy: free watchlist + metered core report |
| **Stock Analysis** | Screener, watchlists, ~5yr history, 15-min delayed, **ads** | Pro $9.99/mo ($79/yr); Unlimited $199/yr | Ads, history depth (5→40yr), exports (1/day→∞), real-time | Retention = speed + free screener + calendars; export as upsell |
| **Koyfin** | 2 watchlists / 2 screens / 2 dashboards, 5 alerts, 2yr fin, 45-day transcripts | none < $39/mo | "2/2/2" cap, history cliff, export, premium news | Leaves $10–20 wide open; great conversion-lever design |
| **Fiscal.ai** (ex-FinChat) | Cited AI summaries, 10yr fin, 2yr KPI, 1 dashboard | Pro $39/mo; Max $79/mo | Custom AI summaries, **click-through filing audit + export (Max)** | Source-citation is table stakes; audit trail is their top-tier wedge |
| **Quartr** | Earnings calls + transcripts + **AI chat free** (mobile) | Core ~$20/mo; Pro = sales | Cross-document search, workspaces, export, seats | Gives away qualitative research free; monetises scale/teams |
| **Public.com Alpha** | **AI over filings + calls, free** (brokerage-bundled) | — | — (free) | **Existential free threat**; grounding undocumented = our opening |
| **PublicView.ai** | — | "extremely affordable", ATHR-backed (Feb 2026) | — | Identical positioning, now funded — watch closely |
| **Quill AI** | — | **$250/mo** (institutional) | — | Sets the sentence-level-citation quality bar we bring downmarket |

**Patterns worth adapting:** (a) free unlimited watchlist + metered core unit; (b) export (PDF/CSV) as a clean paid wedge — universal; (c) history/retention cliff as conversion lever; (d) real-time vs delayed as a speed-based WTP signal; (e) recurring catalysts (new filings/earnings) as the retention engine; (f) source-citation + "what changed" as the trust differentiator free tools skip.

---

## The Value Thesis (one page — every feature is checked against this)

**Who:** retail investors who want to understand a specific company's filings without reading 100 pages or paying for a terminal.

**The job-to-be-done:** *"Tell me what this filing says, what changed since last time, and whether I should care — in plain English I can trust."*

**Our defensible wedge (the four things we must be best at):**
1. **Trust / grounding** — every figure and claim is traceable to the filing (we already store XBRL + section excerpts; we have a `/compare` route). This is what free tools (Public Alpha) don't clearly offer and only $250/mo tools do well.
2. **"What changed"** — filing-over-filing diffing ("vs last 10-Q/10-K") is largely an enterprise feature; bringing it to retail is a moat that maps to our existing compare engine.
3. **Plain English + explained jargon** — not just compression; define "riskless principal," "in arrears" inline. The SEC's own plain-language effort is 25 years unfinished.
4. **Craft / UX** — competitors with the same data lose on interface (TheSECAI "poor UX"). A fast, clean, glanceable product wins retail.

**The monetisation rule (non-negotiable):** *a free user hits the paywall only after they've already felt the value.* Operationalised as: (a) a no-card reverse trial that reveals Pro depth first, then (b) a metered core unit (summaries/month) so value is felt repeatedly before the wall, and (c) contextual, "peek-but-locked" paywalls at the natural feature boundary — never a generic upfront wall ([RevenueCat on paywall placement](https://www.revenuecat.com/blog/growth/paywall-placement/)).

**What "free" must achieve:** be genuinely useful and **evangelizable** — a free user should want to tell a friend. That means: search, company pages, **unlimited watchlist**, a meaningful number of full-depth summaries, and basic (delayed) new-filing alerts stay free forever.

**The North-Star metric (track weekly):** **weekly returning users who read ≥1 summary they did *not* generate themselves that week** — i.e. they came back *for the content* (a watched company filed), not just to run a one-off query. Filings are episodic (quarterly), so the existential risk is "great one-time read, then forgotten." This metric proves the watchlist→alert→return loop works and is the precondition for conversion. Pair monthly with the [Sean Ellis 40%-"very disappointed" PMF survey](https://www.zonkafeedback.com/templates/sean-ellis-product-market-fit-survey-template).

---

## Free vs Pro philosophy

1. **Free = discovery + habit + word-of-mouth.** Search, company/filing pages, unlimited watchlist, a meaningful cap of full-depth summaries, delayed new-filing email alerts. A free user can fully experience and evangelize the core magic.
2. **Pro = volume, depth, speed, power-user surface.** When demand exceeds the free cap, or the user wants history, exports, 8-K coverage, real-time alerts, advanced comparison, or premium-model priority — those are willingness-to-pay signals.
3. **The summary is the metered unit, not a hard feature wall** (Simply Wall St's model) — so value is felt repeatedly first.
4. **Never gate the first experience** — reverse-trial reveal.
5. **Entitlements, not tiers** — named flags (`monthly_summary_limit`, `can_export`, `realtime_alerts`, `eightk_coverage`, `watchlist_limit`, `history_retention_days`, `priority_model`) resolved per-plan, so adding "Team" later is a mapping change.

### Recommended gating split (reconciled with what the code already enforces)

| Lever | Free | Pro | Status in code today |
|---|---|---|---|
| Watchlist slots | **Unlimited** (word-of-mouth) | Unlimited | Limit (20) defined in `entitlements.py` but **not enforced** — recommend keeping free **unlimited** and dropping the 20 cap |
| Summaries / month | **Cap (≈5–10)** | Unlimited | ✅ 5/mo enforced (`summary_pipeline.py`) |
| Summary depth/length | Standard | Deepest + premium model | Reveal full depth in trial |
| New-filing alerts | **Delayed email** | **Real-time** + 8-K | Not built yet (no alert infra) |
| 8-K coverage | ✕ | ✅ | Not built |
| History retention | Recent | Full | Not gated |
| Exports (PDF/CSV) | ✕ | ✅ | ✅ enforced (`summaries.py`) |
| Advanced comparison | Basic / limited | Full | ✅ compare is Pro (`compare.py`) |
| Portfolio / multi-filing digest | ✕ | ✅ | Not built |
| Priority premium-model summary | ✕ | ✅ | Maps to `AI_FAST_MODEL`/default split (see cost note) |
| Rate-limit removal | Standard | Relaxed | Partial (guest quota flag exists) |

**Cost mapping (two-model strategy):** Free/standard summaries → the cheaper production model (`AI_DEFAULT_MODEL`, currently DeepSeek; `AI_FAST_MODEL` for low-risk sub-tasks). Pro "priority" summaries → the premium model. This makes premium-model inference a **paid** entitlement, aligning marginal cost with revenue. Real-time alerts and premium-model summaries should be **Pro-only from day one** (confirm — clarifying Q).

---

## Pricing & packaging recommendation

- **Plans:** Free + **Pro** (single paid tier now). Entitlement system built for N tiers.
- **Price:** **$14/mo** or **$140/yr** ("2 months free", ~16.7% off; default the toggle to annual). In-band, anchored just above Simply Wall St Premium and below its Unlimited.
- **Trial:** **7-day full-Pro reverse trial, no credit card**, auto-downgrade to Free. Pair with a **14-day money-back guarantee** on conversion for trust. (No-card maximises reach + trust at low ACV; card-up-front converts higher but throttles the word-of-mouth funnel.)
- **Conversion mechanics:** usage-limit paywall on summaries, contextual "peek-but-locked" prompts (show the export/8-K/real-time toggle greyed), annual "2 months free" framing, Stripe dunning for involuntary churn.

---

## The decision filter (apply to every feature in the plan)

Score Yes/No. **2+ No → cut or defer. Any No on #1 or #2 → cut.**

| # | Principle | Test question | Fails if… (our context) |
|---|---|---|---|
| 1 | Make something people want | Did a real retail investor ask for this? | A "filing diff heatmap" built because it's cool, when users only ask "is this stock in trouble?" |
| 2 | 100 who love > 1,000 who like | Will a core user *love* this? | A generic market-news feed that broadens appeal but dilutes the "I finally understand this 10-K" magic |
| 3 | Retention before acquisition | Does it bring existing users back next quarter? | Referral widgets before watchlist alerts that pull users back when a tracked company files |
| 4 | Narrow focus / sequence | On the critical path to "read one summary, trust it"? | Portfolio import + tax lots before the summary is loved |
| 5 | Do things that don't scale | Can we test the value manually first? | Auto custom-prompt profiles before hand-curating for 20 users |
| 6 | Default alive | Moves conversion or cuts cost? | A real-time price ticker (infra cost, no conversion lift) pre-revenue |
| 7 | Avoid vanity metrics | Success = a behaviour (return/save/upgrade), not a count? | Justifying by "time-on-page" |

**Anti-patterns this catches:** AI/feature sprawl (#1,#4), vanity dashboard (#2,#7), premature scaling (#5,#6), acquisition-before-retention (#3), settings junk-drawer (#7 — cut any setting used by <2%).

**Before building each section:** (a) 5–10 user conversations, (b) instrument one primary event, (c) define the one metric. Dashboard metric = % of sessions that reach a summary; Watchlist metric = % of watchlist users who return on a new filing (the retention engine); Settings metric = setting-change rate (cut unused toggles).
</content>
