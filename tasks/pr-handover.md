# PR Handover & Audit Backlog Status (2026-06-13)

Record of the audit-backlog execution: the verified disposition of the M1–M10 medium
findings, the now-drained open-PR queue, the remaining non-PR follow-ups, and the
operator runbook for the actions that need maintainer input.

> **Status: PR queue COMPLETE.** All ten medium findings are merged, dismissed-by-decision,
> or verified already-fixed. The only remaining work is non-PR (operator actions + eval-gated
> flag flips), captured in §4–§5.

---

## 1. Medium findings (M1–M10) — final status

| # | Finding | Disposition |
|---|---------|-------------|
| **M1** | Two conflicting `vercel.json` (sfo1 vs iad1, divergent env) | ✅ **merged** — PR #267 (single source of config) |
| **M2** | Sentry DSN hardcoded in `frontend/vercel.json` | ✅ **merged** — PR #267 (DSN → Vercel dashboard env vars; both set + verified) |
| **M3** | SEO canonical host mismatch (`www` vs apex/`api`) | ✅ resolved-by-decision — `www` confirmed the intended canonical host |
| **M4** | N+1 in `filings.py:377` (per-iteration `.first()` in loop) | ✅ fixed — verified on `main`: single prefetch `IN (...)` query |
| **M5** | No backend lockfile; deps float across majors/0.x | ✅ merged — pip-tools lockfile |
| **M6** | Frontend skew (Next16+React18, eslint-config-next@14, EOL ESLint 8) | ✅ **merged** — PR #264 (ADR-0005 records the React-18 stay); ESLint side addressed by the merged lint-gate migration |
| **M7** | Heavy business logic in router (`stream_summary`, 590 lines) | ✅ **merged** — PR #268 (extraction) + PR #272 (hardening) |
| **M8** | No `engines.node` / `.nvmrc` | ✅ resolved — verified: `engines.node: "20.x"` + `.nvmrc` (20.19.0) |
| **M9** | Export endpoints leak `str(e)` | ✅ merged |
| **M10** | All AI tasks use the Pro model (`gemini-2.5-flash` unused) | ✅ merged as an opt-in, **default-off** seam (A11) — flip gated on the S3 eval baseline (§4) |

---

## 2. Related higher/other findings — merged

- **H2** (two summary pipelines diverged) → merged ("Unify on the streaming summary pipeline").
- **H3** (retire legacy `sec_edgar.py` / dead `xbrl_service.py`) → merged; context in issue #244.
- **H4 tail / ruff** (clear findings + make lint gate blocking) → merged.
- **Frontend ESLint flat-config gate** → merged.

---

## 3. Open-PR queue — execution record (all resolved 2026-06-13)

All branched from an older `main`, so each was rebased onto current `main`, ran a full green
CI suite (backend, frontend, e2e), and squash-merged. Final `main` @ `03903e8`.

| PR | Item | Outcome |
|----|------|---------|
| #261 | Dependabot lxml 5.4→6.1 | **Closed** — superseded by #266 |
| #263 | P3 hygiene (utcnow, dup constant, return hints, dead stub) | **Merged** — rebase dropped the obsolete `summaries.py` hunk (code moved to `summary_pipeline.py` via #268); net change is the JWT-identical `utcnow → now(timezone.utc)`, return hints, stub deletion |
| #264 | ADR docs (incl. M6 React-18 decision) | **Merged** |
| #265 | a11y fixes on `/pricing` | **Merged** |
| #266 | lxml 6.1.x XXE fix (CVE-2026-41066) | **Merged** (backend deploy) |
| #267 | Vercel config + Sentry DSN→dashboard (M1/M2) | **Merged** (by maintainer; Vercel env vars set first) |
| #272 | M7 pipeline hardening | **Merged** — kept `PIPELINE_TIMEOUT_SECONDS = 120` (fallback-favoring) |

**Deploy:** the `#263` merge produced the final `main` run, which deployed the backend
(lxml security + pipeline hardening + auth hygiene) to Cloud Run via WIF; Vercel redeployed
the frontend (a11y `/pricing` + the M1/M2 config). Confirmed through image build/push +
Cloud Run revision deploy; the workflow's `Verify health` step gates success and Cloud Run
only shifts traffic to a healthy revision.

---

## 4. Remaining non-PR follow-ups (gated or deferred)

- **Adoption flips — gated on the S3 eval baseline** (`backend/evals/`, needs provider API
  keys + SEC network). Flip a default **only** if a candidate beats baseline on
  schema-validity + numeric accuracy + coverage:
  - **M10 / A11** — `AI_FAST_MODEL` / `AI_SECTION_RECOVERY_MODEL` (route cheap tasks to `gemini-2.5-flash`).
  - **S1** — `AI_USE_STRUCTURED_OUTPUT` (schema-first prompts + enforced JSON).
  - **S4** — `AI_QUALITY_GATE` + `NEXT_PUBLIC_ENABLE_QUALITY_BADGE` (honest degradation).
  - **S5** — `ENABLE_GUEST_DAILY_QUOTA` (per-IP guest cap).
- **S2 follow-up (deferred):** replace the Apple-specific segment regex (`filing_parser.py:~754`)
  with XBRL-derived segments.

---

## 5. Operator runbook — actions waiting on the maintainer

### A. Sentry (M1/M2 — #267) — ✅ DONE
`NEXT_PUBLIC_SENTRY_DSN` + `SENTRY_DSN` set in Vercel (Production + Preview), verified valid
(EU region). Takes effect on the post-merge build. **Post-deploy check:** trigger a test error
on the live site and confirm it appears in the Sentry project.

### B. `NEXT_PUBLIC_EXAMPLE_FILING_ID` — ✅ DONE
Set to `3` and verified against the live API: filing 3 = AAPL 10-K (2025-10-31) with a
populated summary, so the homepage hero + "See an Example" CTA serve real cached content
instantly. Takes effect on the next frontend build.

### C. Refresh-token rollout — verify in prod (post #269/#270)
1. Log in on the live site; confirm both cookies exist: `earningsnerd_access_token` **and**
   `earningsnerd_refresh_token`.
2. Past the 30-min access TTL (or delete just the access cookie), make an authenticated
   request → confirm a silent `POST /api/auth/refresh` (200) keeps you logged in (no bounce).

### D. Homepage v2 — Phase 4 (Measure)
1. Flip the launch gate (`tasks/launch-runbook.md`).
2. Build the PostHog funnel dashboard (`generation_started/succeeded/failed/timed_out`,
   `summary_viewed`, `example_cta_clicked`).
3. Collect a 2-week baseline, then start the A/B program.

### E. (When ready) Run the S3 eval baseline to unlock the §4 flips
1. Provide provider API keys + SEC network access in the eval environment.
2. Run `backend/evals/` baseline vs candidate (structured-output / cheap-model).
3. Flip a default flag **only** if the candidate wins on schema-validity + numeric accuracy + coverage.
