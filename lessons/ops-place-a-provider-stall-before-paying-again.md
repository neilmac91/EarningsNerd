# Place a provider stall at one layer with free probes before paying for another corpus

Date: 2026-09-14   Area: ops

**Context**: #861's paid Copilot assessment timed out on all 18 requests before a first
token. The obvious suspects were the SDK update in that PR and "a provider incident", and
neither could be told apart by rerunning the corpus: a rerun costs money, mixes 18 inputs,
and reports only `timeout`. A two-request diagnostic that varied the SDK also reported
only `deadline`, which showed main's SDK failed too but still could not say *where* the
request died. Two more bounded runs answered it in twelve minutes. The first sent an
unauthenticated POST through the same transport (401 in 0.6 s), a keyed free `GET /models`
(200), the application's exact request shape (200 headers, then no body, streamed or not)
and the bare default request (completed, billed usage). The second varied one field at a
time and, by then, every shape completed with nothing changed on our side. Conclusion: a
time-bound provider stall on non-thinking requests, not the SDK. The balance did not move
across 22 stalled requests, so stalled requests were not billed either.

**Rule** (a diagnostic procedure, not a tree invariant): when a keyed inference call
stalls, dispatch `deepseek-transport-diagnostic.yml` before rerunning a paid corpus. It
installs the SDK and transport at the committed `requirements.txt` pins, runs the
unauthenticated POST and the keyed free GET first, then the application's exact request
shape, the bare default request and one-field variants, and records httpcore phase
timestamps (connect, TLS, send, response headers) so the stall lands at one layer. A single
paid rerun is justified once the exact production shape completes there; put the reason
and the expected cost on the PR before the ready transition, and read the balance before
and after. An unchanged balance across failed requests is evidence about billing, not
proof of zero provider load. Lengthening production deadlines or changing provider on the
strength of one stall is a separate founder decision, not a diagnostic step.

**Enforcement**: the workflow is the mechanism. `test_retired_model_ids.py` holds it to the
shared model configuration; #869 holds its SDK to the committed pin. Whether a rerun was
diagnosed first is a review-time judgement recorded on the PR, so no tree-level gate is
claimed for the sequencing.

**Evidence**: runs 34898642117 and 34899733464; #864, #865, #869; `tasks/review-evidence/resumption-2026-09-14/inference-stall.md`.
