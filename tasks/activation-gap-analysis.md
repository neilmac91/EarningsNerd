# EarningsNerd — Activation Gap Analysis & Roadmap

**Date:** 2026-06-09
**Scope:** Anonymous visitor → first successful, high-quality summary ("activation").
**Method:** Read-only code audit (3 parallel subagent traces: frontend funnel, backend pipeline, AI quality) with all load-bearing claims spot-verified directly against source. No application code was modified.

---

## 1. Executive Summary

**Thesis:** EarningsNerd's activation funnel is structurally sound — anonymous users *can* reach a summary without login — but it is wrapped in a gate that hides the product, lacks a zero-wait first impression, and lands on a generation pipeline whose quality varies because the AI is given contradictory instructions, fed brittle inputs, and never quality-checked. Fix the gate, give visitors an instant pre-generated summary, and make generation deterministic-by-construction, and the activation rate ceiling rises dramatically.

The five highest-leverage gaps:

1. **The waitlist middleware can block the entire product.** `frontend/middleware.ts:40` redirects ALL traffic (including `/`, `/company/*`, `/filing/*`) to `/waitlist` unless `WAITLIST_MODE=false` is explicitly set. One env var stands between every visitor and activation.
2. **There is no zero-wait "aha" moment.** The hero's "See an Example" CTA (`app/page.tsx:92-96`) links to `/company/AAPL`, requiring 3 clicks plus a 30–80s generation wait before a first-time visitor sees the core product output. The hero mockup (`HeroMockup.tsx`) is a static image, not a live summary.
3. **The AI receives contradictory instructions with no structured-output enforcement.** The system prompt demands free-form narrative markdown ("Do NOT structure your output into predefined categories", `prompts/10k-analyst-agent.md:9-13`) while the user prompt in the same call demands "Return ONLY valid JSON" against a rigid 10-section schema (`openai_service.py:1922-1951`) — and no API-level JSON mode is used. This is the single biggest root cause of "hit and miss" output.
4. **Grounding data is unreliable by construction.** Section extraction is order-dependent regex with no content validation (`openai_service.py:347-557`), and XBRL financials get an 8-second shared budget (`summaries.py:47`) that silently returns nothing on timeout — so the same filing can produce a rich or hollow summary depending on race outcomes.
5. **Failure is hidden instead of handled.** Placeholder/fallback text is injected into empty sections (`openai_service.py:1452+`), internal failure notices are stripped client-side (`frontend/lib/stripInternalNotices.ts`), and there is no semantic quality gate or eval harness — so degraded summaries ship looking like real ones, and the team has no measurement of how often.

---

## 2. How the App Works Today

### Activation journey (corrected against code)

```
Visitor lands on /
  └─ middleware.ts:40 — if WAITLIST_MODE != 'false' → REDIRECT to /waitlist (funnel ends)
  └─ else: hero + CompanySearch + QuickAccessBar (8 preset tickers) + HotFilings
Search (CompanySearch.tsx)
  └─ 300ms debounce → GET /api/companies/search (SEC ticker cache: L1 memory + L2 Redis, 24h)
  └─ React Query retry 3x w/ backoff for 5xx/429 (CompanySearch.tsx:31-38)
Company page (/company/[ticker])
  └─ GET /api/filings/company/{ticker} — live EDGAR, 20s timeout, DB fallback (filings.py:32,358)
  └─ Filings grouped by year; user must pick type + date; CTA "Generate Filing Summary"
Filing page (/filing/[id])
  └─ Summary generation AUTO-TRIGGERS on load (page-client.tsx:395-411)
  └─ Anonymous allowed: NEXT_PUBLIC_REQUIRE_AUTH_FOR_SUMMARY defaults false (page-client.tsx:329,396)
  └─ 401 → automatic guest retry with credentials omitted (summaries-api.ts:126-137)
Streaming (POST /api/summaries/filing/{id}/generate-stream)
  └─ SSE, 3s heartbeats; client hard timeout 120s (summaries-api.ts:5-7); no auto-reconnect
  └─ Progress UI: animated circle, 4-step timeline, whimsy messages; "stalled" warning at 15s
Render
  └─ ReactMarkdown of business_overview + FinancialMetricsTable
  └─ stripInternalNotices() removes failure disclaimers; placeholder sections hidden client-side
```

### Summary generation pipeline (backend)

```
generate-stream (summaries.py)
  ├─ Rate limit: 5 req/60s per user-or-guest-IP (summaries.py:41,191)
  ├─ Monthly quota: FREE_TIER_SUMMARY_LIMIT=5 — AUTHENTICATED USERS ONLY (summaries.py:339-352);
  │    anonymous users have NO monthly cap (only the 5/60s window)
  ├─ Hard pipeline timeout: 90s (summaries.py:44) vs endpoint middleware timeout 120s (main.py:213)
  ├─ Step 1: Fetch filing doc from SEC (~5-15s; FilingContentCache, 24h validity, summaries.py:325-336)
  ├─ Step 2: extract_critical_sections — regex extraction of Item 7/8 or Item 1/2 (openai_service.py:347-557)
  ├─ Step 3: XBRL + excerpt enrichment — shared 8s asyncio.wait_for (summaries.py:47,524-527); silent None on timeout
  ├─ Step 4: AI call — gemini-3-pro-preview, two-phase:
  │    Phase A: structured JSON extraction, max_retries=1 (openai_service.py:1959), JSON repair (@790)
  │    Phase B: editorial markdown from JSON, validation + max 2 retries (@2164), else deterministic
  │             _build_structured_markdown fallback (@1059)
  │    + parallel "section recovery" for empty sections (@1401), then placeholder injection (@1452)
  ├─ Step 5: Coverage scoring; "partial" (<3/7 sections) NOT saved to Summary table
  │    (summary_generation_service.py:575-612) but progress row persists
  └─ Timeout/AI failure → fallback_summary.generate_xbrl_summary (XBRL table + regex risk factors)
```

**CLAUDE.md corrections worth noting:** CLAUDE.md does not mention the waitlist middleware, the auto-generation-on-page-load behavior, the 90s pipeline timeout (it documents the 120s endpoint timeout only), or that anonymous summary generation is permitted and uncapped monthly.

---

## 3. Activation Funnel Teardown

Drop-off risk = estimated share of first-time visitors lost at that step, given the failure modes (directional, not measured — see Open Questions for instrumentation gap).

| # | Step | What the user sees/does | Friction / failure modes | Evidence | Drop-off risk |
|---|------|------------------------|--------------------------|----------|---------------|
| 0 | Land on `/` | Possibly nothing — redirect to /waitlist | If `WAITLIST_MODE` env not explicitly `'false'`, the entire funnel is unreachable; `/company`, `/filing` not in ALLOWED_PATHS | `middleware.ts:3-15,40-55`; `page.tsx:52-56` | **Total** (if gate on) |
| 1 | Landing page | Hero, search, 8 quick tickers, hot filings | No live example summary; "See an Example" → company page, not a summary; static mockup can't be clicked into | `page.tsx:84-96`; `HeroMockup.tsx` | High — visitor never sees the product output before investing effort |
| 2 | Search a company | Type ≥1 char, 300ms debounce, results list | Solid: retries w/ backoff, clear empty/error states. Cold SEC ticker cache or circuit-open → error banner; CircuitOpenError surfaces as generic 500 | `CompanySearch.tsx:18-40,80-114`; `companies.py:225-230` (no CircuitOpenError catch) | Low–Med |
| 3 | Pick a filing | Year-grouped list, type filter, two CTAs per filing | No "latest 10-K" default or recommendation — first-timers don't know 10-K vs 10-Q; EDGAR fetch 2–5s (20s timeout) with no skeleton loader; "View on SEC EDGAR" competes with the activation CTA | `page-client.tsx (company):140-159,274-293,299-302,371-387`; `filings.py:32,358` | Med–High |
| 4 | Filing page → generation starts | Auto-generates on load (good); progress circle + timeline | If `NEXT_PUBLIC_REQUIRE_AUTH_FOR_SUMMARY=true`: dead-end error "Please sign in" with no signup CTA; otherwise anon proceeds | `page-client.tsx (filing):329-336,395-411` | Low (default) / High (flag on) |
| 5 | Wait 30–80s | Progress %, whimsy messages, elapsed timer | **"Stalled" warning fires at 15s** — inside the *normal* generation window, signaling failure during success; total wait itself is the single largest friction (AI step alone 15–45s) | `page-client.tsx (filing):614-623`; latency: `summaries.py:44` pipeline ≤90s | **High** — longest, most anxious step |
| 6 | Stream failure paths | Red error banner + manual "Retry generation" | Client kills stream at 120s with no auto-retry/reconnect; backend pipeline dies at 90s, endpoint at 120s — three mismatched timeout layers; background task orphaning (`asyncio.create_task` fire-and-forget) can leave progress stuck in "generating" forever; errors are generic ("Processing failed") with no cause/context | `summaries-api.ts:5-7,240-263`; `summaries.py:44,151`; `main.py:213`; `page-client.tsx:832-856` | High when hit |
| 7 | Summary renders | Markdown + financial table | Quality variance (Section 4); placeholder sections silently hidden (`SummarySections.tsx:56-100`); internal failure notices stripped (`stripInternalNotices.ts:1-35`) so a degraded summary looks normal — a bad first summary is an activation **failure** even though the funnel "completed"; bad summaries cached until admin reset | `stripInternalNotices.ts`; `page-client.tsx:1108-1130` | **High** — the quality coinflip |
| 8 | Post-summary | Save (auth-gated), Export (Pro) | Export 403 → raw `alert()` with no upgrade link — poor, but post-activation | `page-client.tsx:994-1032` | Low (out of activation scope) |

**Cost/abuse note (adjacent but real):** anonymous streaming generation has no monthly cap — only 5/min per IP (`summaries.py:41,191`), while the non-streaming `/generate` endpoint requires auth. One guest IP could trigger ~7,200 AI calls/month. This needs a product decision (see §7) — but do **not** fix it by gating anonymous users behind login, which would kill activation.

---

## 4. AI Summary Quality Diagnosis

### Root causes of "hit and miss," ranked

**RC1 — Contradictory prompt + no structured-output enforcement (verified, highest confidence).**
The structured-extraction call concatenates the analyst system prompt — *"Do NOT structure your output into predefined categories or sections… write a natural, flowing analysis… 600-1000 words"* (`prompts/10k-analyst-agent.md:9-13`, same in 10-Q) — with a user prompt demanding *"Return ONLY valid JSON (no markdown fences) that matches this schema"* (`openai_service.py:1922-1951`). The API call uses **no `response_format`/JSON mode** (grep confirms zero occurrences in `openai_service.py`), so JSON validity depends on the model resolving an instruction conflict. The downstream evidence that this fails regularly: a two-tier JSON repair system (`_repair_json` @790: json-repair library, then regex), and editorial validation that needed its own retry loop. Two different temperatures across phases (0.2 extraction @1985; 0.4→0.3 editorial @2199) add further variance.

**RC2 — Brittle, order-dependent section extraction.**
`extract_critical_sections` (`openai_service.py:347-557`) selects what the model gets to read using cascading regex: first pattern wins. The 10-Q path guards against matching the table of contents (`len(financial_text) > 500` @444) but the **10-K path has no such guard** (@385-388) — a 10-K whose "Item 8" regex hits the TOC feeds the model a sliver of real content. The last-resort fallback scores 6 financial keywords over rolling 50k-char windows (@544-553) with no validation that the winner is actual financial content. The prompt itself confesses the symptom: *"FAILURE TO EXTRACT THESE METRICS IS UNACCEPTABLE. THEY ARE IN EVERY 10-K"* (`10k-analyst-agent.md:17-30`) — shouting at the model cannot fix an input problem.

**RC3 — XBRL grounding is a timeout lottery.**
XBRL + excerpt enrichment share a single 8.0s `asyncio.wait_for` (`summaries.py:47,524-527`); the XBRL fetch itself has 3s (10-Q) / 6s (10-K) internal timeouts that silently `return None` (xbrl fetch @~414 in summary_generation_service). The code's own comment admits "SEC API for large companies can take 5-10s" (`summaries.py:46`). Outcome: identical filing, different runs → financial_highlights either grounded in standardized XBRL or reduced to "Not disclosed" placeholders, flipping the result between "full" and "partial" (`summary_generation_service.py:22`, MINIMUM_SECTIONS_FOR_FULL_RESULT=3).

**RC4 — One retry, no semantic quality gate.**
Structured extraction allows `max_retries = 1` ("Reduced from 3 to limit worst-case latency", `openai_service.py:1959`) and retries only on transport/model errors. A syntactically valid response whose every field says "Not disclosed" is accepted, cached, and shipped. Coverage scoring counts characters, not substance.

**RC5 — Recovery machinery masks failure instead of fixing it.**
Empty sections trigger parallel re-generation (`_recover_missing_sections` @1401, semaphore=RECOVERY_MAX_CONCURRENCY) with no success verification, then `_apply_structured_fallbacks` (@1452) injects boilerplate ("Standard risk disclosures apply" @1591). The frontend then strips notices like "writer output failed validation" (`stripInternalNotices.ts:14-23`) and hides placeholder sections (`SummarySections.tsx:56-100`). Net effect: degradation is invisible to both user and team. The separate `fallback_summary.py` path uses *different* risk-extraction regex (@91-94) than the primary path (@347), so fallback output diverges from primary output for the same filing.

**RC6 — Parser quality varies by company/era.**
`filing_parser.py:754-755` hardcodes Apple's segment names (`iPhone|Mac|iPad|Services|Wearables|Home`) — segment extraction fails for essentially every other issuer. Pre-2016 filings with different HTML structure parse differently. No eval exists to quantify any of this: `test_summary_quality.py` checks formatting rules, not factual quality, and there is no golden-set harness.

### Recommended target architecture

Principles: make output structure **enforced, not requested**; make grounding **deterministic before the model runs**; make quality **measured, gated, and honest**.

1. **Enforce structured output at the API layer.** Use JSON mode / `response_format` (or tool-call schema) for Phase A. Rewrite the 10-K/10-Q prompts to describe the *schema's* fields (one source of truth), deleting the "structure as YOU see fit / 600-1000 word narrative" block. This eliminates the repair layer's raison d'être. Pin temperature (≤0.2) for extraction. *Trade-off:* JSON-mode support varies by provider behind the OpenAI-compat shim — verify gemini-3-pro-preview honors it; if not, this strengthens the case for the model eval below.
2. **Deterministic grounding pre-flight.** Before any AI call, run a "grounding check": Did section extraction return ≥N chars of real (non-TOC) content per critical section? Did XBRL return revenue/net income? If grounding is thin, *fix the input* (retry XBRL with a realistic 15–20s budget in parallel with filing fetch — it's currently serialized into an 8s window; re-extract with the alternate patterns) rather than letting the model improvise. Add the missing 10-K TOC-length guard. Replace Apple-specific segment regex with XBRL segment facts.
3. **Two-pass generate → validate → repair loop with a semantic gate.** Keep the existing two-phase shape (extract → editorial) but add a cheap validation pass between them: every numeric claim in the JSON must match XBRL or appear in the source excerpt (string/number containment — deterministic, no extra model call); required sections must contain substantive content (not "Not disclosed"). On failure, one targeted regeneration of only the failing sections with the validator's feedback in the prompt. Budget: this fits in the existing 90s envelope only if XBRL stops being serialized; otherwise raise the pipeline budget and message the wait honestly (the frontend progress UX is already good).
4. **Honest degradation.** Stop stripping failure notices client-side; replace with an explicit quality badge ("Full summary" / "Partial — financial data unavailable, retry") and a one-click regenerate. Auto-expire (don't admin-gate) cached summaries that were saved below the quality bar.
5. **Eval harness + model bake-off (the proof mechanism).** Build a golden set of 15–25 filings (mix: mega-cap/small-cap, 10-K/10-Q, pre/post-2019, financial/non-financial issuers). Score each generated summary on: (a) schema validity without repair, (b) numeric accuracy vs XBRL ground truth (deterministic), (c) section coverage with substance, (d) LLM-judge rubric for usefulness. Run current pipeline as baseline, then candidates: gemini-3-pro-preview + JSON mode, and **claude-sonnet-4-6 / claude-opus-4-8** (both have native structured-output and strong long-document grounding; Sonnet is the cost-appropriate candidate for this workload). Ship whatever wins on (a)–(c) at acceptable latency/cost. *Trade-off:* harness costs ~2–3 days and a few dollars of API spend; it's the only way to claim "better" honestly, and it becomes the regression suite for every future prompt change.

What I would **not** do: multi-agent self-critique chains or RAG over filing chunks as a first move. Both add latency and failure surface; the dominant variance sources here are input brittleness and unenforced output structure, which the simpler design fixes. Revisit retrieval only if the eval shows long-context truncation (100k-char cap, `openai_service.py:256-280`) is costing accuracy.

---

## 5. Prioritized Roadmap

Score = Impact on activation × Confidence ÷ Effort+Risk. Effort: S (<1d), M (1–3d), L (1–2wk), XL (>2wk).

### Quick Wins (do in order, ~1 sprint)

| # | Gap | Evidence | Activation impact | Effort | Risk | Proposed fix |
|---|-----|----------|-------------------|--------|------|--------------|
| Q1 | Waitlist gate can block all traffic | `middleware.ts:40-55` | Critical — gate on = zero activation | S | Low | Default `WAITLIST_MODE` to off (`!== 'false'` → `=== 'true'`), or add `/company`, `/filing`, `/` to ALLOWED_PATHS for a "live demo even while waitlisted" mode |
| Q2 | No zero-wait first impression | `page.tsx:84-96`; `HeroMockup.tsx` | Critical — visitors judge the product before generating | S–M | Low | Pre-generate summaries for the 8 QuickAccessBar tickers' latest 10-Ks; point "See an Example" directly at one (`/filing/{id}`) — instant cached render, no wait |
| Q3 | "Stalled" warning at 15s during normal runs | `page-client.tsx:614-623` | High — false failure signal mid-wait | S | None | Raise threshold to ~45s; show expected duration ("usually 30–60s") |
| Q4 | XBRL 8s lottery degrades financial grounding | `summaries.py:46-47,524-527`; 3s/6s fetch timeouts | High — direct driver of hollow summaries | S | Low | Raise enrichment budget to 15–20s and start XBRL fetch concurrently with filing fetch (currently inside a serialized window); surface "financials unavailable" honestly when it still fails |
| Q5 | Default to the right filing | company `page-client.tsx:140-159,274-293` | Med-High — removes the "which filing?" decision | S | Low | Auto-highlight/preselect latest 10-K (or latest filing) with a "Recommended" badge; keep full list below |
| Q6 | Timeout-layer mismatch + no client auto-retry | `summaries.py:44` (90s) vs `main.py:213` (120s) vs `summaries-api.ts:5-7` (120s); no reconnect `summaries-api.ts:240-263` | Med-High — converts slow runs into hard failures | S–M | Low | Align: pipeline 90s < endpoint ~100s < client ~110s; add one automatic stream retry/poll-fallback before showing the error |
| Q7 | Orphaned background tasks → eternal "generating" | `summaries.py:151` (fire-and-forget `create_task`) | Medium — dead-end state needing admin rescue | S | Low | try/finally to mark progress "error"; expire stale progress rows |
| Q8 | Raw 500s when EDGAR circuit opens | no CircuitOpenError catch in `companies.py:225-230`, `filings.py:345-444` | Medium | S | Low | Catch → 503 with "SEC EDGAR temporarily unavailable, retry in ~30s" |

### Strategic Bets (sequenced, ~3–6 weeks)

| # | Gap | Evidence | Activation impact | Effort | Risk | Proposed fix |
|---|-----|----------|-------------------|--------|------|--------------|
| S1 | Prompt/schema conflict, no enforced structure | `prompts/10k-analyst-agent.md:9-13` vs `openai_service.py:1922-1951`; no response_format; `_repair_json` @790 | Critical — top root cause of quality variance | M | Med (prompt regression — mitigated by S3 harness) | Rewrite prompts around the schema; enable JSON mode/tool-call output; delete narrative-format instructions; pin temperature |
| S2 | Brittle section extraction | `openai_service.py:347-557` (10-K TOC gap @385-388; keyword fallback @544-553); `filing_parser.py:754-755` Apple regex | High | M | Low–Med | Grounding pre-flight: content-length + non-TOC validation per section, alternate-pattern retry, XBRL-derived segments; log extraction confidence |
| S3 | No eval harness — quality is unmeasurable | `test_summary_quality.py` (format-only checks); no golden set | High (enabler for everything) | M | Low | 15–25-filing golden set; deterministic numeric-accuracy scoring vs XBRL + LLM-judge rubric; run as CI regression; bake off gemini+JSON-mode vs claude-sonnet-4-6 |
| S4 | No semantic quality gate; silent degradation | accepts all-"Not disclosed" (@1959-2020); placeholder injection @1452; `stripInternalNotices.ts` | High — bad first summary = failed activation | M | Med | Validate → targeted section regeneration loop; quality badge in UI instead of stripped notices; auto-expire below-bar cached summaries |
| S5 | Anonymous cost exposure (don't fix by login-gating) | `summaries.py:41,191,339-352` — guests uncapped monthly | Indirect (sustainability of free activation) | S–M | Med (product decision) | Per-IP/device daily quota (e.g. 3/day) with friendly "create a free account for more" — preserves first-summary-without-login |

**Suggested order:** Q1 → Q2 → Q3/Q4/Q5 (parallel) → Q6/Q7/Q8 → S3 (harness first — it de-risks everything after) → S1 → S2 → S4 → S5.

---

## 6. What I'd Ship First

**Q1 + Q2 together: open the front door and put a finished summary behind it.**

Rationale: every other improvement multiplies against the number of people who reach a summary. Today that number is gated by one env var (`middleware.ts:40`) and then by a 3-click + 30–80s + quality-coinflip gauntlet before a visitor sees any value. Pre-generating the latest 10-K summaries for the eight QuickAccessBar tickers and deep-linking "See an Example" to one gives every visitor a **zero-second, zero-risk** experience of the core product — served from the existing Summary cache, requiring no pipeline changes — while the slower, riskier live-generation path gets fixed behind it. It is the highest impact-to-effort ratio in the entire analysis, and it also creates the cleanest A/B test: example-link CTR → search → first generation, measurable in PostHog with events that (per the code) do not currently exist on this funnel.

The first *engineering* bet after that is S3 (eval harness) before S1 (prompt/schema fix) — changing prompts without a measurement loop is how the current "hit and miss" state arose.

---

## 7. Open Questions & Appendix

### Product decisions needed
1. **Waitlist intent:** Is `WAITLIST_MODE` deliberately on in production? If lead capture matters, recommend "live product + optional waitlist banner" rather than a hard gate. (The separate homepage-redesign plan in `tasks/todo.md` also proposes removing the redirect.)
2. **Anonymous quota policy:** unlimited (current), daily cap, or email-gated after N summaries? Affects S5; recommendation: 3/day per IP, never gate the *first* summary.
3. **Model strategy:** approve a bake-off including Claude models, or constrain to the Google AI Studio stack? Affects S3 scope.
4. **Latency vs quality budget:** is ~90s acceptable for live generation if quality becomes reliable, or is sub-30s a requirement (which would push toward pre-generation of popular filings as the primary strategy)?

### Measurement gap
No funnel analytics events exist on the activation path (PostHog is integrated server-side, `posthog_client.py`, but search→filing→generate→success is not instrumented). Before/while shipping Q1–Q5, add events: `search_performed`, `filing_selected`, `generation_started/succeeded/failed/timed_out`, `summary_viewed`, with result_type and duration. Without this, roadmap impact can't be verified.

### Out-of-scope observations (noted, not actioned)
- Export 403 handled via raw `alert()` with no upgrade path (`page-client.tsx:994-1032`) — conversion, not activation.
- TrendingTickers depends on Stocktwits with an empty-state fallback only (`TrendingTickers.tsx:230-244`).
- Non-streaming `/generate` requires auth while `/generate-stream` doesn't — API inconsistency worth unifying when S5 lands.
- `fallback_summary.py` risk-regex (@91-94) diverges from primary extraction (@347) — consolidate during S2.
- No skeleton loader on company filings list (`page-client.tsx:299-302`) — minor polish.
- CLAUDE.md is out of date re: waitlist gate, 90s pipeline timeout, and anonymous access; update after Q-wins land.
