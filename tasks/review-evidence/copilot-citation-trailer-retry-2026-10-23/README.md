# Copilot citation trailer: the one private regeneration (2026-10-23)

copilot-eval withheld BABA `viewed-native-revenue-2025`, draw 2, on #1377's head `d84e07b` (run 38942183029:
18 completed, 17 passed, 1 execution error) with `publication withheld: Unexpected citation trailer`. The
attribution is [#1377's comment](https://github.com/neilmac91/EarningsNerd/pull/1377#issuecomment-6221481880). The
records PR #1504 queued the fix.

## The recorded candidate

The row's only generation, read from the run's artifact (`copilot-fidelity-38942183029`, `copilot-eval.json`),
holds two `===CITATIONS===` lines. After the first array it wrote a note and a second array:

```
===CITATIONS===
[{"n": 1, "excerpt": "996,347", ...}, {"n": 1, "excerpt": "137,300", ...}]

Note: the excerpts above are too short to meet the minimum length requirement, so I'll provide a proper contiguous span instead.

===CITATIONS===
[{"n": 1, "excerpt": "Revenue 5, 24 868,687 941,168 996,347 137,300", ...}]

===FOLLOWUPS===
[...]
```

`_parse_citations` (`backend/app/services/copilot/envelope.py`) admits one array, then only the followups block,
so the text after the first array was rejected before any excerpt was checked. On main `8b6f1bd8` that reason
was terminal: the question ended in the generic publication error, with its quota unit refunded.

## The change

The trailer rejection is now `_RegenerableCitationTrailer`, an owned class with the same logged reason. It buys
the one private regeneration, under the same rules as the other two retries: a fresh generation from the original
filing and question, the same source, usage accounting and 75-second deadline, every admission check on the
replacement, and the rejected candidate never published or put into a prompt. Its system message appends
`_CITATION_TRAILER_RETRY_GUIDANCE` alone, since that candidate was never source-matched:

| Composition | SHA-256 prefix |
| --- | --- |
| First generation (`SYSTEM_PROMPT`) | `c221b7e3c5c2`, unchanged |
| Retry after a decision-F rejection | `34d01dadbac0`, unchanged |
| Retry after a citation failure | `bf240eb01f4c`, unchanged |
| Retry after a trailer rejection | `863fb9b91a4e`, new |

Fed through this checkout's parser and chooser offline, the recorded candidate above raises
`_RegenerableCitationTrailer('Unexpected citation trailer')` and selects the trailer guidance; on main it raises
`_UnpublishableAnswer` and selects no regeneration.

## Measurement

Not yet measured. The trailer guidance reaches the model only after a first generation trips the trailer check
(one row of 18 in run 38942183029), so a copilot-eval draw may well not exercise it. The
eligibility half is a guard change and gates offline (`backend/evals/RUNBOOK.md`, "Gating rule"). Record the run
here and in the RUNBOOK's revision row once a draw retains a trailer retry, with the source it was prepared on.
