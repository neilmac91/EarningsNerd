# Competitor Benchmarking — AI SEC-Filing Analysis (June 2026)

Synthesised from multi-source web research (every row traces to the source list at the bottom).
Verdicts: ✓ present · ◑ partial / could-not-fully-verify · ✗ absent. "could not verify" = no evidence
found in accessible sources, not proof of absence. Vendor accuracy claims (e.g. "99%", "zero
hallucination") are vendor-reported and not independently audited.

Target user for this review = **prosumer / serious individual investor**, so the retail/prosumer
tier is weighted most heavily; the institutional tier is included to map the capability ceiling.

---

## A. Retail / Prosumer tier (the competitive set that matters most)

| Tool | Filing output format | Src citations | PoP **diffing** | Segment/KPI | Chat Q&A | Transcripts | Peer tables | Pricing (prosumer) |
|---|---|---|---|---|---|---|---|---|
| **Fiscal.ai** (ex-FinChat) | AI Copilot Q&A over filings/transcripts; auto peer tables + charts | ✓ click-thru | ✗ | ✓ (2.5k cos KPIs) | ✓ core | ✓ | ✓ | Free / $39 Pro / $79 Max |
| **Stock Titan** (Rhea-AI) | Per-filing AI card: sentiment+impact score, narrative, headline financials | ◑ list-level only | ✗ (single-filing only) | ◑ shallow | ✗ | ✗ | ✗ | Free / $19.99 / $59.99 / $89.99 |
| **TipRanks** | AI equity report: earnings-call summary, sentiment, risk-factor tool | ◑ unverified | ◑ **risk-factors YoY only** | ◑ | ✗ (noted missing) | ✓ | ✓ | ~$30–50/mo |
| **Stockanalysis.com** | Fast data platform; AI summaries of **transcripts** (not filing text) | ◑ | ✗ | ✗ (raw data only) | ✗ | ✓ | ◑ | Free / $9.99 / ~$17 |
| **Quiver Quant** | Alt-data tables (congress/insider/13F); no filing-text summary | ◑ | ✗ | ✗ | ✗ | ✗ | ✗ | Free / $25/mo |
| **Quartr** | Transcript/IR platform + "Instant Summaries"; History Mode tracks drift | ✓ traceable | ◑ KPI/narrative drift (not text diff) | ◑ | ✓ | ✓ core | ✗ | Free app / Pro contact-sales |
| **Koyfin** | Data terminal; AI **transcript** summaries (segment commentary, guidance) | ◑ | ✗ | ◑ | ✗ | ✓ | ◑ requested | Free / $39 / $79 |
| **BamSEC** (→AlphaSense) | Power-user filing workbench; clean filings + **redline compare** | ✓ inherent | ✓ **redline** | ◑ tables | ✗ | ✓ | ✗ | Free / $69/mo |
| **CapEdge** (ex-Docoh) | Free EDGAR overlay: sentiment, added/removed words, **YoY text diff**, readability | ✓ inherent | ✓ **text diff** | ✗ | ✗ | ✓ | ◑ | Free |
| **Bridgewise** (Bridget) | B2B2C scoring engine; rating + peer comp + post-earnings; embedded in brokers | ◑ | ✗ | ◑ | ◑ stock-level | ✓ | ✓ | Enterprise (free via brokers) |

### Read of the retail tier
- **No retail tool produces a deep, evidence-backed 10-K/10-Q *narrative* summary the way EarningsNerd
  aims to.** The AI-native players are either (a) **conversational terminals** (Fiscal.ai, Quartr) where
  the user must *ask* questions, or (b) **transcript summarizers** (Stockanalysis, Koyfin, TipRanks), or
  (c) **single-filing scorers** (Stock Titan). The "generate me a structured analyst-style report of this
  10-K" job is **under-served** → EarningsNerd's core thesis is sound.
- **Closest direct competitor = Fiscal.ai** ($39 Pro): citation-backed, segment KPIs, peer tables,
  chat-with-filing, 350k+ users, bounded-to-dataset "says I don't know" anti-hallucination reputation.
  It is the quality bar to beat — but it is **query-driven, not a fixed report**, and lacks PoP diffing,
  red-flag detection, and GAAP/non-GAAP reconciliation.
- **Source-linked citations are table stakes** for any *credible* AI tool here (Fiscal.ai is best-in-class;
  Stock Titan only links at list level). EarningsNerd shows `supporting_evidence` text on risks but has
  **no click-through to the filing** (see frontend-ux.md) — a gap vs the credible set.
- **Period-over-period disclosure DIFFING is the rarest valuable feature** and is *not* solved by the
  AI-summary crowd. Only the **non-AI overlays** (BamSEC redlines, CapEdge YoY text diff) and TipRanks
  (risk-factors only) do it. This is genuine white space for an AI tool to combine *diff + synthesis*.
- **Red-flag/anomaly detection and GAAP↔non-GAAP reconciliation are essentially absent** at the retail
  tier (Hudson Labs owns red-flags but is institutional). Differentiation openings.
- **Pricing band for paid prosumer tiers clusters tightly: ~$39–$89/mo** (Fiscal.ai $39/$79, Koyfin
  $39/$79, BamSEC $69, Stock Titan $20–90). EarningsNerd's Pro must justify its price inside this band.

---

## B. Institutional / Pro tier (capability ceiling)

| Tool | Output | Src citations | PoP diffing | Segment/KPI | Chat Q&A | Transcripts | Peer | GAAP/non-GAAP | Red-flag | Pricing |
|---|---|---|---|---|---|---|---|---|---|---|
| **AlphaSense** (+Tegus/Intelligize) | Smart Summaries + Generative Grid over filings/transcripts/research | ✓ | ◑ | ✓ | ✓ | ✓ (200k+ transcripts, best) | ✓ | ✗/unverified | ◑ | ~$10–20k/seat/yr |
| **Hebbia** (Matrix) | Agentic doc-grid; rows=docs, cols=questions; cited tables | ✓ | ✓ **best qualitative** cross-period | ✓ | ✓ | ◑ BYO | ✓ | unverified | ◑ tone-shift | ~$10k/seat/yr |
| **Fintool** (now MSFT, Apr 2026) | "ChatGPT+EDGAR" chat; V5 agentic (builds DCF/decks) | ✓ | ◑ | ✓ | ✓ | ✓ | ◑ | unverified | ✓ claimed | Enterprise |
| **Daloopa** | Structured data extraction → Excel; per-number source links | ✓ **gold std** | ◑ numeric only | ✓ **best** | ◑ via MCP | ◑ | ◑ | ✓ **only one** | ◑ numeric | Custom (~$99/mo entry unverified) |
| **Bloomberg** (ASKB) | Sidebar earnings summaries + Document Insights Q&A + agentic workflows | ✓ click-to-transcript | ◑ | ◑ | ✓ | ✓ | ✓ | unverified | unverified | ~$32k/seat/yr |
| **V7 Go** | SEC-filing "agents"; source-linked memos/tables/PPT | ✓ visual grounding | ✓ **true redline** add/removed/modified | ✓ | ◑ | ✗ | ✓ peer-group | ◑ extracts | ✓ compliance | Enterprise (usage-based) |
| **Workiva** SEC Filing Intelligence | Peer-group Q&A + Benchmarking Insights table (filer-side) | ✓ | ◑ | unverified | ✓ | ✗ | ✓ | unverified | ◑ disclosure-gap | ~$36k–$156k/yr |
| **Hudson Labs** (ex-Bedrock) | Forensic risk score + AI red-flag feed + Co-Analyst chat | ✓ | ◑ | unverified | ✓ | ✓ | unverified | unverified | ✓ **best, entire product** | Institutional |

### Read of the institutional tier (what "great" looks like)
- **V7 Go's 10-K agent is the closest feature-for-feature ceiling** to EarningsNerd's extract-and-summarize
  job, and it **exceeds the brief**: true **redline diffing** (added/removed/modified text in risk
  factors/MD&A), **visual grounding** (every extracted point links to the exact source sentence), segment
  breakdowns, and **peer-group** risk-factor comparison.
- **Citations + click-through are universal** at this tier; **Daloopa's per-number hyperlink** is the gold
  standard for numeric traceability.
- **True narrative disclosure diffing remains the least-solved capability even here** — Hebbia and V7 Go
  are the only convincing ones. Confirms it as a differentiation axis, not a solved commodity.
- **GAAP↔non-GAAP reconciliation** as a named feature = essentially **only Daloopa**.
- **Forensic red-flag detection** = **Hudson Labs** (institutional only). No prosumer tool matches it →
  a "lite red-flag" feature would be distinctive in the prosumer segment.

---

## C. Capability-gap narrative — where EarningsNerd stands

**Where EarningsNerd's *concept* is well-positioned**
1. The **"auto-generated structured analyst report of a single 10-K/10-Q"** job is genuinely under-served
   at the retail tier (most rivals are chat terminals or transcript summarizers). A *good* version of
   EarningsNerd's report is differentiated.
2. EarningsNerd already has the *scaffolding* competitors charge for: structured sections, an evidence
   field, financial charts, compare (2–5 filings), watchlist, export. The pieces exist.

**Where EarningsNerd is behind (today), in priority order for a prosumer**
1. **Output quality/depth** — the #1 gap. Rivals like Fiscal.ai return specific, cited, non-hallucinated
   answers; EarningsNerd's pipeline frequently degrades to **deterministic boilerplate** (see
   Phase 2 evidence). This is existential: the product's core artifact is currently weaker than a free
   ChatGPT prompt for many filings.
2. **Click-to-source citations** — table stakes for credible AI tools; EarningsNerd shows evidence *text*
   on risks but no click-through. (Single-filing-scope: link to the relevant Item/section in the source
   filing, not external data.)
3. **Cash-flow / balance-sheet / segment coverage** — Fiscal.ai, Daloopa, AlphaSense all surface these;
   EarningsNerd structurally drops them (only 4 XBRL metrics ingested).
4. **Red-flag / anomaly surfacing & GAAP-vs-non-GAAP** — open white space at the prosumer tier; even a
   lightweight version (single-filing: going-concern language, material-weakness, restatement, large
   one-time items, non-GAAP add-back size) would differentiate.
5. **Conversational follow-up on the filing** — present in Fiscal.ai/Quartr/Bloomberg/Fintool/Hudson;
   absent in EarningsNerd (a clear post-generation UX gap; in-scope as it operates on the one filing).

**Deferred by the single-filing scope (document as future, not near-term):** period-over-period disclosure
diffing (needs prior filing), peer comparison tables (needs peer data), transcript integration, and
consensus/peer context. Notably, **PoP diffing is the rarest and most-wanted feature in the whole market**
— so it is the strongest *future* differentiator once multi-filing ingestion is on the table.

---

## Sources
**Retail/prosumer:** fiscal.ai + wallstreetzen/matchmybroker/skywork reviews; stocktitan.net (+live TTAN
10-K page, rhea-ai.html, pricing); tipranks.com AI equity research + risk-factors + stockbrokers.com review;
stockanalysis.com changelog/transcripts/filings + wallstreetsurvivor/wallstreetzen/trustpilot; quiverquant.com
+ wallstreetzen/quantvps; quartr.com (+history-mode, press release) + findmymoat; koyfin.com release notes +
getapp; bamsec.com features/pricing + findmymoat/daytradereview + hudson-labs alternatives; capedge.com /
help.capedge.com + hudson-labs; bridgewise.com press + etoro/financemagnates/prnewswire.
**Institutional:** alpha-sense.com product/compare/press + prospeo/vendr; hebbia.com blog/resources +
eesel/openai/wikipedia; fintool via opentools/welcome.ai/braintrust/neowin (MSFT acq) + founder posts;
daloopa.com + skills/blog + aichief/futurepedia/Claude support; bloomberg ASKB + prnewswire/a-teaminsight/
american-banker/neugroup; v7labs.com agents/blog/pricing + coldiq/capterra; support.workiva.com SEC Filing
Intelligence + vendr; hudson-labs.com get-to-know-bedrock-ai.
(Full URL list retained in research notes; many vendor pages returned HTTP 403 to automated fetch, so several
verdicts rest on third-party reviews — flagged inline as ◑/"could not verify".)
