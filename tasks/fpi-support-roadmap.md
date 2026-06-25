# Roadmap: Foreign Private Issuer (FPI) Support — Alibaba & Popular ADRs

**Status:** Awaiting approval · **Owner:** Neil · **Branch:** `claude/funny-cannon-6br4hj`
**Trigger:** Beta feedback — "there are no filings present for Alibaba ($BABA)" on `/company/BABA`.

---

## 1. Confirmed Root Cause

Alibaba **resolves fine** (it is in SEC `company_tickers.json` as CIK `1577552`), so a `Company`
row is created. The emptiness is **purely the form-type filter**: every discovery path defaults to
`["10-K","10-Q"]`, and the `FilingType` enum has no `20-F`/`6-K`/`40-F`. Alibaba is a **foreign
private issuer (FPI)** that files only **20-F** (annual) and **6-K** (interim) — never 10-K/10-Q — so
the filter returns an empty list, the page renders its empty state, and no summary can be generated.

**Evidence (file:line):**
- `backend/app/routers/filings.py:104` — `types_list = ["10-K","10-Q"]` default; `:119` passes it straight to `get_filings`.
- `backend/app/services/edgar/compat.py:249-250` — `get_filings()` defaults `filing_types = ["10-K","10-Q"]`.
- `backend/app/services/edgar/compat.py:198-203` — `get_company_submissions()` hardcodes only `FORM_10K` + `FORM_10Q`.
- `backend/app/services/edgar/compat.py:257-264` — `from_string(form, strict=True)` raises on `"20-F"`; `except ValueError: continue` **silently drops** any FPI form even if explicitly requested.
- `backend/app/services/edgar/config.py:17-47` — `FilingType` enum has no `20-F`/`6-K`/`40-F`; `:74-80` `financial_reports()` returns only 10-K/10-Q variants.
- `frontend/app/company/[ticker]/page-client.tsx:43` — `getCompanyFilings(ticker)` called with no `filing_types` (inherits backend default); `:494` renders "No filings found for this company." — exactly what the beta user saw.

The same failure hits **every popular ADR** (TSM, ASML, Toyota, Novo Nordisk, SAP, JD, PDD, BIDU, NIO, …).

> **Key correction from the investigation:** Alibaba reports under **U.S. GAAP in RMB** (with a USD
> convenience translation), **not IFRS**. So for the flagship ticker the blockers are **currency
> (RMB) + the ADS ratio (1 ADS = 8 ordinary shares post-Sep-2024) + 20-F item structure** — *not*
> IFRS. IFRS only matters for European names (ASML, Novo, SAP, etc.).

> **Tailwind, not headwind:** `edgartools` **5.39.0** (already installed) returns `20-F`/`6-K`/`40-F`
> via `get_filings(form=...)` with no allow-list, exposes dedicated `TwentyF`/`SixK`/`FortyF` objects,
> `get_financials()` falls back 10-K→20-F→40-F with IFRS-aware statement resolution, and
> `get_currency_symbol()` gives the reporting-currency symbol. This materially lowers effort.

---

## 2. Scope Boundary (what EDGAR can and cannot serve)

**Supportable via EDGAR** — sponsored FPIs that actually file:
- **20-F** annual reports (most FPIs): BABA, TSM, ASML, NVO, TM, SAP, SE, PDD, JD, BIDU, NIO, NVS, AZN, UL, RIO, BP, SHEL.
- **40-F** (Canadian MJDS filers, e.g. SHOP) — distinct wrapper; lower priority (few names).
- **6-K** interim/furnished reports.

**NOT supportable via EDGAR (the firm outer boundary):** unsponsored-ADR / Rule 12g3-2(b) names that
file **nothing substantive** with the SEC — **Tencent (TCEHY), Nestlé (NSRGY), LVMH, Roche**. EDGAR
holds only a depositary-bank **Form F-6** under a separate `/ADR` CIK — no financials, no narrative,
no XBRL. These require a non-EDGAR home-market source (HKEX/SIX/…) and will get an **honest
"not available" state** (per decision D4).

**Insider data:** Form 4 is effectively **absent** for FPIs (Rule 3a12-3(b); even after the Mar 2026
HFIA Act, broad jurisdiction exemptions still cover most major FPIs). The insiders panel must say
"not generally required for FPIs," not show a broken empty panel.

---

## 3. Popular-Ticker Coverage

| Ticker(s) | Files with SEC | Supportable? | Notes |
|---|---|---|---|
| **BABA** (Alibaba) | 20-F + 6-K (CIK 1577552, FY ends Mar 31) | **Yes** | **U.S. GAAP / RMB** + USD convenience. Blockers: currency, ADS 8:1, 20-F structure. *Not* IFRS, *not* dual-class. |
| TSM, PDD, JD, BIDU, NIO, SE | 20-F | **Yes** | Chinese/Cayman ADRs; **VIE/PRC-control** framing needed; currency varies (RMB/USD). |
| ASML, NVO, TM, SAP, NVS, AZN, UL, RIO, BP, SHEL | 20-F (IFRS) | **Yes** | Needs **IFRS taxonomy + non-USD currency** (Phase 3). |
| SHOP (Shopify) | 40-F (Canadian MJDS, IFRS/USD) | Yes (deprioritized) | Distinct wrapper (AIF + statements as exhibits); single name. |
| BIIB (Biogen) | 10-K (domestic) | Already supported | Confirms the US market is unaffected. |
| TCEHY, NSRGY, LVMH, Roche | Only depositary F-6 | **No (EDGAR)** | Honest unsupported state. **Entity-resolution trap:** don't bind TCEHY → TME (Tencent Music *does* file 20-F); prefer issuer 20-F CIK over an F-6 `/ADR` shell. |

---

## 4. Locked Decisions

| # | Decision | Choice |
|---|---|---|
| D1 | Target depth | **Full phased program** (Phases 0–5, shipping value each phase). |
| D2 | Currency display | **Native, clearly labeled** (ISO-4217 / `get_currency_symbol`). No FX dependency. USD conversion deferred. |
| D3 | 6-K interim | **Defer** — ship 20-F annual first; 6-K is Phase 4. |
| D4 | Unsupported foreign names | **Honest "not available" state** (Phase 5) + TCEHY→TME guard. |

**Engineering defaults (my call, flagged for your veto):**
- **Feature flag `ENABLE_FPI_FILINGS`** (default off), gating discovery + summary, flipped per-environment after FPI evals pass — consistent with how `AI_FAST_MODEL`/`USE_STRUCTURED_OUTPUT` are gated. Removed once stable.
- **Form selection: page-scoped first, FPI-aware detection later.** Phase 1 requests FPI forms only on the company/filing pages (surgical, per CLAUDE.md "minimal impact"); Phase 5 adds FPI-aware detection so feed/alerts include FPIs without doubling SEC calls for every domestic company. **Avoid** a blanket global default (noise + cost).
- **Peers (D2 consequence): exclude FPIs from cross-company ranking initially** (show their own metrics only); revisit same-currency cohorts in Phase 5. Mixing native currencies in a ranking is worse than excluding.

---

## 5. Cross-Cutting Risks (govern the phase ordering)

1. **Currency is the #1 correctness risk.** Every monetary path defaults to USD (`facts_service._CONCEPT_UNITS`, `format.ts` `fmtCurrency:124`, `FinancialMetricsTable` `$`-sniffing, `peers_service`). Opening the form gate while USD is still assumed renders RMB/EUR as `$` — silent **~7× distortion**, worse than failing closed. **Currency must ship *with* financials (Phase 3), never lag.** → Phase 2 narrative ships *without* citing XBRL figures; figures arrive in Phase 3.
2. **Silent 10-K fallback hazard.** `prompt_loader.get_prompt` (`:73-74`), `openai_service._get_type_config` (`:308-342`), `assemble_excerpt_from_sections`, and `fallback_summary.py` all default unknown forms to 10-K/10-Q assumptions. If FPI forms reach summarization before 20-F prompts exist, BABA gets a 10-K prompt that forbids "Not Disclosed" and demands USD/GAAP → high hallucination. **Make every fallback explicit and tested.**
3. **IFRS coverage is partial** (~76–93%/statement via edgartools) and uneven on companyfacts — degrade gracefully (applies to ASML/NVO/SAP, not BABA).
4. **6-K is structurally not a form** — free-form furnished exhibits, often no XBRL, **semi-annual** not quarterly. Needs a separate exhibit-summarization path and careful alert cadence (Phase 4).
5. **Peer comparison across currencies** produces wrong rankings unless cohorts are same-currency — hence "exclude initially."
6. **Entity-resolution traps** — issuer 20-F CIK vs depositary F-6 `/ADR` CIK; TCEHY≠TME.
7. **Domain nuance** — Chinese ADRs need **VIE/PRC-control** framing; BABA must **not** be labeled "dual-class" (single-class, Alibaba-Partnership board nomination); per-ADS metrics need the **8:1** ratio.
8. **Eval harness blind spot** — `evals/scorers.py` USD-only numeric matcher scores a *correct* FPI summary as 0 today. Must extend scorers alongside any FPI golden data, or the harness lies.

---

## 6. Phased Plan

Effort key: **S** ≤1d · **M** ~2–4d · **L** ~1wk · **XL** >1wk. Each phase is independently shippable.

### Phase 0 — Decisions + guardrail spike *(S, no user-facing change)*
Verify edgartools FPI behavior on a **live** BABA accession before committing concept lists (per "Verify Before Done").
- [ ] Extend `backend/scripts/verify_extraction_standalone.py` to pull the latest BABA **20-F** (and one 6-K): assert `get_filings(form="20-F"/"6-K")` is non-empty, `get_financials()` is non-None, `get_currency_symbol()` returns the RMB symbol, and `TwentyF.sections` includes Item 3 (Key Information/Risk Factors) and Item 5 (Operating & Financial Review).
- [ ] **Reconcile the U.S.-GAAP/RMB reality** for BABA (the spike must confirm us-gaap concepts resolve so we don't over-build IFRS for the flagship).
- **Verify:** script prints green against a real accession.

### Phase 1 — FPI filings simply appear *(M — the quick win)*
Make `/company/BABA` **list** its 20-F and 6-K instead of "No filings found." No AI/XBRL needed.
- [ ] `config.py`: add `FORM_20F` (+`/A`), `FORM_6K` (+`/A`), `FORM_40F` (+`/A`); add `from_string` variations (`20F`/`6K`/`40F`); extend `is_annual` to 20-F/40-F; add an `is_interim` concept for 6-K; include new forms in `financial_reports()`.
- [ ] `compat.py`: union FPI forms into the default form set + `get_company_submissions`; switch the `from_string` call to **non-strict** and skip `UNKNOWN` so a new form is *requested* from SEC, not dropped (`:257-264`).
- [ ] `filings.py:104` / `frontend page-client.tsx:43`: request FPI forms on the company/filing page (page-scoped). DB cache query (`:110-113`) follows `types_list` automatically.
- [ ] `client.py:_transform_filing` (`:466`): confirm 20-F/6-K map to the new enum members (not `UNKNOWN`) so stored `filing_type` is correct.
- [ ] Frontend: widen `filterType` from a `"10-K"|"10-Q"` union to derive chips from the distinct returned types; add 20-F/6-K **badge styles**; generalize "annual report" copy to include 20-F/40-F; de-hardcode the "Retrieving 10-Q filing" loading label; ensure a filing row with no summary yet renders a clean "summary not available" state (not a broken 10-K-shaped view).
- [ ] Tests: `FilingType.from_string("20-F")` resolves; compat default includes FPI forms.
- **Verify:** `/company/BABA` lists 20-F + 6-K with working SEC links and correct badges. **The reported bug is gone.**
- **Risk:** keep it page-scoped — do **not** change the global default (`filing_scan`, feed, watchlist latest-filing are app-wide).

### Phase 2 — Basic 20-F annual summaries *(L)*
Generate a correct, grounded 20-F summary using the right item structure. **Narrative only — no XBRL figures yet** (currency lands in Phase 3).
- [ ] Author `prompts/20f-analyst-agent.md` + `20f-structured-agent.md` mapping 20-F items: Item 3 (Key Information/Risk Factors), Item 4 (Information on the Company), **Item 5 (Operating & Financial Review = MD&A)**, Item 8 (Financial Information), Item 18 (Financial Statements). Relax the "'Not Disclosed' is FORBIDDEN" rule and USD-only `$` formatting. Add VIE/PRC-control framing guidance for Chinese ADRs.
- [ ] `prompt_loader.py`: register prompts; update `_normalize_filing_type` for 20-F; **replace the silent 10-K fallback** for unknown forms with an explicit neutral prompt (so a 20-F never silently uses 10-K instructions).
- [ ] `xbrl_service.get_filing_sections` (`:495-497`): relax the `base_form not in {"10-K","10-Q"}` gate to admit 20-F; prefer edgartools `TwentyF.sections`/convenience properties over bespoke regex.
- [ ] `openai_service.py`: add 20-F keys to `_get_type_config` (`:308-342`, larger token/time budget — 20-Fs are big) and `_SECTION_LAYOUT`; add a 20-F section path (prefer edgartools sections over Item-8/7/1A regex at `:419-586`).
- [ ] `summary_pipeline.py` + `summary_generation_service.py`: open the `{"10-K","10-Q"}` **section** gates to 20-F (keep **XBRL** gated until Phase 3 — `summary_generation_service.py:438`).
- [ ] `fallback_summary.py`: handle 20-F instead of defaulting to 10-Q.
- [ ] Tests: `get_prompt("20-F")` returns the FPI prompt (not 10-K); a 20-F golden path.
- **Verify:** a BABA 20-F produces a real, item-correct annual summary (figures may be omitted/text-only until Phase 3).
- **Risks:** 20-F size can blow the 120s summary timeout / context caps; scattered silent 10-K fallbacks — make explicit & test; do not mislabel BABA "dual-class."

### Phase 3 — Currency-correct financials (RMB native + IFRS) *(XL)*
Show figures in the filing's **reporting currency**, correctly, and extend XBRL to IFRS filers.
- [ ] `instance_extractor.py`: parameterize the concept namespace (try `us-gaap:` then `ifrs-full:` — `:132`); add a 20-F entry to `DURATION_WINDOWS` (`:27`, annual ~320–390d). Prefer edgartools standardized `get_financials()` getters (revenue/net_income/total_assets fall through both taxonomies) over hand-maintained raw-tag lists.
- [ ] **Capture + persist reporting currency:** read **all** unit keys (not just `USD`) in `_parse_company_facts` (`xbrl_service.py:786-843`); stop defaulting `facts_service._CONCEPT_UNITS` to USD; carry currency through `FinancialFact.unit` and `FinancialMetric.unit`. Use `get_currency_symbol()`.
- [ ] Treat BABA's **USD convenience translation as non-authoritative**; report as-filed **RMB**, labeled. Apply the **ADS ratio** (8 shares/ADS post-Sep-2024) to per-ADS metrics.
- [ ] `facts_service._fiscal_period` (`:69-72`): map 20-F/40-F → `FY`.
- [ ] Frontend: thread `reporting_currency` through Filing/metric API types into `fmtCurrency` (`format.ts:124`) and `FinancialMetricsTable.formatMetricValue` so values aren't implied-USD; verify no mixed `$`/non-`$` on one page.
- [ ] Open the **XBRL** fetch gate in `summary_pipeline`/`summary_generation_service` to include 20-F.
- [ ] Evals: extend `scorers.py` `_number_renderings` to accept currency codes so a correct RMB value can string-match (else evals falsely fail working FPI output); add a BABA golden entry.
- **Verify:** BABA (and other 20-F filers) show metrics in correct native currency with proper per-ADS handling; eval harness validates an FPI summary.
- **Risk (dominant):** opening the gate with USD still assumed = silent ~7× distortion. **Currency lands with financials, never after.** IFRS coverage is partial — degrade gracefully.

### Phase 4 — 6-K interim *(L — deferred per D3)*
Summarize 6-K interim content, accepting it is free-form and often XBRL-less.
- [ ] Exhibit-centric path using edgartools `SixK.exhibits`/`.press_releases`/`.text()` + cover-page metadata — **not** the Item/XBRL pipeline. **Harden access to `SixK.text`**: resolve via `getattr` and check `callable()` to handle both a method and a plain property/string (edgartools attributes/return types shift across versions — cf. `Section.text`), *and* wrap in try/except (known edgartools edge case #844). Mirror the version-variance defense already used in `ownership_extractor.py`.
- [ ] Author a 6-K prompt that summarizes whatever earnings release / interim statements are attached and does **not** demand item-numbered or GAAP sections.
- [ ] Lightweight 6-K classification (earnings vs press release vs governance); run financial summarization only on those containing statements.
- [ ] `change_report_service` (`:134-135`): add 6-K interim basis; handle **semi-annual** (not quarterly) cadence.
- [ ] Alerts/feed: add 6-K **with care** + new prefs (6-Ks are frequent/heterogeneous — spam risk).
- **Verify:** an earnings 6-K yields a useful interim summary; a governance 6-K degrades to a light generic summary; no alert spam.

### Phase 5 — Adjacent features + honest unsupported states *(XL — polish)*
- [ ] **Insiders panel:** detect FPI status; show "Insider reporting not generally required for foreign private issuers" instead of an empty panel.
- [ ] **Unsupported-name guard (D4):** detect F-6-only `/ADR` CIKs (Tencent/Nestlé) and show "does not file financial reports with the SEC — coverage unavailable" (optional EDGAR link). Prefer issuer 20-F CIK over an F-6 shell during resolution; **TCEHY→TME guard**.
- [ ] **Peers:** currency-aware — exclude FPIs from cross-company ranking, or restrict cohorts to same currency (per D2). Never mix RMB/EUR with USD. **Do not backfill FPI facts into existing same-SIC buckets without currency normalization** (would corrupt domestic peer rankings).
- [ ] **Discovery breadth:** move from page-scoped to **FPI-aware detection** so `dashboard_feed_service` (`:31`), `filing_scan_service` (`:34`), `hot_filings` (`:254-256`), `notification_service` (`:45-54`) include FPIs with appropriate scoring/prefs.
- [ ] **Full-text search:** add 20-F/6-K filter chips (EFTS already supports them).
- [ ] **Examples:** `pregenerate_examples.py:86-91` — allow 20-F so an FPI ticker can be a pre-generated example.
- [ ] Tests/evals: FPI fixtures across section guard, `facts_service` (FY mapping, non-USD unit), copilot golden set, a frontend FPI render spec.
- **Verify:** FPIs are first-class across feed/alerts/search/peers/insiders; unsupported names fail honestly. Repo-wide grep confirms no remaining hard `["10-K","10-Q"]` form gate on user-facing paths.

---

## 7. Done-Gates (per CLAUDE.md "Verification Before Done")
- Phase 0 spike green against a live BABA accession before any code merges.
- Each phase: unit + smoke tests pass; FPI evals (once Phase 3) gate the `ENABLE_FPI_FILINGS` flip.
- Manual: `/company/BABA` verified in **both light & dark** themes (design-system non-negotiable).
- No silent USD mislabeling: a deliberate check that RMB never renders with `$`.

## 8. Non-Goals (explicit)
- Home-market sourcing (HKEX/SIX) for unsponsored ADRs (Tencent/Nestlé/LVMH/Roche) — separate funded project.
- USD FX conversion of financials (deferred; native-currency per D2).
- 40-F deep parsing beyond listing (single name, SHOP) — revisit on demand.
- Cross-currency peer FX-normalization (deferred to a same-currency cohort approach if demand appears).

## 9. Suggested Sequencing
Phase 0 → **Phase 1 (kills the bug, ship behind flag)** → Phase 2 → **Phase 3 (BABA fully trustworthy)** → Phase 5 (resolution/insiders/unsupported honesty) → Phase 4 (6-K). Phases 1+3 deliver the headline outcome ("Alibaba works"); Phase 5's unsupported-name guard is worth pulling early so foreign names stop looking broken even before full coverage.

---

## 10. Implementation Log

### Phase 0 — spike: ✅ DONE, **PASSED against live SEC**
`backend/scripts/verify_fpi_extraction.py` (new). Live run (`python scripts/verify_fpi_extraction.py BABA`):
- BABA resolves → `Alibaba Group Holding Ltd`, CIK `1577552`.
- `get_filings(form="20-F")` → latest accession `0001193125-26-231755` (filed 2026-05-20). ✅
- `get_filings(form="6-K")` → latest accession `0001104659-26-075717` (filed 2026-06-18). ✅
- `get_financials()` → `Financials` object. ✅
- `TwentyF.obj()` → **30 item-sections** (`part_i_item_1` … `part_ii_item_13` …) — confirms edgartools has native 20-F item extraction for Phase 2. ✅
- **Currency resolved to `$`** for BABA (which reports in RMB) — **confirms the Phase 3 currency risk is real**; the default cannot be trusted.

### Phase 1 — listing: ✅ DONE (behind `ENABLE_FPI_FILINGS`, default OFF)
- `backend/app/services/edgar/config.py` — added `FORM_20F`/`_AMENDED`, `FORM_40F`/`_AMENDED`, `FORM_6K`/`_AMENDED`; `from_string` variations (`20F`/`40F`/`6K`); `is_annual` now covers 20-F/40-F; new `is_interim` (6-K) and `is_foreign` props; new `foreign_reports()` classmethod.
- `backend/app/config.py` — new `ENABLE_FPI_FILINGS: bool = False` setting (page-scoped discovery gate).
- `backend/app/services/edgar/compat.py` — `get_filings()` now resolves forms non-strict and skips only genuine `UNKNOWN` (was: strict + `ValueError` → silently dropped 20-F/6-K).
- `backend/app/routers/filings.py` — when `ENABLE_FPI_FILINGS` and no explicit `?filing_types`, the company-filings default expands to `["10-K","10-Q","20-F","6-K","40-F"]`. Page-scoped; feed/scanner/alerts untouched.
- `frontend/app/company/[ticker]/page-client.tsx` — filter chips now derived from the filing types actually present; badge styles extended (annual 20-F/40-F = brand, interim 6-K = info); "Recommended" filing + "annual report" copy generalized to 20-F/40-F.
- Tests: `backend/tests/test_edgar_services.py` — FPI enum/`from_string`/classification tests + an async regression that `compat.get_filings` requests 20-F/6-K and skips truly-unknown forms. **38 passed.**

### Phase 2 — 20-F annual summaries: ✅ DONE (narrative + sections; XBRL/currency deferred to Phase 3)
- `backend/prompts/20f-analyst-agent.md` + `20f-structured-agent.md` (new) — 20-F item structure (Item 3.D risk, Item 5 MD&A, Item 18/17 financials), native-currency (no USD assumption/conversion), VIE/PRC + ADS-ratio framing, no "dual-class" assumption.
- `prompt_loader.py` — registers the 20-F prompts; `_normalize_filing_type` handles `20F`/`6K`/`40F`; the unknown-form fallback to the 10-K prompt is now **logged** (no longer silent) so a 6-K (pre-Phase-4) mis-analysis is visible.
- `xbrl_service.py` — `_extract_sections_sync` gains a 20-F branch (`part_i_item_3` → risk, `part_i_item_5` → MD&A, `part_iii_item_18`/`_17`/`part_i_item_8` → financials); `get_filing_sections` admits 20-F with a **raised timeout (40s)** — a real BABA 20-F parses in ~17.5s, over the 15s default.
- `openai_service.py` — `_SECTION_LAYOUT` + `_get_type_config` gain a 20-F entry (10-K-sized budget); the FY-period label and prompt's section description now cover 20-F.
- `summary_pipeline.py` + `summary_generation_service.py` — section gate opened to 20-F (XBRL gate stays 10-K/10-Q); batch `global_timeout` gives 20-F the 120s 10-K budget.
- `fallback_summary.py` — 20-F MD&A extraction (Item 5).
- **Live-verified:** `get_filing_sections` on the real BABA 20-F returns risk **410,872** + MD&A **139,430** chars (financials section thin at 761 chars → handled by the existing dense-window backfill). Tests: `tests/unit/test_fpi_summary.py` + existing — **86 passed**.

### Phase 3 — currency-correct financials (RMB native + IFRS): ✅ DONE
**Live-grounded finding:** BABA's 20-F XBRL tags the SAME line in BOTH `CNY` (all 3 years) AND a `USD` convenience translation (latest year only). The old extractor saw two values for the anchor period, judged it "ambiguous", and **dropped the whole period → BABA got zero XBRL even with the gate open.** Fixed by filtering to the reporting currency.

- `instance_extractor.py`:
  - `_fact_records` now tries `us-gaap` then `ifrs-full` namespaces; concept candidate lists gained IFRS names (Revenue/ProfitLoss/Equity/etc.) for European filers (BABA itself is U.S.-GAAP).
  - New `_currency` + `_reporting_currency` (picks the currency covering the most period-ends; ties prefer non-USD since USD is the convenience-translation convention).
  - `duration_series_with_currency` / `instant_series_with_currency` filter to the reporting currency and return it (back-compat wrappers `duration_series`/`instant_series` retained for the eval builder + unit tests; **currency-absent = exact prior behaviour**).
  - `DURATION_WINDOWS` gains `20-F`/`40-F` (annual window) — this also opens the instance-extractor's own form gate to 20-F.
- `xbrl_service.py` — `_extract_from_filing_instance_sync` attaches `currency` per entry + a filing-level `reporting_currency` (currency-weighted vote, EPS excluded); `extract_standardized_metrics` threads `currency` into every series point and surfaces top-level `reporting_currency`.
- `facts_service.py` — `_unit_for` substitutes the as-filed currency into the stored unit (CNY / CNY/shares; ratios stay `pure`); `_fiscal_period` maps 20-F/40-F → FY; **`cross_check_facts` now skips non-USD facts** so the USD-only companyfacts cross-check can never overwrite a native CNY value with the USD convenience figure (~7× distortion averted).
- Frontend — `FundamentalsTrendChart` derives the reporting currency from each series' `unit` and formats values in it (no implied `$` on CNY/EUR charts); footnote names the currency. (`FinancialMetricsTable` already passes through the AI's native-currency strings.)
- **XBRL gate opened to 20-F** in `summary_pipeline.py` + `summary_generation_service.py` — now safe because currency lands *with* the financials.
- Evals — `scorers.py` per-share matcher generalized (`*_per_share`, not just `USD_per_share`); `build_golden_set.py` reuses the product's currency-aware series (fixing the same ambiguity bug) and stamps the native currency onto golden units.
- **Live-verified end-to-end:** `get_xbrl_data` on the real BABA 20-F → `reporting_currency=CNY`, revenue **RMB 1,023.67B**, net income **RMB 103.6B**, total assets **RMB 1,909.57B** — all native CNY (never the USD convenience), all 3 comparatives retained. Tests: `tests/unit/test_fpi_currency.py` (new) + existing — **114 passed**.

**Status:** Phases 0–3 complete. **`ENABLE_FPI_FILINGS` can now be flipped on** (preview first, then prod after an eval pass) — BABA lists its 20-F/6-K, generates an item-correct 20-F summary, and shows financials in native RMB. Remaining: Phase 4 (6-K interim, deferred) and Phase 5 (peers/alerts/insiders FPI-awareness + honest "not available" for unsupported foreign names).
