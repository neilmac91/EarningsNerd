# Source capacity preflight — 23 September 2026

The offline CLI measures hash-bound whole-input HTMLParser events without building the source projection or its per-character byte-offset array. It verifies the expected byte count and SHA-256 on the same bounded buffer it parses, requires exact callback positions and complete byte coverage, and preserves the existing 64 MiB source / 2 MiB event limits. Exclusive output creation prevents overwriting another audit. This is an engineering prerequisite for selecting review units; it cannot admit E7 evidence or establish semantic coverage.

## Actual-source measurements

Measured code `abf4ca640d48b35be5099b2b6883c3298cf2d3b3` under Python 3.11.16. All three revised primary source identities match the governing source map. Original candidate hashes are historical and are not substituted. No source packet was changed.

| Primary | Source bytes | Parser events | Largest event bytes | Wall seconds | Peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| H01 | 6,100,579 | 137,099 | 1,499 | 0.605 | 45.20 |
| H02 | 16,080,286 | 355,227 | 2,186 | 1.165 | 65.02 |
| H25 | 57,158,558 | 1,278,811 | 941 | 3.490 | 141.56 |

[Pilot receipt](pilot-receipt.json) binds code, source, audit and measurement identities. All final audit bytes match the provisional b73492dd results; final code, timing and RSS were measured again after the callback correction. Peak memory applies only to this preflight on this machine. Full structural projection, model context, all 980 submission members, graphics and other modalities remain separate capacity obligations. No leaf size or hierarchy admission policy is selected by these results.

## Verification

**3656 passed, 40 warnings in 158.95s (0:02:38)**, zero failures/errors/skips. All four PostgreSQL lanes (24/29/6/5 cases), two performance cases, Ruff, Bandit and dependency checks passed. [Gate receipt](full-gate-receipt.json). The known interpreter-shutdown logging warning followed successful pytest completion.

The existing single invariant compares representative UTF-8/multiline events with the source view, checks source identity before parsing, exclusive audit creation, exact-limit acceptance and overflow rejection. Exactly one committed-state proof per new guard was retained:

- [Raw event-size guard](mutation-proof.json), b73492dd: `1 failed, 2 warnings in 4.88s` after removal; `1 passed, 2 warnings in 0.76s` after byte-identical restoration.
- [Callback-position guard](cursor-mutation-proof.json), abf4ca64: `1 failed, 2 warnings in 0.77s` after removal; `1 passed, 2 warnings in 4.90s` after byte-identical restoration.

Root review found that ignored `</>` markup could be absorbed into a following comment span. The [finding](cursor-finding.json) preserves that evidence, and the [corrective independent review](independent-review-abf4ca64.md) supersedes the explicitly historical b73492dd review. A [new finite 4,096-combination probe](finite-position-probe.json) checks accepted callback mappings after the fix; it is bounded verification, not a general HTML-parser correctness claim.

## Scope and next step

This PR is stacked on #940 and stays draft. Its only backend additions are the capacity CLI and one invariant test. No generator settings, source files, locked tests, readiness/admission control, judge contract or production path changed. The two earlier automatically denied E7 proof experiments were not retried; their release holds remain.

Proceed with [offline source custody](../../readiness-2026-09-21/acceptance/source-review-hierarchy-implementation-plan.md), then issue propagation/reconciliation, then separately reviewed admission integration. Preserve eligible H29 A and ineligible compacted B exactly. E7 still requires 60 independent source briefs, 30 reconciliations and the unchanged frozen programme prerequisites. No E7 generation or Fable call was made here. The [balance read](provider-balance.json) precedes ordinary PR regression CI only.
