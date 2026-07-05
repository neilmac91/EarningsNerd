# EarningsNerd — Architecture Refactor Plan (refined, execution-ready)

## Context

EarningsNerd is a solo-founder fintech whose codebase was largely AI-generated across many feature
sprints. It is in better shape than most such systems (entitlements, refresh-token service, design
system, and the auth test suite are genuine exemplars), but it carries three structural debts that
tax every session: (1) **duplicated orchestration** (two summary pipelines, multiple coverage/parser/
concept/cache copies); (2) **~2,200 LOC of verified-dead code** plus a 3,715-line god module; and
(3) **a test safety net with holes exactly where refactoring needs it** (no pytest config, no shared
fixtures, an orphaned test root, no contract test on the SSE/Stripe/background paths). Resilience is
partly theater — the circuit breaker and SEC rate limiter exist but are bypassed on the primary data
path. The plan anchors current behavior first (Wave 0), deletes dead weight (Wave 1), unifies
duplicates behind that anchor (Wave 2), and installs a memory system (Wave 3).

This document is the **refined** version of the founder's original architecture plan. Its factual
claims were independently re-verified against the live code this session (three parallel audits),
then **independently re-reviewed and approved by a second agent** ("AGREE — approve for
implementation"), whose addenda are verified and folded in below (marked ⊕).
**No application code is modified by this document** — it is the execution spec.

---

## Implementation Notes / Deltas (recorded during execution)

Where execution diverges from the plan below, it is logged here. The plan text is preserved as the
original proposal; **these notes are authoritative for what actually shipped** (see PR #546). Later
waves append their deltas here rather than editing the plan body in place.

**Wave 0a — test consolidation:**
- **Orphaned `/tests/` adoption → deletion (verified, user-approved).** The plan assumed the 6
  repo-root `/tests/` files could be adopted with import rewrites. Verified reality: all 6 are
  bit-rotted and provided **zero** CI coverage (never collected — CI runs `cd backend && pytest`).
  `test_xbrl_fallback.py` tested `XBRLService._parse_xbrl_xml`, removed when the XBRL layer became
  `EdgarXBRLService`. The other 5 (`test_endpoint_security`, `test_security_controls`,
  `test_waitlist`, `test_summarize_filing`, `test_contact_submission`) fail and/or pollute the shared
  suite (stale `<32`-char `SECRET_KEY` predating the ≥32 validation; dead `backend.*` imports; a fake
  `_Settings` missing `AI_DEFAULT_MODEL`; an uncleaned module-level `dependency_overrides[get_db]`).
  All 6 were **deleted** (git preserves them; zero CI coverage lost); the coverage areas
  (endpoint-auth, security-controls, waitlist, summarize_filing, contact) are logged as rewrite
  candidates. The 3 pipeline tests + `fixtures/` remain at `/tests/` for Wave 1's `rm`.
- **D1 (Wave 1) simplified:** because `test_summarize_filing.py` was deleted here, D1 no longer needs
  to remove its `generate_editorial_markdown` monkeypatch. The `test_llm_no_pii.py` `_LLM_ENTRYPOINTS`
  coupling still applies.
- **`test_summary_quality.py` `FORBIDDEN_WORDS` refactor is moot:** the file already imports the gate
  logic from source (`calculate_section_coverage`, `determine_result_type`,
  `MINIMUM_SECTIONS_FOR_FULL_RESULT`, `HIDEABLE_SECTIONS`); `FORBIDDEN_WORDS` /
  `check_for_subjective_language` exist only in the test (the app enforces no such word list), so
  there is no source to import from. Left test-local — an app-side copy the app never uses would be
  dead code.

**Wave 0a — review follow-ups (PR #546, founder review):**
- **Two deleted-coverage invariants promoted into the anchor set (this PR):** the security headers
  `main.py` sets → `backend/tests/unit/test_security_headers.py`; the Stripe price-allowlist
  rejection (unknown `price_id` → 400) → new case in `tests/unit/test_checkout_session.py`. These
  were the only tests covering those invariants; recreated fresh against current fixtures.
- **T11 (waitlist) + T12 (contact) — concrete follow-ups** for the remaining unique deleted coverage
  (join / duplicate / invalid-referral / position math; submission + 3/hour rate limit). Zero
  replacement in `backend/tests` today; to be written hermetically (route-level) in a follow-up.
- **Marker discipline hardened:** `pytest.ini` deselects only `performance` (not `slow`) — `slow`
  had no separate CI path, so slow-marked tests now run in the default lane instead of being silently
  skipped. `tests/performance/conftest.py` auto-stamps `performance` by directory (a new perf file
  can't miss the marker). `requires_db`'s description corrected (no auto-skip). The CI perf step is
  path-scoped and the inert per-step `SECRET_KEY` env (conftest overrides it) was dropped.
- **Doc drift fixed in-PR:** `backend/evals/RUNBOOK.md` Step A path and CLAUDE.md's 5 false
  statements (markers now in `pytest.ini`; the 3 moved file paths; the misleading `pytest tests/`).
- **Known/expected:** running `pytest` from the **repo root** now errors on the 3 remaining
  `/tests/` pipeline tests (their `backend.pipeline` imports lost the deleted root-conftest shim).
  Expected until Wave 1's `rm -rf tests/` — do NOT restore the shim. CI is unaffected (`cd backend`).

**Wave 0b — characterization anchors (PR #547):**
- **10 anchors landed; full backend gate green (1135 passed / 2 deselected; perf 2 passed; ruff +
  bandit clean):** T1 (SSE ordered contract + `to_sse` + a recorded frames fixture regenerated by
  `scripts/gen_summary_stream_frames.py`), T10 (frontend parser parity on that ONE shared fixture),
  T2 (background before-photo — previous_filings divergence, partial-discard, early-return branches),
  T3 (guest-quota 429 gate at `summaries.py:222`), T5 (expired-trial route gate — copilot 403 once
  the free taste is spent + the pure `can_export` export gate), T8 (refresh replay — expiry
  round-trip + reuse-revokes-chain), T9 (recorded companyfacts fixture).
- **T4 (Stripe downgrade):** the `deleted`/`canceled` leg was already covered
  (`test_subscription_webhook_sync::test_subscription_deleted_downgrades_to_free`); the #547 review
  correctly caught that the **`past_due` money-OFF leg had no webhook-level test** (only a
  resolver-level parametrize). Closed by `test_subscription_past_due_downgrades_to_free` — a
  `customer.subscription.updated` (status `past_due`) posted through the real handler asserting
  row→past_due, `is_pro=False`, resolver→Free (no bug; gap closed). **T7 (filing-scan exactly-once):
  already covered** — `test_filing_scan::test_pro_realtime_sent_once_skips_historical_and_dedupes`
  (verify-first audit confirmed by the review).
- **Latent bug surfaced by T9 (pinned as characterization, NOT fixed):** `EdgarXBRLService.
  _parse_company_facts` declares `total_liabilities` + `cash_and_equivalents` buckets but never
  populates them — the companyfacts fallback silently drops those facts even when present. Pinned by
  `test_companyfacts_fixture::test_fallback_parser_ignores_liabilities_and_cash`. Worth a follow-up.
- **Deferred (noted so they don't evaporate):** T6 (10-Q quarterly *surface* — extraction already
  covered by `test_accession_xbrl_extraction` #240; a route test would only exercise a mocked
  payload); T11/T12 (waitlist + contact rewrites, from the #546 review); the frontend
  `__tests__`→`tests/unit` merge (cosmetic — vitest already globs both dirs/suffixes); and extracting
  shared `conftest` fixtures (each anchor keeps its own `client`/seed/`_tables`/`_reset_inflight`
  helpers today — consolidate once ≥N anchors make the churn worthwhile).

**Wave 0b — round-2 review follow-ups (PR #547, founder):** the review found the exit gate not yet
met (anchors present but with gaps). All eight substantive comments are closed:

- **Shared harness (comment #9 — the ≥2× extraction rule had already triggered):** the boundary-mock
  set, the canonical AI payload, the Company+Filing seed, the inflight reset, and the auth
  limiter/lockout reset are now single-sourced in `backend/tests/support/summary_stream_harness.py`,
  imported by T1/T2/T3/T5 **and** the frames-regen script. A renamed `stream_filing_summary` boundary
  is now a one-file edit, not four-in-lockstep.
- **T1 (comments #4/#5):** added the error-frame shape (the real `{type,message}` — a `message→detail`
  rename now fails), a thin route test (`/generate-stream` registered, `text/event-stream` + streaming
  headers, 404 on missing filing), and a full terminal-`complete` key-set assertion. Parity was
  type-sequence-only → now **field-by-field** vs the recorded fixture (masking only volatile values via
  the same `normalize_frame` the regen script uses); the fixture JSON stays a raw array (+ a `.README`
  provenance sidecar) so T10 keeps parsing it. 3→7 tests.
- **T2 (comment #2):** landed the five S1-reconciliation pins the plan's ▲ spec makes mandatory — the
  9-vs-7 coverage-taxonomy DUAL-WRITE, the `determine_result_type` verdict (no XBRL grounding, proven
  divergent from `assess_quality` on one payload), usage-increment-once, partial-discard, and
  zero-PostHog-on-precompute — and fixed the stale docstring (it *is* the T2 divergence record). 6→10.
- **T5 (comment #3):** added the PRIMARY revenue surface — `/generate-stream` — which is NOT a hard
  403: an expired trial is downgraded to Free and hits the Free monthly cap in-band as an SSE
  `{"type":"error"}` paywall frame on a 200 stream. Two tests hold usage at `FREE_TIER_SUMMARY_LIMIT`
  and move only `trial_end` past↔future, isolating the expiry as the cause. 5→7.
- **T3/T8 + lock-friction (comment #8):** T8 now clears the auth limiters via the shared
  `reset_rate_limiters()` seam instead of five private `_hits` reaches (so S3's auth extraction won't
  break a locked anchor on a permitted rename); T3 adopts the harness; both relax brittle exact-upsell
  copy to status + a stable substring (the limit number / "Upgrade to Pro").
- **`__file__` backtick (gemini):** already fixed (`f75cd2d`).

**Exit-gate part 2 — mutation spot-check (comment #7):** each anchor was shown to FAIL under a spot
mutation of its guarded behavior (production perturbed, target test run, then reverted; tree verified
clean afterward). T6 is deferred (not written), so it has no anchor to mutate.

| Anchor | Mutation applied to the guarded production behavior | Observed |
|--------|------------------------------------------------------|----------|
| T1 | error frame key `message` → `detail` (`summary_pipeline.py`) | `test_error_frame_shape` **FAILED** |
| T2 | disable prior-10-K YoY injection (`include_previous` → false) | `test_10k_injects_prior_10k_as_previous_filings` **FAILED** |
| T3 | drop the guest over-quota 429 gate (`summaries.py`) | `test_guest_served_up_to_limit_then_blocked` **FAILED** |
| T4 | add `past_due` to `_ACTIVE_STATUSES` (wrongly grants Pro) | `test_subscription_past_due_downgrades_to_free` **FAILED** |
| T5 | expired trial still grants Pro (`_subscription_grants_pro`→True) | `test_export_pdf_gates_expired_trial` **FAILED** |
| T7 | back-catalogue no longer skipped (`_candidate_filings` baseline filter) | `test_pro_realtime_sent_once_skips_historical_and_dedupes` **FAILED** |
| T8 | token reuse no longer revokes the chain (`revoke_all_for_user` skipped) | `test_refresh_reuse_revokes_the_rotated_chain` **FAILED** |
| T9 | fallback parser populates the liabilities bucket (`_parse_company_facts`) | `test_fallback_parser_ignores_liabilities_and_cash` **FAILED** |
| T10 | parser drops `onComplete` on the terminal `complete` frame | `summaryStream.contract.spec.ts` **FAILED** |

Note (surfaced by the spot-check): T7's dedup is DEFENCE-IN-DEPTH — the `_already_logged` pre-check is
backstopped by the `NotificationLog` unique constraint AND the advancing `last_alerted_at` watermark,
so defeating the pre-check alone stays green; the mutation instead targets the "skips-historical" leg
the same anchor pins. (A follow-up could add a watermark-level dedup mutation for completeness.)

**Baseline recorded {count, wall time, green SHA}:** backend **1146 passed / 2 deselected in 49.4s**
(default lane; `ruff` + `bandit -ll` clean) + **2 performance passed in 18.6s** = 1148 green; frontend
**248 vitest passed (53 files) in 64.5s**, `tsc -p tsconfig.ci.json` clean, `eslint --max-warnings 0`
clean. Green at **`00653e5`** (this delta entry is docs-only, committed on top). Count moved 1135 →
1146 (+11), fully explained by the round-2 additions: T1 +4, T2 +4, T5 +2, T4 +1.

**Wave 1 — deletions (this PR).** Six file-disjoint deletions. The plan called for six parallel PRs;
the execution branch is bound to a single branch, so they ship as six file-disjoint commits in one
Wave 1 PR — same isolation, same per-deletion gate (rg the removed symbols → 0; ruff + bandit + full
suite green), just serialized. Cumulative: **61 files, −2625 LOC** (exceeds the ~2,200 estimate).

- **D1 — openai_service dead editorial cluster (−652).** `generate_editorial_markdown` (its caller
  `summarize_filing` was long ago rewired to deterministic rendering) + its only-callees
  `_validate_editorial_markdown` / `_validate_editorial_numbers` / `_collect_structured_number_strings`
  + the `_writer_models` init block + the separately-dead `summarize_filing_stream`. Coupled in the
  same commit: dropped the two now-dangling `_LLM_ENTRYPOINTS` names in `test_llm_no_pii.py` (the test
  `getattr`s each) and the `stream_chat` docstring mention. `openai_service.py` 3715 → 3063.
- **D2 — `backend/pipeline/` package (−784) + orphaned root `/tests/`.** Never imported by app code —
  only by the 3 root pipeline tests CI never collected. Deleted the package + the whole root `/tests/`
  tree; repointed the two subagent docs (`.claude/agents/engineering/*`) off `backend/pipeline/*`;
  banner-marked `plan_sec_pipeline.md` SUPERSEDED. Resolves the Wave 0a "repo-root pytest errors"
  known-issue. Also removed the 9 finished agent worktrees.
- **D3 — dead EdgarClient XBRL path (−260) + `earnings_whispers`.** `EdgarClient.get_xbrl_data` +
  `_extract_xbrl_data` + `_extract_metric_series` (every live XBRL caller goes through
  `EdgarXBRLService`/compat — not this variant). **Near-miss caught by a dry-run print + a
  usage-check:** the initial line-range included the module-level `edgar_client = EdgarClient()`
  singleton (used by `edgar/__init__` + `compat.py`); re-scoped to preserve it. `earnings_whispers`
  module + its `integrations/__init__` exports removed (superseded by FMP; the calendar test's
  `"earnings_whispers"` is a string label, not a module ref).
- **D4 — the RequestMetrics theater (−154).** `record_request` had **zero callers** (no middleware
  fed it), so the `/metrics` "requests" block always reported zeros. Removed the dataclass, the
  singleton, `get_request_metrics`, the module `record_request`, and the "requests" key (kept the real
  circuit_breaker/cache/db sections). `/health/detailed`'s request counts are circuit-breaker stats —
  untouched. Purged the CLAUDE.md advertisement (Thread-Safe Metrics bullet, the example block, the
  moot "Metrics deadlock" row).
- **D5 — repo-root strays + dead one-offs.** `inspect_db.py`, `templates/{index,results}.html` (no
  code serves them), `scripts/fix_contact_column.py` (**confirmed** the Cloud Run start command is
  `CMD uvicorn main:app …` in `backend/Dockerfile` — not this Render relic), `scripts/update_contact_schema.py`
  (superseded by the ContactSubmission ORM model + create_all, NOT a migration — and its deletion makes
  the CLAUDE.md:844 / ADR-0001 "was removed" claims finally true). Kept `cleanup-branches.sh`,
  `performance-comparison.sh`, `test_resend_simple.py`.
- **D6 — archived 34 finished tasks/ docs.** Top-level `tasks/*.md` 43 → 9. Kept: the active plan +
  `todo.md`, `lessons.md`, the operational runbooks (gcp-deploy/launch/security_privacy), and the docs
  cited by live surfaces (council-prep/earnings-calendar-strategy/fpi-support-roadmap). Link-check: the
  3 live pointers into the finished-cluster were repointed to `tasks/archive/` paths; every `tasks/*.md`
  reference now resolves — 0 danglers.

**Baseline (Wave 1):** backend **1146 passed / 2 deselected (47s)** + **2 performance (18s)**, `ruff` +
`bandit -ll` clean; frontend untouched (all changes backend/docs) and still green — **248 vitest / tsc /
eslint** clean. Test count unchanged at 1146 (every deletion was dead code; the only test edit trimmed
two name-list entries, keeping both tests). Green at **`f27c53b`** (this delta entry is docs-only, on
top). NON-goals held: entitlements/billing, refresh_token_service, and the design system were untouched.

_(Deltas from later waves will be appended here as they are executed.)_

---

## What changed from the reviewed version (verified corrections folded in)

The original plan is accurate: under adversarial caller-hunting **no "dead code" claim was refuted**,
and the load-bearing counts (CLAUDE.md 898 lines, `lessons.md` 385, ADR-0002=Gemini vs DeepSeek
default) check out exactly. The refinements below either sharpen scope or correct magnitude. All cite
verification evidence.

1. **S1 is a behavior-change refactor, not a mechanical dedup.** The two summary paths already route
   heavy lifting through shared helpers; genuinely verbatim duplication is small (the
   `FilingContentCache` write block + highlights normalization). The real divergences run **deeper
   than the original 4-item drift table** and MUST be pinned by T2 and gated by the S1 flag:
   - **`previous_filings`:** SSE passes `None` (`summary_pipeline.py:548`); background injects the
     prior 10-K for YoY context (`summary_generation_service.py:474-488, 681-682`). **The two paths
     produce different 10-K summaries today** — unification necessarily makes a product decision.
   - **Two coverage taxonomies (not "3 implementations"):** `assess_quality` and
     `determine_result_type` both delegate to `calculate_section_coverage` (7 `HIDEABLE_SECTIONS`);
     the truly independent second engine is `coverage_snapshot` (9 `_TRACKED_STRUCTURED_SECTIONS`,
     `openai_service.py:3450`). Both paths persist the 9-section snapshot to progress but gate quota/
     caching on the 7-section count — a pre-existing inconsistency S1 must resolve into one taxonomy.
   - **Verdict semantics differ:** `assess_quality` adds an XBRL numeric-grounding check that
     `determine_result_type` lacks, so "keep `assess_quality`" silently changes *when* the cron path
     marks a result `partial`. This is a contract change, not a no-op.
2. **Deletion PRs must edit tests + exports in the SAME commit** (production is safe; CI is not):
   - D1: besides the `test_llm_no_pii.py` `_LLM_ENTRYPOINTS` name-list (`:15-34`),
     `tests/test_summarize_filing.py:70` monkeypatches `generate_editorial_markdown` with
     `raising=True` — deleting the method `AttributeError`s that test unless the line is removed too.
   - D3: `integrations/__init__.py:3,8,9` exports `earnings_whispers` symbols — edit in the same PR.
3. **D1 mechanism reworded:** `generate_editorial_markdown` is NOT "hard-disabled by an early
   return." Its body is intact; it is dead because its *caller* `summarize_filing` was rewired to
   deterministic rendering (`openai_service.py:3504-3511`). Deletion still safe.
4. **D5's premise is wrong and must be re-based:** there is **no** contact-column `.sql` in
   `backend/migrations/` — the `ContactSubmission` ORM model + `create_all` supersede the scripts,
   not a migration. Also `fix_contact_column.py` was a **Render start-command**
   (`docs/history/render/RENDER_DEPLOYMENT.md:52,86`); you are on Cloud Run now (Dockerfile `CMD`),
   so it is almost certainly dead — confirm the deployed start command before `rm`. And CLAUDE.md:855
   + ADR-0001:19 falsely claim `update_contact_schema.py` was removed; it still exists (fix in M2).
5. **Consolidation surfaces are larger than stated** (more work, not unsafe): revenue/net-income
   concept lists live in **~6 files** (add `statement_parser.py`, `client.py`, `facts_service.py`
   `_CONCEPT_UNITS` to the original 4); a **third** partial `FilingContentCache` write lives in the
   shared `get_or_cache_excerpt` (`summary_generation_service.py:356-363`).
6. **Latent bug #4 (SEC rate) is bounded, not unbounded:** a `--max-instances=2 --concurrency=40`
   pin exists — but in `docs/DEPLOYMENT.md:120` / runbook, **not** in `ci.yml` (gcloud preserves it
   across updates). Worst-case aggregate is ~2× the service + the 5 separate cron-job processes, not
   N×. S4 still applies; additionally pin `--max-instances` in `ci.yml` so it can't silently drift.
7. **Minor factual fixes:** `page-client.tsx` is 10 data hooks / 9 `useState` / **2** raw `fetch()`
   (both PDF/CSV export at `:753,:789`), not 13/10/3. The background path is also invoked by the CLI
   `scripts/pregenerate_examples.py` (via `precompute_one`), not "only internal.py." The `requires_db`
   marker is on 100+ tests but its graceful-skip **never fires** (no `pytest_collection_modifyitems`
   hook). `frontend/tests/unit/` has 2 stray `.test.ts` files, so the `.spec`-only split is muddier.

---

## Ground truth (verified)

- Backend app ~33.2k LOC. Hotspots: `openai_service.py` 3,715; `routers/auth.py` 1,462;
  `edgar/xbrl_service.py` 1,178; `summary_generation_service.py` 955; `facts_service.py` 917;
  `copilot_service.py` 887; `routers/admin.py` 863; `summary_pipeline.py` 844.
- Backend tests: ~1,041 functions / ~100 files; **no pytest config anywhere**; 6 markers registered
  in `conftest.py`; `requires_db` decorative. THREE test roots — `backend/tests` (CI-run), repo-root
  `/tests/` (9 files, **never collected**), frontend dual dirs. CI runs `cd backend && pytest` with
  **no `-m`/path filter** → real-`sleep` perf tests run every push (and lack the
  `@pytest.mark.performance` marker, so naive deselection is a no-op).
- Frontend ~27.6k LOC. `app/filing/[id]/page-client.tsx` 1,016 LOC.
- Memory: `docs/adr/` (5 ADRs, MADR; 0002=Gemini is stale). `tasks/lessons.md` 385-line monolith.
  `tasks/` 45 files / ~6.75k lines. CLAUDE.md 898 lines, drifting. `docs/ARCHITECTURE.md` exists.
- 22 manual SQL migrations; no Alembic; `create_all` + `ensure_additive_columns` at startup.

---

## Wave 0 — Test consolidation (ONE owner, serial; blocking gate)

Nothing structural starts until Wave 0's exit gate is green. Deliverable includes a baseline record
{test count, wall time, green SHA}.

### 0a. Structure (no logic rewrites)
1. **`backend/pytest.ini` = single source of test config.** Move the 6 marker registrations out of
   `conftest.py`; set `testpaths = tests`; `addopts = -m "not performance and not slow"`. **Add the
   missing `@pytest.mark.performance` decorators** to the 2 perf tests
   (`tests/performance/test_concurrent_streams.py`) or the deselection is a no-op. **Relocate
   `backend/scripts/test_startup.py` → `tests/smoke/`** (it is collected today; `testpaths = tests`
   would silently drop it). Do NOT set `asyncio_mode` (149 tests use explicit `@pytest.mark.asyncio`).
   In CI, make the performance run an explicit STEP inside the existing `backend-tests` job (a
   separate job would fall out of the deploy gate's `needs:` list).
2. **Shared fixtures in `conftest.py` — write the anchors FIRST, then extract only fixtures repeated
   ≥2×** (expected: `client`, `db_session`, `make_user`/`make_pro_user`, `authed_client`). No mass
   rewrite of ~100 files; migrate opportunistically.
3. **Adopt the orphaned repo-root `/tests/` — Wave 0 owns all triage** (so Wave 1's pipeline delete
   is a pure `rm`). Move `test_xbrl_fallback.py`, `test_contact_submission.py`,
   `test_endpoint_security.py`, `test_security_controls.py`, `test_waitlist.py`,
   `test_summarize_filing.py` into `backend/tests/unit/`, rewriting `from backend.pipeline…`-era
   imports to `app.*` and dropping the root-conftest `sys.path` shim. The 3 pipeline tests
   (`test_extract_msft_aapl`, `test_validate`, `test_writer`) are **not** moved — they die with the
   pipeline in Wave 1.
4. **Relocate the two `backend/tests` root strays** (`test_edgar_services.py`,
   `test_summary_quality.py`) into `unit/`; fix `test_summary_quality.py` to IMPORT
   `FORBIDDEN_WORDS`/subjective-language lists from source instead of re-implementing them.
5. **Delete the `assert True` placeholder** (`integration/test_summary_stream_heartbeat.py:273`).
6. **Frontend: merge `__tests__/` into `tests/unit/`** on ONE suffix (`.test.*`) — including the 2
   stray `.test.ts` already there; update `vitest.config.mts` include. File moves only.

### 0b. Characterization anchors (T1–T10)
| # | File | Pins |
|---|------|------|
| T1 | `tests/integration/test_summary_stream_contract.py` (new) | Full ordered SSE contract on `POST /api/summaries/filing/{id}/generate-stream`: progress stages → (section-reveal when enabled) → exactly one terminal `complete` whose JSON carries the exact keys the frontend `Summary` type reads; error-event shape; heartbeats tolerated anywhere. **Mechanics:** `dependency_overrides` alone is insufficient — `stream_filing_summary` opens `SessionLocal()` directly; either seed a real SQLite (test_auth_flow pattern) patching boundary singletons *as bound in `summary_pipeline`'s namespace*, or consume the generator directly (test_inflight_dedup pattern) + a thin route test for `to_sse` framing. Instant fakes ⇒ 0 heartbeats ⇒ fully ordered; a heartbeat variant gates a fake on `asyncio.Event`. **MANDATORY autouse fixture resetting `_inflight_generations`.** Emits the recorded-frames fixture shared with T10. |
| T2 | `tests/unit/test_background_generation_characterization.py` (new) | The "before photo" for S1. Pins on `generate_summary_background` with boundary fakes: (i) persisted `Summary` fields on success; (ii) NO row on partial/timeout + progress stage `partial`; (iii) usage-increment semantics; (iv) **for a 10-K, `summarize_filing` receives non-None `previous_filings`** (SSE hardcodes None — do not silently resolve); (v) precompute emits ZERO PostHog funnel events. **▲ Also pin the coverage taxonomy actually persisted (9-section snapshot) vs the gate count (7-section), and that the verdict comes from `determine_result_type` (no XBRL-grounding check) — these are the S1 reconciliation targets.** Divergences documented in the docstring. |
| T3 | `tests/unit/test_guest_quota_route.py` (new) | `ENABLE_GUEST_DAILY_QUOTA=true`: anon gets N, N+1 blocked with quota shape, next-day reset, authed bypass. |
| T4 | `tests/unit/test_stripe_downgrade.py` (new) | `customer.subscription.deleted`/`past_due` → row updated, `is_pro=False`, entitlements downgraded (route-level). Money-OFF path currently untested. |
| T5 | `tests/unit/test_expired_trial_gating.py` (new) | Past `trial_end` blocked at generate-stream AND the copilot ask route (route-level). |
| T6 | `tests/unit/test_quarterly_surface.py` (new) | For a 10-Q, `financial_highlights` carry quarterly (not FY) figures at the endpoint surface (guards regression #240). |
| T7 | extend `tests/unit/test_filing_scan.py` | Exactly-once alerts: one qualifying filing → one alert/watcher; re-scan → zero additional. |
| T8 | `tests/unit/test_refresh_replay.py` (new) | Expired access + valid refresh cookie → new access token on retry; reuse of a rotated refresh revokes the chain. |
| T9 | `tests/unit/test_companyfacts_fixture.py` (new) | A checked-in RECORDED companyfacts JSON through `_parse_company_facts` + `select_fact_data` (the production fallback parser has no realistic-payload test today). |
| T10 | `frontend/tests/unit/summaryStream.contract.spec.ts` (new) | Frontend SSE parser fed the SAME recorded-frames fixture T1 emits (single shared artifact), incl. error + heartbeat interleave. Producer schema drift breaks a test, not prod. |

**Exit gate:** full backend suite green (local + CI); the 10 anchors green; each anchor shown to FAIL
under a spot mutation of its guarded behavior; baseline recorded {count, wall time, green SHA}.

---

## Wave 1 — Deletions (Batch A: six parallel-safe, file-disjoint PRs)

Rule: delete-before-abstract. Every deletion PR runs `rg` for each removed symbol → 0 hits (excluding
`tasks/archive/`), reports LOC + test-count delta, and **edits the coupled tests/exports in the same
commit** (below).

| ID | Task | Same-commit coupling & gate |
|----|------|------------------------------|
| D1 | Delete openai_service dead cluster (~640 LOC): `summarize_filing_stream` (`:2848`), `generate_editorial_markdown` (`:2663`) + validators `_validate_editorial_markdown`/`_validate_editorial_numbers`/`_collect_structured_number_strings`, `_writer_models` (`:430`) | **Also remove:** the two entries in `test_llm_no_pii.py` `_LLM_ENTRYPOINTS` (`:17,:19`) AND the `monkeypatch.setattr(..., "generate_editorial_markdown", ...)` at `test_summarize_filing.py:70` — **at its post-Wave-0 path `backend/tests/unit/`, since 0a step 3 moved it ⊕**. rg each symbol → 0; suite green. (Caller `summarize_filing` already renders deterministically at `:3504-3511` — no code change there.) |
| D2 | Delete `backend/pipeline/` (784 LOC) + the 3 root pipeline tests + root-conftest shim; mark `backend/docs/plan_sec_pipeline.md` superseded; **fix `.claude/agents/engineering/{ai-engineer,backend-developer}.md`** which cite `backend/pipeline/*.py` as canonical | rg `backend.pipeline|from pipeline` → 0; suite green. |
| D3 | Delete dead Edgar ticker path (`EdgarClient.get_xbrl_data` `:285` + `_extract_xbrl_data` `:498`) + `earnings_whispers` integration | **Also edit `integrations/__init__.py:3,8,9` exports.** Do not confuse with the LIVE `edgar_xbrl_service.get_xbrl_data` (`:455`). rg symbols → 0; suite green. |
| D4 | Delete `RequestMetrics`/`record_request` (`metrics_service.py:139,83`) + the request block from `/metrics` and `/health/detailed` surfaces + the CLAUDE.md advertisement | rg `record_request` → 0; smoke green. |
| D5 | Root strays: `rm /templates`, `/inspect_db.py`. For `/scripts` one-offs: **confirm the deployed Cloud Run start command does NOT invoke `fix_contact_column.py`** (it was a Render start-command) before deleting it + `update_contact_schema.py`; the supersession is the ContactSubmission ORM model, NOT a migration. Keep `cleanup-branches.sh` (doc-referenced only) if still used. | Supersession + start-command check documented in the PR body. |
| D6 | `tasks/` hygiene: ~35 finished plan/todo files → `tasks/archive/`; keep live runbooks (gcp-deploy, launch, security_privacy) at top level | Link check: no live doc references an archived path. |

---

## Wave 2 — Structural refactors

**Batch B (parallel, file-disjoint): S1, S3, F1.** S2 starts after D1 merges. S4 is edgar-scoped and
may run in Batch B. **Batch C (serial, after B): F2 → F4 → F3 → S5.**

| ID | Task | Key decisions & guards |
|----|------|------------------------|
| S1 | **Unify summary orchestrators — treat as a behavior-change refactor.** `generate_summary_background` consumes `stream_filing_summary`'s event stream headless; reconcile into ONE coverage taxonomy and ONE verdict function; remove the duplicated `FilingContentCache` writes (incl. the third copy in `get_or_cache_excerpt`) | Ship behind a settings flag (e.g. `USE_PIPELINE_FOR_BACKGROUND`, default false); flip after a **24–48h PostHog soak** (`generation_succeeded/failed` + `quality_verdict` stable — plus **p50/p95 stream latency + per-summary token cost** when YoY context is enabled on the SSE hot path ⊕); remove the old path in a follow-up PR. **PREREQS:** T1+T2 green; the founder decisions below signed off; **`Summary.filing_id` uniqueness verified/added** (no unique constraint today — migration if absent); Cloud Run job timeout budget rechecked (per-form 60/100/120s vs pipeline flat 120s+75s AI). **The flag MUST gate all of:** previous_filings behavior, the coverage-taxonomy choice (7 vs 9 sections), the verdict semantics (does XBRL grounding now apply to cron?), partial-persistence + quota rules, and whether the 6-K path / inflight-dedup apply when drained by cron. Guards: T1 (SSE unchanged), T2 (background semantics preserved OR changed only per a signed-off decision), zero funnel events from cron. |
| S2 | Split `openai_service.py` behind a façade: `extraction/grounding`, `json_repair`, `section_recovery`, `xbrl_narrative`, `markdown_render`, `copilot_chat`; `openai_service.py` re-exports (zero caller churn); pure moves | After D1. Extend `test_ai_service_does_not_import_user_model` to walk the NEW package (the façade-only `hasattr` check goes blind post-split). Suite green after EACH module move. |
| S3 | Auth extraction: `issue_session(user, response)` helper (5 call sites), `oauth_verify` module (Google/Apple JWKS + id-token), password helpers; router keeps HTTP | Anchored by `test_auth_flow.py` (strongest suite) + T8. **Byte-identical `Set-Cookie`** asserted — no cookie-name/flag changes. |
| S4 | Ingestion hardening (edgar/ + integrations/ ONLY): route the **4** raw-httpx SEC calls (`xbrl_service.py:807`, `facts_service.py:453`, and **both** `compat.py` calls — `:69` tickers + `:303` document-fetch, which carry the breaker but bypass the limiter ⊕) through `sec_rate_limiter`; apply `run_with_circuit_breaker` on the primary edgartools path (**~17** unwrapped sites: `client.py` ×12, `xbrl_service.py` ×4, `sixk_extractor.py:117` ⊕); add timeouts to the 5 bare executor DataFrame calls (`xbrl_service.py:677,711,743`; `client.py:509,516`); **ONE concept-list constants module covering the ~6 sites**; collapse `facts_service`'s companyfacts parser into a shared fn with `_parse_company_facts` | Guards: T9 fixture + existing extraction suites; assert breaker-OPEN short-circuits the primary path (extend `test_circuit_breaker`); 24–48h Sentry/log soak. Remove the `facts_service` `sleep(0.2)` fake throttle once the real limiter is wired. |
| F1 | Frontend: ONE `ApiError` (kill the interface/class name collision, `types.ts:2` vs `client.ts:6`), `lib/queryKeys.ts` registry, reconcile `['user']`/`['current-user']`/`['subscription']`(also `['subscription', id]`)/`['usage']` to canonical keys | vitest + tsc + build; grep-gate: no string-literal query keys outside `queryKeys.ts` for reconciled entities. |
| F2 | Decompose `app/filing/[id]/page-client.tsx` (1,016 LOC): `useSummaryGeneration` hook → `features/summaries`; the 2 export `fetch()`s (`:753,:789`) → feature api on the shared axios client; presentational subcomponents | After F1 (imports queryKeys). Guarded by T10 + e2e filing-page spec. **Latent bug L1 (poll-forever on `partial`) is fixed HERE as an explicit decision** — the poller must treat `partial` as terminal and render `partial_data`. |
| F4 | Route stray `fetch()` through the shared client: `WaitlistForm/Counter/Status`, `HotFilings` | After F1, BEFORE F3 (F3 moves these files). |
| F3 | `components/` → `features/` (~25 root components + 4 duplicate subdirs), one domain per commit; merge test dirs to ONE home + suffix | Last frontend task (mass import-path rewrite). tsc + vitest + build after EACH domain batch. |
| S5 | Mechanical backend sweeps, serialized LAST (touch files S1/S3 rewrote): one aware-`utcnow()` helper replacing 36 naive sites (+delete ~6 `tzinfo` patches); config bypasses → Settings (`users.py` Stripe/PostHog, raw `ENVIRONMENT` reads, `IP_HASH_SALT`); ONE placeholder-pattern module (3 today); ONE `FilingContentCache` write helper; ONE `_coerce_float` util; the single stray `green-*` class in `HeroExample.tsx` | Each sweep = its own commit + grep-gate (`rg 'datetime.utcnow'` → 0 in app/; `rg 'os.getenv'` → allow-list only). |

**Explicit NON-goals (do not build):** no Alembic; no async-SQLAlchemy migration; no Redis-backed
rate limiter/dedup; no error-shape unification (frontend depends on current shapes); no shared
integrations base-class. **Do NOT touch:** entitlements/billing (exemplar), `refresh_token_service`,
the design system (the one `green-*` class is the only fix).

---

## Wave 3 — Memory system (docs; start after Wave 1, finalize after Wave 2)

| ID | Task |
|----|------|
| M1 | Create root `lessons/` (one lesson per file: one-line imperative rule + Date/Area/Context/Rule/Evidence; `README.md` index). Split `tasks/lessons.md` into per-file lessons + the ~16 seed lessons (test-suite locations, SEC rate-limits-are-per-process, e2e-runs-without-backend, contract-tests-are-locked, query-keys-registry, migrations-reapply-every-deploy, two-summary-paths, no-alembic, redis-off-in-prod, etc.). Plain markdown, greppable. |
| M2 | ADR-0006 "DeepSeek supersedes ADR-0002 (Gemini)"; mark 0002 Superseded. Fix CLAUDE.md drift NOW only where it misleads: the dead `pipeline/`, the `update_contact_schema.py`-"removed" falsehood (CLAUDE.md:855 + ADR-0001:19), root strays, missing services (invite/precompute/index_membership/reporting_this_week/earnings_calendar/summary_sections, alpha_vantage). **Also purge dead `generate_editorial_markdown` refs from the two live docs `docs/AI_API_OPTIMIZATIONS.md` + `docs/report-quality-improvement-plan.md` ⊕** (a third ref in `docs/history/` is archival — leave or annotate). |
| M3 | Publish CLAUDE.md v2 (~150-line index: identity / commands incl. the real `ruff+bandit+pytest` gate / repo-map pointers / non-negotiable rules / workflow). LAST — it documents the end state (one orchestrator, `queryKeys.ts`, single test home). Move reference detail into the docs it duplicates (`docs/ARCHITECTURE.md`, `lessons/`, `DESIGN_SYSTEM.md`). |

Keep ADRs as immutable WHY; `lessons/` as mutable HOW. CLAUDE.md v2 must not lose load-bearing detail
— every dropped section moves to a pointer target, verified present.

---

## Founder decision points (sign off before the gated tasks)

1. **▲ S1 `previous_filings` (the #1 product decision — the paths diverge TODAY):** should the
   user-facing SSE 10-K summaries START including prior-year YoY trend context (matching what
   pregenerated ones already have), or keep them without it? Recommendation: **converge toward
   including YoY context on both surfaces** (it's the richer product and removes a silent
   inconsistency) — but this is a genuine product call, so gate it behind the flag and A/B on the
   soak. **The soak MUST also watch p50/p95 stream latency + per-summary token cost ⊕** — YoY context on
   the user-facing hot path adds an EDGAR/DB fetch + prompt tokens, so latency/cost join success/quality
   as flip criteria. Fallback: keep per-path behavior via a parameter and revisit.
2. **S1 coverage taxonomy & verdict:** adopt one section taxonomy (recommend the 9-section
   `_TRACKED_STRUCTURED_SECTIONS`, the richer surface already shown in progress) and one verdict
   function (recommend `assess_quality` incl. its XBRL-grounding check applied to cron too —
   stricter, more honest partials).
3. **S1 `Summary.filing_id` unique constraint:** add via idempotent migration (recommend yes —
   closes the concurrent pregenerate+SSE double-insert, latent bug #3).
4. **`backend/pipeline/`:** DELETE (recommended — dead; git preserves it).
5. **Metrics request block:** DELETE (recommended — nothing scrapes it).
6. **Root `/scripts` one-offs:** delete after the start-command + supersession check (recommended),
   else move to `backend/scripts/`.
7. **`--max-instances` in CI:** add the pin to `ci.yml`'s deploy step (recommended — today it lives
   only in the runbook and can silently drift).

---

## Verification (how the plan's claims were checked, and how execution is verified)

**Claims (this session):** three parallel read-only audits traced every load-bearing symbol by name
(not line number) and adversarially hunted for callers. Result: no dead-code claim refuted; resilience
bypass confirmed; test/CI/frontend/latent-bug claims confirmed; corrections above folded in.

**Per-PR gates (binding on every execution agent):**
- Backend: `cd backend && ruff check . && bandit -r app -ll && python -m pytest`
  (+ `python -m pytest -m performance` when touching streaming/concurrency).
- Frontend: `npm run lint && npx tsc -p tsconfig.ci.json && npm run test -- --run && npm run build`.
- **Deletion PRs:** `rg` each removed symbol → 0 (excluding `tasks/archive/`); report LOC + test-count
  delta; edit coupled tests/exports in the same commit.
- **Contract-test lock:** T1–T10, `test_auth_flow.py`, the Stripe webhook tests may be edited in a
  refactor PR ONLY to remove references to symbols deleted in that same PR. Any other edit = STOP,
  surface to the founder.
- **Behavior-change firewall:** Waves 1–2 are behavior-preserving by definition; any semantic change
  (S1's decisions, the latent bugs) must be pre-approved and listed in the PR body as an explicit
  contract change with its updated anchor test.
- **Flag + soak:** S1 and S4 ride a flag/observation cycle — 24–48h of PostHog + Sentry/Cloud Run
  logs before flag-flip or old-path removal (CI e2e runs with no backend, so prod telemetry is the
  only real end-to-end signal).
- **Baseline discipline:** Wave 0 records {count, wall time, green SHA}; every wave re-records; counts
  move only by explained amounts (adopted +N, deleted-with-code −M).
- **Stop conditions:** unrelated test failures, a contract test needing a non-deletion edit, or any
  discovery contradicting these findings → stop, report, re-plan. Subagents do not make product calls.

**Payoff:** ~2,200 LOC dead app code deleted + duplicated orchestration collapsed + ~35 stale docs
archived; `openai_service.py` lands under ~800 LOC core; resilience actually applied on the primary
SEC path; a contract-anchored suite; a per-file, greppable memory system.

---

## On approval
Persist this document to the repo as `tasks/architecture-refactor-plan.md` (descriptive-filename
convention in `tasks/`), then begin **Wave 0** (the blocking gate) as the first unit of work.
Appendix A below is carried verbatim so the CLAUDE.md v2 draft isn't lost (⊕ second-review addendum 3);
M3 publishes it after Wave 2 (updating any details the refactor changed).

---

## Appendix A — CLAUDE.md v2 draft (full text; carried so it isn't lost ⊕)

```markdown
# CLAUDE.md — EarningsNerd

AI-powered SEC filing analysis (10-K/10-Q → grounded summaries for investors). Solo-founder
project: optimize for maintainability, small diffs, and verified behavior.
Stack: FastAPI + sync SQLAlchemy + PostgreSQL (Cloud Run) | Next.js 16 + React 18 + Tailwind +
React Query (Vercel) | AI via OpenAI-compatible API (DeepSeek default; OPENAI_BASE_URL +
AI_DEFAULT_MODEL env-configurable) | Stripe, Resend, PostHog, Sentry.

## Read before working
- lessons/README.md — hard-won operating rules, one file each; scan the index, open what applies.
- docs/adr/ — settled decisions (hosting, edgartools, Redis-off-in-prod, React 18, AI provider).
  Don't re-litigate; supersede with a new ADR.
- docs/ARCHITECTURE.md — system map. frontend/DESIGN_SYSTEM.md — MANDATORY before UI work.
- backend/evals/RUNBOOK.md — before changing prompts, models, or AI flags.

## Commands
Backend (from /backend):
- Dev: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
- FULL local gate (all three, before every push): `ruff check . && bandit -r app -ll && python -m pytest`
- Fast lane: `python -m pytest` (pytest.ini deselects performance/slow by default);
  full: `python -m pytest -m ""`
Frontend (from /frontend):
- `npm run dev` | gate: `npm run lint && npx tsc -p tsconfig.ci.json && npm run test -- --run && npm run build`
Infra: `docker-compose up -d postgres redis` (Redis is DEV-ONLY; prod runs L1 in-memory cache only — ADR-0004)

## Non-negotiable rules
1. **Migrations:** no Alembic. Fresh-DB schema via create_all at startup; ANY change to an existing
   table = a new idempotent SQL file in backend/migrations/ (CI re-applies ALL files every deploy —
   must be safe to re-run). Never edit an applied migration.
2. **Entitlements:** app/services/entitlements.py is the ONLY source of plan truth. Never hardcode
   plan limits or Pro checks elsewhere.
3. **SEC calls:** all sec.gov traffic goes through the edgar service layer (rate limiter + circuit
   breaker). Never raw httpx to sec.gov outside it. SEC cap is 10 req/s per IP — an IP ban takes
   the product down.
4. **Boundaries:** validate external data where it enters (SEC, Stripe, AI responses); do NOT
   re-validate internally-produced data downstream.
5. **Contract tests** (SSE stream contract, auth flow, Stripe webhooks) must not be edited in the
   same PR as the code they guard. If one must change, stop and surface it first.
6. **Data integrity:** Filing.sec_url/document_url are NOT NULL (event-listener enforced);
   URL format rules in lessons/sec-filing-url-format.md.
7. **datetime:** always timezone-aware UTC via the shared utcnow() helper; never datetime.utcnow().
8. **Config:** all env access through app/config.py Settings; never os.getenv in app code.
9. **Design system:** any theme/token change is app-wide (public + authed). Done-gate = the
   legacy-color grep in DESIGN_SYSTEM.md returns nothing AND both themes verified on preview.

## Where things live
- backend/app/routers = HTTP only; backend/app/services = business logic. Summary generation has
  ONE orchestrator: services/summary_pipeline.py (SSE endpoint and background/cron both consume it).
- frontend/features/<domain>/ = domain code (api/ + components/). frontend/components/ = ui/ +
  chrome (Header/Footer/boundaries/logos) ONLY. Query keys live in lib/queryKeys.ts.
- Tests: backend/tests/{unit,integration,smoke,performance} (markers in pytest.ini);
  frontend/tests/{unit,e2e}. NO other test roots — a test outside these does not run in CI.
- One-off scripts: backend/scripts/ with a docstring header. Nothing executable at repo root.
- Plans → tasks/todo.md; finished plans → tasks/archive/; lessons → lessons/ (never back into a monolith).

## Deploy
CI (.github/workflows/ci.yml): backend gate = ruff + bandit + pytest; frontend gate = eslint +
tsc + vitest; e2e = Playwright. deploy-backend runs on main: applies backend/migrations/*.sql to
Cloud SQL, then deploys Cloud Run service + updates the 5 Cloud Run jobs (pregenerate,
filing-scan, digest, backfill-facts, earnings-calendar). Manual fallback: tasks/gcp-deploy-runbook.md.

## Workflow
- Plan mode for any non-trivial task; verify before done (run the gates; for UI, eyeball both themes).
- After ANY user correction: add or update a file in lessons/ following lessons/README.md format.
- When docs contradict code, the code is truth — fix the doc in the same PR and note it.
```

> M3 note: before publishing, reconcile this draft with the actual end state (one orchestrator name,
> `queryKeys.ts`, single test home, the `--max-instances` CI pin, and the DeepSeek/ADR-0006 provider line).
