# Report Quality Review — Scratchpad (branch: claude/nice-curie-ugassy)

Engagement: review report-generation pipeline + report quality, research user needs &
competitors, deliver an approval-ready improvement plan. **No production code until plan approved.**

## Gate 1 answers (from user)
- **Target user:** Prosumer / serious individuals (depth: KPIs, segments, cash-flow quality, non-GAAP recon).
- **Quality vs cost:** Balance — raise quality, hold cost flat. Provider migration in-scope.
- **Phase 2:** Generate live across matrix (~8–10 cos). Keys+network verified present.
- **Data scope:** Single filing only for now. (PoP diffing/peer/transcripts = documented-but-deferred.)

## Environment (verified)
- Keys: OPENAI_API_KEY (Google AI Studio), ANTHROPIC_API_KEY, DEEPSEEK_API_KEY. No Kimi/Qwen/FMP/Finnhub.
- DATABASE_URL NOT set → use eval-harness path (fetches EDGAR directly), not DB app path.
- Network egress OPEN: sec.gov 200, data.sec.gov 200, Google AI reachable.

## Key facts found
- Eval harness already exists: backend/evals/ (golden_set.json, scorers, runner, judge, RUNBOOK).
- Prompts: prompts/10k-analyst-agent.md, 10k-structured-agent.md, 10q-* (analyst + structured).
- Core gen: app/services/openai_service.py (2935 lines) — contains the "targeted excerpts" tell.
- Prior planning docs: docs/history/plans/FILING_SUMMARY_IMPROVEMENT_PLAN.md,
  tasks/eval-hardening-todo.md, tasks/activation-gap-analysis.md.

## Phase tracker
- [x] Gate 1 — clarifying questions asked & answered
- [x] Phase 1 — architecture map + ingestion/pipeline diagnosis (root causes R1-R8)
- [x] Phase 2 — live-generated + scored matrix (8 filings; 0/8 real reports) + rubric
- [x] Phase 3 — user-needs research (ranked) + coverage map
- [x] Phase 4 — competitor benchmarking (~20 tools)
- [x] Phase 5 — synthesis & recommendations (2 tracks + roadmap)
- [x] Gate 2 — docs/report-quality-improvement-plan.md written → STOP for approval
- [~] (supplementary) provider bake-off running in background; fold numbers into §5 when done

## Findings log (evidence: file:line / output / source)

### PHASE 1 — P1.0 + P1.1 IMPLEMENTED + VALIDATED (2026-06-14)Model decision: DEFAULT = deepseek-v4-pro (non-thinking). Web-verified newest (V4, Apr 2026);
deepseek-chat legacy alias retires Jul 24 2026. flash hallucinates on thin input (fabricated JPM
Dimon quote) → pro chosen; still ~4x cheaper than Gemini. Non-thinking = extra_body {"thinking":{"type":"disabled"}}.

P1.1 (financial depth): xbrl extraction 4 metrics → 15. Added cash-flow + balance-sheet + margin
concepts to instance_extractor DURATION/INSTANT_CONCEPTS (auto-flow via generic loop) + statement
fallback (added cash_flow_statement) + extract_standardized_metrics derives FCF (ocf-|capex|),
gross/operating margin + standardizes total_assets/cash/equity/long_term_debt. generate_structured_summary
xbrl_section now feeds all 15 with prior-period YoY. Issuer-safe: no GrossProfit concept → no bogus
bank gross margin (JPM verified).
P1.0 (measurement): score_financial_depth scorer (cash_flow/balance_sheet/margins, term-near-number,
placeholder-aware) wired into RubricScore.financial_depth + runner report `depth` column. 2 unit tests.

Live validation (DeepSeek v4-pro, tasks/phase2-outputs-p1/):
- NVDA 10-Q (thin 3.8k excerpt): BEFORE = "cash flow not observed"; AFTER = full income stmt +
  gross/op/net margins + Operating CF $50.3B + FCF $48.6B, all with YoY. The honest-but-thin → deep win.
- JPM 10-K (bank): AFTER = Total Assets $4.42T (+10.5% YoY), correct net-income DECLINE -2.4%, NO
  bogus gross margin. (Narrative still thin → P1.2.)
- AAPL: even deeper.
Writer still fails (now for being TOO long, 298-372 words) → confirms 3a (drop writer, P1.4).
241 unit+smoke tests pass. NEXT: P1.2 (full-filing markdown ingestion), P1.3 (issuer-type), P1.4
(objective prompt + drop writer), P1.5 (reconcile), P1.6 (bake-off).

## Findings log (earlier phases below)

### PHASE 0 IMPLEMENTED + VALIDATED (approved 2026-06-14) — commit 89aad89
Changes A1-A6 (config.py, openai_service.py, summary_generation_service.py, evals/scorers.py).
Before/after live regen of the 4 previously-failing filings (tasks/phase2-outputs-after/), DEFAULT path:
| Filing | BEFORE | AFTER | note |
| AAPL 10-K | boilerplate | RICH genuine report (cash flow, balance sheet, 3 cited risks, mgmt quotes) | excerpt 50k |
| JPM 10-K | ERROR (crash) | partial, accurate #s, honest narrative gaps | bank: 50k excerpt mis-targeted → R4/A7 |
| NVDA 10-Q | ERROR (crash) | partial, real #s+themes+quote, honest gaps | excerpt 3.8k → R4/A7 |
| WMT 10-K | ERROR (crash) | (validating) | |
Result: 0 crashes (was 4/4 on these), 0 fabricated boilerplate. Crash fix (A1) + truncation fix
(A2) confirmed. Residual = thin extraction on bank/10-Q (R4 → Phase 1 A7) + model still emits
subjective adjectives "robust"/"exceptional" (→ Phase 1 A9 objective-prompt hardening) + EPS
basic-vs-diluted (→ A11 reconciliation). 239 unit+smoke tests pass.

Phase 1 next (await go-ahead): A7 extraction, A8 XBRL 4→~12 metrics, A9 objective schema-first
prompt, A11 XBRL number reconciliation, A12 DeepSeek bake-off. Then Track B: B1 click-to-source,
B2 top-insights-first, A13 cash-flow-quality readout.

## Findings log (earlier phases below)

### PHASE 1 — Pipeline diagnosis (ROOT-CAUSE FOUND)
Production user path: summaries.py:71 → summary_pipeline.stream_filing_summary →
summary_pipeline.py:394 openai_service.summarize_filing (NOT summarize_filing_stream — that
method, openai_service.py:2320, appears to be DEAD CODE / no callers).

summarize_filing (2590) = 2-stage LLM pipeline:
  1. generate_structured_summary (1777): ONE LLM call → 10-section JSON (schema_template 1861-1959).
  2. _recover_missing_sections (1447): targeted LLM retry for empty sections (cheaper model, A11).
  3. _apply_structured_fallbacks (1498): deterministic templater fills STILL-empty sections.
  4. generate_editorial_markdown (2135): 2nd LLM call, JSON→prose markdown (=business_overview).
  5. coverage gate (2892-2911): coverage_ratio<0.5 or writer issue → status "partial".

**ROOT CAUSE of shallow boilerplate:** the exact "tells" the task flagged are HARD-CODED template
strings in _apply_structured_fallbacks, NOT LLM output:
  - openai_service.py:1567 "Net margin tracked at {x} based on available XBRL data."
  - :1624 "Cash flow details were not disclosed in the targeted excerpts; monitor future filings…"
  - :1628 "Revenue scale of {x} provides a proxy for balance sheet size." (meaningless)
  - :1637 "Risk factors for this period align with standard operational and market conditions…"
  - :1648 "Management's discussion focused on operational execution and market conditions…"
They fire when a section comes back empty → user sees confident-sounding hollow filler.

**WHY sections come back empty = INGESTION DEPTH (the big lever):**
  - XBRL "standardized" = ONLY 4 metrics: revenue, net_income, eps, net_margin
    (xbrl_service.py:710-794). NO cash flow / balance sheet / debt / segments — even though
    cash_and_equivalents is collected one layer down (xbrl_service.py:241) then dropped.
  - Text = regex-extracted Item 7/8/1A only, each capped (Item 8 → 40k chars: income stmt +
    balance sheet consume that BEFORE the cash-flow statement) (extract_critical_sections 374-604).
  - So model is asked (schema 1861-1959) to populate cash_flow, balance_sheet, segments,
    covenants, 3-yr trend — from ~4 numbers + capped excerpts → can't → empty → boilerplate.
  - The AAPL "$416.2B proxy for balance sheet size" in the task = golden_set AAPL FY2025 rev
    $416.161B → confirms task's example IS this pipeline's fallback path.

**Prompt-vs-schema contradiction (config.py:135 admits it):** summarize_filing_stream loads
10k-analyst-agent.md ("Do NOT structure into sections, write 600-1000 word cohesive markdown")
as system prompt, then user prompt demands rigid 9/10-section JSON. USE_STRUCTURED_OUTPUT
(config.py:140) default False = legacy contradictory prompt is live; flag only swaps the prompt,
the structured pipeline + fallbacks run REGARDLESS. AI_QUALITY_GATE default False (config.py:148)
= weak output not blocked in prod.

### Eval harness (Phase 2 tooling)
evals/runner.py baseline candidate runs the REAL summarize_filing pipeline (119-133) but does NOT
persist the report text → need a capture script to read actual outputs.
golden_set.json = 19 verified FY2025/26 filings spanning matrix (AAPL/MSFT/NVDA/AMZN, JPM/BRK.B,
WMT/COST/KO, BA/F/TSLA/XOM, RIVN/COIN/INTC/PLTR, PFE, BYND small-cap). GAP: no REIT/utility.
Ground truth = only revenue/net_income/eps (mirrors the shallow extraction).

### PHASE 2 — LIVE GENERATION RESULTS (the headline finding) — tasks/phase2-outputs/
Ran the REAL summarize_filing pipeline (gemini-3.1-pro-preview, prod default) over the matrix.
**0 of 7 filings produced a genuine model-written report.**
| Filing | status | excerpt chars | outcome |
| AAPL 10-K | partial | 50,000 | 100% boilerplate (== task's exact Apple example, byte-identical) |
| BA   10-K | ERROR  | 50,000 | 'list'.get() crash → "Unable to retrieve this filing" |
| JPM  10-K | ERROR  | 50,000 | crash → "Unable to retrieve" |
| WMT  10-K | ERROR  | 50,000 | crash → "Unable to retrieve" |
| NVDA 10-Q | ERROR  | 3,795  | crash → "Unable to retrieve" |
| BYND 10-Q | partial| 4,198  | 100% boilerplate + recovery crash + writer fail |
| XOM  10-K | partial| 760    | boilerplate; missing risk_factors |

Two converging failure modes (both reproduce the task's symptoms):
1. **'list' object has no attribute 'get' CRASH (4/7, fatal).** openai_service.py:2112
   `summary_data.get("sections")` and :1283 `sections.get(key)` and _apply_structured_fallbacks
   assume the model returned a JSON OBJECT. When gemini returns a top-level ARRAY (or a section as
   wrong type), .get() throws → caught at 2634 → user sees "Unable to retrieve" + leaked
   "DEBUG_ERROR:" string (2639). No type-guard anywhere. QUICK WIN.
2. **Empty-sections → 100% boilerplate (3/7).** Even AAPL (clean, 50k excerpt) returns empty
   structured sections → _apply_structured_fallbacks fills every section with templated filler →
   editorial writer gets boilerplate, returns ~25 words → fails 200-300 word gate → _build_structured_
   markdown fallback. Net: pure boilerplate, status "partial", but coverage scores 9/9 (templater fools it).

Contributing root causes (evidence):
- **max_tokens 1800-2500 too small** for the 10-section evidence-rich schema → truncation →
  "Unterminated string" (seen on BYND) → repair salvages fragment → empty sections.
- **Regex section extraction is fragile**, esp. 10-Q + some 10-K: NVDA 3,795 / BYND 4,198 / XOM 760
  chars captured from >1M-char filings (extract_critical_sections 374-604 lookaheads miss).
- **XBRL only 4 metrics** → cash_flow/balance_sheet/segments structurally absent → those sections
  ALWAYS boilerplate even when generation works.
- **Writer length gate (200-300 words 10-K / 120-260 10-Q)** discards short writer output → fallback.
- Accuracy/quality: reports add ~zero insight; BYND distressed co. spun positively ("$58.2M reflects
  ongoing business momentum") with no mention of narrowing losses/going-concern. "Revenue scale
  provides a proxy for balance sheet size" is meaningless. Headline rev/NI/EPS DO match EDGAR/XBRL.

CONFIDENCE: boilerplate path corroborated byte-for-byte vs task's Apple quotes (HIGH). Crash
frequency may vary with model/version in prod, but the type bug is real & at least intermittently fatal.

### PHASE 4 — competitors (subagents → tasks/research/competitors.md) DONE
~20 tools benchmarked. Retail white space: deep evidence-backed 10-K/10-Q narrative summarization
(most rivals = chat terminals or transcript summarizers). Closest rival = Fiscal.ai ($39, citations+
segments+chat). Table stakes = click-to-source citations. PoP diffing rare everywhere (only BamSEC/
CapEdge non-AI, TipRanks risk-only; Hebbia/V7 institutional). Red-flag detection owned by Hudson
Labs (institutional). V7 Go = capability ceiling (true redline diff + visual grounding).

### PHASE 1b — frontend/UX (subagent → tasks/research/frontend-ux.md) DONE
business_overview markdown is default body; structured tabs + charts default OFF (flags). Evidence
shown on risks only, NO click-through. No follow-up Q&A. Compare/watchlist/export(Pro) exist.
stripInternalNotices.ts HIDES backend fallback notices (papers over the problem).

### PHASE 3 — user needs (subagent → tasks/research/user-needs.md) DONE
Top: (1) what CHANGED vs last filing [deferred by scope], (2) cash-flow quality/FCF,
(3) red-flag/anomaly detection, (4) segments+KPIs/non-GAAP, (5) consensus/peers [outside filing],
(6) capital allocation, (7) genuine tone shifts, (8) click-to-source verifiability (table stakes),
(9) plain-language orientation, (10) footnote deep-dive.
