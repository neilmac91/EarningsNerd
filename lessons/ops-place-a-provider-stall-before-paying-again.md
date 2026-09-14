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

**Rule**: When a keyed inference call stalls, do not rerun the paid corpus, lengthen
production deadlines or swap providers. Dispatch `deepseek-transport-diagnostic.yml`
first: it runs an unauthenticated POST, a keyed free GET, the application's exact request
shape and the bare default request, and records httpcore phase timestamps (connect, TLS,
send, response headers) so the stall lands at one layer. Only after the exact production
shape completes there is a single paid rerun justified, and the reason and expected cost
go on the PR before the ready transition. Read the balance before and after; an unchanged
balance across failed requests is evidence about billing, not proof of zero provider load.

**Enforcement**: the diagnostic is the mechanism, kept under `workflow_dispatch` only with
`test_retired_model_ids.py` holding it to the shared model configuration. Merge timing and
spend decisions are not properties of the tree, so this lesson has no tree-level gate;
the PR comment recording the rerun reason is the reviewable artifact.

**Evidence**: runs 34898642117 and 34899733464; #864, #865; `tasks/review-evidence/resumption-2026-09-14/inference-stall.md`.
