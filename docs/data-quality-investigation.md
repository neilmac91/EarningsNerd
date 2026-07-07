# Data-Quality Investigation & Remediation Plan — JPMorgan case

**Date:** 2026-07-07 · **Status:** investigation complete; this document IS the remediation plan (no code changed yet)
**Trigger:** four user-visible data-quality failures found on JPMORGAN CHASE & CO (CIK 0000019617) one week before public beta.
**Method:** four parallel code-investigation streams; every load-bearing root-cause site re-read and confirmed at file:line; ground truth verified live against SEC EDGAR on 2026-07-07 (`company_tickers.json`, submissions API, XBRL companyconcept, EFTS); EdgarTools docs + its actual concept-mapping store cross-checked. Anchor filing: JPM 10-K filed 2026-02-13, accession 0001628280-26-008131, period end 2025-12-31.

## TL;DR

| # | Symptom | Root cause (one line) | Blast radius | Priority |
|---|---|---|---|---|
| 1 | "jpm" search shows duplicate rows, all labelled **JPM-PM** (a preferred ticker) with the preferred's $17.29 price | `/api/companies/search` appends one response row per SEC ticker entry per CIK **and** overwrites `Company.ticker` last-write-wins; preferreds sort last in SEC's ticker file | **1,471 of 8,002 CIKs (18.4%)** are multi-ticker; every preferred-heavy financial (BAC→BAC-PS, WFC→WFC-PZ) and multi-class issuer (GOOGL→GOOGN, BRK-B→BRK-A) corrupts identically | **P0** |
| 2 | Filing history capped at 4 filings; no year filter; no path to older filings | **Ingestion** cap: only SEC's "recent window" is ever fetched; JPM's window spans ~1 year (25,421 filings, 22,069 of them 424B2 structured notes) and holds exactly 1 10-K + 3 10-Q | Systemic mechanism; severity scales with filing volume — mega-filer banks worst (~4 filings), ordinary filers ~20 shown / ~5 years | **P0 note + P1 fix** |
| 3 | Summary badge "Partial · financial figures not grounded in SEC XBRL data"; "not disclosed in the provided excerpts" litter; "X.; Y" text artifacts; bank-nonsense (capex, working capital) | **Four independent causes:** (A) bank-blind grounding check → false alarm; (B) 70k/55k/45k-char excerpt caps; (C) industrial checklist prompt → fabricated FCF driver; (D) `"; ".join` web render | A: all banks · B: all large filings · C: all financials · D: universal | **P0 (A,C,D) + P1 (B)** |
| 4 | Multi-period Cash line stops dead after FY2018; misleading dual axes | Cash concept registry lacks `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents` — the tag JPM (and every ASU 2016-18 adopter) migrated to; charts render trailing gaps as silent line-termination | All large banks/insurers (BAC confirmed, break offset to FY2019); extends to non-financials using the restricted tag as their headline | **P0 data + P1 charts** |

**The systemic pattern.** All four failures share one theme: **financial-sector filers are structurally different** — multiple listed share classes, enormous filing volume (structured notes), component-based revenue (NII + noninterest income), bank-specific XBRL tagging, unclassified balance sheets — and no test, eval, or manual pass ever exercised a bank end-to-end. JPM is not an unlucky company; it is the canary for the entire financial sector, which for an SEC-analysis product is a top-tier customer segment. The remediation plan therefore pairs every fix with a machine-checked guardrail and a detection query (repo rule 12), and adds a bank to every relevant gate.

---

# Part 1 — Investigation summary

## 1. Duplicate search results & wrong ticker (JPM-PM)

### Root cause — two coupled defects in one endpoint (CONFIRMED, reproduced by live simulation)

**RC-1 — duplicates.** SEC's `company_tickers.json` carries one entry per listed security. For CIK 19617 it has **9 entries** (live fetch 2026-07-07, file order): `JPM` (index 11), `JPM-PC` (7476), `VYLD` (8755), `AMJB` (8756), `JPM-PD`, `JPM-PJ`, `JPM-PK`, `JPM-PL`, `JPM-PM` (8757–8761). `_local_search` (`backend/app/services/edgar/compat.py:149-161`) returns all matches as separate results, and the search handler (`backend/app/routers/companies.py:184-254`) collapses them to **one** DB object by CIK but then **appends that same object to the response once per entry** (`companies.py:228-229`) — 9 identical rows for "jpm". The screenshot shows ~6 because the dropdown viewport clips at `max-h-96` (`frontend/features/companies/components/CompanySearch.tsx:254`).

**RC-2 — wrong ticker.** Inside the same loop, each entry mutates the row in place (`companies.py:215-217`); the whole batch is committed once after the loop (`:231-233`). Because every matching entry's mutation lands before that single commit, the row persists with the *last* entry's ticker:

```python
if ticker and company.ticker != ticker:
    company.ticker = ticker          # JPM → JPM-PC → … → JPM-PM (last file entry wins)
```

There is **no primary-ticker selection logic anywhere in the codebase**. The persisted ticker is whatever SEC file-order iteration writes last; preferreds cluster at high indices, so a non-common class systematically wins.

**Why this is worse than a wrong label.** `companies.cik` is UNIQUE (`backend/app/models/__init__.py:155`) so there is only one JPMorgan row and no data fragmentation — but `ticker` is the **operational key** everywhere downstream:

- **Stock quotes:** `companies.py:238` → `_get_stock_quote_with_timeout(company.ticker)` → Yahoo chart API (`companies.py:320`). With `JPM-PM` stored, the site displays the **preferred share's $17.29** as JPMorgan's price (common ≈ $300). A wrong price on the homepage of a financial product.
- **URLs:** `/company/{ticker}` routes and the sitemap (`backend/app/routers/sitemap.py:44-46`) — `/company/JPM-PM` is published to search engines.
- **Exports:** multi-period XLSX/PDF filenames (`backend/app/routers/analysis.py:216`, `:394`) — hence `JPM-PM_FY2016-FY2025_annual-metrics.xlsx` — and the workbook Overview sheet.
- **Peers, precompute:** keyed by ticker (`backend/app/services/peers_service.py:50`, `backend/app/services/precompute_service.py:77`).

### Related latent defects (same code path)

1. **`/search` can 500 on first contact with a multi-ticker issuer:** for a company not yet in the DB, the loop creates **multiple `Company` rows with the same CIK** in one flush → unique-constraint violation → generic except → HTTP 500 (`companies.py:201-233`).
2. **Once the ticker is overwritten, `/company/JPM` breaks:** the ticker lookup misses (`companies.py:404`), the handler blindly re-inserts `Company(cik=…, ticker="JPM")`, hits the unique CIK, and 500s. Same pattern at `backend/app/routers/filings.py:157-179` and `precompute_service.py:80-101`. Of the 5 company-upsert sites, only `earnings_alert_service.py:85-96` guards `IntegrityError` (SAVEPOINT + re-query — the correct pattern).
3. **`exchange` is hardcoded `None`** (`compat.py:146`) — no share-class filtering is even possible today; **names are ALL-CAPS** verbatim from the SEC file; duplicate React keys (`key={company.id}` repeated) in the dropdown.

### Blast radius — systemic across multi-ticker issuers

Live analysis of `company_tickers.json` (2026-07-07): 10,407 entries, 8,002 distinct CIKs, **1,471 CIKs (18.4%) with >1 ticker** (max 27). Because a common ticker is a substring of its preferred tickers (`"jpm" in "jpm-pc"`), searching any issuer's own common ticker **guarantees** the corruption for that issuer. Verified last-write-wins outcomes: BAC→**BAC-PS** (17 classes), WFC→**WFC-PZ**, GOOGL→**GOOGN**, BRK-B→**BRK-A**, JPM→**JPM-PM**. Effectively every large US bank — the core audience for this product — shows a preferred-share ticker and price after one search.

## 2. Filing history capped at ~4 filings

### Verdict: an INGESTION cap, confirmed to the day

The filings list is populated **only** from SEC's "recent submissions window" — `edgar_company.get_filings(form=…, amendments=…, trigger_full_load=False)` (`backend/app/services/edgar/client.py:423-427`), landed 2026-07-07 in the filing-load performance fix (PR #579 / `docs/perf-and-scaling-audit.md` QW1+QW2). SEC's recent block holds the greater of ~1,000 filings or ~1 year. **JPM's recent block (live fetch): 25,421 filings spanning 2025-07-03 → 2026-07-07** — JPM is a massive structured-note issuer (22,069 × 424B2, 1,757 × FWP, 1,145 × 424B3) — and within it exactly **one 10-K (2026-02-13) and three 10-Qs (2026-05-01, 2025-11-04, 2025-08-05)**: precisely the four filings on the company page, to the day. The prior 10-Q (May 2025) sits in the first older shard, just outside the window. EDGAR holds ~161,907 JPM filings across 30+ years; the app can reach 4.

No numeric literal produces "4": the app's own caps — `CACHED_FILINGS_LIMIT = 20` (`backend/app/routers/filings.py:22`) warm-path, `RECENT_FILINGS_MATERIALIZE_CAP = 50` (`client.py:59`) — never bind for JPM because only 4 rows ever exist. The full-history fallback exists but is **gated `limit is not None`** (`client.py:446`); the filings-list path passes `limit=None`, so it never fires — the code comment says list callers "rely on DB-first serving for deep history," but for a mega-filer that deep history **was never fetched in the first place**. No job backfills the `Filing` table (the filing-scan cron fetches the same recent window, watched companies only, `filing_scan_service.py:34,40`).

Notably, the perf audit **anticipated exactly this** and proposed the stronger fix — "page backward through the additional files only until N matches are found" (`docs/perf-and-scaling-audit.md:241-245`) — but the explicitly-labelled "weaker" alternative is what shipped.

### No escape hatch exists

- The endpoint has **no pagination/year/date params** — signature is `(ticker, background, filing_types)` only (`filings.py:140-146`); the frontend passes nothing and renders whatever comes back (chips and year groups are derived from the returned 4 rows).
- Filing detail pages resolve **by integer DB id only** (`filings.py:343-352`); an un-ingested 2019 10-K has no id → unreachable, unsummarizable.
- Full-text search (EFTS, indexed since 2001) can *find* old filings but links **out to sec.gov** (`FullTextSearchResults` renders `hit.document_url` external) — no path creates a Filing row from a hit.

### Blast radius & related defects

Systemic mechanism, severity graded by filing volume: mega-filer banks/broker-dealers (JPM, MS, GS, C, BAC, WFC) → ~4 reports; ordinary filers → recent window spans many years but the **20-shown/50-stored display caps** still bind (~5 years max). Related defects: **year grouping uses `filing_date`, not fiscal year** — JPM's FY2025 10-K is bucketed under "2026" (`frontend/app/company/[ticker]/page-client.tsx:164-165`); **10-K/A / 10-Q/A amendments are silently dropped** (`compat.py:239-240` forces `include_amended=False`); a filer whose latest report predates the window gets a **permanently empty panel** (the `==0` fallback is limit-gated); warm-vs-cold count drift (20 vs 50).

## 3. Single-filing AI summary — partial, ungrounded badge, artifacts

Four **independent** root causes. Critically, none is an XBRL fetch failure — XBRL extraction *succeeded* for this filing.

### 3A. The "not grounded" badge is a FALSE NEGATIVE from a bank-blind check

The badge text is `quality.reasons[0]` rendered by `SummaryDisplay.tsx:157-166`; the verdict comes from `assess_quality` (`backend/app/services/summary_generation_service.py:180-204`):

```python
for key in ("revenue", "net_income"):
    ...
    checks.append(_xbrl_value_appears(float(value), haystack))
```

It demands the XBRL **`revenue`** and `net_income` values appear literally in the summary text. But for banks, the pipeline's own grounding NOTE (`backend/app/services/ai/xbrl_narrative.py:122-127`) instructs the model that "there is NO single revenue line here … do NOT sum them into, or invent, a single 'Revenue' number" — report NII and noninterest income separately. JPM's summary correctly shows NII $95.4B + noninterest income $87.0B and never the string "182.4" → `checks = [False, True]` → `tier="partial"` with exactly the observed reason string. **The pipeline forbids the number, then penalizes its absence.** The badge only fires when `xbrl_metrics` is truthy (any XBRL failure sets it `None` and skips the check, `summary_pipeline.py:529-536`) — so the badge is proof XBRL succeeded. Every figure in the JPM summary is correct; the flag is wrong. **Affects every bank, systematically.**

### 3B. Excerpt truncation drops segments, cash flow, balance-sheet detail

What reaches the model is capped by `_SECTION_LAYOUT` (`backend/app/services/ai/extraction.py:419-437`): 10-K → Item 8 **70,000 chars**, Item 7 **55,000**, Item 1A **45,000** (total excerpt ≤320k). A bank 10-K's Item 8 alone runs to several hundred KB; the segment note (CCB/CIB/CB/AWM/Corporate), the full cash-flow statement, and balance-sheet line detail sit **past the cap**, while MD&A headline numbers (which lead Item 7) fit inside it. That is precisely the observed output: headline figures present; "Not disclosed in provided excerpts" for CCB/CIB revenue, cash, debt breakdown, working capital. The code even names JPM in a comment (`extraction.py:449-452`) — but its dense-window backfill triggers only on *thin* sections, not *truncated-full* ones. The already-approved report-quality plan (`docs/report-quality-improvement-plan.md`, 2026-06-14) scoped this exact fix as Phase-1 **A7/A8** — never built (only Phase-0 honest-labeling shipped, which is why the gaps are now labelled instead of papered over). Related: `_recover_missing_sections` only re-asks for **fully empty** sections (`section_recovery.py:26-57`), so the partially-filled segment table (AWM/Corporate present) is never recovered. **Affects all large filings — banks and mega-caps worst.**

### 3C. A non-bank industrial checklist forces fabrication

`backend/prompts/10k-analyst-agent.md:106` requires "capital expenditures and free cash flow (operating cash flow − capex). **When free cash flow runs well below net income, name the reason (capex intensity, working-capital build)**"; `:111` demands current assets/liabilities/working capital/current ratio. There is **no bank variant** of any prompt. For a bank — no classified balance sheet, immaterial capex, OCF driven by trading flows — this checklist produced the summary's flatly false claim: *"free cash flow was negative due to high capex and working capital changes."* JPM's OCF was −$147.8B because of trading-asset flows; capex is irrelevant. This is the exact fabrication mode already documented in `lessons/arch-no-precomputed-deltas-in-grounding.md` (salient delta + "name the reason" directive = the model invents a driver) — still live in the prompt. **Affects all financials, and it is the worst trust failure in this incident: a confident, wrong causal claim.**

### 3D. The "X.; Y" join artifact — a web-only render bug

The web page renders `business_overview`, built by `_build_structured_markdown` → `markdown_render.py`, which joins list fields with `"; "`: key_points at `:58` (into one Executive Summary paragraph, `:61`), and Profitability/Cash flow/Balance sheet bullets at `:106/:109/:112` — plus **four more sites**: management themes/capital allocation (`:143/:146`) and outlook drivers/watch items (`:178/:180`). Model bullets end with "." → "…$87.0B**.;** Total assets grew…". The PDF export uses a different serializer (`summary_sections.py`) that renders true bullets — which is why the exported PDF looks clean while the web page shows the artifact. **Universal: every web-rendered summary.**

### Why CI never caught any of this — the eval blind spot

The golden set **does** include JPM (`backend/evals/golden_set.json:169-216`, noted "financial issuer (different statement structure)") — but: evals never run `assess_quality` (badge is product-only); they score the structured JSON payload, never the rendered `business_overview` markdown (the `.;` artifact is invisible, `evals/scorers.py:390-402`); and the bank-revenue gate `score_bank_revenue_integrity` (`scorers.py:342,379-382`) activates only when ground truth carries NII/non-II components — **JPM's entry has none**, so the gate is inert. Worse, JPM's ground truth expects a single `revenue=182447000000` that the product prompt forbids the model from emitting: the eval's expectation contradicts the product's instruction.

## 4. Multi-period analysis — the vanishing cash series & chart presentation

### Root cause: a concept registry that predates ASU 2016-18 (CONFIRMED code + EDGAR)

The multi-period grid is a pure `financial_fact` read (`trend_analysis_service.py:286-295`); rows are written by concept registries. The cash registry (`backend/app/services/facts_service.py:996-1000`):

```python
"cash_and_equivalents": (
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsAndShortTermInvestments",
    "Cash",
),
```

is missing **`CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents`** — the tag ASU 2016-18 adopters migrated to. EDGAR companyconcept ground truth for JPM (annual, USD, $B):

| FY end | CashAndCashEquivalentsAtCarryingValue | CashCashEquivalents**RestrictedCash**AndRestrictedCashEquivalents |
|---|---|---|
| 2016 | **391.2** | 391.2 |
| 2017 | **431.3** | 431.3 |
| 2018 | **278.8** ← last year JPM tagged this concept | 278.8 |
| 2019 | — | **263.6** |
| 2020 | — | **527.6** |
| 2021 | — | **740.8** |
| 2022 | — | **567.2** |
| 2023 | — | **624.2** |
| 2024 | — | **469.3** |
| 2025 | — | **343.3** |

The FY2016–18 product values match the legacy tag **exactly**; JPM's real FY2019–25 cash lives entirely under the missing tag. The same gap exists in all three write-path registries (`facts_service.py:996-1000`, `edgar/instance_extractor.py:99-104`, `edgar/xbrl_service.py:729-734`). The irony: the registry's own header comment (`facts_service.py:951-954`) documents the merge-across-tags design *specifically so that* "a filer that migrated tags … keeps its full history" — and revenue got exactly this bank-aware treatment after the MCB bug (FI component tags + `_FI_SKIPPED_CONCEPTS`, `:985-992,1012`). Cash never did.

**The fix merges cleanly:** the restricted-cash tag *restates FY2016–18 with identical values*, and ingestion is "first tag with data wins per period" (`facts_service.py:1034-1036`, `setdefault` at `:1099`) — so appending the new tag last fills FY2019+ without touching FY2016–18.

### Blast radius — sector-wide, filer-specific cutover year

Bank of America (CIK 0000070858, EDGAR-verified): legacy tag ends **FY2019**, restricted-cash tag carries FY2020+ (380.5/348.2/230.2/333.1/290.1/231.8 $B) — same break, one year later. Every large bank/insurer that adopted ASU 2016-18 is affected, with a filer-specific last-good year; exposure extends to non-financial filers that use the restricted-cash tag as their headline cash line. Related structural gaps for banks: `gross_profit`, `current_assets`/`current_liabilities`/`working_capital` are single-concept mappings banks never tag (panels collapse silently); `total_liabilities` is not ingested or displayed **for anyone** (absent from `COMPANYFACTS_INSTANT_TAGS` and `DATASET_CONCEPT_ORDER`; separately, the pinned known bug that `_parse_company_facts` never fills its cash/liabilities buckets, `tasks/architecture-refactor-plan.md:87-90`, sits on the single-filing fallback path — related, but not this cause).

A subtle export defect compounds it: the XLSX "Window growth" column silently computes cash CAGR over the truncated FY2016..FY2018 window — a wrong-window growth number presented alongside full-window metrics.

### Chart-presentation defects (`frontend/features/analysis/components/TrendCharts.tsx`)

- **Missing data renders as silent line-termination:** every `<Line>` sets `connectNulls` (`:389`), which bridges only *interior* gaps — trailing nulls (FY2019–25) have no later anchor, so the stroke just stops at FY2018 with no gap marker or "not reported" state. A data gap is indistinguishable from a broken chart.
- **Hardcoded axis pairing:** the Balance-sheet panel pins `rightAxis: ['shareholders_equity']` (`:452-459`), leaving debt+cash on the left; with no `domain` config on either axis (`ui/Chart.tsx:170-178`), the two scales are unrelated auto-fits.
- **The Cash-generation panel is single-axis** (`:439-447`): OCF's ±$150B swings set the shared domain and flatten the $57B net-income line into noise.

## 5. EdgarTools guidance cross-check (founder-requested)

Reviewed: common-pitfalls, choosing-the-right-api, performance, customizing-standardization, and Company API doc pages, plus the library's actual `concept_mappings.json` (GitHub main) and the repo's own `backend/docs/edgartools-best-practices.md` (v5.40.x review).

- **The cash gap would NOT have been prevented by following EdgarTools.** Its own "Cash and Cash Equivalents" standardization maps only `(CashEquivalentsAtCarryingValue, Cash, CashAndCashEquivalentsAtCarryingValue, CashCashEquivalentsAndShortTermInvestments)` — no restricted-cash balance tag, no `CashAndDueFromBanks`; its "Revenue" mapping has no FI components. The library **shares both blind spots** this repo has hit (consistent with the earlier MCB finding). Owning the concept registries remains the right call; contributing the restricted-cash tag upstream is a nice-to-have.
- **The ticker fix aligns with library semantics:** EdgarTools' Company API exposes `get_ticker()` (primary) vs `.tickers` (all classes) and treats CIK as the stable identifier — exactly the primary-ticker-per-CIK model P0-1 introduces.
- **Filing history:** the docs' "full history in a single submissions request" claim under-states mega-filer reality (the repo measured 44 shards / 25–45MB for MS; JPM has 68 shards ≈ 680MB). `get_filings(year=…)` exists but forces the full load. The EFTS-based enumeration in P1-6 is decisively cheaper. `enable_local_storage()` is worth remembering if a bulk local backfill is ever needed.
- **Pitfalls-page hygiene items** (null-checks before ratios, section-existence checks, `head()`/lazy slicing, values-in-actual-dollars) are already adopted in the codebase or reinforce the planned fixes; nothing on the page contradicts this plan.
- **Operational note surfaced by the repo's own best-practices doc:** the bank statement-financials path is gated by `USE_STATEMENT_FINANCIALS` (default `False`, `config.py:355`) and its rollout runbook requires a **`Company.sic` backfill first** (SIC was NULL in prod when written). Whether prod has flag+backfill applied is unverified from the repo — carried in Assumptions; the P0 fixes below are correct in either state.

---

# Part 2 — Remediation plan

Ordered by **user-trust impact × beta imminence**. Every fix: $0/month new infra (existing Cloud Run service, internal job endpoints, Cloud Scheduler; marginal costs are SEC request budget and ~$0.15–0.30 per eval run). Effort: **S** ≤1d · **M** ≤1wk · **L** >1wk. Each fix carries a machine-checked guardrail (repo rule 12) and a detection method for finding other affected companies.

**Hard sequencing constraints** (violating these re-corrupts data):
1. The ticker **repair script runs only AFTER the search-fix deploy** — otherwise the next `/search` re-corrupts repaired rows.
2. The prod facts **resync runs only AFTER the registry-change deploy** — the job executes inside the deployed service.
3. The **only eval-baseline re-pin happens in P0-4** (P0-2's badge/join fixes are not eval-scored; ship P0-2 first so re-pins never conflict).

## P0 — land before beta (≈4.5–6 focused days total)

### P0-1 · Ticker integrity — Effort M (1.5–2d) · Trust impact: CRITICAL (wrong stock prices)

**Approach:**
- **Search fix** (`routers/companies.py:194-233`): dedupe the loop by CIK (skip seen CIKs); **never** assign `company.ticker` from a per-entry `sec_data`; new rows get `primary_ticker_for_cik(cik)`; existing rows update ticker only *to* the canonical primary (permits real renames, forbids preferred-downgrades); wrap flush/commit in `begin_nested()` + `IntegrityError` re-query (race guard).
- **New helper** `primary_ticker_for_cik(cik)` on the compat service: first file-order entry per CIK from the already-cached tickers dict (`compat.py:41-104` — Python dicts preserve the file's insertion order, and `_local_search` already iterates it). **Heuristic live-verified across all 1,471 multi-ticker CIKs:** first-entry is the common listing for every checked issuer (JPM, BAC, WFC, C, MS, GS, SCHW, MET; Alphabet→GOOGL; Berkshire→BRK-B). Exactly **3 edge cases** exist (BH-A dual-class; ICR-PA/ATH-PA — issuers with *no* listed common), all defensible. Do **not** use shortest-ticker (breaks GOOGL→GOOG) or `company_tickers_exchange.json` (exchange can't distinguish preferreds).
- **Miss-path hardening** at the three blind-insert sites (`companies.py:406-430`, `filings.py:157-179`, `precompute_service.py:80-101`): on ticker-miss → resolve CIK → **query by CIK first, reuse the row if found (no insert)**; only insert when the CIK is genuinely new, with the SAVEPOINT pattern from `earnings_alert_service.py:85-96`. This also makes stale bookmarked `/company/JPM-PM` URLs resolve to the canonical row — **no redirect table needed**; the frontend then `router.replace`s to the canonical ticker and the sitemap self-heals on next render.
- **Repair script** `backend/scripts/repair_ticker_by_cik.py` (precedents: `fix_null_sec_urls.py`): fetch the tickers file once through the edgar layer, compute primary per CIK, `--dry-run` default (prints old→new, not-in-file rows, collisions), `--apply` to write. Match CIKs in both zero-padded and stripped forms (`compat.py` pads to 10; `earnings_alert_service.py:84` stores unpadded). Run **after** deploy.

**Risk + mitigation:** repair-before-fix re-corruption → enforced deploy order (constraint 1). Concurrent search races → SAVEPOINT. Delisted tickers not in the file → left unchanged, listed in dry-run report.
**Guardrail:** pytest with a multi-ticker fixture (JPM + 8 share classes, BRK, GOOGL): search returns exactly 1 row per CIK bearing the primary ticker; one DB row; repeat search does not mutate; `/company/JPM-PM` resolves to the JPM row without inserting; the IntegrityError path returns 200, never 500.
**Detection:** weekly diff of `companies.ticker` vs primary-per-CIK from the SEC file (1 cached request); alert on any mismatch (folds into P1-9).

### P0-2 · Summary quick fixes: badge false-negative + join artifact — Effort S (0.5–1d) · Trust impact: HIGH

**Approach:**
- **(D)** Replace all **8** `"; ".join` sites in `markdown_render.py` (`:58, :106, :109, :112, :143, :146, :178, :180`) with real `- ` markdown bullet lines — restoring parity with the PDF serializer (`summary_sections.py`), which already bullets the same data.
- **(A)** Extract a shared predicate `fi_components_present(xbrl_metrics)` used by **all three** of: the bank NOTE emitter (`xbrl_narrative.py:122`), `bank_guards.py:16-32`, and `assess_quality` — so the instruction and the checker can never drift again. In `assess_quality`, for the `revenue` check only: when FI components are present, accept `revenue-literal-grounded OR (NII grounded AND noninterest-income grounded)`. `net_income` check unchanged; non-bank behavior byte-identical.
- **No eval re-pin:** neither surface is eval-scored (`assess_quality` never runs in evals; scorers read payload fields, not rendered markdown). CI's eval job runs on the path filter and must pass with zero delta.

**Masking risk (A):** none in practice — today the badge fires on **100% of banks** (pure false-positive → users learn to ignore it → zero effective sensitivity). After the fix it fires exactly when neither the total nor both components ground.
**Guardrail:** deterministic pytest asserting rendered markdown from "."-terminated bullets contains no `".;"` anywhere (regex over full output — covers all 8 sites); `assess_quality` unit tests (bank-with-components → full; bank missing a component → partial; non-bank unchanged); an import test asserting all three modules use the single shared FI predicate.
**Detection:** log counter on `tier=partial` reason strings bucketed by SIC; a bank-heavy spike after any prompt change is the recurrence signal.

### P0-3 · Cash concept registry + prod resync — Effort S (0.5–1d incl. resync) · Trust impact: HIGH (7 missing years on every big bank's flagship Pro chart)

**Approach & rollout (exact steps):**
1. Append `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents` **last** in the three registries (`facts_service.py:996-1000`, `instance_extractor.py:99-104`, `xbrl_service.py:729-734`). Appending last is provably safe *for the confirmed-affected class*: per-period first-tag-wins (`setdefault`, `facts_service.py:1099`) keeps FY2016–18 on the legacy tag's identical values (no row churn, no `is_latest` demotions); FY2019+ fill as brand-new rows.

   **Cross-company consistency caveat (raised in review — real, and deliberately not "solved" by tag order).** Appending last means the legacy tag wins for any *overlap* period where a filer reports **both** tags. The two tags are different quantities: `CashAndCashEquivalentsAtCarryingValue` (ACV) *excludes* restricted cash; the restricted-cash tag is the ASU 2016-18 total that *includes* it. For JPM and banks whose two tags coincide in the overlap years (EDGAR-verified: JPM FY2016–18 identical), there is no discontinuity. But a filer with **material** restricted cash that reports both tags early and later migrates to reporting **only** the restricted-cash total would show a series that steps up by the restricted-cash amount at the migration boundary — two definitions mixed within one series. **Flipping the order (restricted-cash first) does not fix this**: it inverts which side is "wrong", redefines the `cash_and_equivalents` metric to *include* restricted cash (semantically off for a field named "cash & equivalents"), and churns already-ingested rows. The correct general fix is a **per-series single-definition rule** — pick, per company, the one tag with the widest year coverage and use it for every year, or normalize the total to unrestricted by subtracting tagged restricted cash — which is more than a P0 registry append. **Decision:** ship append-last now (provably correct for the confirmed banks, zero-churn), and add the mixed-definition detection query below so the affected population is *sized* before deciding whether the per-series rule is worth building (parked P2 pending that count).
   - **Mixed-definition detection** (run after the resync; drives the P2 go/no-go): flag any company whose `cash_and_equivalents` series switches source tag mid-window (`raw_tag` changes between adjacent FY rows) **with** a >5% value discontinuity at the switch. `financial_fact.raw_tag` is persisted for exactly this ("record the winning tag so a concept that flips between filings can be detected", `backend/docs/edgartools-best-practices.md`). A near-zero count confirms append-last is sufficient in practice; a large count justifies the per-series rule.
2. Deploy (migration-free — no schema change).
3. Find affected companies (run before and after):
```sql
SELECT c.id, c.ticker,
       MAX(ff.fiscal_year) FILTER (WHERE ff.concept = 'cash_and_equivalents') AS last_cash_fy,
       MAX(ff.fiscal_year) FILTER (WHERE ff.concept = 'total_assets')         AS last_assets_fy
FROM financial_fact ff JOIN companies c ON c.id = ff.company_id
WHERE ff.is_latest AND ff.fiscal_period = 'FY'
  AND ff.concept IN ('cash_and_equivalents','total_assets')
GROUP BY c.id, c.ticker
HAVING MAX(ff.fiscal_year) FILTER (WHERE ff.concept = 'total_assets')
     - COALESCE(MAX(ff.fiscal_year) FILTER (WHERE ff.concept = 'cash_and_equivalents'), 0) >= 2;
```
4. Force resync for the affected list: `POST /internal/jobs/sync-companyfacts {"tickers":[…], "force":true}` (`internal.py:205-214` → `ingest_companyfacts(force=True)`, bypassing the 24h TTL). **Not** `backfill-facts` (it re-derives from stored filings — wrong lever). Cost: exactly **1 SEC companyfacts request per company**, serial through the shared limiter — even 500 companies is minutes.
5. Verify: detection SQL returns empty; JPM/BAC show FY2019–25 (263.6→343.3B / 380.5→231.8B); cached trend narratives auto-invalidate (`dataset_fingerprint` mismatch, `trend_analysis_service.py:1190-1198`) and regenerate on next view.

**Deliberately NOT in this fix:** summing `CashAndDueFromBanks` + `InterestBearingDepositsInBanks` as a component fallback (different semantics, cross-tag alignment and double-count risk; the verified failure class is fully covered by the one tag — parked P2, gated on the weekly coverage report). Do **not** touch `test_companyfacts_fixture.py:115-121` — it pins `_parse_company_facts`, a different path (owner: P1-7); no existing test pins the registry, so nothing breaks.
**Guardrail:** registry-consistency pytest (the ASU 2016-18 tag present in all three registries, appended after legacy tags) + a recorded-fixture test for `normalize_companyfacts` with a JPM-shaped payload (legacy tag FY16–18 + new tag FY16–25) asserting FY16–18 keep legacy values and FY19+ resolve from the new tag.
**Detection:** the coverage-gap SQL above, generalized per concept (folds into P1-9).

### P0-4 · Bank prompt carve-out — Effort M, timeboxed to 1 day of eval iteration · Trust impact: CRITICAL (stops fabricated causal claims)

**Approach — one eval-gated PR:**
- **(a) Defuse the fabrication trap for everyone:** edit `10k-analyst-agent.md:106` → name the FCF reason "**only as management states it; otherwise report the figures without a cause**" (this also resolves its direct contradiction with `:100`, which already bans unsupported filler); qualify `:111` with "where the company reports a classified balance sheet". Mirror in the 10-Q/structured variants where the same lines appear.
- **(b) Runtime FI addendum** injected beside the existing XBRL grounding block, gated on the shared `fi_components_present` predicate from P0-2: skip working-capital/current-ratio/capex-FCF checklist items; instead require NII, noninterest income, efficiency, provision/allowance for credit losses, capital ratios, and deposit/loan trends as disclosed. (Inline conditional, **not** a separate prompt file — the loader maps by filing type only, `prompt_loader.py:19-37`, and a SIC-routed file set means touching the loader + 4 files days before beta.)
- **(c) Golden-set activation:** add EDGAR-verified `net_interest_income`/`noninterest_income` to JPM's `golden_set.json` ground truth — this **activates hard gate G5** (`score_bank_revenue_integrity`) for JPM permanently. Activating G5 in the same PR that enforces components is safe; activating it earlier gambles on the current prompt.
- **(d)** Full-set eval `--runs 3` + `scripts/pin_baseline.py` re-pinning `baseline_scores.json` **in the same PR** (per `lessons/ops-eval-gate-for-ai-changes.md`).

**Risk + mitigation:** G5 raises `gate_fail_rate` if a run drops a component → iterate within the timebox; **pre-agreed fallback:** land (a) alone now (small delta, still eval-gated), defer (b)+(c) one week.
**Guardrail:** G5 itself, permanently active for JPM; plus the eval regression gate.

### P0-5 · Filing-history honest note — Effort S (2–4h) · Trust impact: HIGH per dollar (cheapest honesty win available)

Filings panel note: *"Showing filings since {oldest filing_date}. Full history on SEC EDGAR →"* linking `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K&dateb=&owner=include&count=40` (company `cik` is already in the response; zero API budget). Copy per `DESIGN_SYSTEM.md`. Remains permanently for the pre-2001 tail after P1-6.

## P1 — first two weeks after beta

### P1-6 · Historical filings backfill + year/form filters — Effort M · Trust: HIGH

**Approach:** a `filing_history_service` on the **existing EFTS integration** (`app/integrations/sec_api.py`) — enumerate a company's 10-K/10-Q since 2001 by CIK+forms with **date-windowed** requests (~8–10-year windows; live-verified: query-less form+cik+dates requests return all hits in one page — 78 JPM 10-Qs in one response — but `size` is unsupported and `from>0` is client-rejected for query-less searches, so windowing replaces pagination). **~2–6 requests per company** vs ~68 shard fetches / ~680MB for JPM via the submissions files. Requirements from live probes: a bounded **3-attempt 5xx retry** (EFTS 500s intermittently; `_is_rate_limit_error` only retries 429s, `sec_rate_limiter.py:180-192`); map `file_type` via `FilingType.from_string(strict=False)`; EFTS `_id` = `{dashed-accession}:{primary-doc}` → both `sec_url`/`document_url` NOT NULL constraints and the URL-format rule are satisfiable via the integration's existing `_build_urls`; insert with per-row SAVEPOINT (accession is unique — dedupes against existing rows).
**Trigger:** new internal job `POST /internal/jobs/backfill-filing-history {tickers|watchlist_only, limit}` (clone the sync-companyfacts shape, `internal.py:174-214`), seeded on watchlist + most-visited; plus an on-visit background enqueue guarded by a `history_backfilled_at` additive nullable column (one idempotent SQL file + `ensure_additive_columns` — compliant with the no-Alembic regime). Bounds: serial through `sec_rate_limiter`, ~10 requests/company cap, ~50 companies/run cap, stamp prevents re-runs.
**Surface:** add `limit` param to `GET /api/filings/company/{ticker}` (JPM's full 10-K/10-Q history is only ~130 rows); "Show full history" load-more + year filter UI; **fiscal-year grouping via the already-returned `report_date`** (fixes the FY2025-10-K-under-"2026" defect) with `filing_date` fallback. Detail pages and summaries then work unchanged through the existing DB-id flow (old filings' XBRL is handled by the accession-aware extractor). Pre-2001 stays external-linked (acceptable: pre-XBRL, so summaries couldn't be grounded anyway).
**Guardrail:** pytest with `httpx.MockTransport` (the integration's built-in seam) asserting NOT-NULL URLs, dashed-accession dedupe, /A handling, and the per-company request cap. **Detection:** filing-count anomaly query (companies whose `financial_fact` FY span ≥5 years but ≤2 stored 10-K rows).

### P1-7 · Excerpt/truncation lift (3B) — Effort L (already scoped & approved)

Execute the June-2026 report-quality plan's Phase-1 **A7/A8** (robust, segment-aware section extraction; XBRL standardized metrics 4→~12) against `_SECTION_LAYOUT` (`extraction.py:419-437`). Eval-gated; re-pin expected. This work item also owns: the `_parse_company_facts` cash/liabilities gap (update its characterization test then), banks' structurally-blank current/working-capital metrics, and evaluating the `USE_STATEMENT_FINANCIALS` flip per the rollout runbook in `backend/docs/edgartools-best-practices.md` (SIC backfill first).

### P1-8 · Chart missing-data & axis fixes — Effort S–M

`TrendCharts.tsx`: (i) explicit **"not reported after FY{n}"** state for any series whose last point precedes the dataset's final period (trailing nulls currently just end the stroke — `connectNulls` can't bridge them); rendered as a legend/footnote annotation per design system §10; (ii) `rightAxis: ['net_income']` on the Cash-generation panel (`:439-447`) using the dual-axis machinery the Balance-sheet panel already has; (iii) axis-domain sanity pass on dual-axis panels. Ship **after** P0-3's resync so annotations reflect repaired data. **Guardrail:** component test asserting the gap annotation renders for a series ending ≥2 periods early.

### P1-9 · Detection & recurrence umbrella — Effort S

Weekly data-quality report (existing Cloud Run job pattern or an internal-token endpoint; email via the existing resend service — zero new infra): (a) `companies.ticker` vs primary-per-CIK diffs; (b) per-concept coverage gaps (the P0-3 SQL generalized over `total_assets`/`cash_and_equivalents`/`shareholders_equity`/`operating_cash_flow`); (c) filing-count anomalies; (d) `tier=partial` reason counts by SIC bucket. This is the rule-12 "never again" gate for the whole incident **class**, not just these four instances.

## P2 — parked (explicitly, so they don't evaporate)

`ticker_aliases` table (only if a real ticker rename ever 404s — compatible with the no-Alembic regime via `CREATE TABLE IF NOT EXISTS`); bank cash component-sum fallback (gated on P1-9 evidence of residual gaps); pre-2001 history hybrid via edgartools full-load for small filers; `total_liabilities` ingestion + display; upstream EdgarTools PR adding the restricted-cash tag to `concept_mappings.json`.

## Suggested week sequence (solo founder, agentic tooling)

- **Day 1:** interim safeguards 1+2 deployed (below); P0-2 PR (badge + joins).
- **Day 2:** P0-1 search fix + repair script PR; deploy; run repair (`--dry-run` → `--apply`); verify quotes/sitemap.
- **Day 3:** P0-3 registry PR; deploy; detection SQL; force resync; verify JPM/BAC charts.
- **Days 3–4:** P0-4 prompt PR + eval runs (timeboxed; fallback ready).
- **Day 4:** P0-5 note.
- **Day 5:** buffer — eval iteration, manual detection pass, beta checklist.

---

# Part 3 — Interim safeguards (beta week, each ≤1 day)

1. **Day-1 hotfix slice of P0-1:** CIK-fallback + SAVEPOINT at the three miss-path inserts only. Stops the live `/company/{ticker}` and `/filings/company/{ticker}` 500s for already-corrupted rows **immediately**, before the search fix and repair land.
2. **IntegrityError alerting:** structured log line (`company_upsert_conflict`, cik, path) at the three insert sites + a Cloud Run log-based alert. Makes any recurrence visible in minutes.
3. **P0-5's honest filings note ships regardless** of everything else — it converts a silent data gap into stated scope.
4. **Manual detection runbook:** run the ticker-diff script and the three detection SQLs by hand **now**, and again the day after beta opens (~1 hour; automation is P1-9).
5. **Badge de-escalation stopgap** (only if P0-2A slips): when `fi_components_present` and the *sole* partial reason is the grounding string, render neutral "Partial coverage" wording without the "not grounded in SEC XBRL data" accusation — one conditional in the badge renderer.
6. **Chart gap stopgap** (only if P1-8 slips): static footnote on the Balance-sheet panel whenever any series' last period < the dataset's last period — "Some series are not reported for recent years — see the Metrics table." (~2 hours.)
7. **Post-repair hygiene checklist:** deploy restarts clear the in-process quote cache; eyeball the sitemap after the ticker repair; spot-check one bank (BAC) end-to-end (search → company page → summary badge → multi-period chart → XLSX filename).

**What NOT to gate:** the multi-period analysis itself (its figures are correct — the cash series is *missing*, not wrong, and P0-3 fixes it before beta) and single-filing summaries in general (the figures shown are accurate; the failures are omissions and labelling, which P0-2/P0-4 address and the badge honestly discloses meanwhile).

---

# Assumptions & could-not-verify

- **No production DB access.** Prevalence is quantified from SEC data + code invariants, not row counts. The stored `companies.ticker = "JPM-PM"` and NULL-vs-populated `Company.sic` are inferred (ticker: from the export filename + screenshots + the deterministic code path; live-simulated end-to-end).
- **Prod env flags unverified:** `USE_STATEMENT_FINANCIALS` (default `False`; its rollout runbook exists in `backend/docs/edgartools-best-practices.md` — status unknown) and `ENABLE_FPI_FILINGS` (CI sets `true`; a council note argued to keep it dark). Neither changes any root cause above; both are flagged where they affect remediation (P1-7).
- **The $17.29 quote** is from the screenshot; the code path (wrong ticker → Yahoo chart API) is confirmed, the live Yahoo response was not fetched.
- **Screenshot shows ~6 duplicate rows vs 9 simulated** — viewport clipping (`max-h-96`) + the file grows over time; the mechanism is confirmed.
- **Segment-note truncation offset (3B)** is inferred from the caps + output pattern ("HYPOTHESIS" grade): the caps and the model's "provided excerpts" behavior are confirmed; the exact byte offset of JPM's segment note past the 70k cap was not measured (the filing text was not re-fetched).
- **edgartools `trigger_full_load=False` window semantics** are from its docs + the exact to-the-day match of the four filings; not executed in isolation.
- **EDGAR/EFTS figures** (ticker file counts, JPM/BAC companyconcept values, submissions counts, EFTS response shapes/500s) were fetched live on 2026-07-07 and may drift.
- The four failure streams were investigated by four independent passes and cross-verified; every file:line cited in Part 1's root causes was re-read directly in this repo at HEAD (`d2def68`).
