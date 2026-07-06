# Stop tuning prompt prose when judge flags are heterogeneous or prompt-compliant

Date: 2026-07-01   Area: arch

**Context**: After the driver/outlook win, a follow-up guardrail for the redistributed modes (derived-figure-as-reported, inferred tone) showed NO improvement — buried DO-NOT bullets lose to the model's pull to synthesize (the same V1 failure mode); the category was a heterogeneous grab-bag no single guardrail moves; and crucially the 10-K prompt itself INSTRUCTS "Total Debt = current portion + long-term debt", so the flagged debt roll-up was prompt-COMPLIANT and useful. Reverted; did not ship. The banked win stands at faithfulness 3.00→3.78.

**Rule**: Not every judge-flagged category is a prompt-prose problem. When (a) the flags are heterogeneous, (b) some are the model correctly following instructions the judge is merely strict about, and (c) a lesson-shaped fix (salient + example) would still only cover part — STOP tuning prose. The residual belongs to a different lever (a deterministic "summary figure not traceable to XBRL/filing" provenance check) or is simply the floor.

**Evidence**: Before(V3=3.78)/after(redist): OTHER-mode flags 12→12, mean 3.78→3.56, runs-with-G3 4/9→6/9; persisted verbatim: "total debt (term + commercial paper) = $98.7B", "26.2% of total sales".
