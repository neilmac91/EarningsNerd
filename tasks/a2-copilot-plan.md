# A2 — "Ask this Filing" Copilot — V2 Plan

_Synthesised from 3 research agents (cost/brains, OSS/techniques, UI/UX + competitive teardown of Brightwave, AlphaSense, Fiscal.ai, Hebbia, BamSEC). Approved 2026-06-21: **Full V1 incl. numeric tool-use**, shipped as a sequence of PRs off `main`, starting with P1. Pro-only._

## The big reframe (vs the original one-liner)
1. **No vector DB for V1.** DeepSeek context caching makes the filing a one-time cost per session (~$0.001/cached follow-up). Stuffing the already-cached section excerpt beats pgvector on cost for v4-pro, adds no infra, and removes retrieval's worst failure: a *false* "this filing does not disclose X". → pgvector deferred to a future cross-filing feature (F1/F3).
2. **Far less greenfield than assumed.** `provenance_service.py` already verifies excerpts (`verify_excerpt_in_text`) and builds `#:~:text=` deep-links (`build_text_fragment_url`). Frontend already has "✓ Verified / ↗ Cited" vocabulary + a proven SSE consumer (`runStreamAttempt`). → A2 ≈ chat UI + a thin grounded-QA endpoint on existing rails.

## Decisions
- **Pro-only.** New `copilot` entitlement (PRO=True, FREE=False); FREE sees a locked teaser + upsell. Fair-use soft cap for Pro (~1,000 Q/mo, degrade not hard-block).
- **Architecture:** long-context stuffing + DeepSeek caching. Stuff section-aware critical excerpt (`FilingContentCache.critical_excerpt`/`markdown_content`) + a structured XBRL/`financial_fact` block.
- **Model:** `deepseek-v4-pro` (all Copilot users are Pro), via `priority_model`.
- **Numeric tool-use in V1:** function-calling against `financial_fact` (exact, XBRL-cited numbers). The biggest differentiator.
- **Scope:** single filing. Scoped assistant, not a market oracle.

## Cost & value
- ~**$0.49 / Pro-user / month** at 200 Q (worst ~$2.50 at the 1,000 soft cap). Caching → ~$0.001/cached follow-up.
- ⚠️ Absolute $ assumption-based (live DeepSeek pricing unreachable; verify before launch). Relative "caching ≫ pgvector" conclusion robust.
- Value: flagship differentiator, Pro-conversion driver, verifiable citations + honest "not disclosed", numeric moat via XBRL-cited figures.

## Architecture (V1)
- **Endpoint:** `POST /api/summaries/filing/{id}/ask-stream` (SSE; excluded from timeout middleware by the `*stream*` rule). Mirrors the summary stream.
- **Prompt:** system contract (answer only from provided content; cite a verbatim section-labelled excerpt per claim; "This filing does not disclose X" when unsupported) + section excerpt + XBRL block + conversation history.
- **Grounding (reuse `provenance_service`):** model emits `{answer, claims:[{text, excerpt, section_ref}]}`; server verifies each excerpt (`verify_excerpt_in_text` against pre-normalized cached text), sets `verified`, builds `fragment_url`. Quote-verification gate strips/flags unverifiable claims → enforces honest citations + "not disclosed".
- **Numeric tool-use:** `get_financial_fact`, `compute_metric` (arithmetic server-side), `list_available_concepts` — filtered to this filing's company + `is_latest`; citation = `raw_tag` + `accession`.
- **Metering:** extend `UserUsage` with a QA counter; entitlement gate + soft cap.
- **Eval:** extend `backend/evals/` — per-filing golden Q&A incl. unanswerable questions + a deterministic citation-faithfulness scorer (reuse G3 hallucination pattern).

## UI/UX
- **Right-docked, collapsible Copilot rail in split view** with the summary as the citation target. Bottom-sheet on mobile w/ citation-tap → collapse + "↑ Back to answer". Slate-950/mint research-desk aesthetic.
- Token-streamed answers + live **grounding ticker** ("✓ Grounded in 2 excerpts").
- **Inline `[1]` chips:** hover → verbatim-quote popover + ✓Verified/↗Cited; click → smooth-scroll + mint flash-highlight (in-app first, SEC `#:~:text=` fallback). Collapsible Sources list.
- **"Does not disclose X" card** — visually distinct, explains why, redirects to right filing type.
- Empty state + filing-type-aware suggested questions (seed from existing `action_items`); persistent "Scoped to this filing ●" chip.
- **FREE = locked teaser** + upsell (reuse `UpgradeModal` + `isPaywallStreamError`/analytics).
- Wow: `⌘K`/`/` to ask; select-text → "Ask about this ✦"; flash-highlight; grounding ticker.

## Build phases (each its own PR, green CI before next)
> **Delta (2026-06-21):** P1–P5 are shipped & merged. The original P6/P7 below are **superseded** by the reshaped **["Revised remaining plan (post-P5)"](#revised-remaining-plan-post-p5-2026-06-21--reshaped-after-a-deep-sanity-check)** at the bottom of this doc (now P6 trust/engagement UX · P7 in-app filing viewer · P8 evals + analytics + polish). This section is kept for historical context.
- [x] **P1 — Backend QA endpoint:** `ask-stream` SSE, prompt assembly (section excerpt + XBRL), DeepSeek streaming + caching, structured claims output, reuse `provenance_service` for verify + fragment URLs, "not disclosed" path, Pro-only entitlement gate + metering. Tests. — _shipped (#349)_
- [x] **P2 — Frontend shell:** `FilingWorkspace` split layout + `AskCopilotRail` (dark), collapse + persistence, mobile bottom sheet. — _shipped (#350)_
- [x] **P3 — Stream consumption:** `askFilingStream` (copy of `runStreamAttempt`) + streaming bubble + caret + heartbeat. — _shipped (#350)_
- [x] **P4 — Citations:** chip render, hover popover, click→`useCitationHighlight` flash, Sources list, Verified/Cited vocabulary, `flash-highlight` keyframe. — _shipped (#351)_
- [x] **P5 — Numeric tool-use:** `get_financial_fact`/`compute_metric`/`list_available_concepts` + XBRL-cited rendering. — _shipped (#352)_
- [ ] ~~**P6 — Integrity + monetization UX**~~ — _superseded; folded into the revised P6 below._
- [ ] ~~**P7 — Eval + polish**~~ — _superseded; folded into the revised P8 below._

## Risks / watch-items
- DeepSeek caching semantics + actual v4-pro pricing — verify before launch.
- DeepSeek function-calling reliability (strict mode) for numeric tools.
- Big 10-Ks exceeding context → rely on the 320k-char critical excerpt + XBRL; true retrieval only if insufficient.
- Filing-page palette is legacy light/gray — Copilot ships dark; gradual reskin, don't block.

## Out of scope (future V2+)
- pgvector + section-aware chunking + `bge-reranker` + hybrid BM25/RRF — for cross-filing/company-wide Ask (F1/F3).
- "Ask across periods" on `/compare`; server-persisted transcripts + Citation-Audit per-claim grading (Brightwave).

---

## P1 — Implementation spec (this PR)

Pro-only, SSE, grounded single-filing Q&A backend. **Excludes** numeric/XBRL tool-use (that is P5)
and pgvector. Context = cached filing excerpt + a compact read-only XBRL block. Reuses the existing
provenance / entitlements / metering / streaming primitives.

### Files created / modified
1. **`backend/app/services/entitlements.py`** — add `copilot: bool = False` to `Entitlements`;
   `copilot=True` in `_PRO`, `copilot=False` in `_FREE` (explicit).
2. **`backend/app/config.py`** — `COPILOT_MONTHLY_QUESTION_CAP: int = 1000`,
   `COPILOT_MAX_TOKENS: int = 1200`, `COPILOT_CONTEXT_CHAR_CAP: int = 120000`,
   `COPILOT_HISTORY_TURNS: int = 6`.
3. **`backend/app/models/__init__.py`** — `qa_count = Column(Integer, default=0, nullable=False)` on
   `UserUsage`.
4. **`backend/app/services/subscription_service.py`** — `get_user_qa_count`, `increment_user_qa`,
   `check_qa_limit(user, db) -> (allowed, count, cap)` (cap = `COPILOT_MONTHLY_QUESTION_CAP`).
5. **`backend/app/services/openai_service.py`** — `async def stream_chat(self, messages, *,
   model=None, max_tokens=1200, temperature=0.2) -> AsyncGenerator[str]` yielding delta content
   (model defaults to `self.model`; thinking disabled for DeepSeek; tolerant try/except).
6. **`backend/app/services/copilot_service.py`** (new) — `answer_filing_question(*, filing, question,
   history) -> AsyncGenerator[dict]`.
7. **`backend/app/routers/summaries.py`** — `POST /filing/{filing_id}/ask-stream`, `AskRequest`,
   `require_entitlement("copilot", "Ask this Filing")`, rate limit, 404, `check_qa_limit`→429 /
   increment, SSE `StreamingResponse`.
8. **`backend/migrations/20260621_user_usage_qa_count.sql`** — idempotent additive migration.
9. **`backend/earningsnerd.db`** (gitignored) — `ALTER TABLE` to add `qa_count` for local tests.
10. **`backend/tests/unit/test_copilot.py`** (new) — grounding, not-disclosed, gating, metering.

### Model contract (system prompt)
Answer ONLY from the provided filing content; cite a verbatim excerpt + section ref per claim. Output:
- Answer prose with inline `[1]`,`[2]` markers, then a line `===CITATIONS===`, then a JSON array
  `[{"n":1,"excerpt":"<verbatim quote>","section":"<e.g. Item 7 — MD&A>"}]`.
- If unanswerable: `===NOT_DISCLOSED===` then one sentence stating what's missing.

### Streaming / sentinel handling
- Sentinels: `===CITATIONS===`, `===NOT_DISCLOSED===`. Hold back a tail of `max(len(sentinel))`
  chars across chunk boundaries so a split sentinel is detected.
- Emit `{"type":"token","text":...}` for answer prose only (before any sentinel).
- `===NOT_DISCLOSED===` → collect trailing text → `{"type":"not_disclosed","answer":...}`.
- `===CITATIONS===` → stop tokens, buffer rest; after stream parse JSON (json_repair fallback),
  verify each excerpt via `verify_excerpt_in_text` against the once-normalized source, build
  `fragment_url` via `build_text_fragment_url` when verified else base_url.

### SSE event schema (emitted dicts)
- `{"type":"progress","stage":"reading"}`
- `{"type":"token","text":"<prose chunk>"}`
- `{"type":"not_disclosed","answer":"<sentence>"}`
- `{"type":"complete","answer":"<full prose>","citations":[{"n","excerpt","section_ref","verified",
  "fragment_url"}],"grounded":<int verified>,"kind":"answer"|"not_disclosed"}`
- `{"type":"error","message":"<msg>"}`

Generator never raises — all exceptions become an `error` event.

### Done criteria
- `cd backend && ruff check .` clean.
- `cd backend && python -m pytest tests/unit/test_copilot.py -q` green.

---

## Revised remaining plan (post-P5, 2026-06-21) — reshaped after a deep sanity-check

**Shipped & merged:** P1 (QA backend) · P2+P3 (rail + SSE streaming) · P4 (interactive citations) · P5 (numeric XBRL tool-use). Foundation is strong: honest grounding (quote-verify + "not disclosed"), exact XBRL-cited numbers, interactive chips, Pro-gated/metered/streaming.

**New decisions (user, 2026-06-21):** build the **in-app filing viewer**; fold in **all** of: live "show the work" ticker, inline chips for numeric facts, dynamic follow-up suggestions, and the **eval harness + analytics** (treated as launch-gating rigor). A fresh-eyes audit of the merged code is folded in as fixes.

The original P6/P7 split is replaced by three sharper phases (each its own PR, green CI before next):

### P6 — Trust & engagement UX (mostly frontend + light backend)
- **Live "show the work" ticker:** backend emits new SSE activity events from the tool loop — e.g. `{"type":"activity","label":"Looking up revenue (XBRL)"}` and a `done` variant — surfaced as a live status line during streaming (Brightwave/Hebbia signal). Needs `copilot_service`/`stream_chat_with_tools` to yield tool start/finish, and the rail to render them.
- **Inline chips for numeric facts:** give XBRL facts inline `[n]` chips in the prose (today they only hit the Sources list). Approach: assign the model the fact citation numbers via the tool-result content (e.g. each fact result carries `ref: n`) so it can cite `[n]` inline; chips render via the existing `injectCitations`.
- **Dynamic follow-up suggestions:** after each answer, 2–3 contextual next questions (model emits a `===FOLLOWUPS===` block, or a cheap fast-model pass), rendered as tappable chips.
- **Richer FREE locked-teaser:** blurred sample Q&A + value prop + upsell (reuse `UpgradeModal` + `isPaywallStreamError` → `analytics.paywallPromptShown`). Refined not-disclosed / out-of-scope cards.

### P7 — In-app filing viewer (the headline UX elevation)
- Render the cached filing (`FilingContentCache.markdown_content`) in an on-page reader (split-view we already set up / a panel), so a citation click **scrolls to + flash-highlights the exact passage in place** instead of a new-tab SEC jump. Reuse the excerpt-normalisation/matching from `provenance_service`; add the `flash-highlight` keyframe; SEC deep-link stays as the "open original filing" affordance. Mobile: sheet/peek with "↑ back to answer".
- Spike first: confirm the cached markdown highlights cleanly against the verbatim excerpts.

### P8 — Rigor: evals + analytics + polish (launch-gating)
- **Eval harness** (extend `backend/evals/`): per-filing golden Q&A incl. deliberately **unanswerable** questions (measure refusal calibration), **citation-faithfulness** scorer (quote-verify as a metric), **numeric-accuracy** vs `financial_fact`. Deterministic gates; LLM/RAGAS judge as corroboration only.
- **Copilot analytics:** events for question asked, grounded-rate, not-disclosed-rate, tool-use, paywall-shown, Pro-conversion.
- **Polish:** `⌘K`/`/` to ask, select-text → "Ask about this", citation-popover **portal** (fix scroll-container clipping), accessibility pass.

### Audit fold-in
Any correctness/robustness bugs the fresh-eyes audit flags in the shipped P1–P5 code are fixed first (either a small pre-P6 PR or rolled into the relevant phase).

