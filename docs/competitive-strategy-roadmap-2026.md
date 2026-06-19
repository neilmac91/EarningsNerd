# EarningsNerd — Competitive Strategy & Product Roadmap (2026)

> **Author's note:** This is a strategic synthesis document, not an implementation spec. It maps
> EarningsNerd's *actual* code-level capabilities against a forensic teardown of two adjacent
> platforms — **Stocktwits** (social/sentiment) and **Fiscal AI** (AI financial-data synthesis) —
> and converts the gap into four sequenced, file-specific plans. Every recommendation is anchored
> either to a concrete capability already in this repo or to a cited competitor learning.

---

## 0. The Strategic Thesis (read this first)

EarningsNerd sits between two poles:

- **Stocktwits** is an *attention graph*. Its defining metric is message-volume-weighted sentiment
  (the 1–100 "Stocktwits Score"), not price or fundamentals. It is fast, social, and addictive —
  but openly **manipulable via coordinated posting**, **mega-cap-skewed**, and legally defended by
  a wall of disclaimers ([WallStreetZen review](https://www.wallstreetzen.com/blog/stocktwits-review/)).
  It is the casino floor.
- **Fiscal AI** (formerly FinChat) is a *truth graph*. Its defining feature is a conversational
  Copilot **grounded in the S&P Market Intelligence dataset that cites every answer back to the
  source filing** and "tells you when it does not have the answer rather than making one up"
  ([matchmybroker](https://www.matchmybroker.com/tools/fiscal-ai-review),
  [WallStreetZen](https://www.wallstreetzen.com/blog/finchat-io-fiscal-ai-review/)). It is the
  research desk.

**EarningsNerd's wedge is the "third-wave coffee" of equity research: single-origin, traceable,
crafted, calm.** Our brand promise maps with unusual precision onto a *defensible product
philosophy*:

| Third-wave coffee value | EarningsNerd product expression | Why it beats the incumbents |
|---|---|---|
| **Provenance / traceability** ("this bean, this farm, this lot") | Every number and claim links to the exact SEC filing excerpt that produced it | Fiscal AI proves citations build trust; Stocktwits has *none* |
| **Curation over firehose** | We surface *what changed and why it matters*, not an infinite scroll | Stocktwits' feed is noise; we sell signal |
| **Craft & restraint** | Calm, editorial, dark-first UI; no flashing red/green casino meters | Stocktwits' mobile is buggy & cluttered; Fiscal AI admits "the interface could be sleeker" |
| **Honest labeling** | We tell you when a summary is *Partial*, and when the AI doesn't know | Direct steal of Fiscal AI's anti-hallucination ethos |

Concretely: **we do not become a social network. We become the most trustworthy, best-designed
way to understand a single filing — and then we add the *lightest possible* layer of human insight
on top.** The order matters. Depth first (Fiscal AI's lesson), community second and selectively
(Stocktwits' lesson, de-risked).

---

## Phase 1 — Technical Baseline (what we actually have)

Verified against the codebase, not just `CLAUDE.md`. Notable constraints and latent opportunities:

### Capabilities we can build on *today*
- **A structured 7-section AI pipeline.** Summaries are not free text — they are typed JSON:
  `executive_snapshot`, `financial_highlights`, `risk_factors`, `management_discussion_insights`,
  `segment_performance`, `liquidity_capital_structure`, `guidance_outlook`, plus `notable_footnotes`
  and `three_year_trend` (`backend/app/services/summary_generation_service.py`;
  `frontend/types/summary.ts`). **This structure is the substrate for citations, chat, and diffs.**
- **XBRL grounding already exists.** Financial figures are validated against SEC-verified XBRL values
  (`summary_generation_service.py` ~L127–141). We already *do* the thing Fiscal AI sells —
  grounding numbers in source data. We just don't *surface the provenance* to the user yet.
- **Filing content is cached as markdown.** `FilingContentCache` + the markdown body are the raw
  material for a retrieval/chat layer — no re-fetch from SEC required.
- **SSE streaming infra is production-grade.** Summaries already stream token-by-token with 3s
  heartbeats (`summaries.py`, `STREAM_HEARTBEAT_INTERVAL`). A "chat with this filing" feature
  reuses this transport wholesale.
- **Sentiment signals already computed — but read-only.** `hot_filings.py` produces an 8-component
  buzz score (recency, search interest, velocity, FMP earnings proximity, Finnhub `buzz_ratio`,
  bullish spread vs. sector); `trending_service.py` blends Stocktwits watchers + FMP; Finnhub gives
  `buzz_ratio` / `bullish_percent`. **None of this is presented as a first-class, sourced "Pulse" —
  it's plumbing.**
- **Comparison engine exists.** `compare.py` does 2–5-way side-by-side of financial metrics + risk
  factors (Pro-gated). `dashboard/WhatChangedCard.tsx` hints at a diff narrative that isn't yet a
  headline feature.
- **A real design system, dark-first.** Tailwind `darkMode: 'class'`, `ThemeProvider` with
  localStorage + system fallback, mint `#10B981` accent, Inter type, Recharts 3.8.1, custom glass
  cards / shimmer / count-up animations. Dark mode is *already* a strength — Fiscal AI doesn't
  confirm having it, and we should design dark-first as a brand signature.
- **Entitlements + Stripe + usage metering.** `entitlements.py` (FREE = 5 summaries/mo, PRO =
  unlimited; `can_export`, `can_compare_filings`, real-time alerts, 8-K coverage, history retention),
  `UserUsage` monthly metering, `Subscription` model. We can gate and meter new AI features cleanly.
- **`SavedSummary.notes` already exists** — a per-user free-text note attached to a summary. This is
  the seed of the entire community strategy (see Plan A / "Margin Notes").
- **Compliance scaffolding is real.** Data export (`GET /api/users/export`), account deletion
  (`DELETE /api/users/me`), `AuditLog` + `audit_service.py`, cookie consent, a documented retention
  policy, and existing Privacy / Security / Terms pages. We are *not* starting from zero on trust.

### Constraints & flags to respect
- **Redis is OFF in production** (`SKIP_REDIS_INIT=true`; L1 in-memory only). Any new feature must
  not assume a shared cache/queue. **→ This pushes us toward Postgres-native solutions** (see Plan B,
  `pgvector`).
- **No social/UGC data model exists.** No comments, votes, follows, or reactions anywhere. Greenfield
  — which means we get to design it *right* and *minimally*.
- **Feature flags gate the roadmap** (`frontend/lib/featureFlags.ts`): `ENABLE_FINANCIAL_CHARTS`
  (off), `ENABLE_SECTION_TABS` (off), `ENABLE_QUALITY_BADGE` (off), `ENABLE_CALENDAR` (off),
  `ENABLE_RECOMMENDED_FILING` (on). **Several brand-defining wins are already built and merely
  switched off.**
- **Doc/Reality discrepancy:** `CLAUDE.md` claims **shadcn/ui**, but the codebase has *no*
  shadcn/Radix — only a single custom `ui/EmptyState.tsx`. This matters for Plan B: the interactive
  primitives we need (hover-cards for citations, dialogs for annotations, popovers) don't exist yet.
- **Single AI provider, no embeddings store.** Gemini via OpenAI-compatible API; no vector store. A
  retrieval/chat feature needs an embeddings + retrieval layer added.

---

## Phase 2 — Competitive Teardown (condensed & cited)

### Stocktwits — the attention graph
- **Symbol-centric, not follower-centric.** Everything organizes around the `$cashtag`; each ticker
  has a symbol page aggregating stream + charts + news + sentiment + "watchers"
  ([help.stocktwits.com](https://help.stocktwits.com/c/faqs/articles/how-do-i-post-on-stocktwits)).
- **Sentiment as a first-class, low-friction primitive.** One-tap **Bullish/Bearish** tags on posts,
  aggregated into a per-ticker ratio and a **1–100 "Stocktwits Score"** ranked by *message volume*
  ([sentiment hub](https://stocktwits.com/sentiment)). **Known weaknesses: manipulable by
  pump-and-dump posting and mega-cap-skewed** ([WallStreetZen](https://www.wallstreetzen.com/blog/stocktwits-review/)).
- **Discovery surfaces:** Trending / Most Active / Watchers / Most Bullish / Most Bearish / Gainers /
  Losers, refreshed ~5 min. "Watchers" = their following/heat proxy.
- **Monetization is layered:** Free (ads) → **Plus** $7.99/mo (ad-free, badge, themes) → **Edge**
  ~$22.95/mo or **$229.50/yr** — *the real data paywall: social-sentiment overlays, advanced search,
  full trending lists, 10k-char longform posts* → **Enterprise/API** (Sentiment API, Messages API via
  Databricks, Alpaca integration) ([subscriptions](https://stocktwits.com/subscriptions),
  [Edge help](https://help.stocktwits.com/c/stocktwits-edge/articles/stocktwitsedge)).
- **Creator layer:** **Rooms** (live chat) + **Premium Rooms** (gated expert content) = influencer
  monetization ([rooms](https://stocktwits.com/rooms)).
- **2025 re-platforming:** **eToro trading partnership** (a "Trade" button routes to eToro execution)
  ([eToro PR](https://www.etoro.com/en-us/news-and-analysis/latest-news/press-release/stocktwits-etoro-new-partnership/))
  + **acquisition of AI startup Thematic** → the **Social Relative Strength Index (SRS)**, AI
  screeners, stream summaries, and a backtesting index builder
  ([Thematic acquisition](https://stocktwits.com/news-articles/business/others/stocktwits-acquires-ai-startup-thematic/ch8KVxsR5pd)).
  (Note: there is **no** "Aurora" AI assistant — that premise is false.)
- **Legal posture (rewritten 2025):** strong "not a broker-dealer / not investment advice" +
  **AS-IS** + **indemnification** + **AAA arbitration with class-action waiver and 30-day opt-out**;
  a **broad, survives-deletion content license** (host/reproduce/modify/sublicense — fuel for their
  AI mining); **age raised 13→18**; **reactive, no-pre-screen moderation** with takedown rights;
  a "no artificial amplification" clause **but a conspicuous absence of an explicit
  paid-promotion/touting disclosure rule** despite documented pump-and-dump exposure
  ([Terms](https://stocktwits.com/about/legal/terms/), [Privacy](https://stocktwits.com/about/legal/privacy),
  [Disclaimer](https://stocktwits.com/about/legal/disclaimer/)).
- **Scale:** "10M+ users" claimed (Jan/Jul 2025 PRs); third-party estimates ~5M MAU; **mobile app
  stability is a documented liability** ([WallStreetZen](https://www.wallstreetzen.com/blog/stocktwits-review/)).

### Fiscal AI — the truth graph
- **Grounded conversational Copilot.** NL Q&A over financials with cross-query context; generates
  charts, tables, and *simplified DCF models* from plain text; "Chat with Company Filings" interrogates
  10-Ks/transcripts ([WallStreetZen](https://www.wallstreetzen.com/blog/finchat-io-fiscal-ai-review/),
  [Koyfin vs FinChat](https://traderhq.com/koyfin-vs-finchat/)).
- **Depth:** 100k+ global companies, **20+ years history**, **2,250+ company-specific KPIs +
  non-GAAP**, sourced from **S&P Market Intelligence (Capital IQ)**, earnings updated within ~1 hour
  ([EU Investing Hub](https://www.euinvestinghub.com/articles/fiscal-ai-review/),
  [TraderHQ](https://traderhq.com/finchat-review-ai-financial-assistant-smart-investors/)).
- **Trust is the product.** *Every answer cites its sources with click-through to the original
  filing*; the Copilot is bounded to the verified dataset and **declines rather than hallucinates**;
  it claims **2–4× general-purpose LLMs on FinanceBench** (a marketing figure, treat with caution)
  ([matchmybroker](https://www.matchmybroker.com/tools/fiscal-ai-review)).
- **Presentation:** chartbuilder, tearsheet company overviews, comparison tables, customizable
  dashboards (1/10/unlimited by tier), in-platform DCF; "clean, modern" but reviewers say it "could be
  sleeker"; **web-only, no mobile**; dark mode unconfirmed.
- **Interaction:** chat-first layered over dashboards/screeners; **now an official app inside ChatGPT
  (June 2026) and a Claude Connector / MCP server** (`api.fiscal.ai/mcp`) — i.e., it distributes its
  data *into* the AI tools users already use ([MCP docs](https://docs.fiscal.ai/docs/guides/mcp-integration)).
- **No community/sharing features at all.**
- **Tiers:** Free ($0, ~10–25 companies, 10y, 1 dashboard, DCF, 2-week Pro trial) / **Pro** ~$39/mo
  annual / **Max** ~$79/mo annual (20+y, unlimited dashboards, **click-through audit to filings**,
  full export) / **API+MCP/Enterprise** (custom; reported customers incl. Morgan Stanley, Franklin
  Templeton, VanEck) ([reviews](https://www.euinvestinghub.com/articles/fiscal-ai-review/)).
- **Trajectory:** FinChat (Apr 2023) → rebrand to **Fiscal AI mid-2025 + $10M Series A** (~$13M
  total), **350k+ users, SOC2 Type II**; strategic pivot to being "the financial-data layer behind
  fintech tools" ([Series A blog](https://fiscal.ai/blog/series-a-announcement/)).

---

## Phase 3 — Strategic Synthesis (the high-leverage learnings, brand-filtered)

Seven learnings survive the brand filter. Each is tagged **[ADOPT]**, **[ADAPT]**, or **[AVOID]**.

1. **[ADOPT] Citations are the trust moat — and we're already 80% there.** Fiscal AI's single
   biggest differentiator is click-through provenance. We *already* ground numbers in XBRL and cache
   filing markdown; we simply don't surface the link. **Surfacing provenance is the cheapest,
   highest-trust feature available to us** and it is the literal embodiment of our "single-origin /
   traceable" brand. → Plan A #1, Plan D.

2. **[ADAPT] Conversational depth, but bounded.** Fiscal AI's "Chat with Company Filings" is the
   category-defining interaction. We can build the same on `FilingContentCache` + XBRL + the existing
   SSE transport — and we will copy the part that matters most: **the Copilot must cite every claim
   and say "the filing doesn't disclose this" rather than guess** (their explicit anti-hallucination
   stance). → Plan A #2, Plan B #2.

3. **[ADAPT] Sentiment as *sourced data*, never as a hype meter.** Stocktwits proves sentiment drives
   discovery; it also proves the 1–100 chatter score is gameable and mega-cap-skewed. We already
   compute richer, harder-to-game signals (filing recency, real search interest, earnings proximity,
   news buzz). **We present a calm, multi-source "Filing Pulse" anchored to filings — not a
   leaderboard anchored to who shouts loudest.** → Plan A #3, Plan D.

4. **[ADAPT] The lightest possible community primitive — "Margin Notes."** Stocktwits' UGC is a
   firehose; Fiscal AI has none. The artisanal middle path already has a seed in code:
   `SavedSummary.notes`. We evolve it into **section-anchored annotations** (private by default,
   optionally shareable) — editorial marginalia, not a comment war. This is "curation over firehose"
   made literal. → Plan A #4, Plan B #1.

5. **[ADAPT] Layered monetization with a clear *data* paywall.** Both companies gate the *depth*, not
   the access: Stocktwits Edge gates social-sentiment data; Fiscal AI Max gates history depth +
   audit + export. Our FREE/PRO split already exists; we should make **Copilot chat, full Filing
   Pulse history, and shareable notes the PRO value story** — and consider a Fiscal-AI-style
   **2-week Pro trial** to demonstrate depth. → Plan A #6, Plan B #3.

6. **[AVOID] The Stocktwits legal/UGC posture — but steal its checklist.** Do **not** copy their
   broad, survives-deletion content license (it contradicts our trust brand) or their *missing*
   paid-promotion rule. **Do** adopt the protective machinery the moment we ship any UGC: UGC
   license (narrow, user-favorable), Acceptable Use / no-market-manipulation **with an explicit
   paid-promotion disclosure rule** (the gap they left open becomes our trust headline), DMCA/takedown,
   reporting/moderation, and age 18+ for community features. → Plan C.

7. **[AVOID for now / flag for later] Don't chase trading execution or a public data-API/MCP — yet.**
   Stocktwits' eToro routing and Fiscal AI's MCP/ChatGPT distribution are *late-stage* distribution
   plays. For a pre-launch product they're a distraction — but the MCP/"EarningsNerd in your AI tools"
   bet is strategically aligned with where both competitors moved and should be a *named Later bet*,
   not a Now build. → Plan A "Later", Plan B #5.

**The unifying principle:** copy Fiscal AI's *substance* (grounded, cited depth) and Stocktwits'
*social ergonomics* (symbol-centric organization, sentiment as a primitive), but render both through
a calm, dark-first, provenance-obsessed aesthetic that neither competitor has.

---

## Phase 4 — Actionable Development Plans

### Plan A — Product Feature Roadmap

Sequenced **Now (0–6 wks) / Next (6–16 wks) / Later (quarter+)**. Each item names the brand filter
and the codebase hook.

#### NOW — turn on the trust story (mostly already built)

**A0. Flip the switches we already shipped.** Lowest-effort brand wins, all gated off today:
- `ENABLE_QUALITY_BADGE` → **on.** The honest "Full / Partial" badge *is* our "honest labeling"
  brand value and Fiscal AI's "tells you when it doesn't know" ethos, already computed by the
  deterministic quality verdict in `summary_generation_service.py`. *Brand: honest labeling.*
- `ENABLE_FINANCIAL_CHARTS` → **on.** Recharts revenue/income/EPS viz is built (`FinancialCharts.tsx`);
  data density is table stakes against Fiscal AI. *Brand: precision fintech.*
- `ENABLE_CALENDAR` → **on** (FMP-gated earnings calendar) as a discovery surface on the dashboard.
- Keep `ENABLE_SECTION_TABS` evaluated per UX testing (Plan D prefers progressive disclosure over
  tabs).

**A1. Provenance / "Trace to Source."** *The flagship trust feature.* For every metric in
`financial_highlights` and every `risk_factors` claim, attach and surface the source: a hover-card
(desktop) / tap-sheet (mobile) showing the **exact filing excerpt + a deep link to SEC EDGAR**.
- *Hook:* XBRL grounding + `FilingContentCache` markdown already exist; we add excerpt capture +
  citation IDs to the `raw_summary` schema.
- *Learning:* direct adaptation of Fiscal AI's click-through citations
  ([Koyfin vs FinChat](https://traderhq.com/koyfin-vs-finchat/)).
- *Brand:* single-origin traceability — the defining motif.

#### NEXT — the depth & calm-signal layer

**A2. "Ask this Filing" — a grounded Copilot.** A chat panel scoped to a single filing (not the whole
market) that answers in natural language and **cites the section/excerpt behind every claim**, and
explicitly says *"This filing does not disclose X"* when it can't answer.
- *Hook:* reuse SSE streaming (`summaries.py`), `FilingContentCache`, XBRL; add retrieval (Plan B #2).
- *Learning:* Fiscal AI's Copilot + anti-hallucination grounding
  ([matchmybroker](https://www.matchmybroker.com/tools/fiscal-ai-review)).
- *Brand:* calm research desk; scoped, not a market-wide oracle.
- *Monetization:* metered — limited Q&A on FREE, generous on PRO (extends `UserUsage`/`entitlements.py`).

**A3. "Filing Pulse" — sourced sentiment, not a hype meter.** Replace the raw buzz plumbing with a
single, restrained, *explained* indicator on each filing/company page, decomposed into its sources
(filing recency, real search interest, earnings proximity, news buzz, social watchers) with each
component labeled and dated.
- *Hook:* `hot_filings.py` 8-component score + `trending_service.py` + Finnhub `buzz_ratio` /
  `bullish_percent` already compute this; we persist snapshots (Plan B #4) to chart the trend.
- *Learning:* Stocktwits' discovery value **minus** its manipulability — we anchor to filings and
  multi-source signals, not posting volume ([WallStreetZen](https://www.wallstreetzen.com/blog/stocktwits-review/)).
- *Brand:* calm gauge, muted palette, no flashing red/green.

**A4. "Margin Notes" — the artisanal community primitive.** Section-anchored annotations on a summary,
**private by default**, with an explicit opt-in to make a note public on that filing. No global feed,
no infinite scroll. Curated, thoughtful, editorial.
- *Hook:* evolve `SavedSummary.notes` into a first-class `Annotation` model (Plan B #1).
- *Learning:* the *opposite* of Stocktwits' firehose — adopt the symbol/section-anchoring, reject the
  noise.
- *Brand:* marginalia in a well-made book; curation over firehose.
- *Gate:* requires the full Plan C trust machinery before *public* notes ship.

**A5. "What Changed" as a headline feature.** Promote the latent diff capability into a first-class,
narrated **quarter-over-quarter / year-over-year change report** ("revenue mix shifted X→Y; a new
risk factor on supply concentration appeared; guidance language softened").
- *Hook:* `compare.py` (2–5-way) + `dashboard/WhatChangedCard.tsx` already exist.
- *Learning:* this is *our* answer to both competitors — neither leads with a narrated fundamental
  diff; it's a uniquely "filing-native" hook.
- *Brand:* signal over noise; we tell you what matters.

#### LATER — distribution & creator bets (named, not yet built)

- **A6. Pro trial + tier repackaging.** Adopt a Fiscal-AI-style **2-week Pro trial**; make Copilot
  depth, Pulse history, shareable notes, and export the PRO story. (`Subscription.trial_end` already
  exists.)
- **A7. Curated expert notes (the anti-"Premium Rooms").** Instead of live trading rooms, a small set
  of *vetted* analysts publish standout Margin Notes — quality-curated, not volume-driven creator
  monetization.
- **A8. "EarningsNerd in your AI tools" (MCP/API).** A read-only MCP server / public API exposing our
  *cited* summaries — mirroring Fiscal AI's MCP and Stocktwits' data-licensing direction
  ([Fiscal MCP](https://docs.fiscal.ai/docs/guides/mcp-integration)). Strategic, not urgent.

**Explicitly NOT doing:** trading execution / brokerage routing (Stocktwits' eToro play); a 1–100
hype score; a global social feed; live chat rooms. These contradict the brand or the stage.

---

### Plan B — Architectural & Codebase Recommendations

**B1. New data models for annotations & light social (greenfield, do it right).**
- `Annotation`: `id, user_id, summary_id, filing_id, section_key (enum of the 7+ sections),
  anchor_excerpt, body, visibility (PRIVATE|PUBLIC), status (ACTIVE|HIDDEN|REMOVED), created_at,
  updated_at`. Migrate `SavedSummary.notes` content into it (back-compat: keep `notes` as a private
  annotation).
- `AnnotationReport`: `id, annotation_id, reporter_user_id, reason, created_at` (moderation; see Plan C).
- `CompanyFollow`: either a `visibility`/`type` column on the existing `Watchlist` or a thin new
  table — to power a "watchers"-style follow without inventing a full social graph.
- *Pattern fit:* matches the existing SQLAlchemy model style in `backend/app/models/__init__.py`;
  schema is created at startup via `Base.metadata.create_all()` (no Alembic) — add models there and
  ship a one-off `migrations/` SQL for production back-fill, per repo convention.

**B2. Retrieval layer for "Ask this Filing" — use `pgvector`, not new infra.**
- **Decision:** add the **`pgvector` extension to the existing Cloud SQL Postgres 15** and store
  filing-chunk embeddings there. *Rationale:* Redis is OFF in prod (`SKIP_REDIS_INIT=true`) and the
  two-tier cache is L1-only, so a Redis-based vector store is out; standing up a dedicated vector DB
  violates "Minimal Impact." We already run Postgres 15 on Cloud SQL — `pgvector` reuses it.
- New `FilingChunk(filing_id, section_key, chunk_text, embedding vector, token_count)`, populated from
  `FilingContentCache` markdown at summary-generation time.
- Embeddings + chat completion go through the existing OpenAI-compatible client (`openai_service.py`);
  add an embeddings call against the configured base URL. Reuse the **circuit breaker, rate limiter,
  and SSE streaming** already in place.
- **Citation tracking is a hard requirement:** the retrieval response must carry `(section_key,
  chunk_id, excerpt)` through to the UI so Plan A1/A2 can render provenance. Bake this into the
  contract from day one — retrofitting citations is painful.

**B3. Metering & entitlements for AI cost control.**
- Extend `entitlements.py` with `copilot_queries_per_month` and `pulse_history_days`; meter Copilot
  usage through `UserUsage` (it already tracks monthly counts). Chat is the most expensive feature
  we'll run — gate it before launch, not after.
- Add a per-filing **excerpt/embedding cache** (L1 + the Postgres chunk table) so repeated Copilot
  sessions on a hot filing don't re-embed.

**B4. Persist sentiment snapshots for trend lines.**
- New `SentimentSnapshot(company_id, filing_id?, captured_at, composite_score, components JSON)`
  written on each `hot_filings`/`trending` refresh. Today the buzz score is computed on the fly and
  thrown away; persisting it is what turns A3's "Filing Pulse" from a number into a *trend* (the thing
  Stocktwits' ephemeral score can't show well).

**B5. Front-end primitives: adopt Radix (resolve the `CLAUDE.md` discrepancy).**
- `CLAUDE.md` claims shadcn/ui; the code has none. The new features need **accessible, headless
  primitives**: HoverCard/Popover (citations), Dialog (annotation composer, upgrade), Tooltip,
  Tabs. **Recommendation: adopt `@radix-ui` primitives (the shadcn substrate) for these specific
  interactions**, styled with the existing Tailwind tokens — don't hand-roll accessibility for
  popovers/dialogs. Update `CLAUDE.md` to match reality either way.

**B6. Moderation & safety plumbing (small, but required before public UGC).**
- Reuse `AuditLog` + `audit_service.py` for annotation create/edit/hide/report events.
- Soft-delete via `Annotation.status`; a simple admin review queue under `/api/admin/` (the admin
  router + `is_admin` flag already exist).

**B7. Privacy-by-design for the chat feature (engineering side of Plan C).**
- User Copilot queries are *user content* and will be sent to Google AI Studio (Gemini). Today
  `DATA_COMPLIANCE.md` records Gemini as receiving "SEC filing content (**no PII**)". Chat changes
  that. Engineer for: query logging with retention limits, inclusion in `GET /api/users/export` and
  `DELETE /api/users/me`, and a config flag to disable query persistence. (Policy side in Plan C.)

---

### Plan C — Trust & Compliance Strategy

We already have a strong base (Terms with not-investment-advice / AI-accuracy / AS-IS / liability cap
/ indemnification; Privacy + Security pages; export/delete; AuditLog; retention policy; GDPR/CCPA/
PIPEDA/CAN-SPAM framing per `docs/DATA_COMPLIANCE.md`). The gaps are **(a) the moment we ship UGC**
and **(b) the moment we ship chat**. Stocktwits' rewritten Terms are the checklist; our brand decides
which clauses we copy and which we deliberately invert.

**C1. Implement *before any public Margin Note ships* — the UGC layer.**
- **A narrow, user-favorable content license** (invert Stocktwits' broad grant). Stocktwits takes a
  "worldwide, transferable, sublicensable… modify/adapt… survives deletion" license fueling its AI
  mining ([Terms](https://stocktwits.com/about/legal/terms/)). **We grant ourselves only the minimum
  needed to display/host the note, users explicitly retain ownership, and we commit in writing not to
  sell user notes or train models on them without consent.** *This "you own your notes, we don't mine
  them" stance is a marketable trust differentiator*, not just legal hygiene.
- **Acceptable Use Policy with an explicit market-manipulation + paid-promotion disclosure rule.**
  This is where we *beat* Stocktwits: they prohibit "artificial amplification" but left a
  **conspicuous gap — no Section 17(b)-style requirement to disclose paid promotion**
  ([WallStreetZen](https://www.wallstreetzen.com/blog/stocktwits-review/)). We require: no pump-and-dump,
  no coordinated manipulation, **and mandatory disclosure of any compensation or position when a note
  could move a security.** Make this a visible community standard, not buried boilerplate.
- **Notice-and-takedown (DMCA-style) + reporting/flagging + reactive moderation policy.** Mirror
  Stocktwits' "we do not pre-screen but may remove" stance, backed by the `AnnotationReport` model
  and admin queue (Plan B6).
- **Age gate for community features: 18+.** Stocktwits raised 13→18 in its 2025 rewrite
  ([Terms](https://stocktwits.com/about/legal/terms/)). Our current Terms say "age of majority in your
  jurisdiction" (`frontend/app/terms/page.tsx` §5) — sufficient for read-only use; require **explicit
  18+** before a user can *publish* a public note.
- **Liability for UGC:** extend the existing indemnification (Terms §11) to cover user-posted content,
  and add a "views are the author's, not EarningsNerd's, and are not investment advice" disclaimer on
  every public note surface.

**C2. Implement *before chat ships* — the AI-data layer.**
- **Update the Privacy Policy + `docs/DATA_COMPLIANCE.md`** to disclose that **user Copilot queries
  are processed by a third-party LLM sub-processor (Google AI Studio / Gemini)** and may contain
  user-entered text. The current compliance doc's "Gemini receives filing content (no PII)" line
  becomes inaccurate the day chat launches — fix it in the same PR as the feature.
- **AI-specific disclaimer on the chat surface:** reiterate "may be incomplete or wrong; verify
  against the original filing" (Terms §4 already establishes this for summaries — extend to chat),
  and make **citations the legal shield**: every answer links to source, reinforcing "informational
  only."
- **Retention + DSAR coverage:** chat history must be exportable (`GET /api/users/export`) and
  deletable (`DELETE /api/users/me`); add it to `DATA_RETENTION_POLICY.md`.

**C3. Arbitration — a deliberate brand choice (decide explicitly).** Stocktwits imposes AAA
arbitration + class-action waiver with a 30-day opt-out. This is defensible but consumer-unfriendly
and sits awkwardly against an "artisanal, trustworthy" brand. **Recommendation: keep the current
court/governing-law approach (Terms §14) for now** rather than bolt on mandatory arbitration; revisit
with counsel only if UGC liability exposure grows. Flag for legal review, don't auto-copy the
incumbent.

**C4. Trust signals as product.** Fiscal AI advertises **SOC2 Type II** as an institutional trust
signal. Our Security page already lists encryption, hashing, RBAC. **Put SOC2 on the roadmap as an
explicit milestone** (especially if the Plan A8 API/MCP bet matures toward prosumer/institutional
users), and keep the open DPA items in `DATA_COMPLIANCE.md` (Resend, PostHog, Sentry) moving.

---

### Plan D — UX/UI Design Directives

The aesthetic brief: **third-wave coffee × precision fintech**. Warm, restrained, editorial,
provenance-obsessed, dark-first. The directives below are concrete and tied to existing tokens.

**D1. Design dark-first; make it a signature.** We already have `darkMode:'class'`, `ThemeProvider`,
and a mint `#10B981` accent. Fiscal AI doesn't confirm dark mode and reviewers call its UI
"not sleek"; Stocktwits' mobile is buggy. **A genuinely beautiful dark-first experience is open
territory** — design the dark palette as primary, light as the variant. Keep the mint accent rare and
intentional (a single warm highlight, like a coffee-crema tone), against deep neutral backgrounds and
generous whitespace.

**D2. Provenance is the hero UI pattern.** Every number and claim carries a quiet "trace" affordance —
a subtle underline/dot that, on hover (Radix HoverCard) or tap (mobile sheet), reveals the **exact
filing excerpt + EDGAR deep link**. This is the visual embodiment of "single-origin / traceable."
*No competitor renders provenance as a calm, ambient layer — Fiscal AI links to it, but we make it
the texture of the page.*

**D3. Calm signal, never casino.** Stocktwits' 1–100 score and flashing bull/bear coloring are exactly
what we reject. **Filing Pulse** is a single muted gauge with a plain-language label and a
"what's driving this" breakdown; sentiment uses desaturated tones, not saturated red/green. Trends use
restrained Recharts styling (thin lines, muted grid) consistent with the existing chart components.

**D4. Editorial typography & progressive disclosure.** Lean into Inter + the existing
`prose prose-slate dark:prose-invert` markdown styling. **Prefer collapsible sections
(`SummarySections.tsx`) over a tab-heavy layout** — an unrolled, readable document with quiet section
headers reads like a well-set magazine, not a Bloomberg terminal. Re-evaluate `ENABLE_SECTION_TABS`
against this; default to disclosure, not tabs.

**D5. Margin Notes as marginalia.** Render annotations in the *margin* (or an inline, quiet thread
anchored to a section) — visually subordinate to the filing content, like pencil notes in a book.
Public notes show author + the mandatory "not advice / position disclosed" line (Plan C1). No
vote counts, no karma, no leaderboards — *curation over gamification.*

**D6. The Copilot as a calm side panel.** "Ask this Filing" opens as a slide-in panel (Radix Dialog/
Sheet) that keeps the filing visible; answers stream in (existing SSE feel — treat the stream as a
crafted "pour," reusing `SummaryProgress` patterns) and render inline citations as the same trace
chips from D2. Empty state uses the existing `ui/EmptyState.tsx` with 2–3 *suggested questions* to
flatten the learning curve (Fiscal AI's onboarding lesson).

**D7. Excellent responsive web = a real moat.** Stocktwits mobile crashes; Fiscal AI has *no* mobile.
We don't need a native app — **a flawless, fast responsive web experience** (especially the trace
sheets and Copilot panel on mobile) is a differentiator both incumbents leave on the table. Make the
mobile trace/citation interaction first-class, not an afterthought.

**D8. Honest-state craft.** Wire `ENABLE_QUALITY_BADGE` into the design language: a quiet "Full /
Partial" chip, not a warning banner. Craft the loading (`SummaryProgress`) and empty
(`EmptyState.tsx`) states deliberately — these moments are where "artisanal" is felt or lost.

---

## 90-Day Execution Sequence

| Horizon | Plan A (Product) | Plan B (Arch) | Plan C (Trust) | Plan D (UX) |
|---|---|---|---|---|
| **Weeks 0–6 (Now)** | A0 flag-flips; A1 Trace-to-Source | B5 Radix primitives; citation IDs in `raw_summary` | C2 (privacy copy ready for chat); SOC2 milestone defined | D1 dark-first; D2 provenance pattern; D8 honest states |
| **Weeks 6–16 (Next)** | A2 Copilot; A3 Filing Pulse; A5 What-Changed | B2 pgvector + retrieval; B3 metering; B4 sentiment snapshots; B7 chat privacy eng | C2 ship with chat (privacy + DSAR + disclaimer) | D3 calm signal; D6 Copilot panel; D4 disclosure layout |
| **Quarter+ (Later)** | A4 Margin Notes (public); A6 Pro trial; A7 curated notes; A8 MCP/API | B1 annotation models; B6 moderation plumbing | C1 full UGC legal layer; C3 arbitration decision; C4 SOC2 | D5 marginalia; D7 mobile polish |

**Critical path & gating rules:**
- A2 (Copilot) **must not ship** without B2 citation tracking and C2 privacy disclosure.
- A4 public Margin Notes **must not ship** without the full C1 UGC layer (license, AUP +
  paid-promotion rule, takedown, 18+ gate) and B6 moderation plumbing.
- A0 + A1 are near-free and should ship first to establish the trust/brand story immediately.

---

## Appendix — Sources

**Codebase (Phase 1):** `backend/app/services/summary_generation_service.py`,
`backend/app/services/hot_filings.py`, `backend/app/services/trending_service.py`,
`backend/app/integrations/{finnhub,stocktwits,earnings_whispers,fmp}.py`,
`backend/app/services/entitlements.py`, `backend/app/routers/{summaries,compare,admin,users}.py`,
`backend/app/models/__init__.py`, `frontend/types/summary.ts`,
`frontend/components/{FinancialCharts,SummarySections,SummaryProgress}.tsx`,
`frontend/lib/featureFlags.ts`, `frontend/app/{terms,privacy,security}/page.tsx`,
`docs/DATA_COMPLIANCE.md`, `docs/DATA_RETENTION_POLICY.md`.

**Stocktwits (Phase 2):**
[subscriptions](https://stocktwits.com/subscriptions) ·
[Edge help](https://help.stocktwits.com/c/stocktwits-edge/articles/stocktwitsedge) ·
[sentiment hub](https://stocktwits.com/sentiment) ·
[posting/cashtags](https://help.stocktwits.com/c/faqs/articles/how-do-i-post-on-stocktwits) ·
[Terms](https://stocktwits.com/about/legal/terms/) ·
[Privacy](https://stocktwits.com/about/legal/privacy) ·
[Disclaimer](https://stocktwits.com/about/legal/disclaimer/) ·
[Thematic acquisition](https://stocktwits.com/news-articles/business/others/stocktwits-acquires-ai-startup-thematic/ch8KVxsR5pd) ·
[eToro partnership](https://www.etoro.com/en-us/news-and-analysis/latest-news/press-release/stocktwits-etoro-new-partnership/) ·
[WallStreetZen review](https://www.wallstreetzen.com/blog/stocktwits-review/).

**Fiscal AI (Phase 2):**
[Series A announcement](https://fiscal.ai/blog/series-a-announcement/) ·
[MCP integration docs](https://docs.fiscal.ai/docs/guides/mcp-integration) ·
[API free-trial docs](https://docs.fiscal.ai/docs/guides/free-trial) ·
[WallStreetZen review](https://www.wallstreetzen.com/blog/finchat-io-fiscal-ai-review/) ·
[matchmybroker review](https://www.matchmybroker.com/tools/fiscal-ai-review) ·
[EU Investing Hub review](https://www.euinvestinghub.com/articles/fiscal-ai-review/) ·
[Koyfin vs FinChat](https://traderhq.com/koyfin-vs-finchat/) ·
[TraderHQ review](https://traderhq.com/finchat-review-ai-financial-assistant-smart-investors/) ·
[BetaKit (seed/history)](https://betakit.com/finchat-secures-1-5-million-usd-from-social-leverage-to-expand-ai-powered-stock-research-platform/).

> *Verification caveats carried from research:* Stocktwits MAU figures range 5M–10M+ by source/date;
> the "2–4× ChatGPT on FinanceBench" figure and Fiscal AI's institutional customer roster are
> third-party-reported marketing claims, not independently audited; several fiscal.ai primary pages
> returned HTTP 403 and were corroborated via independent reviews. Treat scale/benchmark numbers as
> directional.
