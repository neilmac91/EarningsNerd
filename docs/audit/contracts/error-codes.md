# Error-code contract (E31)

Day-zero interface from Agent A (identity) for every producer of a refusal a browser must act on (Agent B:
billing and entitlement emitters; Agent C: summary, analysis and Copilot emitters and their API adapters; Agent E:
`main.py` registration) and for the frontend matchers that read them today. It adds one optional machine-readable
field, `code`, beside the words the backend already sends, so the client can stop choosing navigation, modals,
retries and upgrade prompts by matching prose. Nothing here replaces `detail`, `message`, a status code or a route.
Code is truth: where this document and the code disagree after either lands, the code wins and this file is
corrected in that pull request ([AGENTS.md §2](../../../AGENTS.md#2-precedence-when-documents-conflict)).

| | |
| --- | --- |
| Item | E31 (P1). High tier wherever it touches `dependencies.py`, `main.py`, `routers/{auth,subscriptions}.py`, `summary_stages/**` or `routers/summaries.py` |
| Contract and generic seam owner | Agent A: `backend/app/error_codes.py` and `backend/app/api_errors.py` (new), `backend/app/dependencies.py`, `frontend/lib/api/client.ts`, `frontend/lib/api/types.ts`, `frontend/app/dashboard/error.tsx` |
| Producers | B: `routers/subscriptions.py`, entitlement and billing refusals. C: `summary_stages/admission.py`, `routers/summaries.py`, `routers/analysis.py`, Copilot. A: `routers/auth.py`, `dependencies.py`. E: the `main.py` handler |
| Consumers | A: `lib/api/client.ts`, `app/dashboard/error.tsx`. C: `features/summaries/api/summaries-api.ts`, `features/filings/api/copilot-api.ts`, `features/analysis/api/analysis-api.ts` |
| Accepted policy | Neil, 2026-10-25: additive error codes, legacy API compatibility kept, changed locked expectations documented |
| Base read | `main` at `086de72` |

## 1. Wire format

**HTTP.** An error body may carry a top-level string `code` beside its unchanged `detail`:

```json
{"detail": "Verify your email address before you subscribe.", "code": "email_verification_required"}
```

The status, headers (`WWW-Authenticate`, `Retry-After`) and `detail` (a string, or FastAPI's validation list)
stay exactly what they are today. `code` is absent wherever no row of §3 applies. The repository already ships this
shape once: the free earnings-alert cap answers 403 `{"detail": ..., "code": "earnings_alert_limit"}`
(`backend/app/routers/watchlist.py`, read by `frontend/features/calendar/api/calendar-api.ts`). That code stays as
it is and is registered in §3.

**SSE.** A stream's error event may carry the same field beside its unchanged keys:

```json
{"type": "error", "message": "You've reached your monthly limit of 5 summaries. Upgrade to Pro for unlimited summaries.", "code": "free_allowance_exhausted"}
```

Frames stay `data: <json>\n\n` with no `event:` line (`summary_pipeline.to_sse`), `type` stays the discriminator,
and keys that exist today (`summary_id` on finalize's error) stay. No new event type is introduced.

**Spelling.** A code is lowercase ASCII snake case, `^[a-z][a-z0-9_]{2,63}$`. A code keeps one meaning forever: a
changed meaning takes a new code, and a retired code is never reused.

## 2. Compatibility during a rolling deployment

Frontend (Vercel) and backend (Cloud Run) deploy independently, and old tabs outlive both. Every pairing works:

| Server | Client | Behaviour |
| --- | --- | --- |
| old, no `code` | old | as today |
| new, with `code` | old | the old client never reads `code` (`detailMessage` reads `detail` only; the SSE readers read `message` only) and behaves as today |
| old, no `code` | new | the new client finds no code and runs today's status and prose matchers, kept as the fallback |
| new, with `code` | new | the known code decides; the prose may then change without changing behaviour |
| new, code unknown to this client | new | treated as absent: status and prose decide, as today |

Two rules make an unknown or wrong code harmless:

1. **A code is honoured only on its registered channel** (§3's second column). On an HTTP error response that is the
   code's registered status: a 500 that carries `plan_required` is a 500. On a stream it is an event of `type`
   `"error"` carrying a code §3 registers for SSE, whatever the stream's own 200; an HTTP-only code inside a stream
   event is ignored. The status-based behaviour that exists today (silent refresh on a 401, `isRetryable` for
   429/5xx) is never switched off by a code.
2. **A code never grants anything.** It can choose which refusal UI to show, whether to offer a retry and where to
   navigate. It never marks a request as succeeded, never unlocks a gated control, and never triggers a refresh or
   a re-login by itself: the refresh flow stays keyed on status 401, the request path and an active session, as in
   `lib/api/client.ts` today.

The legacy prose matchers (`backendMessageMatches.spec.ts`, `backend/tests/unit/test_frontend_matchers_parity.py`)
stay in force until every producer of §3 has shipped its code and §6's fixtures pass across owners. Retiring them,
and any rewording that would break them, is later work (E37, E68, F56), unblocked only then.

## 3. Vocabulary, version 1

Six cases from the E31 scope, plus the one code already in production. "Producer" names the owning agent and the
exact site found on `086de72`. "Client" says what a recognised code makes the browser do. Each is today's behaviour,
now keyed on the code, except where the row says otherwise.

| Code | Status (HTTP) / channel | Producer sites today | Client behaviour |
| --- | --- | --- | --- |
| `auth_required` | 401 | **A**: `routers/auth.py::get_current_user` ("You are not logged in."), reached through `dependencies._resolve_current_user`. **C**: the PDF and CSV export 401s in `routers/summaries.py` ("Authentication required"). Not in v1: `admin.py::_require_admin`, and the refresh and login 401s, which are session and credential answers, not feature gates | Keep the existing silent refresh and replay on 401. When the refresh is refused with 401 (`sessionLossConfirmed`), or the path is not refreshable, show the log-in state; a refresh refused any other way (429, 5xx, network) is not session loss. The dashboard boundary routes to `/login`. Today it tests words that no message reaching it carries (`backendMessageMatches.spec.ts`'s UNSOURCED rows), so this is E31's fix, not a restatement. The stream readers keep today's 401 handling, Retry included: `streamErrorCopy.spec.ts` pins that no 401 reads as non-retryable |
| `email_verification_required` | 403 | **B**: `routers/subscriptions.py::create_checkout_session` ("Verify your email address before you subscribe.") | Dispatch `EMAIL_VERIFICATION_REQUIRED_EVENT` (the verification modal), then surface the detail as today |
| `plan_required` | 403 | **A**: `dependencies.py::require_entitlement`, `require_pro`, and `require_copilot_or_taste` when the taste allowance is 0 (its words from `copilot_taste_exhausted_detail`). **C**: `routers/summaries.py` regenerate ("Regenerating a summary is a Pro feature.") and the PDF/CSV export refusals; `routers/analysis.py` PDF export | Show the plan or upgrade card for the surface; never offer Retry |
| `free_allowance_exhausted` | 403 (HTTP); SSE `error` | **A**: `require_copilot_or_taste` with allowance > 0. **C**: the serialized Copilot admission in `routers/summaries.py`, which raises the same words (both build them with `copilot_taste_exhausted_detail`). **C**: `summary_stages/admission.py`, the free monthly summary limit (SSE) | Show the upgrade card (Free's allowance is used up); never offer Retry; the summary surface also fires `paywallPromptShown` |
| `pro_fair_use_limit` | 429 (HTTP); SSE `error` | **C**: `summary_stages/admission.py`'s Pro ceiling (SSE; its sentence says "paused", but it is the monthly fair-use cap, not a transient pause), the Copilot cap 429 in `routers/summaries.py`, the analysis cap 429 in `routers/analysis.py` | Show the plan card **without** an upgrade button (the user already has Pro) and the reset timing; never offer Retry. A 429 **without** this code stays a plain rate limit (`Retry-After`), retryable as today |
| `generation_paused` | 503 (HTTP); SSE `error` | **Reserved: no producer on `086de72`.** No kill switch or generation-level flag exists. The candidates are C's: the chat provider-admission wait (`services/ai/provider_admission.py`) and a future operator pause. Whether either emits it is C's decision in its own pull request | Show a transient "try again shortly" state with Retry; never an upgrade card; never counted as a plan limit |
| `earnings_alert_limit` | 403 | Existing: `routers/watchlist.py` free earnings-alert cap (the calendar's own reader keeps it) | Unchanged: `features/calendar` keeps its own `validateStatus` reader |

Producers not in the table emit no code in this wave. A new code is added by a pull request that edits this table,
the backend enum and the client's known set together (§4 makes that a gate).

## 4. The shared primitives (Agent A)

**Backend**, split so a service can emit a stream code without importing the HTTP layer:

- `backend/app/error_codes.py` (new, imports no HTTP framework, so `summary_stages/admission.py` and other services
  may import it): `class ErrorCode(StrEnum)` holds the table's codes; `REGISTERED_STATUS` maps each to its HTTP
  status; `STREAM_CODES` is the set §3 registers for SSE. `def sse_error(message: str, code: ErrorCode, **fields) ->
  dict` returns `{"type": "error", "message": message, "code": code.value, **fields}` and raises `ValueError` for a
  code outside `STREAM_CODES`, so a producer's own test of that branch fails instead of shipping a code the client
  ignores.
- `backend/app/api_errors.py` (new, for routers and `dependencies.py`): `class CodedHTTPException(HTTPException)`
  takes `code`, `detail` and optional `headers`, and its status is `REGISTERED_STATUS[code]`, so a code cannot be
  sent on the wrong status. It replaces an `HTTPException` of that status with the same `detail` and headers.
  `coded_http_exception_handler` answers it as `JSONResponse({"detail": exc.detail, "code": exc.code}, ...)`.
- `backend/tests/unit/test_api_error_codes.py` fails when the backend's table, the client's (`ERROR_CODES` in
  `frontend/lib/api/client.ts`) and §3 of this file differ in a code, a status or the SSE channel (CLAUDE.md rule 12:
  the gate lands with the primitive).
- The watchlist's existing `earnings_alert_limit` is a literal in a `JSONResponse` today. Moving it onto `ErrorCode`
  is its owner's later change. Until then the gate keeps the name registered.

**Registration** (Agent E, `backend/main.py`): `app.add_exception_handler(CodedHTTPException,
coded_http_exception_handler)`. It must be registered before any producer raises the class, in the same rollout or
earlier. Until it is, FastAPI's `HTTPException` handler answers a `CodedHTTPException` with its status, `detail` and
headers and no code, so the order is safe in both directions.

**Frontend** (`frontend/lib/api/client.ts`, `frontend/lib/api/types.ts`):

- `ERROR_CODES` holds §3's table (status and SSE channel per code), `type KnownErrorCode` is its keys, and
  `parseErrorCode(value: unknown, on: number | 'stream'): KnownErrorCode | undefined` returns a code only when
  `value` is a known code string arriving on its registered channel: `on` is the error response's status, or
  `'stream'` for a stream's error event. The channel is a required argument, so no caller can skip the check.
  Everything else is `undefined`.
- `ApiError` gains `code?: KnownErrorCode`, set by the response interceptor from `error.response.data.code`. Its
  constructor stays `(status, detail)`, as the 53 test constructions in `frontend/tests/unit` use it, and
  `status`, `detail`, `backendDetail`, `isRetryable` and `sessionLossConfirmed` keep their behaviour.
- The verification dispatch and the dashboard boundary read the code first, then today's prose.
- C's three SSE readers call `parseErrorCode(data.code, 'stream')` on an error event and
  `parseErrorCode(body.code, response.status)` on an error body. They own their adapters and the order they apply
  the code and the legacy matcher.

## 5. What each owner changes, and what it must not

- **A**: the primitives of §4, `dependencies.py`'s emitters (C's named E37 patch lands after this vocabulary,
  keeping status and old-client fallback), `get_current_user`'s 401, `client.ts`, `types.ts` and
  `app/dashboard/error.tsx`.
- **B**: `create_checkout_session`'s 403 and any other entitlement or billing refusal B owns, as rows of §3.
- **C**: the admission SSE errors, the summary, analysis and Copilot HTTP refusals, and the three readers.
- **E**: the `main.py` handler of §4.
- **No owner** rewrites a `detail` or `message` in the pull request that adds its code. Copy changes follow under
  their own items once §6 passes.

**Locked expectations.** Several existing tests compare whole bodies or whole events, so an added `code` key
changes them. Each producer's pull request names its rows as an accepted contract change (CLAUDE.md rule 6,
Neil's 2026-10-25 acceptance of additive codes) and edits only the added key:

- `backend/tests/unit/test_summary_pipeline_anchors_admission.py`: the quota and fair-use event equalities. This
  is a **locked characterization anchor**, so C's pull request documents the exact before and after dicts.
- `backend/tests/unit/test_cached_filings_pool_lifetime.py`: the export and Pro-gate body equalities (the
  `[{"detail": ...}] * 8` forms). Its editing lease is serialized between A (E121, F19) and C (E171).
- Substring pins (`test_expired_trial_gating.py`, also a locked anchor, `test_excel_export.py`,
  `test_summary_unready_refresh.py`, `test_force_regenerate_keeps_xbrl.py`) read `detail` and `message` and stay
  untouched.

**Telemetry note.** `code` is an exact key of the Sentry `EventScrubber` denylist (for Apple's form-posted OAuth
code, `app/utils/telemetry_bootstrap.py`). A request body's `code` key is withheld from Sentry events. Response
bodies are not sent to Sentry, so the field costs nothing there and needs no change.

## 6. Closure evidence (E31 closes only on all of it)

Each fixture runs once with the code present, once with it absent (an old server), once with an unknown code, and
once with a known code on the wrong status:

1. **A**: `frontend/tests/unit/apiErrorDetail.spec.ts`, `apiErrorBackendDetail.spec.ts`, `authErrorStatus.spec.ts`
   (interceptor parsing, `ApiError.code`, and the verification dispatch). A prose-change mutation shows that a
   recognised code still routes when the detail's words change.
2. **A**: backend tests for `api_errors.py`, the `dependencies.py` emitters and `get_current_user`, through real
   ASGI requests: status, headers, `detail` byte-identical, `code` present.
3. **B**: `create_checkout_session`'s 403 through ASGI, with and without the handler registered.
4. **C**: `summaryStream.contract.spec.ts` (a locked anchor; additive fixture rows only, documented),
   `summaryStreamAuthRefresh.spec.ts`, the Copilot and analysis reader specs, and the admission SSE events with
   `code`.
5. **E**: the registered handler's ASGI test against `main.app`.

Shared parser tests alone do not close E31. Only producer-to-consumer output from every owner does.

## 7. Open points for the CTO

- `generation_paused` has no producer. C decides whether provider-admission exhaustion is a transient pause worth
  a code, or stays a generic failure.
- The summary exports' 401 says "Authentication required" where `get_current_user` says "You are not logged in.".
  Both take `auth_required`, and unifying the words is copy work for later. `admin.py::_require_admin`'s own 401
  stays out of v1: its callers pass the user `get_current_user` resolved, which has already refused a missing one,
  so that branch is unreachable.
