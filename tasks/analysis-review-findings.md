# Multi-Period Analysis — Production-Readiness Audit (MSFT quarterly + annual runs)

Audit date: 2026-07-06 · Scope: PRs #552/#555 as shipped, live at `/analysis` · Evidence: both
screenshot sets (quarterly 2023Q4†–2026Q3 and annual FY2016–FY2025), the repo at current `main`,
SEC companyfacts ground truth fetched fresh (`CIK0000789019.json`, 4.8 MB, data through
2026-03-31), the repo's own pipeline executed end-to-end on that JSON against in-memory SQLite,
PR review-history read, EdgarTools 5.40.1 source study, a legal-inventory pass over repo + live
site, and an independent adversarial verification pass over the highest-severity findings.
Investigation only — no code changed.

---

## 1. Verdict

**The numbers are right; the labels and the citation surface are not.** Every one of the 57
Sources-list entries (28 quarterly + 29 annual), all 8 KPI-card values, the derived-Q4 arithmetic,
and every sampled YoY/QoQ/CAGR figure re-derives exactly from raw SEC companyfacts data — zero
numeric mismatches, including the fiscal-calendar-sensitive cases (June-30 FYE labelling, derived
Q4 = FY − Q1 − Q2 − Q3). The deterministic engine is trustworthy and the body↔Sources citation
mapping is 1:1 correct for all 57 resolved citations. What is **not** shippable as-is: (a) the
"— derived Q4" / "† computed Q4" label is stamped on values that are not derived Q4s — including
fiscal-**year** rows — because one flag conflates two different meanings, and whether it appears
at all flickers arbitrarily by ingestion path; (b) raw multi-reference citation markers
(`[F58, F59, F60]`, `[F91..F100]`) leak verbatim into the paid narrative — and the server's own
prompt *teaches the model that exact form*; (c) the AI narrative twice misstates a figure right
next to a "verified" citation (a "1.3 percentage points" claim that is actually 0.9pp, and
"$20.0B" for $19.83B) — the class of error the "every figure verified" header claims cannot
happen; and (d) the paid PDF export carries **no disclaimer at all** on a financial-analysis
artifact built to circulate. All are fixable with modest, well-localized changes; a phased plan
is at §8. Nothing proceeds until you approve it.

---

## 2. Findings register

Severity per rubric: P0 wrong/materially-misrepresenting displayed data or legal-exposure gap;
P1 misleading-but-explainable / broken core interaction / citation promise failure; P2
conventions a finance-literate user notices; P3 enhancements. "(verified)" = the finding was
additionally attacked by an independent fresh-context verification pass and survived at the
exact cited sites; every high-severity finding below was so verified, none was refuted.

| ID | Sev | Area | Finding | Status | Evidence anchor |
|----|-----|------|---------|--------|-----------------|
| A1 | P0 | labeling | "— derived Q4" / "† computed Q4" stamped on computed metrics in **every** period and both modes (e.g. `Net margin = 47.3% (2026Q2) — derived Q4`; `Gross margin = 64.0% (FY2016) — derived Q4`) | confirmed (verified) | `facts_service.py:1343` → `trend_analysis_service.py:677-678`; `MetricsTable.tsx:49-57,105-111`; `PeriodPicker.tsx:151`; `export_service.py:283-284,302-306`; `trends-analyst-agent.md:25-27`; reproduced live in Part-B pipeline run |
| A2 | P1 | labeling/data | The derived flag flickers by ingestion path, not by any property of the value: per-filing rows are `source="edgar_xbrl"`, companyfacts computed metrics `source="derived"`; `is_latest` is last-writer/identity-collision dependent → annual FY2023-25 margins unflagged while FY2016-22 flagged; FY2024 working capital unflagged while FY2025 flagged | confirmed (verified) | `facts_service.py:176` + `edgar/xbrl_service.py:1066-1129` vs `facts_service.py:1343`; upsert semantics `facts_service.py:484-535,1434-1457`; Part-B run (companyfacts-only DB flags **all** periods) vs annual screenshot (mixed) |
| B1 | P1 | citations | Multi-reference markers ship verbatim (`[F58, F59, F60]`, `[F9,F10]`, `[F91..F100]`, `[F222 vs F211]`) — resolver matches single markers only; **the server's own prompt renders signal markers comma-joined in one bracket**, modeling the illegal form; series-level CAGR has **no marker at all**, so CAGR claims cannot be legally cited | confirmed (verified; reproduced) | `trend_analysis_service.py:669` (`_MARKER_RE`), `:637-638` (signals `", ".join`), `:617` (CAGR in header, no marker); live repro: input `[F58, F59, F60]` → output unchanged, `[F999]` → silently stripped |
| B2 | P1 | citations/grounding | "Verified" claim overreach: invented single markers are silently stripped (claim survives uncited); the badge counts only resolved markers; and the model misstates values next to correct citations — annual "gross margin slipped **1.3 percentage points** [11]" (actual −0.94pp; −1.3% is the *relative* change), quarterly "**$20.0B** … derived 2023Q4 [21]" (actual $19.83B) | confirmed (computed) | `trend_analysis_service.py:706-711,721`; SEC recompute: FY2024 GM 69.76% → FY2025 68.82% = −0.94pp, relative −1.35%; FCF 2023Q4 = 19,827,000,000 |
| B3 | P2 | citations/UI | Resolved `[n]` citations render as plain text — bare `ReactMarkdown`, no components map — while the design system documents a citation-chip contract (`[n]` and `[F#]` become chips, unmatched stay literal) already implemented in the production copilot renderer | confirmed (verified) | `NarrativePane.tsx:127-129`; `DESIGN_SYSTEM.md:136-145`; `CopilotMessage.tsx` (chip renderer exists, unused here) |
| C1 | P2 | table | CAGR column permanently "—" in quarterly mode (dead UI); engine computes CAGR annual-only **by design** (test-asserted) | confirmed; engine side by-design | `trend_analysis_service.py:364-374`; `test_trend_analysis_service.py:278`; `MetricsTable.tsx:79-92` renders the column unconditionally |
| C2 | P1 | table | Metric (first) column scrolls out of view on horizontal scroll; no sticky-first-column capability exists anywhere (DataTable supports sticky *header* only); MetricsTable also nests a redundant second `overflow-x-auto` wrapper | confirmed (verified) | `DataTable.tsx:87-90,130`; `MetricsTable.tsx:114` |
| C3 | P2 | data-display | Sign-flip / near-zero-base growth renders nonsense percentages ("QoQ −14,399.2%", "−499.5%", "+212.9%"); no n/m guard server-side, and the same raw values are fed to the AI prompt | confirmed (computed) | `trend_analysis_service.py:199-203`; recomputed −14,399.2% exactly (investing CF +$503M → −$71.9B, the Activision quarter) |
| C4 | P2 | tone semantics | Purely sign-based green/red: capex "+54.0%" and current-liabilities increases render gain-green; long-term-debt **reduction** "−5.9%" renders loss-red — backwards to an investor, and inconsistent with the product's own signals (debt build is a red flag) | confirmed (verified) | `financialTone.ts:16-19`; `MetricsTable.tsx:59-63`; `KpiStrip.tsx:38`; no inversion map exists (repo grep) |
| C5 | P2 | convention | Margin deltas shown as relative % (net margin 47.3%→38.3% = "QoQ −19.0%"; KPI "NET MARGIN YoY +4.0%") while the narrative prompt and the inflection signals use percentage points — two registers in one product; this exact ambiguity produced the B2 "1.3pp" narrative error | confirmed | `MetricsTable.tsx:59-63` (raw relative), `trends-analyst-agent.md:55` ("Quantify the move in percentage points"), `detect_margin_compression` uses pp (`trend_analysis_service.py:471-479`) |
| C6 | P3 | table | EPS blank ("—") in derived Q4 columns — **by design and correct** (EPS is not additive; weighted shares move) | by-design | `facts_service.py:1287-1289` docstring; EdgarTools comparison shows a safe derivation path exists (NI ÷ weighted diluted shares) if wanted |
| D1 | P2 | charts | No persistent legends on any panel; series identifiable only via hover tooltip (tooltip does show names — partially mitigating) | confirmed | `TrendCharts.tsx` (no `Legend` import); `Chart.tsx:269` (tooltip renders names) |
| D2 | P2 | charts | Mixed-magnitude series share one Y axis — annual Balance sheet plots equity ($83B→$343B) against debt/cash (~$30–50B), flattening the latter | confirmed | `TrendCharts.tsx:172-187` (one YAxis for all lines); annual screenshot |
| D3 | P3 | charts | Fixed `h-56` panels, no expand/collapse (owner item 1), no per-chart/table export (owner item 2 — no CSV/XLSX/PNG utility exists in the repo), no data-label toggle (owner item 3) | confirmed greenfield | `TrendCharts.tsx:134`; repo grep: no `xlsx`/`papaparse`/`html2canvas`/`file-saver` |
| E1 | P0 | legal | The analysis **PDF export carries no disclaimer whatsoever** (no "informational purposes", no "not investment advice", no AI-error caveat, no Terms link) — on a paid artifact designed to circulate detached; the older summary PDF *does* carry an informational-purposes line. On-page, the only advice disclaimer is the global footer one-liner | confirmed (verified) | `export_service.py:346-351` vs `:117-124`; `AnalysisPageClient.tsx:317-320` (no advice language); `Footer.tsx:63-65` |
| E2 | P1 | legal/claims | "Every figure is verified against SEC XBRL" (page header + Sources header) overstates what the code does (only **cited** figures are verified; invented markers are stripped silently); free-tier teaser shows an "8 verified citations" badge over admittedly approximate sample data; pricing FAQ promises a 30-day refund that Terms §7 contradicts; Terms/Privacy/Security "Last updated" dates render as `new Date()` — today's date, always | confirmed | `AnalysisPageClient.tsx:197-201`; `NarrativePane.tsx:24`; `demo-analysis.json:2` + `AnalysisTeaser.tsx:22-35`; `pricing/page.tsx:391-393` vs `terms/page.tsx:130-131`; `terms/page.tsx:11-15` |
| F1 | P3 | KPI | Annual net-margin KPI card has no sub-metric (CAGR is null for percent units); a pp-change line would fill it | confirmed | `KpiStrip.tsx:67` (`series.cagr` null for `pure`-unit… percent series) |
| F2 | P3 | polish | "an 1,700-basis-point expansion" (grammar); large vertical gaps between narrative sections in the quarterly run (root cause not chased — likely `.markdown-body` heading margins); very long unbroken Sources tokens (`us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`) may overflow at mobile widths (**unverified** — needs a device check) | partially verified | annual/quarterly screenshots; `NarrativePane.tsx:26-45` (no `break-words`) |
| F3 | P3 | export/PDF | PDF renders narrative markdown escaped-literal (bold `**` and `[n]` appear as raw text); PDF export endpoint fetches any analysis by integer id with only `can_export` (no ownership check) — verified **by-design-acceptable**: rows are a shared cache of public-company data and the model docstring states `created_by_user_id` is "analytics only, never an access gate" | confirmed (verified) | `export_service.py:240-248`; `analysis.py:291-328`; `trend_analysis.py:39-47` |
| G1 | — | data | **Positive finding:** all 57 Sources values, 8 KPI values, derived-Q4 arithmetic, fiscal labelling (June-FYE, 2026Q3 = quarter ended 2026-03-31), CAGR guards (negative endpoints → null; ratio units → null), signals (2.5pp compression is real), badge counts (28/29 = resolved distinct markers), and the 1:1 body↔Sources mapping all check out | verified pass | §4 below |

Refuted/none-found: no numeric mismatch anywhere (T3's full sweep passed); "charts unreadable
without hover" is softened — the tooltip does name series (D1 stands as a legend gap, not a
labeling absence); no defect found in cache keying (fingerprint + PROMPT_VERSION) or metering
(fresh completions only).

---

## 3. Detailed findings (confirmed items)

### A1 — One flag, two meanings: everything computed is labelled "derived Q4" (P0)

**What the user sees.** Quarterly Sources: `[13] Net margin = 47.3% (2026Q2) — derived Q4`,
`[20] Free cash flow = … (2026Q3) — derived Q4`, `[26] Current ratio = 1.28x (2026Q3) — derived
Q4` — real, reported quarters labelled as derived fourth quarters. Annual Sources: `[9] Gross
margin = 64.0% (FY2016) — derived Q4` — "derived Q4" on a fiscal-**year** row is nonsense on its
face. The table shows the same † (tooltip: "Computed fourth quarter: full year minus the three
reported quarters") on every margin/FCF/working-capital/current-ratio cell in quarterly mode and
on most annual margin cells; the "† = computed Q4" badge and page-footer line appear in annual
mode where Q4 derivation cannot be what † means; the PDF reuses both.

**Root cause.** Two different operations share one `source="derived"` value:
1. `derive_q4_facts` (`facts_service.py:1282-1316`) — the true Q4 = FY − (Q1+Q2+Q3) derivation.
2. `derive_same_period_metrics` → `_make` (`facts_service.py:1334-1345`) — same-period computed
   metrics (margins ×100, FCF = OCF − |capex|, WC, current ratio) for **every**
   (fiscal_year, fiscal_period) group, including FY and Q1–Q3.

Everything downstream renders that single flag as "derived/computed Q4": the Sources excerpt
(`trend_analysis_service.py:677-678`), the point flag itself (`:332`), the table dagger + badge
(`MetricsTable.tsx:49-57, 105-111`), the picker-chip tooltip (`PeriodPicker.tsx:151`), the PDF
(`export_service.py:283-284, 302-306`), and — worst — the **AI prompt** (`trends-analyst-agent.md`
rule 5) tells the model `[derived]` means "computed fourth-quarter figures", inviting the model to
write false "derived Q4" caveats about annual figures.

**Impact.** A paying user can quote "MSFT's 2026Q2 net margin is a derived-Q4 estimate" — false.
Trust-critical labeling on the feature's core honesty mechanism is wrong in both directions
(over-flagging computed metrics, and — via A2 — under-flagging some genuinely derived data).

**Recommended fix (read-time classification — no migration needed).** In `build_dataset`,
classify per point: `derived_q4 = (source == "derived" AND fiscal_period == "Q4")` (true Q4
derivations, including computed metrics *on* a derived Q4 column, which genuinely rest on derived
inputs) vs `computed` (everything else `derive_same_period_metrics` makes). Then: "— derived Q4"
suffix, †, chip/PDF daggers, and the prompt's `[derived]` only for `derived_q4`. The picker-chip
dagger logic (`available_periods`, `trend_analysis_service.py:156-169`) keys off the same
`source != "derived"` test and needs the matching update. Computed metrics need no per-value
tag — the existing footer line "Growth rates, margins and ratios are computed server-side"
already discloses it (optionally a distinct "· computed" suffix in Sources). Ingest-level
source-vocabulary split (`derived_q4` vs `computed`) is the deeper fix but requires a data
migration and updates to `test_companyfacts_ingest.py:307-335` (which pins the current value);
note also that `financial_fact.py:49-50`'s own column comment enumerates
`edgar_xbrl|companyfacts|frames|fsds` and never listed "derived" — the vocabulary drifted once
already. Do the split later if at all.

**Acceptance criterion.** For the MSFT quarterly run: Sources rows for 2026Q1–Q3 metrics carry no
"derived Q4" text; 2023Q4/2024Q4/2025Q4 rows do. For the annual run: **no** row and **no** badge
says "Q4" anywhere. Prompt rule 5 wording matches the new flag.

**Tests to add.** Unit tests on `_point_citation` excerpt text for (a) a computed metric on a real
quarter, (b) a computed metric on an FY row, (c) a derived-Q4 flow — none exist today (nothing
asserts the excerpt text at all).

### A2 — The derived flag flickers by ingestion path (P1)

**What the user sees.** Annual run: gross margin FY2016 tagged "derived", FY2024/FY2025 untagged;
working capital FY2016/FY2025 tagged, FY2024 untagged; net-margin daggers on FY2016–FY2022 but not
FY2023–25. No property of the values explains the pattern.

**Root cause.** Two writers produce the same concepts with different `source` values: the
per-filing pipeline (`normalize_standardized_to_facts`, `facts_service.py:119-179`) stamps *all*
its rows — including the same computed margins/FCF/WC/CR emitted by
`extract_standardized_metrics` (`edgar/xbrl_service.py:1066-1129`) — `source="edgar_xbrl"`, with
10-K rows labelled `fiscal_period="FY"` (`:98-102`); the companyfacts ingest stamps its computed
metrics `"derived"`. Which row holds `is_latest` for a given period depends on insertion order and
on accession-identity collisions in the upsert (`facts_service.py:484-535`, `:1434-1457`): where
the companyfacts row's accession matches the already-ingested 10-K's accession the insert is
skipped (edgar_xbrl row stays current → unflagged); where the latest companyfacts vintage carries
a different accession (e.g. a balance-sheet instant last reported in a later 10-Q comparative) it
inserts and demotes (derived flag appears). Running the pipeline on a companyfacts-only database
flags **every** computed metric in every period — confirming production's mix comes from path
interleaving, not intent. A side symptom: Sources provenance is inconsistent for the same reason —
edgar_xbrl-sourced rows show a bare concept name (`· XBRL · revenue`) where companyfacts rows show
the real tag (`· XBRL · us-gaap:RevenueFromContract…`), because the per-filing computed rows carry
`raw_tag=None`.

**Impact.** The honesty badge is non-deterministic; two users analyzing the same company after
different ingest histories see different flags.

**Recommended fix.** The A1 read-time classification eliminates the *visible* flicker (Q4-derived
status derives from `fiscal_period`, which is stable across paths). The residual source-precedence
question was investigated and **decided — keep last-writer-wins**: values converge across the two
paths by construction and empirically, and all `financial_fact` consumers are source-agnostic
(see §9 D4 for the full evidence and the documented fallback if a real divergence ever appears).

**Acceptance criterion.** Same dataset → same flags regardless of whether the per-filing backfill
ran before or after the companyfacts sync (add a test that ingests in both orders and asserts
identical dataset flags).

### B1 — Multi-reference citation markers leak into the paid narrative (P1)

**What the user sees.** Quarterly body: `[F58, F59, F60]`, `[F222 vs F211]`, `[F72, F84]`,
`[F125, F126]`. Annual body: `[F1..F10]`, `[F31..F40]`, `[F9,F10]`, `[F91..F100]`, `[F211..F220]`,
`[F161..F170]`, `[F171..F180]` — raw machine markers in prose a Pro user paid for.

**Root cause — three layers, verified live:**
1. `_MARKER_RE` (`trend_analysis_service.py:669`) matches only `[F<digits>]`. Reproduced:
   `"margin compressed [F58, F59, F60]"` passes through the resolver byte-for-byte unchanged
   (while an invented `[F999]` is silently stripped — a different behavior with its own problem,
   see B2).
2. **The server teaches the model the illegal form.** `compact_dataset_for_prompt`
   (`trend_analysis_service.py:637-638`) renders inflection signals as
   `f" [{', '.join(markers)}]"` → the prompt literally contains
   `margin_compression: Operating margin compressed 2.5pp … [F58, F59, F60]`. The pipeline run
   confirms F58/F59/F60 are exactly operating margin 2026Q1/Q2/Q3 — the model copied the server's
   own notation into the "Red flags" section, as `tasks/lessons.md` predicts ("the model imitates
   a modeled output far more reliably than it obeys an abstract rule").
3. **CAGR is uncitable.** Series CAGR renders in the prompt header (`— CAGR +13.4%`, `:617`) with
   no marker, while hard rule 2 demands a marker on every figure. Every annual leak of the
   `[F91..F100]` range form sits next to a CAGR claim — the model improvised a way to cite a
   figure the dataset gave it no way to cite.

**Impact.** Every leaked form is an unverified numeric claim standing under a "28 verified
citations" badge; visually it reads as debug output.

**Recommended fix (belt-and-braces, in this order):**
- **Resolver** (fixes cached-model-behavior and future drift): extend resolution to bracket groups
  containing multiple F-refs — expand `[F58, F59, F60]` → `[n][m][k]`, `[F9,F10]`, `[F1..F10]`
  (resolve endpoints; for ranges either expand fully or resolve first+last), `[F222 vs F211]` →
  `[n] vs [m]`; unknown refs inside a group strip as today. This resolver is analysis-only —
  Copilot has its own `_resolve_citations`; no shared-contract risk.
- **Prompt/data**: render signal markers as separate brackets (`[F58] [F59] [F60]`) in
  `compact_dataset_for_prompt`; assign real markers to CAGR (it is a server-computed figure and
  belongs in the grounding contract); add a hard rule with a worked negative example ("one marker
  per bracket — write `[F9] [F10]`, never `[F9, F10]` or `[F9..F10]`").
- Bump `PROMPT_VERSION` (`:32`) — every cached narrative regenerates lazily on next request
  (verified: a version mismatch falls through to full regeneration and overwrites in place; stale
  text is never served). One side-effect to decide on: regeneration is **metered** — the router
  meters every non-cached completion (`analysis.py:270-277`), so a fleet-wide bump costs each
  user one `ANALYSIS_MONTHLY_CAP` unit on their first re-request plus a model-cost spike.
  Decision (plan-final): exempt **system-invalidated** regenerations from the meter — the
  generator knows when it regenerated because a cached row exists but its `prompt_version` or
  fingerprint mismatched; tag the complete event (e.g. `invalidated: true`) and skip metering in
  the router for that case. User-initiated `force` refreshes stay metered (abuse surface
  unchanged).

**Acceptance criterion.** Regenerated MSFT runs contain zero `[F` sequences in the rendered
narrative; the badge count equals the number of distinct bracketed references the reader sees.

**Tests to add.** Resolver cases for list/range/vs forms (none exist — current tests cover only
single/invented/whitespace forms, `test_analysis_stream.py:28-47`); a prompt-rendering test
asserting no comma-joined markers in signals; a CAGR-marker resolution test.

### B2 — The "verified" promise vs. what the code can promise (P1)

Three mechanisms let unverified numbers stand under the verified badge:
1. **Silent stripping** (`trend_analysis_service.py:706-711`): a marker the dataset never issued
   is deleted, leaving its figure as uncited prose — indistinguishable from clean text.
2. **Unparsed multi-refs** (B1): neither resolved nor stripped nor counted.
3. **Model paraphrase drift**: two live instances — annual Red flags: "FY2025 gross margin slipped
   **1.3 percentage points** [11]" — recomputed from SEC data: FY2024 69.76% → FY2025 68.82% =
   **−0.94pp**; −1.3% is the *relative* change the dataset feeds the model for a percent-unit
   series (C5 is the enabler). Quarterly: "the **$20.0B** generated in the derived 2023Q4 [21]"
   — the cited value is $19,827M ($19.8B). The citation system verifies the *referenced value*,
   not the *prose claim beside it* — precisely the gap the "every figure is verified against SEC
   XBRL" header (`AnalysisPageClient.tsx:199-200`) papers over.

Also noted: the model performs small arithmetic the prompt forbids ("nearly 48% increase over
eleven quarters", "capex consumed over $60B across those two quarters" — both arithmetically
correct, both derived, the latter cited with a leaked multi-ref). The trajectory-section
instruction ("anchor with the top line's CAGR or endpoint-to-endpoint move") *demands* a figure
the quarterly dataset doesn't provide (no CAGR, no window delta) — a contract tension to resolve
server-side by providing the endpoint-to-endpoint delta as a citable value.

**Recommended fix.** (a) Copy honesty now: header and Sources title → "every **cited** figure";
(b) count strips/unparsed forms during resolution and expose the count (log + PostHog + tooltip
"N figures verified · M statements unverifiable"), with an optional regenerate-once policy when
the count is nonzero; (c) fix the pp/relative enabler per C5; (d) add the pp-vs-relative worked
example to the prompt; (e) longer-term, a deterministic post-generation scan for numeric tokens
adjacent to citations that don't match the cited value within display rounding (the eval harness's
"figure not traceable" idea).

**Acceptance criterion.** A narrative containing a stripped or unparsed marker can no longer ship
with an unqualified "N verified citations" badge; regenerated MSFT annual narrative states the
gross-margin move as −0.9pp (or −1.3% *relative*, labelled as such).

### B3 — Citations render as plain text; the DS chip contract exists and is unused (P2 — owner item 4's "formatting" half)

`NarrativePane.tsx:127-129` renders the narrative through bare `ReactMarkdown` with no components
map: resolved `[1]`…`[28]` are plain body text — no chip, no link to the Sources row, no hover
excerpt. `DESIGN_SYSTEM.md:136-145` documents the shipped copilot contract — `[n]` and `[F#]`
markers become chips, unmatched markers stay literal, `verified` drives the trust badge — and
`features/filings/components/copilot/CopilotMessage.tsx` implements it (chips + popovers +
deep-links). **Recommendation:** extract the marker-to-chip rendering from CopilotMessage into a
shared renderer and use it in NarrativePane with a popover showing the Sources excerpt; scroll-to
+ `citation-flash` (an existing motion token) on the Sources row on click. Size M.

### C1 — Quarterly CAGR column: by design in the engine, dead UI in the table (P2 — owner item 5)

The engine computes CAGR only in annual mode and only for non-ratio units
(`trend_analysis_service.py:364-374`), asserted by `test_trend_analysis_service.py:278`. That's a
defensible product decision (a "CAGR" across 12 quarters is annualization, not compound annual
growth over years). The table, however, renders the CAGR column unconditionally
(`MetricsTable.tsx:79-92`), so quarterly mode ships a permanently empty column. **Ship: hide the
column in quarterly mode** (one condition in the columns memo). Optionally later: a "window
growth" column (endpoint-to-endpoint % over the selected quarters — which also gives the narrative
its missing citable trajectory anchor, see B2). I would ship the hide now and treat annualized
quarterly CAGR as not worth its confusion risk.

### C2 — Sticky metric column (P1 — owner item 6)

Confirmed absent: `DataTable.tsx` implements `stickyHeader` only (`:87-90`); no sticky-column
capability exists anywhere in the repo. Spec (reusable DataTable capability, not a one-off):
`stickyFirstColumn?: boolean` — first `th`/`td` get `sticky left-0` with an **opaque** surface
(`bg-panel-light dark:bg-panel-dark` — cells are transparent today, so without an explicit fill
the scrolled content bleeds through), `z-10` (`z-20` for the header corner cell when combined
with `stickyHeader`), and a right-edge hairline (`border-r border-border-light
dark:border-border-dark`) so the boundary reads while scrolled. Row-hover must repaint the sticky
cell too (hover class on the `td`, not only the `tr`). Remove MetricsTable's redundant outer
`overflow-x-auto` wrapper (`MetricsTable.tsx:114`) — DataTable's root already scrolls
(`DataTable.tsx:130`), and the sticky cell must live inside the actual scroll container. Verify in
both themes. Size M. Test: a Vitest render asserting the first column's computed classes, plus a
Playwright horizontal-scroll assertion.

### C3 — Sign-flip growth needs an n/m convention (P2)

`_growth` (`trend_analysis_service.py:199-203`) divides by `abs(prior)` with no sign guard;
production shows "QoQ −14,399.2%" (investing CF +$503M → −$71.9B — recomputed exactly). Finance
convention is "n/m" (not meaningful) across sign changes. **Fix server-side** so the table, KPI,
PDF, and the AI prompt all inherit it: return `None` (or a distinct `"nm"` sentinel if you want
the display to say "n/m" rather than nothing) when `sign(current) != sign(prior)`. I'd also gate
`|prior|` below a small floor relative to `|current|` (e.g. |prior| < 5% of |current| → n/m) to
kill the "+212.9%" class. Keeping raw math for same-sign moves is correct. Frontend renders "n/m"
in the flat tone. Acceptance: no growth figure with |value| > 500% appears for a sign-flipping
series; prompt lines show `QoQ n/m`.

### C4 — Direction tone should not read as judgment on spend/leverage rows (P2)

`directionOf` (`financialTone.ts:16-19`) is sign-only; no inversion map exists. Result: capex
+54.0% green, current liabilities +12.7% green, long-term debt −5.9% **red** — a debt reduction
painted as a loss. The product already takes valence positions (debt build and margin compression
are red-flag signals), so "green = numerically up" is not a consistently neutral register either.
**Recommendation:** a per-concept tone policy local to the analysis feature — `inverted`:
{long_term_debt, current_liabilities} (up = loss tone, down = gain tone); `neutral` (flat tone):
{capital_expenditures, investing_cash_flow, financing_cash_flow} where direction has no fixed
valence (capex up can be growth investment). Everything else keeps sign-based. Size S
(a map + one lookup in MetricsTable/KpiStrip). Alternative — all-neutral "direction, not
judgment" — is defensible but wastes the tone system; either way, document the register in
DESIGN_SYSTEM.md. Flagged in §9 as a taste call for you.

### C5 — Margins: percentage points, not relative % (P2)

Table and KPI show relative % on percent-unit series ("net margin QoQ −19.0%"; "NET MARGIN YoY
+4.0%"), while the narrative prompt instructs pp and the margin-compression signal computes pp —
two registers, and the relative form directly enabled the B2 "1.3pp" error. **Fix server-side:**
for `percent`-unit series, compute growth as `current − prior` (pp) and label it (`+0.5pp`,
`−9.0pp`); feed the same to the prompt ("YoY −0.9pp"); KPI net-margin sub-line becomes pp (also
fills F1's blank annual card: "+13.6pp over window" or YoY pp). Frontend formats with a `pp`
suffix. Acceptance: MSFT quarterly net-margin 2026Q3 shows "QoQ −9.0pp"; the annual gross-margin
FY2025 cell shows "YoY −0.9pp"; regenerated narratives quote pp figures matching the dataset.

### D1/D2 — Chart legends and mixed-magnitude axes (P2, folds into §6)

No `Legend` anywhere in `TrendCharts.tsx`; the multi-line panels (Margins, Cash generation,
Balance sheet) are three same-weight lines distinguishable only by hover (`ChartTooltip` does
render series names — `Chart.tsx:269`). The annual Balance-sheet panel plots equity to $343.5B
against debt ~$40B on one axis, flattening debt/cash into the baseline (`TrendCharts.tsx:172-187`,
single `YAxis`). Proposals in §6.

### E1/E2 — Legal (P0 gap on the PDF; claims to soften)

Full inventory, gap analysis, drafted disclaimer text, and counsel flags are in §7. The two
load-bearing facts: the analysis PDF's entire legal content is a data-provenance footnote
(`export_service.py:346-351`) — the older summary PDF carries "for informational purposes only"
(`:117-124`) and the new paid flagship carries less; and the page-level accuracy claim ("every
figure is verified") exceeds what `resolve_narrative_citations` actually guarantees (B2).

---

## 4. Data validation results

**Methodology.** Ground truth: `https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json`
fetched 2026-07-06 (descriptive User-Agent, single request; data horizon 2007-09-30 → 2026-03-31,
covering every displayed period). Two independent checks: **(A)** a from-scratch recomputation
(own tag selection: latest-`filed` wins per period, first-tag-with-data wins across the repo's
candidate lists; duration classification 320–390d = FY, 75–105d = quarter; derived Q4 =
FY − ΣQ1–3; margins/FCF/WC/CR recomputed) compared against every transcribed screenshot value;
**(B)** the repo's actual pipeline (`normalize_companyfacts` → `upsert_facts_bulk` →
`build_dataset` → citation machinery) executed on the same JSON via in-memory SQLite. Tolerance:
USD levels exact to the displayed integer; percentages/ratios ±0.06 on the displayed rounding
(1dp margins, 2dp ratios); growth figures ±0.15pp of the displayed 1dp value.

**Results.**

| Check | Result |
|---|---|
| Quarterly Sources [1]–[28] values | **28/28 pass, exact** (incl. all derived-Q4 arithmetic: rev 56,189M; OCF 28,770M; capex 8,943M; FCF 19,827M for 2023Q4) |
| Annual Sources [1]–[29] values | **29/29 pass, exact** |
| KPI cards (4 quarterly + 4 annual values) | **8/8 pass** (Q: $82.9B/$31.8B/$15.8B/38.3%; A: $281.7B/$101.8B/$71.6B/36.1%) |
| KPI growth lines | 4/4 pass (Q YoY +18.3/+23.1/−22.1/+4.0 relative; A CAGR +13.4/+19.5/+12.4) |
| Narrative growth claims sampled | +18.4% [3], +16.7% [4], +24.3% [5], +20.9% [6], +20.0% [7], +59.5% [8] — all pass |
| Table CAGR column (annual) | Pipeline reproduces every screenshot CAGR incl. working capital −5.1%, investing/financing CF "—" (negative endpoints → null, correct), margins/ratio "—" (percent/pure units, by design) |
| Sign-flip cells | −14,399.2% (Q invCF 2024Q2) and −499.5% (A finCF FY2018) reproduce exactly — the math is "correct", the convention is the problem (C3) |
| Fiscal labelling | 2023Q4 = quarter ended 2023-06-30, 2026Q3 = quarter ended 2026-03-31 — correct for MSFT's June-30 FYE; FY windows derived from period durations, `fp` never trusted |
| Body↔Sources mapping (owner item 4, second half) | **All 57 resolved citations map 1:1 and semantically correctly**; repeated markers correctly reuse one number ([2], [6], [11], [18], [19], [27] reused). Growth claims citing *level* sources (e.g. "+18.4% [3]" where [3] is the 2026Q1 revenue level) match the design: YoY is an attribute of the cited dataset point |
| Narrative prose fidelity | **2 failures**: "1.3 percentage points" (actual −0.94pp — unit conflation) and "$20.0B" (actual $19.83B) — see B2. "over $60B capex across two quarters" checks out (=$60.75B) but is model arithmetic the prompt forbids |
| "N verified citations" badge | Code meaning established: `grounded = len(citations)` = distinct **resolved** `[F#]` markers (`trend_analysis_service.py:721`). The counts shown (28/29) are internally consistent, but the badge's implicit claim does not extend to leaked multi-refs (7 in the quarterly body, ~9 in the annual) or silently-stripped markers — so "verified citations: 28" is accurate while "every figure verified" is not (B2/E2) |

**Not independently validated:** nothing material. (Both screenshot sets were provided —
the annual set arrived mid-audit and is fully covered above. The only screenshot-derived items I
could not re-derive from SEC data are the two narrative prose errors' exact wording, which are
transcription-verified against the images.)

---

## 5. EdgarTools capability matrix & optimization opportunities

Study method: repo usage read directly; EdgarTools studied from the GitHub releases page, PyPI
metadata, readthedocs, and **direct source reads of the pinned tag v5.40.1** (entity/parser,
query, entity_facts, enhanced_statement, ttm/calculator, search/efts, ownership).

**Version pin: no gap.** `edgartools==5.40.1` (`backend/requirements.txt:55`) **is the latest
release** (June 29). The real exposure is forward churn: 6 releases in 10 days
(5.36.0 → 5.40.1), each touching parsers this repo consumes (ownership reorg 5.36/5.37, XBRL
`currency` column 5.37.0 — which `instance_extractor.py:200-213` depends on, section extraction
5.40.x). The defensive-wrapper posture is evidence-based, in the repo's own words
(`ownership_extractor.py:3-8` documents cross-version column-casing and property-vs-method drift).

| Stage | Today (hand-rolled?) | EdgarTools native | Adopt? |
|---|---|---|---|
| Companyfacts retrieval | Raw httpx ×3 call-sites, shared `sec_rate_limiter` (`facts_service.py:1465-1492`, `:440-466`) | `Company.get_facts()` / `EntityFacts` (sync, own throttling, LRU) | **No** — adoption stacks a second rate limiter and loses the app's async token bucket |
| Standardized metrics | Hand-curated tag lists (`facts_service.py:950-1002`) + FI statement profiles | Learned mappings from 32k filings; 150 IFRS→GAAP maps | **Mostly no** — EdgarTools shares the bank-revenue blind spot this repo already fixed (`instance_extractor.py:444-449`); its IFRS maps are the one interesting piece for the currently-unsupported IFRS filers |
| Fiscal labelling | Window-derived, `fp/fy` distrusted (`facts_service.py:1116-1156`) | Parser copies `fy/fp` verbatim (`parser.py:192-194`); repairs live only in the statement layer (Issue #779 names MSFT) | **No** — the repo's write-time derivation is uniformly safe; EdgarTools' raw facts API would reintroduce the comparative-period mislabeling class |
| Q4 derivation | FY − ΣQ1–3, all three quarters required, flows only, no EPS (`facts_service.py:1282-1316`) | **Stronger**: Q4 = FY − YTD9 preferred (single-vintage, survives a missing quarter) with FY − ΣQ fallback; quarterly EPS re-derived from NI ÷ weighted shares (`ttm/calculator.py:525-755`) | **Port the two ideas, not the dependency** — YTD9-based Q4 (requires keeping the currently-discarded 9-month YTD slices) and derived-Q4 EPS (fixes C6). Derived rows must inherit the (fixed) badging + eval coverage |
| Multi-period stitching | DB-level from `financial_fact` — one companyfacts request serves 10FY+12Q, with citations/caching/`is_latest` | `MultiPeriodStatement`, `XBRLS.from_filings` (would reintroduce N per-filing parses in the request path) | **No** for the pipeline; `to_llm_context()` is worth a look for prompt formatting only |
| Form 4 / ownership | Already EdgarTools-backed behind a defensive wrapper | `edgar.ownership` improved in 5.36/5.37 | Keep as-is; after any pin bump re-run `scripts/verify_insider_extraction.py` |
| Full-text search | Deliberate thin async EFTS client (`sec_api.py:9-12`) | `edgar.search.efts` — sync, no 8-K `items` field | **No** — adoption would regress |

**Recommendations:** (1) keep the hand-rolled companyfacts pipeline (it is architecturally ahead
of EdgarTools' raw facts API for a persistence workload); (2) port YTD9-Q4 and EPS-quarterization
ideas into `derive_q4_facts` behind eval coverage; (3) stay exactly-pinned and treat every future
bump as a behavior change gated on the evals + insider verification script; (4) monthly review of
the releases page (6 releases/10 days cadence makes long lags a real gap).

---

## 6. Enhancement proposals (owner items 1–3 + chart gaps)

All DS-constrained: tokens only, both themes, reduced-motion fallbacks, no new colors outside
`seriesColor()`/financial tones.

1. **Expand/collapse charts (owner 1) — size M.** Per-panel expand toggle on the Card header
   (icon Button, `aria-expanded`): expanded panel spans both grid columns
   (`md:col-span-2`) and grows `h-56 → h-96`; grid reflows naturally. Recharts'
   `ResponsiveContainer` handles resize. Animate height with `--duration-base/--ease-standard`;
   instant under reduced motion. No modal needed (no repo pattern exists; grid-span is cheaper and
   keeps context). Risk: low — pure presentation.
2. **Per-chart / table export (owner 2) — size M, greenfield.** No export utility exists in the
   frontend (verified: no `xlsx`/`papaparse`/`html2canvas`/`file-saver`). Ship dependency-free:
   **PNG** — serialize the panel's SVG (`XMLSerializer` → `Image` → `<canvas>` → `toBlob`),
   painting the theme background first so dark-mode exports aren't transparent; **CSV** — build
   from `dataset.series` (label, unit, one column per period + CAGR) with the same formatting
   helpers, download via Blob (the existing PDF blob-download pattern in
   `AnalysisPageClient.tsx:164-183`). Defer XLSX (CSV opens in Excel; a real `xlsx` dep can come
   later if asked). Gate behind the existing `can_export` entitlement like the PDF. Risk: SVG→PNG
   needs a font-inlining check for the Geist Mono axis labels — verify output on both themes.
3. **Data-label toggle (owner 3) — size S/M.** A small toggle (chip-style Button group in each
   panel header, default off) conditionally adds Recharts `<LabelList dataKey position="top">`
   with the panel's formatter, 10px `CHART_FONT`, theme-aware fill. Auto-thin labels when
   `periods.length > 8` (annual 10 / quarterly 12 get crowded): render every other label. Risk:
   overlap on volatile series — acceptable for an opt-in.
4. **Legends (D1) — size S.** A custom DS legend row (color swatch + label, `CHART_FONT`, 11px)
   above each multi-line panel — not Recharts' default `<Legend>` (unstyled). Bonus: make legend
   items clickable to toggle series visibility (local state; Recharts `hide` prop) — which is also
   the cheapest mitigation for D2.
5. **Mixed-magnitude axes (D2) — size M.** For the Balance-sheet panel: move equity to a right
   axis (`yAxisId`) leaving debt/cash on the left — the ComposedChart dual-axis pattern already
   exists in panel 1 — with the legend making the axis assignment explicit. Alternative
   (indexed-to-100 view) rejected: it breaks the "every pixel is a citable dollar value" promise.
6. **KPI polish (F1) — size S.** Annual net-margin card sub-line: window pp change
   ("+13.6pp FY2016→FY2025") once C5 lands.

---

## 7. Legal review — **for counsel review, not legal advice**

(Prepared by the audit as research for you to take to qualified counsel; no attorney-client
relationship; nothing here should ship without counsel sign-off.)

**Current state (verified in repo and on the live site, which match):**

| Surface | What it says today |
|---|---|
| Analysis page header | *Claim*: "an AI analysis where **every figure is verified** against SEC XBRL" (`AnalysisPageClient.tsx:197-201`) |
| Analysis page footer line (Pro-results only) | Data provenance + "† = computed Q4" (`:317-320`) — no advice language; not shown to free users |
| Narrative pane | "AI trend analysis" heading (the only AI disclosure); badge tooltip "Every cited figure resolves to an exact SEC XBRL value" (scoped correctly, unlike the header); Sources title repeats "every figure verified" (`NarrativePane.tsx:24,86-89`) |
| Global footer | "Data sourced from SEC EDGAR. Not investment advice." (`Footer.tsx:63-65`) — the only advice disclaimer an analysis user sees |
| **Analysis PDF** | **Nothing** beyond the provenance footnote (`export_service.py:346-351`); the summary PDF has "for informational purposes only" (`:117-124`) — the paid flagship has less than the free feature |
| Terms | Strong §3 (no advice/recommendation/fiduciary; past-performance caution) and §4 (AI may err — but says "Summaries", not analyses) (`terms/page.tsx:53-89`) |
| Free teaser | Full sample narrative with an "8 verified citations" badge over figures `demo-analysis.json:2` itself calls "approximate" |

**Gaps (severity given this is a paid surface with detachable PDF exports):** no
point-of-consumption disclaimer anywhere on the analysis surface (high); PDF entirely bare (high —
it circulates without the footer or Terms); past-performance caution absent from a literally
past-performance product surface (medium-high); AI-disclosure on the PDF is a subordinate clause
(medium); no "not affiliated with the SEC" line anywhere (low).

**Recommended text and placements** (short forms; tone matches the product voice):
- **(a) Analysis page footer** (`AnalysisPageClient.tsx:317-320`, and move outside the
  `isPro && dataset` gate so free/teaser users see it too): append — "This analysis is
  AI-generated, for informational purposes only, and is not investment advice or a
  recommendation; past performance does not predict future results. Verify against the original
  filings on SEC EDGAR. See our [Terms](/terms)."
- **(b) Narrative pane**, directly under the Sources list (travels with the teaser too):
  "AI-generated. Informational only — not investment advice. Cited figures resolve to SEC XBRL
  values; uncited statements are the model's interpretation and can be wrong."
- **(c) Analysis PDF footer** (`export_service.py:348-351`) — self-contained long form: an "About
  this document" block covering AI generation + date, SEC XBRL sourcing, EarningsNerd-computed
  figures (†), "AI-generated text may be incomplete, out of date, or wrong; the authoritative
  source is always the original SEC filing", informational-purposes / no advice / no
  recommendation / no fiduciary, past-performance caution, Terms URL, "not affiliated with or
  endorsed by the SEC". Also add "not investment advice" + Terms pointer to the summary PDF.
- **(d) Global footer**: extend to "Data sourced from SEC EDGAR. AI-generated content — for
  informational purposes only. Not investment advice. Not affiliated with the SEC."
- **(e) Terms additions** (outline): extend §4 beyond "Summaries" to analyses/exports; an
  exported-documents clause; a derived/computed-figures clause; a definition of "verified
  citations" (what it does and does not warrant); reconcile the §6/§8 redistribution limits with
  selling PDF export; name the AI provider consistently (Security page says DeepSeek powers
  "summaries and Copilot" — analysis narratives too).

**Counsel flags:** (F1) the "every figure verified" claim vs. silent marker-stripping — an express
accuracy claim the code can't fully guarantee can cut against the warranty disclaimer and raises
false-advertising exposure independent of any disclaimer; engineering options in B2. (F2) raw
`[F#]` markers visible mid-stream and in leaked multi-refs undercut the "verified" representation.
(F3) teaser's "verified" badge over approximate sample data. (F4) Terms/Privacy/Security "Last
updated" dates are `new Date()` at render — every visitor sees today's date
(`terms/page.tsx:11-15`) — trivial fix, matters for change-notice enforceability. (F5) the prompt
forbids "hedging boilerplate", so the narrative will never self-disclaim — the chrome must carry
it. (F6) pricing FAQ's "30-day money-back guarantee" (`pricing/page.tsx:391-393`) directly
contradicts Terms §7 "fees are non-refundable" (`terms/page.tsx:130-131`). (F7) production Copilot
dropped the per-answer disclaimer the DS reference component carries (`AskFilingAnswer.tsx:468`) —
fix pattern (b) applies there too.

---

## 8. Remediation plan (all §9 decisions folded in — fully specified, awaiting your go to start Phase A)

Sizes: S ≤ ½ day · M 1–3 days · L > 3 days. Order within phases is dependency order.

**Phase A — correctness & label integrity (P0/P1)**

1. **A1/A2 derived-flag fix** (M): read-time `derived_q4` classification in `build_dataset`
   (`source=="derived" AND fiscal_period=="Q4"`); Sources suffix/†/chips/PDF/prompt keyed to it;
   prompt rule 5 reworded. Tests: `_point_citation` excerpt for computed-metric-on-real-quarter,
   computed-metric-on-FY, true derived-Q4; ingest-order-independence test. Acceptance: annual run
   shows no "Q4" flag anywhere; 2026Q1–Q3 rows unflagged; Q4 columns flagged.
2. **B1 citation-leak fix** (M): resolver expands list/range/vs bracket groups; signals prompt
   renders separate brackets; CAGR gets real markers; hard rule + worked negative example;
   `PROMPT_VERSION` bump (regenerates all cached narratives lazily). Tests: resolver multi-ref
   cases; prompt-render assertion; CAGR resolution. Acceptance: zero `[F` in regenerated output.
3. **B2 verified-claim honesty** (S code + copy): header/Sources copy → "every **cited** figure";
   strip/unparsed counters logged + surfaced in the badge tooltip; pp-vs-relative worked example
   in the prompt. Depends on 2 (and pairs with 5).
4. **E1 disclaimers — two-track per §9 D6** (S–M): ships now — analysis PDF "About this
   document" block; page-footer + narrative-pane one-liners (outside the Pro gate); summary-PDF
   parity; global-footer extension; `new Date()` fix pinned to each page's last *content* change
   from git history; pricing-FAQ refund correction per D5 (+ `PricingPage.test.tsx` update).
   Holds for counsel — the Terms clause additions (§7e), with §7 as the counsel brief.
**Phase B — quick wins (P2)**

5. **C5 pp for percent series** (M): server-side growth = pp for `percent` series across dataset,
   prompt, table, KPI, PDF; "pp" labels. Acceptance: net-margin cells show pp; narrative quotes pp.
6. **C3 n/m guard** (S–M): `_growth` → None/"nm" on sign flips (+ small-base floor); "n/m"
   display; prompt inherits.
7. **C1 hide quarterly CAGR column** (S).
8. **C4 tone policy map** (S — register decided, §9 D1: inverted debt/liabilities, neutral
   capex/investing/financing; document in DESIGN_SYSTEM.md).
9. **C2 sticky first column** (M): DataTable `stickyFirstColumn` per spec in §3; drop the
   redundant wrapper.
10. **D1 legends** (S).
11. **B3 citation chips** (M): shared marker-chip renderer from CopilotMessage; popover +
    scroll-to-source + citation-flash.

**Phase C — enhancements (P3, owner items 1–3) — SHIPPED 2026-07-06 (same PR as this note)**

12. **Chart expand/collapse** (M). ✅ per-panel PanelCard, col-span-2 + h-96, base-token height
    transition, reduced-motion fallback.
13. **PNG/CSV export** (M). ✅ dependency-free (`chartExport.ts`): per-panel PNG via SVG→canvas
    with live theme background; whole-dataset CSV (raw numbers, computed-Q4 flagged in headers);
    Pro results surface only.
14. **Data-label toggle** (S/M). ✅ per-panel aria-pressed toggle, LabelList content renderer,
    auto-thinned past 8 periods.
15. **Balance-sheet dual axis** (M, after 10). ✅ equity → right axis, legend "(right)" suffix,
    single-sided panels stay single-axis.
16. **KPI pp sub-line** (S, after 5). ✅ shipped with Phase B (`window_pp`); Phase C added the
    basis-window tooltips.
17. **Derived-Q4 EPS + YTD9-based Q4 derivation** (M–L, eval-gated). ✅ YTD9-preferred Q4
    (ΣQ fallback + mismatch telemetry) and shares-based Q4 EPS with the EPS≈NI÷shares
    consistency gate; MSFT acceptance: derived Q4 FY2025 diluted EPS 3.6500 vs 3.65 reported.
18. **F2/F3 polish**. ✅ prompt a/an guard (no PROMPT_VERSION bump — grammar only); pane heading
    rhythm (.markdown-body); Sources `break-words`; PDF renders the narrative's GFM subset;
    teaser F3 fix (Sample-data badge replaces verified/cached).

**Phase-C follow-ups also shipped in the same PR:** the D2 engineering track (one-shot
regenerate-on-strip retry + deterministic numeric-fidelity scan); shared `citation_markers`
module + copilot multi-ref pre-pass; shared `AiDisclaimer` (closes F7's copilot gap + the
summary card's web/PDF parity gap) and `legalDates`; DESIGN_SYSTEM.md tone-register section
(D1). **Still open (human action):** the counsel pass on the Terms additions (§7e / D6 track 2).

Every phase-A/B item ships with the verification discipline from `tasks/lessons.md`: ruff + bandit
+ pytest + vitest + `next build`, and a both-themes preview check for anything visual.

---

## 9. Decisions (owner answers received 2026-07-06; Q4/Q6 investigated and decided)

1. **D1 — Tone register (C4): decided.** Metric-aware policy per the recommendation — `inverted`
   for {long_term_debt, current_liabilities} (up = loss tone, down = gain tone), `neutral` (flat
   tone) for {capital_expenditures, investing_cash_flow, financing_cash_flow}, sign-based for
   everything else. Register to be documented in DESIGN_SYSTEM.md alongside the financial-tone
   section.
2. **D2 — "Verified" claim (B2/E2): decided.** The recommendation ships: soften the page header
   and Sources title to "every **cited** figure" now, surface strip/unparsed counters in the
   badge tooltip, add the pp-vs-relative worked example to the prompt. Engineering the literal
   claim (regenerate-on-strip + deterministic numeric-fidelity scan) stays a Phase-C follow-up,
   not a launch blocker.
3. **D3 — Quarterly CAGR (C1): decided.** Hide the column in quarterly mode. No "window growth"
   replacement column for now (the narrative's citable trajectory anchor still lands via B1's
   CAGR markers in annual mode; quarterly trajectory framing is prompt-side).
4. **D4 — Source precedence (A2 residual): investigated → keep last-writer-wins; no write-path
   precedence, no migration.** Evidence: (i) values converge across the two paths by
   construction — headline concepts are cross-checked and corrected to companyfacts within 1%
   (`facts_service.py:395-437`), computed metrics share formulas verbatim
   (`derive_same_period_metrics` docstring), and the instant-concept tag priority lists are
   mirrored (`instance_extractor.py:114` `LongTermDebtNoncurrent → LongTermDebt` = 
   `COMPANYFACTS_INSTANT_TAGS`, `facts_service.py:999`; same for the cash triple) — and
   empirically: all 57 displayed values from the mixed-source production DB matched the
   pure-companyfacts recomputation exactly. (ii) The user-visible incoherence is fully removed by
   Phase-A's read-time `derived_q4` classification, which keys on `fiscal_period` — stable across
   paths. (iii) All three `financial_fact` consumers (analysis, `peers_service.py:66-126`,
   `copilot_tools.py:219-353`) read `is_latest` with no source-dependent logic, so a precedence
   rank + re-promotion migration would be a core-write-path change with app-wide blast radius
   purchased against a divergence that doesn't exist in evidence ("Minimal Impact"). Guards that
   ship with Phase A instead: the ingest-order-independence test (same dataset flags/values
   regardless of which path ran last) and a `facts_service` docstring documenting the dual-writer
   property. Documented fallback if a real value divergence is ever observed: source-rank at
   upsert (companyfacts ≥ edgar_xbrl) + a one-off re-promotion migration. Accepted residual:
   Sources rows sourced from per-filing computed metrics show a bare concept name instead of a
   `us-gaap:` tag (cosmetic provenance).
5. **D5 — Refund copy (E2/F6): decided.** Correct the pricing FAQ to match Terms §7 (remove the
   "30-day money-back guarantee" claim; replace with accurate cancellation language, e.g.
   "cancel anytime — you keep Pro until the end of the paid period"). Update
   `PricingPage.test.tsx` in the same change (it asserts page copy; see `tasks/lessons.md`
   2026-07-04).
6. **D6 — Disclaimer staging (E1/§7): investigated → two-track, ship interim now.** Rationale:
   the live P0 state is a **paid PDF with zero disclaimer** circulating detached — shipping
   conservative, factual, industry-standard informational/not-advice boilerplate strictly
   reduces exposure versus waiting, and the §7 drafts are standard-practice language (low regret
   risk; counsel refines wording later). **Ships now (Phase A item 4):** the PDF "About this
   document" block, the page-footer and narrative-pane one-liners (outside the Pro gate), the
   global-footer extension, the D2 claim softening, the D5 FAQ correction, and the
   `new Date()` last-updated fix — pinning each legal page's date to its last **content** change
   from git history (the 2026-07-04 `c6a7ef6` touch was a styling-only sweep and must not be
   used as the content date). **Holds for counsel:** the Terms of Service clause additions
   (§7e — exported-documents, derived-figures, verified-citations definition, license-scope
   reconciliation, AI-provider naming) — that is genuine contract drafting, and Terms §13's
   change-notice mechanics make batching those edits with counsel the right process. The §7
   package is the counsel brief; the Terms follow-up lands as its own change after review.
   Every interim surface keeps the "for counsel review" caveat in the PR description.
