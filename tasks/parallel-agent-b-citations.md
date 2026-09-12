# Agent B — Copilot missing factual citations (lane note)

Lane-owned progress note for the wave-3 parallel implementation. Codex integrates the central
`tasks/todo.md` and release records; nothing here grants scope beyond `AGENT-B-CITATIONS-PROMPT.md`.

## Baseline

Separate clone, own branch, no shared worktree. `origin/main` verified at
`48f3758e0729409c7ebbbb26c887cfa02f672455` (#828) — the reviewed starting main — and the working
branch starts from exactly that commit with a clean tree. Primary main was not touched. The
handover ZIP verifies against its own `MANIFEST.json`: all seventeen files match byte length and
SHA-256.

## Engineering checkpoint (first interface report)

### The defect, read directly

`evidence/copilot-second-assessment.json` `results[14]` (BABA, accession `0000950170-25-090161`,
question `viewed-native-revenue-2025`, run 2) answers

> Revenue for the fiscal year ended March 31, 2025 was RMB996,347 million.

with `tool_trace.tool_results == []`, `citations == []` and `stripped_misplaced_markers == 0`. The
score row records `figure_coverage 0.0`, `figure_count 1`, `uncited_figures 1`, `passed true`. The
value is right and the attribution is absent, exactly as the retained acceptance note says. A
`used_facts`-only repair cannot reach it: the model called no tool at all.

### Matching, rounding and scope policy

Certification is positive and whole-answer. The repair fires only when *every* one of these holds;
any failure abstains and returns the answer unchanged.

1. **No existing marker.** The answer contains no `[n]`/`[Fn]`-shaped bracket anywhere. An answer
   that already cites something is never rewritten.
2. **One finite claim shape.** The whole stripped answer matches one anchored grammar: a
   consolidated-revenue subject phrase, `for/in (the) (fiscal) year ended <Month D, YYYY>`, a
   copula, then native currency + amount + optional scale word, then a terminal period. The
   grammar names a concept vocabulary, never a ticker, company or amount. Anchoring is what
   rejects multi-metric, comparative, causal, quoted, conditional and derived text: a second
   proposition simply falls outside the match.
3. **Real calendar date.** The month/day/year must construct a valid `date`.
4. **Filing form.** `filing_type` is an annual report form (`10-K`/`20-F`/`40-F`, amendments
   included) — the same form test `facts_service._fiscal_period` uses to stamp `FY`.
5. **Filing period.** `filing.period_of_report` equals the claimed date.
6. **Fact identity.** One `get_financial_fact` call on the existing DB-only accession-bound owner
   (`copilot_tools.run_tool`, concept only — the plainest existing selector, unchanged). The
   returned fact must pass the existing `_valid_fact_provenance`, then match exactly: same
   `accession`, `concept` equal to the claim's concept, `fiscal_period == "FY"`, `period_end`
   equal to the claimed date, canonical `unit` equal to the claim's canonical currency, and no
   `kind`/`value_kind`/`source_facts` (a derived result never certifies a reported figure).
7. **Value and sign, at the stated precision.** The filing value must round to the numeral exactly
   as written: `|value - stated| <= 0.5 * 10^-decimals * scale`. `996,347 million` admits ±5e5;
   `996.3 billion` admits ±5e7. The comparison is signed, so a negative filing value can never
   certify a positively stated amount.
8. **The resolver would keep it.** The three existing adjacency guards (value, concept, currency)
   are run on the exact window the resolver will compute. They are falsification-only and are not
   treated as certification — this is a last check that we never ship a marker the resolver
   would strip.

### Source evidence actually available — one deviation to record

The brief asks for annual **duration**. That evidence does not exist at this layer.
`facts_service._build_facts` never writes `period_start`, so every `edgar_xbrl` fact carries
`period_start = NULL`; both retained assessments confirm it (`ps=None` on all 30+ successful tool
results in each), and `backend/evals/RUNBOOK.md` already records "Runtime per-filing facts
currently omit duration starts". A duration test would therefore abstain on every real answer and
the fix would be a no-op on the actual defect.

So this slice certifies annual **scope** instead, from metadata that genuinely exists: the viewed
accession is an annual report form, its `period_of_report` equals the fact's `period_end` equals
the claimed date, and the fact carries the annual `FY` label that only an annual-form point
receives. It does not claim a proven duration, and it does not invent one.

**Residual this leaves, stated plainly:** a 10-K/20-F whose XBRL exposed a same-period-end Q4
duration point under the same concept and unit would collapse to one row under
`uq_financial_fact_identity` and would be indistinguishable here. Closing that needs duration in
the fact writer (another lane) or a prior-period cadence check.

**Concrete interface question for Codex — not a founder question.** Corroborating annual cadence
from the filing's own comparative row (prior `FY` `period_end` 357–373 days earlier, the window
`copilot_tools._prior_comparable` already uses) would need a selector that returns the sibling
period ends. That is a change to `copilot_tools`' shared selection semantics, so it is **not** in
this slice. Say whether you want it as a follow-up and under whose ownership.

### Consumer and preserved behavior

The repair sits in `answer_filing_question`, after `expand_citation_marker_groups` and before
`_resolve_citations` — so the existing source-owned resolver keeps sole ownership of numbering,
placement and `fact_to_citation` provenance, and the authoritative `complete.answer` the frontend
replaces buffered prose with (`frontend/features/filings/api/copilot-api.ts`) carries the marker.
No frontend change, no new SSE event, no locked-contract edit, no prompt/model/provider change.

Only the marker is inserted; every other prose byte, punctuation included, is preserved. No SEC
call, no second model call, no model rewrite. The lookup is server-initiated and is recorded as
such: the registered fact carries `_origin = "server_citation_lookup"`, and because the eval
harness observes tool calls by wrapping the closure passed to `stream_chat_with_tools`, this
lookup correctly never appears as model tool-call history.

Streaming is unchanged and still provisional: token text precedes final citation resolution today,
so no claim is made that every streamed byte is cited.

### Negative controls

Equal amount with the wrong concept; wrong accession; wrong full date; `period_of_report`
disagreeing with the claim; year-only scope; quarter-ended text; a `Q4` fact; a non-annual filing
form; `ambiguous_fact`; `not_disclosed`; wrong currency label; wrong scale; negative value against
a positive claim; a derived (`yoy_growth`) fact; quoted, conditional, comparative and multi-metric
text; a segment-qualified subject; and a value just outside the display-rounding half-interval.
The known Microsoft advisory false positives are covered too: those answers carry markers, so
rule 1 abstains and `count_uncited_figures` stays advisory — it is never consulted by the repair
and never becomes a blocking validator.

### Deviation from the proposed file layout

The proposal allowed "a small adjacent helper if it materially improves readability". A separate
module would have had to duplicate `_CURRENCY_ALIASES` and the adjacency guards or move them
downward, and two divergent currency tables is a real correctness hazard. The repair therefore
lives beside the resolver in `copilot_service.py`, reusing one vocabulary.

## Status

`IMPLEMENTING` at this checkpoint. No push, no PR, no assessment, no external action.
