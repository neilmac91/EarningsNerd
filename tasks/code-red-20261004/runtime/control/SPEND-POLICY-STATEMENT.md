# CEO/CFO safe cost-policy statement for the R3 operating-envelope disposition (2026-10-04T14:49:36Z)

Issued by the chief/CEO, reusing the CFO's completed reconciliation (CFO FIRST-DELIVERABLE, SHA-256
`925fcc6b5a0a69c65fa1813c9d2da738a8f28b3cb1b011e22cb430a4354f476c`) and the chief's ledger access
statement (`control/LEDGER-ACCESS.md`). No CFO worker was launched: no exact paid action is proposed.

| Item | Value | Status |
|---|---|---|
| Shared future DeepSeek authority | USD 15.000000 (founder, 2026-10-03T21:49:32Z) | one combined ceiling; not per run or per chat; not additive to old allowances |
| Recorded future-window use at snapshot | 297 calls / USD 0.547516 | telemetry estimate, not an invoice |
| Retained distinct holds | USD 1.881713 (other-owner 1.000000; uncertainty 0.600000; cancelled-run unknown 0.281713, not zero) | retained |
| Conditional unreserved at snapshot | USD 12.570771 | **snapshot only** (ledger SHA-256 `99c7259f…`, 2026-10-04T09:35Z) |
| Live ledger | not reachable from this session | **paid dispatch, reservations and ledger writes HELD** |
| Provider operating-spend field for the beta envelope | **HOLD** | no reservation can be recorded without the live ledger; no spend is proposed by the CTO handback |

Policy applied to the disposition: recorded budgets stay distinct from actual spend, reservations,
runtime concurrency and capacity. The USD 15 ceiling is **not** concurrency, capacity or runtime-budget
admission. A ZIP snapshot is not a spend lock. Pricing (PR1009) stays draft-held at the approved
USD 19/month or USD 190/year; no Stripe, promotion, trial, registration or invitation change. If the
disposition reaches a point where a provider operating budget must be named, it records that field as
HOLD with the dependency "live ledger access or founder hash confirmation" and owner CEO.
