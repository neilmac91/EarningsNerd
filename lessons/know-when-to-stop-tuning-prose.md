# Not every judge-flagged category is a prompt problem — stop tuning prose when flags are heterogeneous or prompt-compliant

**Area:** ai-evals · **Date:** 2026-07-01

After the driver/outlook win, I tried a follow-up guardrail for the modes fabrication redistributed
into: derived-figure-as-reported (a segment's % of total, a "total debt" summed from components) and
inferred "tone". Added two DO-NOT bullets + worked examples to all three prompts, judged before(V3=3.78)
/after(redist). Result: **no improvement** — OTHER-mode flags unchanged (12→12), mean faithfulness
3.78→3.56 (noise/slight drag), runs-with-G3 4/9→6/9. The targeted modes PERSISTED verbatim ("total
debt (term + commercial paper) = $98.7B", "26.2% of total sales"). Reverted; did not ship. **Why it
failed / lessons:** (1) unlike the driver directive (which I moved into the salient LEAD instruction), a
DO-NOT bullet is buried and loses to the model's pull to synthesize — the same V1 failure mode. (2) The
category is HETEROGENEOUS (debt roll-ups, segment %, dividend-per-quarter, liquidity, plus genuine
arithmetic errors) — no single guardrail moves a grab-bag, and "mark as derived" can't fix a wrong sum.
(3) CRUCIAL: the 10-K prompt itself INSTRUCTS "Total Debt = current portion + long-term debt", so the
model's debt roll-up is prompt-COMPLIANT and useful — the judge just dings it on provenance. Suppressing
prompt-requested, correct derivations is not a clear quality win. **Rule:** not every judge-flagged
category is a prompt-prose problem. When (a) the flags are heterogeneous, (b) some are the model
correctly following instructions the judge is merely strict about, and (c) a lesson-shaped fix (salient
+ example) would still only cover part — STOP tuning prose (CLAUDE.md: don't keep pushing). The residual
belongs to a different lever (a deterministic "summary figure not traceable to XBRL/filing" provenance
check, Wave 5) or is simply the floor. The driver/outlook guardrail captured the high-leverage,
coherent fabrication category; faithfulness 3.00→3.78 is the banked win.
