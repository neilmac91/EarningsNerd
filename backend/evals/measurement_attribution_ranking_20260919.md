# E2 attribution-verifier ranking measurement — 2026-09-19

Never merge this branch. The only behavior change enables AI_ATTRIBUTION_VERIFY in the eval-baseline environment. AI_ATTRIBUTION_GATE stays false, and service/job deployment flags remain false. The changed eval path makes the PR execute a real full-cohort evaluation rather than reporting a skipped success. Eval-parity tests intentionally reject the measurement environment mismatch; this branch is evidence collection only.

Measure the existing #912 evidence-ranking implementation, retain the complete JSON/Markdown artifact and source identity, hand-read every flagged clause against its supplied passages and excerpt, then judge with cli:claude-fable-5-1 contract version 2 when the founder's subscription is available. Do not substitute a judge model. The September 19 probe was quota-exhausted. A deterministic gate pass or a verifier verdict alone cannot authorize production activation.

Close this draft after artifact capture; record results in a separate reviewed documentation PR on main. No production generation, historical repair, flag change or baseline re-pin is part of this measurement.
