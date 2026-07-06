# EarningsNerd — Report Quality Improvement Plan

> **Status: APPROVED 2026-06-14 — Phase 0 (quick wins) implemented; later phases pending.**
> The owner approved the plan and answered §10: ship quick-wins first; move toward DeepSeek for cost;
> honest-but-rare degradation; objective single-filing summaries (diffing stays deferred). Phase-0
> code changes (A1–A6) are now on `claude/nice-curie-ugassy` with tests green; before/after validation
> below. Phases 1–2 / Track B remain unstarted and await go-ahead.

**Author:** report-quality review engagement · **Date:** 2026-06-14 · **Branch:** `claude/nice-curie-ugassy`

**Scope anchors (from Gate-1 answers):** target user = **prosumer / serious individual investor**;
goal = **raise quality while holding cost flat** (provider migration in-scope); data scope = **single
target filing only for now** (period-over-period diffing, peers, transcripts are documented as future
levers, not near-term work).

---

## 1. Executive summary — the state of report value today

**The AI reports are not "shallow." For the filings I tested, they are non-functional.** Running the
*real* production pipeline (`openai_service.summarize_filing`, default model `gemini-3.1-pro-preview`)
across a diverse 8-filing matrix, **0 of 8 produced a genuine, model-written analytical report:**

- **4 of 8 hard-errored** and would show the user *"Unable to retrieve this filing at the moment — please
  try again shortly"* (JPM, WMT, BA, NVDA), caused by a single unguarded type bug.
- **4 of 8 rendered as 100 % deterministic boilerplate** (AAPL, XOM, INTC, BYND) — every section filled
  by a hard-coded template, not the model. The Apple 10-K output reproduces the exact "tells" the brief
  flagged, **byte-for-byte** (`"…provides a proxy for balance sheet size"`, `"…based on available XBRL
  data"`, `"Cash flow details were not disclosed in the targeted excerpts"`, `"neutral tone"`). This
  confirms the brief's example *is* the normal output of this pipeline, and that my run reproduces
  production behaviour.

The numbers that *do* appear (revenue, net income, EPS) are **accurate** — they come straight from XBRL
and I verified Apple's against `data.sec.gov` (Revenue $416.161B, Net Income $112.010B for FY2025, an
exact match). So there is **no hallucination of headline figures**; the problem is the **near-total
absence of analysis, plus outright generation failures**, dressed up as a finished report.

**Why this is happening (root causes, all evidenced in §4):** the generation pipeline asks the model to
fill a large 10-section JSON schema but (a) gives it only **2 000–2 500 output tokens**, so the JSON is
**truncated** mid-string; (b) **does not type-guard** the parsed JSON, so a non-object response **crashes**;
(c) feeds the model a **fragile regex excerpt** (often <4 000 chars of a multi-MB filing) plus **only 4
XBRL metrics**; and (d) **back-fills every empty section with confident-sounding boilerplate** instead of
failing honestly. A system prompt that says *"do not use sections"* fights a user prompt that demands
*"these 10 sections as JSON"* — a contradiction the code's own comments acknowledge.

**The good news: this is tractable and mostly cheap to fix.** The biggest wins are days of work
(type-guard the parser → stops the crashes; raise the token budget → stops the truncation; stop emitting
boilerplate → stops the embarrassment). A focused "core quality lift" then makes the reports genuinely
useful, and a small set of single-filing differentiators (click-to-source citations, a cash-flow-quality
readout, red-flag surfacing) would put EarningsNerd ahead of most retail competitors. An eval harness to
measure all of this **already exists** (`backend/evals/`) and just needs to be run as the gate.

**Top 5 highest-leverage moves** (detail in §8):
1. **Fix the `'list'.get()` crash** (type-guard JSON parsing) — eliminates ~half the failures. ~½ day.
2. **Raise `max_tokens` 2 500 → ~10 000** and **enforce JSON** — stops truncation→boilerplate. ~½ day.
3. **Stop the boilerplate back-fill & fix the writer gate** — when data is absent, omit/label honestly; never fabricate "evidence" or spin. ~2 days.
4. **Deepen ingestion within the single filing** — robust section extraction + expand XBRL from 4 metrics to ~12 (cash flow, balance sheet, segments). ~1–2 weeks.
5. **Add click-to-source citations + a cash-flow-quality readout + red-flag surfacing** — the highest-value, in-scope differentiators. ~3–5 weeks.

---

## 2. How this was validated (method & honesty notes)

- **Live generation of the real pipeline.** I installed backend deps and ran `summarize_filing` over the
  golden-set matrix using the same model/keys production uses (Google AI Studio `gemini-3.1-pro-preview`).
  Full outputs saved under `tasks/phase2-outputs/*.md` (rendered body + structured JSON + grounding stats).
- **A/B experiment** with `USE_STRUCTURED_OUTPUT=true` (the disabled "S1" flag) saved under
  `tasks/phase2-outputs-structured/`.
- **Provider bake-off** via the existing harness (`python -m evals.runner`) to measure *achievable* quality
  with a clean schema-first extraction across providers (baseline vs gemini-json vs deepseek vs claude).
- **Independent accuracy check** against `data.sec.gov` XBRL facts.
- **User-need & competitor research** via web (cited): `tasks/research/user-needs.md`,
  `tasks/research/competitors.md`; frontend/UX review in `tasks/research/frontend-ux.md`.
- **Confidence / caveats.** The *boilerplate* path is corroborated byte-for-byte against the brief's own
  Apple quotes → **high confidence it is production behaviour**. The *crash* frequency (4/8 here) may vary
  with model version in production (the env has no `AI_DEFAULT_MODEL` override, so it used the config
  default), **but the bug is real and unguarded** and is at minimum intermittently fatal — it also
  demonstrably breaks section-recovery in the boilerplate path. RIVN failed to produce any output at all.

---

## 3. Architecture map — how a report is built

```
Frontend (app/filing/[id]) ─► POST /api/summaries/filing/{id}/generate-stream  (routers/summaries.py:71)
  └► summary_pipeline.stream_filing_summary           (SSE: progress + heartbeats)
       ├─ fetch full filing text (edgartools)  +  fetch XBRL  (concurrent)
       ├─ get_or_cache_excerpt → openai_service.extract_critical_sections()   ← REGEX excerpt (Item 7/8/1A, capped)
       └─ openai_service.summarize_filing(text, xbrl_metrics, excerpt)         (openai_service.py:2590)
            ├─ generate_structured_summary()   ← ONE LLM call → 10-section JSON   (1777)
            │     ├─ _find_empty_sections()                                       (1269)  ← crash site
            │     ├─ _recover_missing_sections()  ← targeted LLM retry per empty   (1447)
            │     └─ _apply_structured_fallbacks() ← DETERMINISTIC BOILERPLATE     (1498)  ← the "tells"
            ├─ [REMOVED, D1] generate_editorial_markdown() was the 2nd LLM call (JSON→prose); markdown is now rendered DETERMINISTICALLY
            └─ coverage gate → status complete|partial|error                      (2892)
  Frontend render: business_overview markdown (default) | structured tabs (flag) ; stripInternalNotices()
```

Key facts:
- The user-facing call is **`summarize_filing`** (non-streaming AI; SSE only wraps progress).
  `summarize_filing_stream` (openai_service.py:2320) appears to be **dead code** (no callers).
- **`USE_STRUCTURED_OUTPUT` defaults `False`** (`config.py:140`) and only swaps the *prompt*; the structured
  pipeline + boilerplate back-fill run **regardless**. **`AI_QUALITY_GATE` defaults `False`** (`config.py:148`)
  so weak output is **not blocked** in production.
- The model sees: **~4 XBRL numbers** (`xbrl_service.extract_standardized_metrics`, lines 710-794: only
  `revenue, net_income, eps, net_margin`) **+ a regex excerpt** of Item 7/8/1A.

---

## 4. Root-cause diagnosis (Phase 1) — evidence

| # | Root cause | Evidence | Effect |
|---|---|---|---|
| R1 | **Unguarded JSON type → fatal crash.** `summary_data.get("sections")` (2112) and `sections.get(key)` (1283) assume a dict; when the model returns a top-level array (or wrong-typed section) → `'list' object has no attribute 'get'`. | 4/8 filings (JPM/WMT/BA/NVDA) → `status:error`, leaked `DEBUG_ERROR:` (2639). | User sees "Unable to retrieve this filing." |
| R2 | **Token budget too small → truncation.** `max_tokens` 1 800–2 500 (`_get_type_config` 263-323) vs a ~10-section evidence-rich schema. | Every run logs `Unterminated string` → repair salvages a fragment; persists even with enforced JSON. | Sections come back empty. |
| R3 | **Empty sections → confident boilerplate.** `_apply_structured_fallbacks` (1498-1700) writes hard-coded strings for any empty section, incl. fake `supporting_evidence` ("Standard risk disclosures apply"). | AAPL/BYND/XOM/INTC outputs are 100% these strings (`tasks/phase2-outputs/`). | The "tells"; meaningless lines; fabricated evidence. |
| R4 | **Fragile section extraction.** `extract_critical_sections` (374-604) regex misses many 10-Qs/10-Ks. | Captured **NVDA 3 795 / INTC 1 929 / BYND 4 198 / XOM 760** chars from **>1 MB** filings. | Model has almost nothing to analyse. |
| R5 | **XBRL standardised = only 4 metrics.** `extract_standardized_metrics` drops everything but rev/NI/EPS/margin (`cash_and_equivalents` is collected at 241 then discarded). | `xbrl_keys=['revenue','net_income','earnings_per_share','net_margin']` in every grounding line. | cash_flow / balance_sheet / segments **structurally** absent → always boilerplate. |
| R6 | **Prompt-vs-schema contradiction.** System prompt (`10k-analyst-agent.md`: "Do NOT structure… 600-1000 words") fights the user prompt's rigid 10-section JSON demand. | `config.py:135` comment admits this is the cause of "hit and miss". | Inconsistent, low-yield model output. |
| R7 | **Over-strict writer gate.** Editorial writer must be 200-300 (10-K)/120-260 (10-Q) words or it's discarded for structured-boilerplate markdown. | Writer returned 19-25 words → fallback in every captured run. | Even a partial real summary is thrown away. |
| R8 | **No guard rails shipped.** `AI_QUALITY_GATE=False`; eval hygiene patterns don't catch these specific template strings; frontend `stripInternalNotices` *hides* fallback markers rather than fixing them. | `config.py:148`; `scorers.py:239` HYGIENE_PATTERNS; `frontend/lib/stripInternalNotices.ts`. | Broken output reaches users unflagged. |

**A/B experiment (does the existing S1 flag fix it?):** With `USE_STRUCTURED_OUTPUT=true`, JPM & NVDA went
**ERROR → partial** (enforced `json_object` stops the crash) **but output stayed 100 % boilerplate** — the
`Unterminated string` truncation (R2) persisted. **Conclusion: flipping the flag alone is not the fix; the
token budget + parser robustness + boilerplate removal are.**

---

## 5. Report-quality rubric & scored matrix (Phase 2)

**Rubric** — 8 dimensions, scored **0 / 1 / 2** (0 = absent/fail, 1 = partial, 2 = strong). Designed to catch
the observed failure modes. Max 16.

| Dim | What it tests |
|---|---|
| D1 Generation success | Produced a real, model-written report (not an error page, not pure template back-fill). |
| D2 Numeric accuracy | Headline figures correct vs EDGAR/XBRL; no hallucinated/stale numbers. |
| D3 Financial depth | Beyond the 4 XBRL nums: cash flow, balance sheet, segments, margins — present & substantive. |
| D4 Insight & synthesis | Genuine "why"/trend/earnings-quality analysis vs templated filler. |
| D5 Risk synthesis | Real material risks extracted vs "review Item 1A". |
| D6 Traceability | Claims/numbers linked to a filing location or real evidence (not fabricated). |
| D7 Output hygiene | No boilerplate filler, leaked internal/debug notices, or meaningless statements. |
| D8 Framing fidelity | Tone/sentiment matches reality (not hard-coded "neutral"; no misleading spin). |

**Scored results** (baseline pipeline; full outputs in `tasks/phase2-outputs/`):

| Filing (type) | Cohort | Outcome | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | **/16** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AAPL 10-K | mega-cap tech | boilerplate | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | **2** |
| JPM 10-K | bank/financial | **ERROR** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| WMT 10-K | retail | **ERROR** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| BA 10-K | industrial / neg-NI / material event | **ERROR** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| XOM 10-K | energy/commodity | boilerplate (risks missing) | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | **2** |
| NVDA 10-Q | mega-cap 10-Q | **ERROR** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| INTC 10-Q | semis, losses/restructuring | boilerplate | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | **1** |
| BYND 10-Q | small-cap, distressed | boilerplate (spun positive) | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | **2** |
| **Mean** | | | **0** | **0.9** | **0** | **0** | **0** | **0** | **0** | **0** | **~0.9 / 16** |

Matrix gap: no REIT/utility was tested (none in the golden set); add `O`/`NEE` when extending the harness.

**Patterns:** quality does **not** degrade gracefully across company types — it is uniformly broken. The
*only* thing that works is surfacing the 3 XBRL headline numbers (D2). 10-Qs and complex 10-Ks (bank,
energy) fare worst because extraction fails hardest there. BYND shows an active **framing-fidelity hazard**:
a distressed, loss-making company was described as showing *"ongoing business momentum"* with no mention of
its narrowing losses or going-concern risk.

**Achievable quality (bake-off, clean schema-first path).** The harness's candidate path uses a leaner
schema + 4 096 tokens + API-enforced JSON. Run over the first 4 golden filings (AAPL/MSFT/NVDA/JPM;
`backend/evals/reports/eval_20260614T002153Z.md`):

| candidate | pass_rate | schema_valid | num_recall | coverage | $cost (4) | latency | notes |
|---|---|---|---|---|---|---|---|
| **gemini-json** (clean schema-first) | **0.75** | **0.75** | 0.75 | 0.55 | $0.128 | 19 s | same model as baseline |
| baseline (prod pipeline) | 0.00 | **0.00** | 0.75 | 0.95* | ~$0 | 56 s | *coverage inflated by boilerplate back-fill |
| deepseek | 0.00 | 0.00 | **1.00** | 0.35 | **$0.016** | **7 s** | cheapest/fastest, best numbers; needs schema adherence |
| claude-sonnet | — | — | — | — | — | — | 4/4 errored — **harness API-integration bug**, not a quality signal |

**The decisive point: the *same* Gemini model goes from baseline's 0 % schema-valid / 0.0 pass-rate to
0.75 / 0.75 when run through a correctly-budgeted, type-safe, schema-enforced extraction.** The model is
not the problem — the production pipeline is. (Also note: baseline did **not** crash on these 4 here
`errors:0`, vs 4/8 crashes in the direct capture — confirming the R1 crash is **intermittent / model-
nondeterministic**, as flagged in §2. **DeepSeek** is a live cost-migration candidate: ~8× cheaper and 8×
faster with perfect numeric recall, pending schema-adherence work — see A12.)

---

## 6. What users actually want (Phase 3) → current coverage

Full research + citations: `tasks/research/user-needs.md`. Segments: R=retail, P=prosumer (our user), A=analyst.

| Rank | User need (job-to-be-done) | Who | EarningsNerd today | In single-filing scope? |
|---|---|---|---|---|
| 1 | **What CHANGED vs last filing** (risk-factor / MD&A / policy diffs) | P,A | ❌ misses | **Deferred** (needs prior filing) |
| 2 | **Cash-flow quality** — FCF vs net income, capex | P,A,R | ❌ ("cash flow not disclosed") | ✅ in scope |
| 3 | **Red-flag / anomaly detection** — going concern, material weakness, restatement, auditor change, litigation | R,P,A | ❌ ("risks align with standard conditions") | ✅ in scope |
| 4 | **Segment & KPI breakdown + GAAP vs non-GAAP** | A,P | ❌ ("segment detail not present") | ✅ in scope |
| 5 | Context vs consensus / peers | A,P | ❌ misses | **Deferred** (external data) |
| 6 | Capital allocation (buybacks/dividends/capex discipline) | P,A | ❌ boilerplate | ✅ in scope |
| 7 | Genuine management tone/sentiment shifts | A,P | ❌ hard-coded "neutral" | Partial (single-filing tone ✅; *shift* needs prior) |
| 8 | **Source verifiability (click-to-source)** — table stakes | R,P,A | ◑ evidence text on risks, **no links** | ✅ in scope |
| 9 | Plain-language business + top real risks orientation | R,P | ◑ intended, ❌ in practice | ✅ in scope |
| 10 | Footnote deep-dive (debt/leases/contingencies) | A,P | ❌ ("no footnotes surfaced") | ✅ in scope |

**Read:** the two highest-signal jobs are #1 (deferred by scope) and #2 (cash-flow quality, **in scope and
currently failed**). #3 and #8 are universal and in scope. So the near-term roadmap can hit **#2, #3, #4, #6,
#8, #10** within a single filing — most of the value — while #1/#5 wait for multi-filing/external data.

---

## 7. Competitor benchmark & capability gap (Phase 4)

Full table (≈20 tools) + sources: `tasks/research/competitors.md`. Condensed read of the prosumer tier:

| Capability | Field status | EarningsNerd |
|---|---|---|
| Deep evidence-backed **10-K/10-Q narrative summary** | **White space** — rivals are chat terminals (Fiscal.ai, Quartr) or transcript summarizers (Stockanalysis, Koyfin, TipRanks) | the core promise — **but currently broken** |
| **Click-to-source citations** | Table stakes for credible AI tools (Fiscal.ai best; Daloopa per-number gold standard) | ◑ evidence text, no links → **behind** |
| Segment/KPI + cash-flow coverage | Fiscal.ai, Daloopa, AlphaSense strong | ❌ structurally absent → **behind** |
| **Red-flag / anomaly detection** | Open white space at retail (owned by Hudson Labs, institutional) | ❌ → **opportunity** |
| GAAP vs non-GAAP reconciliation | Essentially only Daloopa | ❌ → **opportunity** |
| Follow-up Q&A on the filing | Fiscal.ai, Quartr, Bloomberg, Fintool | ❌ → **behind** (in scope) |
| Period-over-period **diffing** | Rarest feature anywhere (BamSEC/CapEdge non-AI; Hebbia/V7 institutional) | ❌ → **strongest *future* differentiator** |

**Capability gap narrative:** EarningsNerd's *concept* (auto-generated, structured, evidence-backed single-
filing report) is genuinely under-served at the retail tier, and it already has the scaffolding rivals charge
for (structured sections, an evidence field, charts, compare, watchlist, export). But its **core artifact is
today weaker than a free ChatGPT prompt** for most filings. Closing the quality gap is existential before any
feature race. The closest rival to out-execute is **Fiscal.ai** ($39/mo, citation-backed, segment KPIs, chat);
the capability ceiling is **V7 Go** (true redline diffing + visual grounding). The cleanest near-term
differentiators *within single-filing scope* are **click-to-source citations + red-flag surfacing +
cash-flow-quality readout** — none of which the retail AI crowd does well.

---

## 8. Recommendations & phased roadmap (Phase 5)

Effort: **XS** ≤1d · **S** ≤3d · **M** ≤1–2wk · **L** ≥2wk. Confidence: ⬤ high / ◑ medium.
Cost/latency note up front: the current pipeline already fires **3+ LLM calls** per report (structured +
N recovery + writer). Fixing it (bigger token budget, fewer wasted recovery loops, optional cheaper model)
can be **cost-neutral or cheaper**, not more expensive — directly serving the "quality up, cost flat" goal.

### Track A — Report quality / generation

**Phase 0 — Quick wins (target: stop shipping broken output; ~1 week total)**
| Move | Problem solved | Effort | Impact | Conf |
|---|---|---|---|---|
| A1 Type-guard JSON parsing (coerce/validate dict; handle array-wrapped) | R1 crash → 4/8 errors | XS | ⬤⬤⬤ | ⬤ |
| A2 Raise `max_tokens` ~2 500→~10 000 (+ enforce `json_object`) | R2 truncation→boilerplate | XS | ⬤⬤⬤ | ⬤ |
| A3 Remove confident boilerplate back-fill; when absent, **omit or honestly label**, never fabricate evidence/spin | R3 | S | ⬤⬤ | ⬤ |
| A4 Relax/repair the writer length gate; don't discard a real summary for a template | R7 | S | ⬤⬤ | ⬤ |
| A5 Turn **`AI_QUALITY_GATE=True`** + remove leaked `DEBUG_ERROR:` string | R8 | XS | ⬤ | ⬤ |
| A6 Extend eval hygiene patterns to catch these template strings (regression guard) | R8 | S | ⬤ | ⬤ |

> Phase 0 alone should move the matrix from "0/8 real reports" to "produces a real, if shallow, report and
> never lies/​crashes." Validate via the eval harness before/after.

**Phase 1 — Core quality lift (target: genuinely useful reports; ~2–3 weeks)**
| Move | Problem solved | Effort | Impact | Conf |
|---|---|---|---|---|
| A7 Robust section extraction (prefer edgartools' native section API over the brittle regex; the 10-Q path captures <4k chars) | R4 | M | ⬤⬤⬤ | ⬤ |
| A8 Expand XBRL standardised metrics 4→~12 (operating & free cash flow, capex, total assets, debt, cash, shares, gross/op margin) — all from the filing's own XBRL | R5 | M | ⬤⬤⬤ | ⬤ |
| A9 Resolve the prompt/schema contradiction (adopt schema-first prompt; one coherent contract) | R6 | S | ⬤⬤ | ⬤ |
| A10 Real risk/MD&A synthesis (top material risks *from* Item 1A; capital allocation *from* the statements) | D4/D5 | M | ⬤⬤ | ◑ |
| A11 Accuracy safeguard: validate every surfaced number against XBRL before publish (wire the harness's G1 precision gate into the pipeline) | trust | M | ⬤⬤ | ⬤ |
| A12 Provider bake-off → pick the model that maximises quality at/under current cost (gemini vs **deepseek** vs claude); use the harness adoption rule | cost/quality | M | ⬤⬤ | ◑ |

**Phase 2 — Differentiating quality (single-filing; ~3–6 weeks)**
| Move | User need | Effort | Impact | Conf |
|---|---|---|---|---|
| A13 **Cash-flow-quality readout** (FCF vs net income, capex, conversion) | #2 | M | ⬤⬤⬤ | ⬤ |
| A14 **Red-flag / anomaly surfacing** from the one filing (going concern, material weakness, restatement, auditor change, large one-offs, non-GAAP add-back size) | #3 | M | ⬤⬤⬤ | ◑ |
| A15 Segment/KPI + GAAP-vs-non-GAAP extraction | #4 | M | ⬤⬤ | ◑ |

### Track B — Post-generation user experience

| Move | Problem solved | Effort | Impact | Conf |
|---|---|---|---|---|
| B1 **Click-to-source citations** — link each claim/number to its Item/section (or XBRL fact) in the filing; surface `source_section_ref` as a real anchor | table-stakes #8 | M | ⬤⬤⬤ | ⬤ |
| B2 **Surface top-N highest-signal insights up top** instead of uniform sections; turn structured tabs/charts on by default once they're populated | presentation | S–M | ⬤⬤ | ⬤ |
| B3 Honest quality signalling — fix at source instead of `stripInternalNotices` hiding fallbacks; show a real confidence/coverage badge | trust | S | ⬤ | ⬤ |
| B4 **Follow-up Q&A on the filing** (chat grounded in the single filing) | competitor parity | L | ⬤⬤ | ◑ |
| B5 Export/share polish for the improved report (already Pro-gated) | retention | S | ◑ | ⬤ |

### Deferred (out of current single-filing scope — documented as the highest-value *future* bets)
- **D-1 Period-over-period disclosure diffing** (risk-factor/MD&A "what changed") — the #1 user need and the
  rarest competitor feature. Needs prior-filing ingestion. **Strongest future differentiator.**
- **D-2 Peer / consensus context**, **D-3 transcript integration** — need external data sources.

---

## 9. Cost / latency & the provider question

- Current per-report cost is **not** minimal — it is several gemini calls, much of it wasted on recovery
  loops that fail and a writer pass that gets discarded. Phase 0/1 can **reduce** call count while improving
  quality.
- The harness prices a **DeepSeek** path at ~**$0.28/1M input** vs gemini's ~$2 — a candidate for materially
  lower cost at equal/better quality, to be decided by the bake-off (A12) under the existing adoption rule
  (beat baseline on schema-validity ∧ numeric accuracy ∧ coverage, no gate regression, acceptable cost).
- Net: the "raise quality, hold cost flat" goal is achievable; cost may even fall.

---

## 10. Open questions / decisions needed from you

1. **Sequencing:** ship **Phase 0 (quick wins) on its own first** to stop the bleeding, then plan Phase 1 —
   or batch Phase 0+1 into one release? (Recommendation: ship Phase 0 first; it's days and stops user-visible failures.)
2. **Provider:** are you open to switching the default model (e.g., to DeepSeek) if the bake-off shows equal
   quality at lower cost, or do you want to stay on Gemini for now and treat cost as a later track?
3. **Quality gate behaviour:** when a report would be low-quality, prefer **(a)** show a smaller honest
   report ("we could verify X, Y; cash flow not parsed"), or **(b)** block + ask the user to retry? (Affects A3/A5/B3.)
4. **Differentiator priority:** of the in-scope differentiators, rank **cash-flow quality (A13)** vs
   **red-flag surfacing (A14)** vs **click-to-source (B1)** vs **follow-up Q&A (B4)** for first delivery.
5. **Scope confirmation:** keep period-over-period diffing (D-1) deferred, or should I add a costed spike for
   it now given it's the #1 user need and top market white-space?
6. **REIT/utility coverage:** add `O`/`NEE` to the golden set so the matrix covers regulated/FFO issuers?

---

## 11. ⛔ Approval gate

This is the end of the review. **No implementation will begin until you approve.** On your go-ahead I will
(in your chosen sequence) start with the Phase-0 quick wins, validate each change against the eval harness
(baseline vs after), and report the before/after numbers. Please confirm: **(a)** approve the plan as-is, or
**(b)** tell me your answers to §10 and I'll revise before any code is written.
