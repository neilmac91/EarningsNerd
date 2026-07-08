# Filing-Summary Quality & Design: Investigation and Tiered Improvement Plan

**Date:** 2026-07-08 · **Status:** Proposed (investigation complete; no code changed)
**Scope:** the AI-generated filing summary — its content, design, grounding, and rendering across web, PDF, and CSV.
**Reproduction case:** NVIDIA CORP 10-Q filed 2026-05-20 (CIK 1045810) — founder-annotated web screenshots plus the PDF/CSV exports of the same summary.

**Fixed constraints (designed around, not revisited):**

1. **One universal summary** per filing, generated once, cached for all users (`UNIQUE(filing_id)`). No per-persona variants.
2. **DeepSeek `deepseek-v4-pro` stays the generation model.** Everything here optimizes prompt, schema, grounding, and verification *around* it.
3. **Exports stay data-linked to the summary** — PDF and CSV must always reflect the same underlying data as the web view.
4. **New infrastructure ≤ ~$50/month; low build complexity** (solo founder).

---

## Part 1 — The world-class target state

### What the finished summary looks like

A reader opens a filing page and sees **one structured document** — not a markdown blob — rendered as a single scrolling page with a sticky section outline:

- **The Print** leads: the 2–3 figures that matter, each with a driver and a so-what, versus the filing's own prior-period comparatives. No "Key Takeaways" card repeating it below.
- **Every number on the page is computed exactly once, in code, from XBRL** — the same `+85.2%` in the prose, the metrics table, the What-changed chips, the PDF, and the CSV. Margins move in **percentage points**, never bare relative percentages. Positive/negative deltas render through the design system's `financialTone` recipes (green/red + arrow glyph, both themes).
- **Every evidence-bearing claim carries a real citation** — the same `CitationChip` treatment the "Ask this filing" copilot already ships: verbatim excerpt, section reference, Verified badge, deep link into the filing. No `(Evidence: …)` parentheticals, no `Source Section Ref: Item 2. MD&A` strings.
- **No internal scaffolding is ever user-visible.** `Tone:`, `Headline:`, `Key Points:`, `Drivers:` are schema field names; the renderer turns them into typography, iconography, and layout — or omits them (a neutral tone renders as nothing).
- **The analytical bar is genuinely higher.** The worked example: NVIDIA's Q1 FY2027 net income "more than tripled to $58.3B" — but $16.0B of that is unrealized mark-to-market gains on equity securities, exactly the accounting noise Warren Buffett warned makes GAAP bottom lines "useless… for analytical purposes" ([2018 letter](https://www.berkshirehathaway.com/letters/2018ltr.pdf), on [ASU 2016-01](https://www.newconstructs.com/how-asu-2016-01-impacts-invested-capital-and-oci/)). The world-class summary has an **Earnings Quality** section that separates operating from one-time results, pairs net income with cash from operations, and says so — instead of headlining "+211%" five times.
- **Forward-looking content is prominent, not an afterthought:** guidance, known trends and uncertainties (the Item 303 mandate), subsequent events, and management's forward statements quoted verbatim — the content the founder asked for more of.
- **PDF and CSV are projections of the identical structured document.** They cannot drift from the web view because all three consume one projection function.

### The four standards that define "world class" here

| Standard | Definition | Where it's specified |
|---|---|---|
| **Content** | 9 filing-only sections, inverted pyramid, one home per number, 10-rule prose bar | Part 3 |
| **Design** | `DESIGN_SYSTEM.md`-compliant structured components; no raw markdown blob; financialTone deltas; single card header | Parts 2(d), 5 (T1/T2) |
| **Grounding** | Numbers from code (one delta service + number-diff gate); words from the model; citations anchored and verified | Part 4 |
| **Rendering** | One structured content model → one projection (`render_sections`) → web + PDF + CSV + What-changed | Part 2 (verdict), Part 5 (T2) |

---

## Part 2 — Root-cause findings (Stream 1, verified in code)

### 2.0 The verdict on the serializer hypothesis

**True — nuanced to three serializers over one shared structured model.** The structured content model already exists and is identical everywhere (`Summary.raw_summary["sections"]`, a 9-section taxonomy defined by the inline `schema_template` at `backend/app/services/openai_service.py:259-357`). What diverges is serialization:

1. **High-fidelity (exports only):** `backend/app/services/summary_sections.py::render_sections` (line 411) renders sections into format-agnostic `Section`/`Block` dataclasses (lines 79-110) with clean titles ("Executive Assessment", "Financial Highlights" with a real Metric/Current/Prior/Change/Takeaway table, "Investment Risks & Concerns" with a #/Risk/Evidence table…). Its own docstring (lines 1-13) is the smoking gun — it was **built to end this exact divergence**:

   > *"The PDF exporter, the CSV exporter, and the on-page UI used to each decide independently how to render those sections, which is exactly why they diverged (page = 9 sections, PDF = 5, CSV = 2)… `export_service` turns those into HTML (PDF) and CSV rows, so the two formats can never drift apart again. The placeholder filtering and risk normalization **mirror the frontend**…"*

   Only PDF (`export_service.py:31-96`, WeasyPrint) and CSV (`export_service.py:119-155`) were migrated onto it. The page never was — it is hand-"mirrored" instead, which is why the exports look right and the web view doesn't.

2. **Web serializer A (backend):** `backend/app/services/ai/markdown_render.py::_build_structured_markdown` (lines 36-195) flattens the same sections into a markdown string that is **stored** as `Summary.business_overview` at generation time and rendered verbatim by plain ReactMarkdown at `frontend/features/summaries/components/SummaryDisplay.tsx:190`. Its docstring still calls it a fallback, but it is called unconditionally (`openai_service.py:823`) — it is the primary web renderer wearing a fallback costume, which is how its leaks went unnoticed.

3. **Web serializer B (frontend):** `frontend/lib/formatters.ts::renderMarkdownValue` (lines 5-40) generically flattens structured objects by title-casing raw JSON keys (`source_section_ref` → `Source Section Ref:`) for the "Key Takeaways" card (`SummarySections.tsx:251, 273-314`).

### 2.1 Defect (a) — internal scaffolding leaking into the web view

| Leaked text | Producer | Exact location |
|---|---|---|
| `- Guidance: …` | backend markdown flattener | `markdown_render.py:184` |
| `- Tone: neutral` (Outlook) | backend markdown flattener | `markdown_render.py:187` — note the neutral-tone suppression applied to the executive snapshot (`markdown_render.py:72`) was **not** applied here: the same rule, half-applied, is itself a symptom of multi-serializer drift |
| `Drivers` / `Watch items` label bullets | backend markdown flattener | `markdown_render.py:189-190` |
| `(Evidence: …)` | backend markdown flattener | `markdown_render.py:142` |
| `Headline:` / `Key Points:` / `Tone: neutral` / `Source Section Ref: Item 2. MD&A` | frontend dict flattener | `formatters.ts:22-34`, consumed at `SummarySections.tsx:251` |

None of this text exists in the model output as prose — `tone`, `source_section_ref`, `headline`, `key_points`, `drivers`, `watch_items` are **schema field names** (`openai_service.py:269-355`) that both flatteners stringify instead of rendering.

### 2.2 Defect (b) — the ".;" join artifacts (and why a merged fix didn't reach users)

The artifact came from joining "."-terminated bullet strings with `"; "`. It was **already fixed** in the merged data-quality remediation (P0-2): all 8 `"; ".join` sites in `markdown_render.py` became true GFM bullets (documented in that file's docstring, lines 16-22). The founder's screenshots still show it because:

- `business_overview` is rendered **at generation time and stored** (`summary_pipeline.py` persist step), and
- **summaries carry no prompt/schema version stamp.** Only Multi-Period Analysis has one (`trend_analysis_service.py:38` `PROMPT_VERSION = "trends-v4"`, checked for auto-invalidation at `routers/analysis.py:375`). A serializer fix therefore never invalidates stored summaries; they persist until a Pro user hits `force=true` (`routers/summaries.py:165-198`) or an admin runs `POST /api/admin/summaries/reset-all` (`routers/admin.py:758-857`).
- Worse: `reset-all` is FK-safe **because it skips saved summaries** (`saved_summaries.summary_id` FK) — so the summaries users cared enough to bookmark are the ones that can never be refreshed. This is a structural gap, not an oversight in the fix.

### 2.3 Defect (c) — cross-section redundancy

Three structural causes, all confirmed:

1. **The schema requests the same figures in three places** — `executive_snapshot.key_points`, `financial_highlights.table`, and `three_year_trend` (`openai_service.py:259-357`) — and `_apply_structured_fallbacks` re-injects revenue/net-income/margin into all three when thin (`markdown_render.py:289-357, 427-449`).
2. **What-changed duplicates Outlook verbatim by construction:** `Summary.key_changes` is set to `_stringify(guidance_outlook)` (`openai_service.py:814, 1016`) — the *same node* that `_build_structured_markdown` renders as the Outlook section — and `change_report_service.py:172` uses it as the What-changed card's lead paragraph.
3. **Page-level duplication:** the markdown "Financials" section *and* the structured `FinancialMetricsTable` (`SummaryDisplay.tsx:217-222`) both render the same metrics on one page.

### 2.4 Defect (d) — design-system non-compliance

- **Triple header:** frontend `<h2>Summary</h2>` (`SummaryDisplay.tsx:165`) + "Full summary" `Badge` (`:169-176`) + a backend `## Executive Summary` heading inside the markdown blob — three competing headings from two codebases.
- **Inconsistent bolding:** the main card has no custom ReactMarkdown renderer; bold is whatever the backend markdown emits (table-derived lines get `**Metric:**`, the Profitability/Cash flow/Balance sheet groups don't). `@tailwindcss/typography` is **not installed**, so every `prose` class on summary components is inert; real styling is `.markdown-body` in `globals.css:272-399`.
- **Justified text:** no `text-justify` utility exists anywhere in the repo; the design system is silent. (Founder explicitly wants justified body text — adopted in T1.7.)
- **Delta chips:** left-aligned (`WhatChanged.tsx:57` — `flex flex-wrap gap-2`, no centering) and hand-rolled, while the sanctioned recipes exist unused here (`lib/financialTone.ts` `directionText`/`directionChip`, `Badge` `beat`/`miss` variants).
- **Un-highlighted figures:** key figures render as plain prose because the markdown path has no metric-highlighting components.

### 2.5 Defect (e) — weak citations, next to a solved problem

The quality bar already exists in the same product:

- **Copilot citations:** `CopilotCitation {n, excerpt, section_ref, verified, fragment_url}` (`frontend/features/filings/api/copilot-api.ts:9-16`), rendered by `CitationChip.tsx` (popover with section header, verbatim excerpt, Verified/Cited badge, "Open original") and the `SourcesList` footnotes in `CopilotMessage.tsx`.
- **Backend verification:** excerpts verified verbatim against cached filing text (`provenance_service.py:86-98` `verify_excerpt_in_text`), `#:~:text=` deep links (`provenance_service.py:101-114`), and `[F#]` numeric-fact markers guarded by value- and concept-adjacency checks (`copilot_service.py:357-491`).
- **Summary risks already carry the data** — `supporting_evidence`/`source_section_ref` with provenance enrichment (`provenance_service.py:186-245`) and a structured renderer (`SummaryRisks.tsx` + `SourceTrace.tsx`) — but only on the flag-gated tabbed branch. The markdown body path uses none of it and prints `(Evidence: …)` prose instead.

### 2.6 Defect (f) — section ordering

Backend markdown order is hardcoded in `_build_structured_markdown`; page card order is the JSX sequence in `SummaryDisplay.tsx:132-277`. The copilot callout (`AskFilingCallout`, `:262-264`) sits last on the page; the founder wants it near the top.

### 2.7 Defect (g) — the same delta computed four different ways

The founder's Financial Highlights screenshot exposed a fourth defect class: **at least four independent computations of the same change**:

| Surface | Computation | NVIDIA example |
|---|---|---|
| LLM prose / `financial_highlights.table.change` | model-generated text | "+85% YoY", "211%" |
| `FinancialMetricsTable` | client-side `calculateChange` (`FinancialMetricsTable.tsx:29-41`), relative-% for everything **including margins** | "+85.0%", "+210.1%", Gross Margin "+23.8%" |
| What-changed chips | deterministic XBRL diff (`dashboard_feed_service.compute_what_changed:111-184`) | "+85.2%", "+210.6%" |
| CSV export | model text preserved | "+85% YoY", "+14.4 ppts" |

For a finance product, three different values of "the same" number on one page is a credibility killer, and a margin shown as "+23.8%" (relative) versus "+14.4 ppts" is a category error. The founder also asked for citations on the table's LLM-written "Investor Takeaway" column (picked up in T4.2).

### 2.8 Locked contracts any fix must respect

- **SSE stream:** `progress` → (`preview`, gated off by `STREAM_SECTION_REVEAL=false`) → **one** `chunk` whose `content` is the final markdown (`summary_pipeline.py:793`) → `complete`/`partial`/`error`. There is **no token streaming** — a decisive simplifier: the structured web page needs zero SSE contract change (see T2.5).
- **Locked tests:** `backend/tests/unit/test_background_generation_characterization.py` (5 tests), `backend/tests/integration/test_summary_stream_heartbeat.py`, `frontend/tests/unit/summaryStream.spec.ts` + `summaryStream.contract.spec.ts`; serializer pins `test_export_service.py`, `test_structured_markdown_render.py`, `test_markdown_render_bullets.py`. Amendments only via the documented same-PR contract-change procedure (Part 5, amendment ledger).
- **One orchestrator:** `summary_pipeline.py::stream_filing_summary` serves both SSE and the background/cron drain — every change lands inside it, never as a second path.

---

## Part 3 — The content framework (Stream 2)

### 3.0 Principles (each from a source actually consulted)

1. Value comes from growth, margins, reinvestment, and risk — not reported earnings ([Damodaran primer](https://aswathdamodaran.substack.com/p/earnings-cash-flows-and-free-cash); overview via [Quartr synthesis](https://quartr.com/insights/investment-strategy/aswath-damodaran-the-dean-of-valuation)).
2. Cash flows are "least contaminated by accounting overreach"; SBC is a real cost, not an add-back ([Damodaran primer](https://aswathdamodaran.substack.com/p/earnings-cash-flows-and-free-cash)).
3. Normalize: strip one-time and non-operating items before judging performance ([Damodaran, normalizing earnings](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/valquestions/normearn.htm)).
4. Unrealized mark-to-market equity gains are not operating performance — Buffett: the ASU 2016-01 rule makes the GAAP bottom line "useless… for analytical purposes"; focus on operating earnings ([1986](https://www.berkshirehathaway.com/letters/1986.html)/[2018 letters](https://www.berkshirehathaway.com/letters/2018ltr.pdf); [ASU 2016-01 explainer](https://www.newconstructs.com/how-asu-2016-01-impacts-invested-capital-and-oci/)). This is precisely NVIDIA's $16.0B quarter.
5. Capital allocation is the CEO's most important job — always state how cash was deployed and whether it created value ([Buffett 1987 letter](https://www.berkshirehathaway.com/letters/1987.html)).
6. Value is created only when returns on invested capital exceed the cost of capital ([Mauboussin ROIC framework](https://www.morganstanley.com/im/publication/insights/articles/article_returnoninvestedcapital.pdf), read via [synthesis](https://summitstocks.substack.com/p/understanding-return-on-invested)); judge the print against the bar expectations set ([Mauboussin & Rappaport](https://www.fool.com/investing/2022/01/19/expectations-investing-qanda-mauboussin-rappaport/)).
7. Earnings quality = cash conversion; NI persistently above CFO signals accrual risk ([CFA Institute FRQ reading](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/financial-reporting-quality); [O'Glove](https://macro-ops.com/quality-of-earnings-a-book-review/); [Schilit](https://www.autymate.com/book-summary/financial-shenanigans)).
8. MD&A's own mandate is the summarizer's mandate: management's eyes, context for the numbers, quality/variability of earnings and cash flow, and **known trends and uncertainties** — explicitly *not* recitation ([SEC 2003 MD&A interpretive guidance](https://www.sec.gov/rules-regulations/2003/12/commission-guidance-regarding-managements-discussion-analysis-financial-condition-results-operations)).
9. The sell-side reaction note is the proven compression format: print → drivers → guidance change → thesis impact ([structure](https://ctacquisitions.com/sell-side-analyst/); [AAII five steps](https://www.aaii.com/journal/article/306380-how-to-analyze-corporate-earnings-in-five-steps)).

**Audience union (why one architecture, no personas):** traders/journalists need the top of the pyramid (print, surprise, catalysts, quotes); analysts/students the middle (drivers, segments, margin bridge, definitions); long-term investors the quality layer (cash conversion, capital allocation, moat evidence, risks). The needs are nested, not disjoint — an inverted-pyramid document lets each self-select depth.

### 3.1 The section architecture (SummaryDoc v2)

Nine filing-only sections. Hard rule: **each number has exactly one home**; only §1 may echo up to three headline figures (by reference, not re-computation).

| # | Section | Contents (and which numbers live here exclusively) | Why it earns its place | Primary readers |
|---|---|---|---|---|
| 1 | **The Print** | Headline; ≤3 key figures (by `metric_id` reference) each with driver + so-what, vs the filing's own prior-period comparatives; "what this filing changes." **Absorbs Key Takeaways** — there is no second summary. | The reaction-note lead ([sell-side](https://ctacquisitions.com/sell-side-analyst/)) | All; trader/journalist most |
| 2 | **Results That Matter** | The single P&L metrics table: revenue, operating income, **operating margin in ppts**, diluted EPS — current/prior/change (all renderer-injected) + one-line driver each. **Cash lines deliberately excluded** (they live in §3). | Analysis-not-recitation ([SEC MD&A](https://www.sec.gov/rules-regulations/2003/12/commission-guidance-regarding-managements-discussion-analysis-financial-condition-results-operations)) | Analyst, student |
| 3 | **Earnings Quality & Cash Conversion** | Operating-vs-one-time bridge (adjusted vs reported — e.g. NVIDIA's $16B unrealized gains); NI-vs-CFO gap and the accrual read; FCF and conversion; red-flag scan (receivables/inventory vs sales, one-time gains as % of pretax). | The differentiator; "is the profit real?" ([Buffett 2018](https://www.berkshirehathaway.com/letters/2018ltr.pdf); [Damodaran](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/valquestions/normearn.htm); [CFA](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/financial-reporting-quality)) | Analyst, long-term investor |
| 4 | **Value Drivers & Capital Allocation** | Buybacks/dividends/M&A/capex this period with a value verdict; ROIC level/trend where XBRL supports it (cost-of-capital comparison stays qualitative — not filing data). | CEO's #1 job ([Buffett 1987](https://www.berkshirehathaway.com/letters/1987.html)); ROIC discipline ([Mauboussin](https://www.morganstanley.com/im/publication/insights/articles/article_returnoninvestedcapital.pdf)) | Long-term investor, analyst |
| 5 | **Forward Signals** | Guidance (raised/cut/maintained/not given — with the *why it matters* when absent); known trends & uncertainties (Item 303 lens); demand/pricing/backlog signals; subsequent events; management quoted **verbatim only when forward-looking or unusual**. | Cures the backward-looking complaint; MD&A's forward mandate ([SEC](https://www.sec.gov/rules-regulations/2003/12/commission-guidance-regarding-managements-discussion-analysis-financial-condition-results-operations)) | All; trader/analyst most |
| 6 | **Risks** | Material risks tied to specific line items with anchored evidence; critical accounting estimates + sensitivities; **10-Q renders the delta vs prior risk set only**. | Item 303 discipline; evidence-tied risk beats boilerplate | All |
| 7 | **Segments** | Segment revenue/operating income table (renderer-injected from XBRL dimensions) + model commentary on mix and concentration. Segment figures live here, never restated as group color. | Segment mix is where the real story is | Analyst, student, LT investor |
| 8 | **Balance Sheet & Liquidity** | Leverage, maturities, covenants, liquidity runway, working-capital dynamics. | MD&A liquidity mandate beyond recitation ([SEC](https://www.sec.gov/rules-regulations/2003/12/commission-guidance-regarding-managements-discussion-analysis-financial-condition-results-operations)) | LT investor, analyst |
| 9 | **Notable Footnotes** | One home for fine print: SBC magnitude, related-party items, revenue-recognition changes, contingencies/litigation, concentration disclosures. | Where quality issues hide ([O'Glove](https://macro-ops.com/quality-of-earnings-a-book-review/)/[Schilit](https://www.autymate.com/book-summary/financial-shenanigans)) | Analyst, journalist |

**What Changed stays a separate, labeled surface** (the sanctioned cross-filing surface per repo rule 2), reframed as an **information delta** — guidance revisions, new disclosures, changed risks — with deterministic metric chips, never a re-listing of the summary's own numbers (fixes §2.3 cause 2).

**Filing-only adaptation (deliberate deviations from the research):** the research framework's "beat/miss vs consensus" and "price-implied expectations" are excluded — the summary derives only from the filing's own text and XBRL (repo non-negotiable #2). The comparison bar is the filing's own comparatives; a consensus module could exist someday as a separate labeled surface fed by `app/integrations/` (fmp/finnhub), but it is out of scope here.

**Redundancy kill, explicitly:** Key Takeaways → absorbed into §1. Cash lines → out of the §2 table into §3. Outlook → elevated into §5. "3-Year Investment Perspective" → dissolved (trend framing belongs to Multi-Period Analysis, the labeled cross-filing product). What-changed → information delta.

### 3.2 Per-form flexes (one architecture, different weights)

- **10-K:** audited (§3 gains confidence; include auditor opinion/ICFR); full risk set in §6; §7 anchors business description/moat; §5 draws the full known-trends discussion.
- **10-Q:** unaudited (flag it); §1/§2 emphasize sequential + YoY; §6 is the risk **delta**; §5 elevates subsequent events and guidance revisions.
- **20-F:** state IFRS vs US GAAP; FX/translation prominent in §2/§3/§8; IFRS 8 segment presentation in §7 ([FPI overview](https://perkinscoie.com/public-company-handbook-chapter-15-foreign-private-issuers)).
- **40-F:** MJDS wrapper — summarize the underlying Canadian MD&A/AIF and say so ([form comparison](https://www.toppanmerrill.com/blog/how-to-navigate-forms-10-k-10-q-20-f-40-f-8-k-and-6-k/)).
- **6-K:** episodic and furnished, often the guidance vehicle — compress to §1 + §5 (+ whichever of §3/§6/§7 the event touches); omit empty sections entirely ([SEC Form 6-K](https://www.sec.gov/files/form6-k.pdf)).

### 3.3 The prose quality bar (encoded into prompts and evals, not left as advice)

1. Every claim pairs **magnitude + driver + so-what**; a level with no comparison and no driver is filler.
2. Margins and rates change in **percentage points**, with the bridge ("74.9% from 60.5%, +14.4 ppts, on the absent H20 charge").
3. **Operating vs one-time separated, always** — unrealized gains, impairments, settlements never sit unlabeled inside "earnings."
4. **Net income is always paired with CFO/FCF**; a divergence names its accrual cause.
5. Management is quoted **verbatim only for forward-looking or unusual statements**, attributed to the exact section ("MD&A, Item 2"), never to restate results.
6. **One home per number**; §1 may echo ≤3 headline figures.
7. Prefer change and rate-of-change over levels.
8. Label every forward number's source: management guidance vs the summary's own read.
9. Every risk ties to a specific line item or disclosed fact; no generic risk language (an existing gate: `no-generic-risk-language.spec.tsx`).
10. Flag provenance inline where it changes interpretation: audited vs unaudited, GAAP vs non-GAAP vs IFRS, restated.

---

## Part 4 — Tooling plan (Stream 3, verified against current docs)

### 4.1 EdgarTools: capability → section map

Repo pins `edgartools==5.40.1`; current is **5.41.0** (PyPI, 2026-07-07) — a trivial bump with section-extraction gains. Capabilities to exploit ([GitHub](https://github.com/dgunning/edgartools) · [docs](https://edgartools.readthedocs.io/en/latest/) · [releases](https://github.com/dgunning/edgartools/releases)):

| Capability (API) | Feeds | Note |
|---|---|---|
| `TenK`/`TenQ` item access, `Section.markdown()`, `Section.warnings` | All section text; extraction health signal | Owned by in-flight **A7** (report-quality plan); `Section.warnings` should gate generation on thin extraction |
| `xbrl.statements.income_statement()/balance_sheet()/cashflow_statement()` (as-reported) | §2, §3, §8 | As-reported avoids the ~2,000-tags→95-concepts standardization drift that produced the bank-revenue problem |
| `xbrl.query().by_dimension("…Axis", …)` | **§7 segments** — revenue/op income per reportable segment, geography | Dimensional data exists only where the filer tagged it; degrade gracefully |
| `financials.get_financial_metrics(period_offset=0/1)` + raw facts | The delta service's inputs (current + prior period pairs) | Convenience only — deltas are computed in our code |
| `calculation_linkbase()` | Foot-check that extracted subtotals add up | Cheap sanity gate before numbers enter the prompt |
| `EightK.press_releases` (EX-99) | §5 corroboration: guidance often lives in the earnings release | Second grounded source, still SEC-hosted |
| `Ownership` (Forms 3/4/5), `ThirteenF` | Future §4 color (insider nets) | Defer; not in the ≤T6 roadmap |
| 20-F/6-K support | FPI roadmap (`ENABLE_FPI_FILINGS`) | Thinner than TenK — plan on `markdown()` + XBRL + exhibits, not item properties |

### 4.2 DeepSeek `deepseek-v4-pro`: how to drive the fixed generator

Verified against live docs (post-knowledge-cutoff model; sources: [pricing](https://api-docs.deepseek.com/quick_start/pricing) · [json mode](https://api-docs.deepseek.com/guides/json_mode) · [thinking mode](https://api-docs.deepseek.com/guides/thinking_mode) · [rate limits](https://api-docs.deepseek.com/quick_start/rate_limit)):

- **1M-token context, 384K max output.** Keep generation context ≲128K tokens where retrieval is most reliable (the existing 320k-char excerpt cap ≈ 80k tokens is comfortably inside).
- **Pricing:** input cache-hit **$0.003625/M** vs cache-miss **$0.435/M** (**120×**), output $0.87/M — matching the repo's cost-model settings. **A 2× peak-hour surcharge (UTC 01:00–04:00 and 06:00–10:00) arrives with the full V4 release ~mid-July 2026** ([SCMP](https://www.scmp.com/tech/big-tech/article/3358868/after-triggering-price-war-deepseek-reverses-course-surcharge-peak-hour-api-use)) — batch regeneration must be scheduled off-peak (T6.2).
- **JSON:** `response_format={"type":"json_object"}` only — **no strict schema enforcement**. The prompt must contain the word "json" plus a filled example; validate with pydantic + the already-shipped `json-repair`, one retry that echoes the validation error. **Do not adopt `instructor` or function-calling:** v4-pro rejects `tool_choice="required"` with HTTP 400 ([DeepSeek-V3 #1376](https://github.com/deepseek-ai/DeepSeek-V3/issues/1376); [pydantic-ai #5193](https://github.com/pydantic/pydantic-ai/issues/5193)).
- **Thinking mode must stay disabled for extraction** (the repo already does this via `extra_body`): in thinking mode temperature/top_p are silently ignored and function calling is unsupported.
- **The model will not abstain:** ~94% "answer-anyway" rate on unknowns ([DeepInfra overview](https://deepinfra.com/blog/deepseek-v4-pro-model-overview)) — the architectural conclusion is that **it must never compute or guess a figure**.
- **Prompt patterns to adopt:** schema-plus-worked-example in prompt; source text delimited as `<section id="…">` with citations required to reference section ids + verbatim spans; **extract-then-write only if evals demand it** (start single-pass; the two-pass option stays in reserve); temperature 0 for extraction; **cache-friendly stable prefix** — invariant instructions + schema first, filing text last, byte-identical across calls (T6.1).

### 4.3 The verification layer (no second generator; ≤$50/month)

The governing principle, reconciling the tooling research with the repo's own lessons (`arch-no-precomputed-deltas-in-grounding`, `arch-stop-tuning-prose-know-the-floor`): **numbers from code, words from the model.**

1. **One delta service** (`metric_delta_service.py`, extracted from `dashboard_feed_service.compute_what_changed`): every %/ppt/margin/per-share change computed once from XBRL facts, with one formatting policy (`ratio`→ppts; else signed one-decimal %). Consumers: the LLM schema (values renderer-injected against `metric_id` references — the model writes only driver/commentary text, and the reference table carries **no "explain why" directive**, per the lesson), `FinancialMetricsTable` (client-side `calculateChange` deleted), What-changed chips, exports. Cost: $0.
2. **Number-diff gate:** post-generation, extract every numeric token from the output and diff against (computed set ∪ filing-text numbers); unexplained figures become a quality-gate reason. This is the deterministic "figure-not-traceable" check the prompt-tuning lesson said the residual belongs to. Cost: $0.
3. **Citation anchoring:** `rapidfuzz` is **already installed** (edgartools dependency). Every evidence span fuzzy-anchors against the actual section text (accept ≥~92; below → drop the citation and record a coverage reason), reusing `verify_excerpt_in_text` + `build_text_fragment_url`. Cost: $0.
4. **Optional self-verify pass** (`SUMMARY_SELF_VERIFY`, default off): DeepSeek-as-verifier with a different prompt (claims vs excerpts vs computed numbers → JSON verdict), non-thinking, temp 0. ~$0.0014/filing with warm cache, ~$0.014 cold — **$1–15/month** at realistic volume. Enable only if evals show it catches what 1–3 don't.
5. **Offline only:** RAGAS/HHEM-style faithfulness models stay in `backend/evals/` as regression metrics, never in the request path.

**Cost summary:** $0/month new infrastructure; ≤ ~$20/month variable LLM worst case (self-verify on + heavy eval iteration) — under the $50 cap. One-off corpus regeneration ≈ $0.04–0.05/filing at cache-miss prices.

---

## Part 5 — The tiered roadmap

Effort: **S** = 0.5–1.5 solo-founder days, **M** = 2–4, **L** = 5–8. Every tier is independently shippable. Any prompt/flag/extraction change runs the eval gate and **re-pins `baseline_scores.json` in the same PR** (RUNBOOK; `--runs 3+` aggregates for prose changes). Every "never again" rule lands with its machine gate in the same PR (`arch-structural-gates-over-prose-rules`).

### Tier 1 — Correctness & consistency (~7–9 days, $0/mo)

*Stop shipping contradictory numbers and internal scaffolding; make stored summaries refreshable.*

| # | Item | Impact | Effort | $/mo |
|---|---|---|---|---|
| 1.1 | **Kill backend markdown leaks** in `markdown_render.py`: render guidance/tone/drivers/watch-items as prose and bullets without field-name labels; apply the exec-snapshot neutral-tone suppression (`:72`) to Outlook (`:186-187`); replace `(Evidence: …)` with structured evidence (interim: drop from prose); fix the stale "fallback" docstring. Amends serializer pins (`test_structured_markdown_render.py`, `test_markdown_render_bullets.py`) + G4 hygiene patterns extended to the ex-leaked labels as regression guards — same PR. | **H** — template junk on every summary | S–M | 0 |
| 1.2 | **Kill frontend dict-flattener leaks**: replace `renderMarkdownValue`-driven Key Takeaways content with real components for the known `executive_snapshot` keys; suppress neutral tone and raw section refs. **First verify which branch production serves** (`ENABLE_SECTION_TABS` is true in `vercel.json`, false in local defaults; the founder's screenshots show the non-tab branch). | **H** | S | 0 |
| 1.3 | **Version stamps**: `schema_version SMALLINT` + `prompt_version TEXT` on `summaries` (idempotent dated migration + ORM columns), constants beside a new `SummaryDoc` schema module, stamped on every write, staleness surfaced in the API and an admin count. Makes the stranded pre-P0-2 rows identifiable. | **H** — unblocks every later tier | S–M | 0 |
| 1.4 | **In-place refresh**: `force_regenerate` upsert in the pipeline's save step that UPDATEs the existing row (preserves `summaries.id` → saved-summary bookmarks survive; satisfies `UNIQUE(filing_id)`), guarded by a **keep-better quality gate** (a refresh only overwrites when `assess_quality` tier ≥ stored tier — mandatory, because the 75s AI-timeout XBRL fallback would otherwise let a bulk refresh silently downgrade full summaries to partials). New `POST /api/admin/summaries/refresh-stale?schema_version_lt=&filing_type=&limit=` regenerating stale rows off-peak, traffic-first. Adds an additive characterization test for the force path. | **H** — saved summaries are permanently stale today | M | one-off regen ≈$0.05/filing |
| 1.5 | **One delta service** (`metric_delta_service.py` extracted from `compute_what_changed`): backend display strings consumed by `FinancialMetricsTable` (delete client `calculateChange`), What-changed chips, CSV. Margins in **ppts everywhere**. | **H** — four disagreeing deltas is a credibility killer | M | 0 |
| 1.6 | **What-changed dedup**: stop using `key_changes` (= stringified `guidance_outlook`) as the card lead; deterministic delta framing instead; column deprecated-in-place (still written, nothing reads it). | **M** | S | 0 |
| 1.7 | **Design-system batch**: consolidate the triple header to one `CardHeader` (demote/strip the backend `##` heading at render until T2 removes markdown); route delta figures through `financialTone`; center What-changed chips; move `AskFilingCallout` up per founder; **implement justified body text** (`text-align: justify` + `hyphens: auto` on `.markdown-body p`, documented in `DESIGN_SYSTEM.md` as an app-wide decision per rule 11 — founder's explicit request; note the ragged-right readability caveat and that it's a one-line revert). | **M** | S–M | 0 |

### Tier 2 — Single source of truth (~8–11 days, $0/mo)

*Finish the convergence `summary_sections.py` was built for: one projection feeding web, PDF, CSV.*

| # | Item | Impact | Effort | $/mo |
|---|---|---|---|---|
| 2.1 | Extend `Section`/`Block`: `metrics` kind (typed rows, values injected from the delta service), `callout` kind, optional per-block `evidence {excerpt, section_ref, verified, fragment_url}`, stable `Section.id` slugs; version-dispatch on `schema_version`. | **H** | M | 0 |
| 2.2 | `sections_to_markdown(render_sections(...))` replaces `_build_structured_markdown` as the `business_overview` writer — markdown becomes a **derived artifact** of the one projection (column kept for SSE/legacy; nothing user-facing renders it after 2.4). Amends the two markdown pin suites, same PR. Delete the "mirror the frontend" comments — the dependency inverts here. | **H** — ends three-serializer divergence at the root | M | 0 |
| 2.3 | Additive `rendered_sections` field on the summary GET (serialized Section/Block JSON, computed on read — no new column, no staleness). | **M** | S | 0 |
| 2.4 | **`SummaryBlocks` structured page**: single scrolling page + sticky section TOC, one block-renderer component per `Block.kind`; replaces the ReactMarkdown card *and* the `SummarySections` tabs; `FinancialMetricsTable` becomes the `metrics`-block renderer (kills the duplicate Financials rendering); Key Takeaways absorbed into The Print. **Supersedes the in-flight B2 item's tab container while delivering its goal** (structured rendering by default); retire `ENABLE_SECTION_TABS`. React 18, `components/` allowlist respected (new components in `features/summaries/components/`). | **H** | L | 0 |
| 2.5 | SSE: **zero event changes** (single terminal `chunk` + refetch-on-`complete` already matches the structured page). One documented additive amendment: `complete` gains `schema_version` (contract doc + `summaryStream.contract.spec.ts` + characterization fixtures in one PR). | **M** | S | 0 |
| 2.6 | Export polish (absorbs part of in-flight B5): `metrics`/`callout` rendering in `export_service.py`; PDF/CSV parity snapshot tests extended (pin update same PR). | **M** | M | 0 |

### Tier 3 — Content re-architecture (~10–14 days; one-off regen ≈$4/100 filings)

*The SummaryDoc v2 cutover — sequenced **after** the in-flight A7/A8 extraction work lands, which §2/§8 depth depends on.*

| # | Item | Impact | Effort | $/mo |
|---|---|---|---|---|
| 3.0 | **Scorer/golden-set extensions FIRST** (blocking 3.1): redundancy scorer (numeric token in >1 section), delta-consistency scorer (every %/ppt ∈ computed set), citation-verify scorer (modeled on the copilot verbatim-excerpt verifier), forward-looking-verbatim scorer (rapidfuzz ≥92); coverage scorer re-keyed by `schema_version` so v1 baselines stay comparable; `assess_quality`'s 4/9 bar re-derived for the v2 taxonomy (the quality badge must not lie across the cutover). | **H** (enabler) | M | ~$3 per full eval pass |
| 3.1 | **SummaryDoc v2** + rewritten `backend/prompts/{10k,10q,20f,6k}-structured-agent.md`: the Part-3 sections, one-home-per-number enforced by schema design, `metric_id` references with renderer-injected values, pydantic + json-repair + one error-echo retry; `SUMMARY_SCHEMA_VERSION=2`. Eval-gated `--runs 3`, baseline re-pinned same PR. Gives the in-flight A13/A14/A15 items their concrete section homes. | **H** — the content jump | L | regen via 1.4 |
| 3.2 | **Number-diff machine gate** (Part 4.3.2) wired into `assess_quality` as a deterministic reason. | **H** | M | 0 |
| 3.3 | Staged corpus regeneration through `refresh-stale`: traffic-ranked, off-peak, keep-better-gated. | **M** | S | ≈$4/100 filings one-off |

### Tier 4 — Citations everywhere (~6–8 days, $0/mo) — implements in-flight B1

| # | Item | Impact | Effort | $/mo |
|---|---|---|---|---|
| 4.1 | `evidence` population on Print claims, Results drivers, Forward quotes, Footnotes (risks already have it): generalize `provenance_service` enrichment with rapidfuzz anchoring (accept ≥92, else drop + coverage reason). | **H** — trust is the product | M | 0 |
| 4.2 | Web: `CitationChip`/`SourceTrace` on evidence-bearing blocks, including **Investor-Takeaway citations** on the metrics block (commentary evidence beside the existing `MetricSourceLink` XBRL provenance). | **H** — founder's direct ask | M | 0 |
| 4.3 | PDF: numbered footnote appendix with fragment URLs (CSV: source-ref column). | **M** | S | 0 |
| 4.4 | Citation scorer flips advisory → gating for summary evals. | **M** | S | 0 |

### Tier 5 — Analytical depth (~8–10 days, $0/mo) — absorbs in-flight A13/A14/A15

| # | Item | Impact | Effort | $/mo |
|---|---|---|---|---|
| 5.1 | **Earnings Quality fed deterministically**: NI-vs-CFO gap, FCF, one-time bridge computed from XBRL/cash-flow statements (= A13) + red-flag callouts (= A14); model writes commentary only. | **H** — the section sophisticated readers pay for | M–L | 0 |
| 5.2 | **Segments** via `xbrl.query().by_dimension` → injected table + commentary (= A15). Requires the edgartools 5.40.1→5.41.0 bump: regression-run extraction on the 27-filing golden set; coordinate with the A7 owner. | **M** | M | 0 |
| 5.3 | Value Drivers: buybacks/dividends/capex from XBRL; ROIC trend where data supports; eval-gated verdict prose. | **M** | M | 0 |
| 5.4 | Forward Signals hard gate: the verbatim-quote rapidfuzz check becomes blocking (non-verbatim quotes dropped). | **M** | S | 0 |

### Tier 6 — Cost & operations (~3–4 days; net cost-negative)

| # | Item | Impact | Effort | $/mo |
|---|---|---|---|---|
| 6.1 | **Stable prompt prefix** for DeepSeek context caching (invariant instructions + schema first, filing text last, byte-identical). Honest framing: the 120× saving applies to repeated prefixes — the wins are eval runs, retries, and regenerations, not first generations. | **M–H** on dev-loop cost | S | −$2–10 |
| 6.2 | Config-driven **off-peak windows** for cron precompute + refresh-stale (avoid UTC 01:00–04:00 / 06:00–10:00 once the 2× surcharge lands mid-July 2026). | **M** | S | avoids 2× |
| 6.3 | Optional **`SUMMARY_SELF_VERIFY`** flag (default off): the Part-4.3.4 verifier pass; enable only if evals prove marginal catch-rate. | **M** | M | +$1–15 |
| 6.4 | If live section streaming is ever wanted: additive `preview.sections` alongside `markdown` under `STREAM_SECTION_REVEAL`, via the documented amendment procedure. | **L–M** | S–M | 0 |

**Running total:** $0/month new infrastructure; ≤ ~$20/month variable LLM worst case. Under the $50 cap with headroom.

### Contract-amendment ledger

| Change | Tests amended (same PR, documented in PR body) |
|---|---|
| T1.1, T2.2 markdown output changes | `test_structured_markdown_render.py`, `test_markdown_render_bullets.py`; G4 hygiene re-pin |
| T2.1/T2.6 export changes | `test_export_service.py` |
| T2.5 `complete.schema_version`; T6.4 `preview.sections` | SSE contract doc + `summaryStream.contract.spec.ts` + `test_background_generation_characterization.py` fixtures — **additive fields only; never rename or repurpose `chunk`/`complete`/`partial`/`error`** (`chunk.content` stays final markdown — the guest path and `stripInternalNotices` depend on it) |
| T3.0 scorers | new deterministic scorers + golden-set ground truth land before 3.1; baselines re-pinned at the cutover PR |

### Dovetail map (in-flight work)

| In-flight item | This plan's relationship |
|---|---|
| **A7/A8** (edgartools sections; XBRL 4→~12 metrics) — report-quality Phase 1 / data-quality P1-7 | **Owned elsewhere; T3.1 sequences after it.** §2/§8 depth consumes A8's metric set |
| **P0-4** (bank prompt carve-out) — data-quality track, open | Untouched; v2 prompt work (3.1) coordinates timing to avoid eval-baseline collisions |
| **P0-2** (join fix, FI signals, quality badge) — merged | Built on; T1.3/1.4 make it actually reach stored summaries |
| **B1** (click-to-source citations) | **Implemented by T4** |
| **B2** (structured tabs default-on) | **Superseded in container, honored in goal** by T2.4's structured page; `ENABLE_SECTION_TABS` retired |
| **B3** (honest quality badge) | Reinforced by T1.3 + T3.0's re-derived bar |
| **B5** (export polish) | Absorbed by T2.6 + T4.3 |
| **A13/A14/A15** (cash-flow quality, red flags, segments) | **Given concrete section homes** by T3.1; implemented by T5 |

### Do-not-do list

- Persona or user-conditional summaries (violates one-cached-summary and `UNIQUE(filing_id)`).
- Generation-model swap or a second generation path (one orchestrator; DeepSeek v4-pro only).
- `instructor`/function-calling structured output (v4-pro `tool_choice` 400 trap) — `json_object` + pydantic + json-repair only.
- Model-computed arithmetic anywhere; precomputed deltas in *narrative grounding* alongside "explain why" directives (lesson `arch-no-precomputed-deltas-in-grounding` — computed values live in schema fields the model copies or never touches).
- Consensus/market data or any cross-filing content in the summary body (labeled What-changed surface only).
- Vector DB / RAG infrastructure (the excerpt fits in context; keep ≲128K tokens instead).
- Duplicating A7/A8/P0-4 scope.
- Redis-dependent designs (prod is L1-only per ADR-0004); DDL in the startup path; `@tailwindcss/typography`; renaming SSE events; dropping the `business_overview` column (demote, don't drop).

### Risks & design tensions

1. **Streaming vs structured is smaller than it looks:** there is no token streaming today (single terminal `chunk`), so the structured page changes nothing mid-generation. The tension only materializes if `STREAM_SECTION_REVEAL` is enabled before T6.4.
2. **Refresh economics & the mass-downgrade trap:** every schema/prompt bump stales the corpus (~$0.05/filing to regenerate); the 75s-timeout XBRL fallback makes the T1.4 keep-better gate mandatory, not optional. Multi-instance double-generation during refresh is possible (per-process in-flight map) but bounded; last-writer-wins under the upsert is acceptable and documented.
3. **Eval churn at the v2 cutover:** coverage/quality scorers are keyed to the 9-section taxonomy; scorers must be versioned by `schema_version` and baselines re-pinned in the cutover PR. Prompt iteration over 27 filings × 3 runs is the hidden cost — T6.1's prefix caching largely pays for it.
4. **Badge honesty across the cutover:** T3.0 must land with T3.1 (or the badge is suppressed for v2 rows) so `assess_quality` never scores v2 output against the v1 bar.
5. **`ENABLE_SECTION_TABS` ambiguity:** true in `vercel.json`, false in local defaults, and the founder's screenshots show the non-tab branch — verify what production actually serves before spending T1.2 effort on the wrong branch.

---

## Part 6 — Assumptions and things not fully verified

1. **Production flag state:** `ENABLE_SECTION_TABS` (and `ENABLE_QUALITY_BADGE`) could not be confirmed for the live Vercel deployment — `vercel.json` says true, local defaults say false, screenshots look like false. T1.2 starts by checking the deployed value.
2. **The `.;` artifacts in the screenshots are attributed to stale stored summaries** (pre-P0-2 `business_overview` + no version stamp). This fits all evidence (fix merged; NVIDIA summary generated 2026-07-07 per the CSV header — regenerating it should confirm) but was not re-verified against the production database.
3. **DeepSeek peak-pricing timing** ("full V4 release ~mid-July 2026", off-peak discounts unconfirmed) is from press coverage of an announced change; exact dates/rates may shift. The off-peak scheduling item (T6.2) is config-driven for this reason.
4. **edgartools 20-F/40-F extraction maturity** is thinner than TenK/TenQ (no rich item properties); the FPI flexes in Part 3.2 assume `markdown()` + XBRL + exhibit parsing, which needs a spike when `ENABLE_FPI_FILINGS` becomes real.
5. **Two finance primary sources were cited by title, read via secondary syntheses** (Damodaran's `earnings.pdf` notes; Mauboussin's Morgan Stanley ROIC paper — both PDFs resisted text extraction). Every other finance/tooling claim links the source actually consulted.
6. **Segment dimensional coverage varies by filer** — §7 must degrade gracefully (omit the table, keep commentary) when dimensions aren't tagged.
7. **Effort estimates** assume solo-founder pace with the existing test/eval harness; they are calendar-day shapes, not commitments.
8. **Consensus/expectations content** is deliberately excluded from the summary (filing-only rule). If it's ever wanted, it's a separate labeled surface fed by `app/integrations/` — new scope, new entitlements decision, not assumed here.

---

## Self-check against the acceptance criteria

- **Section architecture concrete enough to build from:** Part 3.1's table + Part 5 T3.1's schema and per-form prompt list; the Plan-agent schema sketch (field-level) is preserved in T3.1's description.
- **Every recommendation carries impact / effort / cost:** all tier tables.
- **Every finance and tooling claim cites a consulted source:** inline links throughout Parts 3–4 (with the two title-only citations disclosed in Part 6.5).
- **No persona variants; no generation-model change:** constraints §1–2, do-not-do list.
- **Exports stay data-linked:** by construction (Part 2.0 → T2's single projection).
- **New infra ≤ $50/month:** $0 fixed; ≤ ~$20/month variable worst case.
