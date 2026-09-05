# Carry reconciliation quality through values, growth, citations and exports

Date: 2026-09-05   Area: arch

**Context**: WS-7 review found that analysis charts/grids, narrative sources and Excel could
display flagged facts without their reconciliation warning. A growth number can also depend
on an unreconciled earlier value even when its latest value is clean. A verified citation proves
the source match; it does not independently reconcile the underlying financial figure.

**Rule**: Compute growth-quality flags from the same inputs used for the calculation in the
backend. Preserve the point/derived-quality fields through every consumer, including citations,
chart exports and workbooks. Show quality independently of citation traceability.

**Evidence**: PR #697; backend `tests/unit/test_data_completeness.py` pins earlier-input growth,
citations and exported cell comments. Frontend metric/KPI/trend/narrative regression cases pin
the corresponding visible warnings; mutations removing these paths must fail those tests.
