# Use explicit model evidence when the founder cannot supply a human panel

Date: 2026-09-22 · Area: quality evaluation

**Context.** The founder corrected an earlier “human review complete” message: a solo
founder cannot supply the proposed hundred-plus hours of independent review. Repeating
requests for reviewer forms would not deliver the intended quality evaluation.

**Rule.** Use an explicit versioned AI-assisted protocol with actual model/context records;
never populate human commitments or human acceptance from model work. Preserve each
source reviewer's material concerns through source-backed reconciliation, even when rejected.
Record unknown exposure as a limitation rather than manufacturing an unseen attestation.
Retain numerical and material-defect criteria and provide a short product-risk decision.

**Evidence.** `evals/acceptance_ai_protocol.py` validates model roles, source-only context
receipts and disposition of every original issue; `acceptance_readiness.py` preserves the
separate human v1 path and seals v2 evidence. `acceptance_ai_decision.py` checks the fixed
rubric and always reports `human_acceptance=false`. The tests in
`tests/unit/test_acceptance_ai_protocol.py` reject dropped issues, generated-output exposure
and coherent edits after the evidence seal.
