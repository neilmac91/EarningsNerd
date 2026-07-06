# Don't ship an amplifier that adds fabrication risk without a measurable quality gain — bad trade for a trust product

**Area:** ai-evals · **Date:** 2026-07-01

The Wave-4a YoY% amplifier (append "YoY: +X%" to grounding rows) was dropped for inducing fabricated
cash-flow drivers. Hypothesis: now that the driver-groundedness guardrail is merged, YoY is safe to
revive. Tested it hard (subscription cli:sonnet, 3×3), before(guardrail,no-YoY) vs two variants:
- **full YoY** (all rows): faithfulness held at 3.78 (the guardrail DID prevent the old 4→2 crash), but
  causal fabrications rose 2→4 — incl. a capex "reflecting investment in manufacturing" the YoY delta
  invited. Runs-flagged 4/9→6/9.
- **Option B** (YoY off the 5 cash-flow/capex rows — the volatile, filing-unexplained deltas): 3.44,
  causal 3 (incl. a geographic "reflecting export controls" fabrication), 7/9 flagged.
At n=9 the faithfulness numbers (3.78/3.78/3.44) and causal counts (2/4/3) all overlap within noise —
so the robust reading is: **YoY gives NO measurable faithfulness or deterministic gain** (a YoY% isn't
a scored fact; the block already shows current+prior so the reader sees the trend), while it reliably
tempts the model to attribute a CAUSE to whichever delta it makes salient — a risk the guardrail only
partly catches. **Rule:** an amplifier that adds no measurable quality but adds any fabrication risk is
a bad trade for a trust-critical product — don't ship it, however "nice" it seems. The guardrail
prevents the catastrophe but doesn't license reintroducing the trigger. Reverted; recorded. (Founder
call, reputation-first: neutral-with-downside ⇒ no ship.)
