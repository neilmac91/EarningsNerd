# E7 custody corrections — 27 September 2026

Four bounded guards now reject excessive overlapping coverage before hashing, verify context-before-hash ordering, reject unsupported bare inline-XBRL facts/hidden sections, and prevent outputs aliasing unused contract templates. This is offline preparation, not E7 admission or semantic acceptance.

Code commit: `9abd0a2b681d7af7eed27f50b145c48616259e77`, base `b53455bb3b13817d44cf089f3280ced143998583`. The [verification receipt](verification.json) records the backend tree, eleven unchanged locked files and evidence hashes.

- [Full backend gate](full-gate.txt): Ruff/Bandit pass; **3718 passed, 40 warnings in 171.82s**, Python 3.11.16, PostgreSQL 15.15, all four PostgreSQL lanes and performance included, exit 0. A post-suite logging teardown diagnostic remains in the raw log.
- The [first run](corrections-full-gate-runtime-failure.txt) had five environment failures because the previous isolated Python runtime lost standard-library files. A replacement runtime resolved the affected 50 tests, then the full gate. No product/test workaround was introduced.
- [Four mutation proofs](correction-mutation-proof.json) each failed their specific gate, restored exact committed source bytes and ended with [58 passing focused tests](mutation-restored.txt). These are synthetic local faults; no previously denied budget/source-brief proof was attempted.
- [Independent review](correction-review.md) found no actionable issues. Root separately reviewed the complete diff and scope. No admission/runtime call sites, model settings or locked tests changed.

Deterministic prompt construction, independently retained complete attempt history, semantic issue preservation, reconciliation and admission integration remain unfinished. The old registry is explicitly a caller-declared snapshot; matching hashes alone do not prove complete history or a correctly constructed prompt.

The founder authorized necessary changes and DeepSeek spend overnight on September 27. Existing acceptance criteria and evidence contracts remain intact. Fresh balance from read-only workflow `36274483325` was USD 63.80 at September 26 21:54:03 UTC. Ordinary hosted CI is separate from E7/E8 evaluation budgets. No holdout or Fable call was made by this correction.
