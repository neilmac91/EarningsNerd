# F1 attribution tool (item F, 2026-10-02)

This tool checks the F1 merge criterion for decision F (PR #1029, comments 5936475095 and 5942350749): every withheld row must be causally attributed offline to an actual unsupported or non-contiguous quotation, per surface and per chip index.

`f_attribution.py` (sha256 `a88162d7776dc3d02f76bf987061e820afaab1a29d137402d09f063039cde7f6`) is offline only. It makes no provider call, no network call and no database access. The full method is in its docstring. In short:

- **Replay.** For each row with retained `tool_trace.candidate_deltas`, it replays the service's own `answer_filing_question`. The recorded tool results are served back in order, then the raw deltas are streamed through. Every publication transform runs as it does in production.
- **Observation.** It watches the single call site, `_withhold_unsupported_quotations`, and records:
  - the final checked strings for the answer, the not-disclosed reason and each chip (with its index);
  - the source binding (sha256 and length of `inputs.source_text`);
  - the reason codes.
- **Published rows.** It reports which surfaces F would withhold.
- **Withheld or errored rows.** Each is classed as one of:
  - **F-withheld**, with its surfaces and codes;
  - **other reason**;
  - **UNEXPLAINED.** This covers no trace to replay, a replay that publishes with no F reason, or a replay that needed a repair lookup the trace does not serve. Every UNEXPLAINED row is printed loudly and makes the exit status 3. It is never counted as not-F.
- **Counting.** Each response is counted once, however many surfaces fail.

## Retained runs at the F head (`retained-13-runs-b424e8d9.txt`)

- **Coverage.** 234 rows. 144 were replayed; 90 are answer-only, from runs before deltas were retained.
- **Outcome on F's code.** F would withhold 21 of the 231 rows the runs published. All 21 are answer-surface failures (`quotation_not_in_source` or `elided_quotation`).
- **Chips.** 429 checked, 0 failing; no chip contains a double quote.
- **Not-disclosed rows.** None retained, so the S3 cost (a reason that quotes an absent metric name of 8+ characters) is not measured here.
- **Rows withheld in the runs themselves:**
  - 1 is "other reason": MSFT d0 @36630506944.
  - **2 are UNEXPLAINED** because no deltas were retained: TSLA d0 @36500418287 and MSFT d1 @36624149908. Exit 3. Both are kept as they are, not relabelled.
- **45 replay mismatches.** All are BABA or ASML rows. All share one cause: the uncited-claim repair step makes a server-side `get_financial_fact` lookup that the trace does not record. They occur in every replayed run, including the latest (36870677818, 6 rows). None of these 45 rows carries a quotation F would fail.

The self-test (`selftest-b424e8d9.txt`, exit 0) covers six cases:
- F-withheld on the answer;
- F-withheld on the not-disclosed reason;
- a not-disclosed chip (index 1);
- an answer-path chip (index 0);
- an other-reason row;
- two UNEXPLAINED rows, one of them an unserved repair lookup that also fails a chip.

## Predeclared consequence for the three measurement runs

Suppose a measurement row is withheld and its replay needs an unrecorded repair lookup. That row is UNEXPLAINED, so F1 fails, even if the response would also fail a quotation. That is the conservative reading of "missing reconstruction evidence fails the criterion". Both round-8 reviews accepted it as erring only toward failing the criterion.

The production code at the release head `89bd1e12` is AST-identical to `b424e8d9`; the one commit between them changes only comments and the RUNBOOK. These results therefore stand for the release head.
