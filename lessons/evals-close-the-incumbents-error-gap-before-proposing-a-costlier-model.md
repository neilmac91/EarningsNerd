# Close the incumbent model's error gap before proposing a costlier or slower one

Date: 2026-10-25   Area: evals

**Context**: The trend-depth study recommended moving the Multi-Period Analysis from DeepSeek flash to
Claude Sonnet 5.5. Sonnet gave verified numbers the wrong metric, period or sign about a third as often and
marked its judgements, but it cost about 30 times as much ($0.21 against $0.007 an analysis) and took
about a minute instead of 10 seconds. The founder rejected the switch on cost and wait time. The founder
asked instead why DeepSeek's error rate runs higher, and for that to be fixed.

**Rule**: When a candidate model beats the incumbent on quality but costs or waits materially more
(several times the cost, or a wait the reader notices), lead with the incumbent:
1. Diagnose its errors by class and by root cause: the evidence it was given, the prompt, its settings,
   and the checks around it.
2. Fix what can be fixed, and measure again on held-out data.
3. Present the costlier model only as an option, with its cost and latency in the same sentence as its
   quality gain, and leave the switch to the founder.

A model change is not the default answer to an error gap.

**Evidence**: `tasks/analysis-depth-2026-10/REPORT.md` §8 and §10 as they stood on 2026-10-24, and the
founder's reply of 2026-10-25 (keep DeepSeek, fix its error rate).
