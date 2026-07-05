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
- [ ] **P1 — Backend QA endpoint:** `ask-stream` SSE, prompt assembly (section excerpt + XBRL), DeepSeek streaming + caching, structured claims output, reuse `provenance_service` for verify + fragment URLs, "not disclosed" path, Pro-only entitlement gate + metering. Tests.  ← _current_
- [ ] **P2 — Frontend shell:** `FilingWorkspace` split layout + `AskCopilotRail` (dark), collapse + persistence, mobile bottom sheet.
- [ ] **P3 — Stream consumption:** `askFilingStream` (copy of `runStreamAttempt`) + streaming bubble + caret + heartbeat.
- [ ] **P4 — Citations:** chip render, hover popover, click→`useCitationHighlight` flash, Sources list, Verified/Cited vocabulary, `flash-highlight` keyframe.
- [ ] **P5 — Numeric tool-use:** `get_financial_fact`/`compute_metric`/`list_available_concepts` + XBRL-cited rendering.
- [ ] **P6 — Integrity + monetization UX:** not-disclosed/out-of-scope cards, grounding ticker, suggested questions, FREE locked teaser + upsell + analytics.
- [ ] **P7 — Eval + polish:** evals harness extension (golden Q&A + unanswerable + faithfulness scorer); `⌘K`, select-to-ask, animations.

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

## Shipped status (2026-06-21)

**P1–P6 shipped & merged to `main`.**
- P1 grounded QA backend · P2+P3 rail + SSE streaming · P4 interactive citations · P5 numeric XBRL tool-use.
- Pre-P6 audit fixes (#354): stream-failure → `error` event (not answer prose), meter-on-success, bounded `history`.
- P6a (#355) live "show the work" ticker · P6b (#356) inline `[F#]` chips for numeric facts (+ grounded-count fix) · P6c (#357) dynamic follow-up suggestions · P6d (#358) richer FREE locked teaser + paywall analytics.

## P7 — In-app filing viewer (in progress)

Goal: render the cached filing on-page; a citation click **scrolls to + flash-highlights the exact passage in place**, with the SEC `#:~:text=` deep link kept as a secondary "open original" affordance.

- **P7a (spike + endpoint):** `GET /api/filings/{id}/content` serves `FilingContentCache.markdown_content` (public SEC data, ungated; 404 / `has_content:false` handled). Frontend `excerptMatch.findExcerptMatch(haystack, excerpt)` locates an excerpt tolerant of markdown stripping (`**`,`#`,`|`), whitespace, quoted spans, and a leading-prefix fallback — returning original-text offsets to map back to a DOM Range. Spike proven by unit tests.
- **P7b (viewer + wiring):** `FilingViewer` drawer (lazy-fetches content, renders via ReactMarkdown), a `FilingViewerContext` so a `CitationChip` click requests an in-app highlight (builds a flat-text+node map from the rendered DOM, runs `findExcerptMatch`, scrolls to + flash-highlights the Range; `flash-highlight` keyframe in `globals.css`). Falls back to the SEC link when content is unavailable. Mounted in the filing page.

## P8 — Rigor (next)
Eval harness (golden Q&A incl. deliberately unanswerable → refusal calibration; citation-faithfulness + numeric-accuracy scoring), Copilot analytics dashboards, polish (⌘K, select-to-ask, popover portal fix, a11y).
