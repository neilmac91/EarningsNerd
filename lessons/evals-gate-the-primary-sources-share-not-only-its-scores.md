# When a pipeline has a primary source and a degrading fallback, gate the share the primary source serves, not only the output's scores

Date: 2026-10-16   Area: evals

**Context**: From early October 2026 the summary's native section source returned nothing (SEC
refused edgartools 5.58.0's index URL behind `Filing.obj()`), and every 10-K, 10-Q and 20-F excerpt
silently fell back to the regex extractor (E28). The fallback was designed to be acceptable, and it
was: numeric accuracy and coverage held, citation fidelity fell from 0.97 to 0.818–0.871, and the
regression gate treats citation fidelity as a WARN. Every eval-baseline run for the next twelve days
printed a warning and passed, while each report recorded `coverage_inventory.source:
regex_fallback` for all 64 eligible attempts. The evidence was in every artifact; no check read it.

**Rule**: When an output can come from a primary source or a degraded fallback, the regression gate
checks the share served by the primary source, read from each attempt's provenance, as an absolute
HARD floor when the source is deterministic. Quality scores alone cannot catch a fallback built to
score acceptably. Set the floor from the measured healthy share and name the known misses. Keep a
report without provenance inert (a note, not a measured zero), so the check never fails on old
artifacts or turns silent on new ones. Pin the gate's label and form set to the code that writes
them.

**Evidence**: `backend/evals/regression_gate.py::_check_native_sections` and its tests in
`backend/tests/unit/test_eval_regression_gate.py` (the E28 collapse is HARD; 62 of 64 with ASML's
20-F as the known miss is clean); the six-report table in
`tasks/review-evidence/e28-native-sections-2026-10-15/README.md`.
