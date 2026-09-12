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

### Matching and certification policy (revised after Codex review)

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
4. **Fact identity.** One `get_financial_fact` call on the existing DB-only accession-bound owner
   (`copilot_tools.run_tool`, concept only — the plainest existing selector, unchanged). The
   returned fact must pass the existing `_valid_fact_provenance`, then match exactly: same
   `accession`, `concept` equal to the claim's concept, `period_end` equal to the claimed date and
   to `filing.period_of_report`, canonical `unit` equal to the claim's canonical currency, and no
   `kind`/`value_kind`/`source_facts`.
5. **Its own reported duration, inside the annual window.** `period_start` must be present and
   `period_end - period_start` must fall in 320–390 days — the single window
   `facts_service._CF_ANNUAL_WINDOW` and `instance_extractor.DURATION_WINDOWS` already own, with a
   test asserting all three stay equal. This is the binding proof and nothing substitutes for it.
6. **Value and sign, at the stated precision.** The filing value must round to the numeral exactly
   as written: `|value - stated| <= 0.5 * 10^-decimals * scale`. `996,347 million` admits ±5e5;
   `996.3 billion` admits ±5e7. Signed, so a negative filing value can never certify a positively
   stated amount.
7. **The resolver would keep it.** The three existing adjacency guards run on the exact window the
   resolver will compute — falsification-only, and not treated as certification.

The annual-report-form check is retained as a narrowing condition (the sentence's "fiscal year
ended" scope should match the document the user is reading), but it is explicitly NOT counted as
scope evidence.

### Correction taken from the Codex review

The first implementation certified annual **scope** from the annual form, `period_of_report`
equality and the `FY` label. That was wrong and is now removed. Both refutations hold, verified
here against the code rather than accepted on report:

- `edgar/xbrl_service.py` `filter_and_sort` only **ranks** the durations sharing a period end
  (`_duration_penalty` returns 0 when `start` is missing and nothing rejects a non-standard
  duration), so a lone three-month point survives; `append_items` then emits
  `{period, value, form, accn, raw_tag}` and drops `start` entirely.
- `facts_service._fiscal_period` derives `FY` from the FORM, so the annual-form test and the `FY`
  label are one signal wearing two hats. Rejecting an explicitly `Q4`-labelled fixture never
  rejected the real ambiguous record.

Reproduced end to end through production code, no hand-written intermediates
(`test_quarterly_point_in_an_annual_filing_never_certifies`): a 3-month `Revenues` point
2024-12-29 → 2025-03-29 in a 10-K emerges from `_parse_company_facts` as
`{'period': '2025-03-29', 'value': 95359000000.0, 'form': '10-K'}`, survives
`extract_standardized_metrics`, and `normalize_standardized_to_facts` stamps
`fiscal_period='FY'` with `period_start=None`. It passes `_valid_fact_provenance`. Under the old
certifier it certified; it now does not.

### Source evidence actually available — and the honest consequence

Duration cannot be established at this layer for most facts, and no `copilot_tools.py` change
helps: `_fact_provenance` already returns `period_start`, so the field is exposed — it is simply
NULL. The writers were read directly:

- `normalize_standardized_to_facts` never puts `period_start` in the dict it builds, so every
  per-filing `edgar_xbrl` row stores NULL.
- The companyfacts **backfill** (`_base_fact`, `source="companyfacts"`) DOES write a real
  `period_start`, classified by `_classify_duration`. Those rows carry genuine duration.
- `upsert_facts` skips an existing identity, so whether a given accession's row carries duration
  depends on which writer arrived first. Neither `xbrl_data` nor the instance path records it.

**Consequence, stated plainly: the retained BABA `results[14]` row carries no duration, so the
repair now abstains on the exact defect that motivated it.** The mechanism is correct and fires on
genuine evidence — `test_uncited_answer_gains_a_citation_when_the_fact_proves_the_year` shows the
full positive path on a fact with a 364-day duration — but this change does **not** repair the
retained case. That is pinned as a test
(`test_retained_baba_row_still_abstains_because_it_carries_no_duration`) rather than presented as
fixed.

### Interface proposal for Codex — carry duration into the fact record

Not implemented; `facts_service.py` and the shared XBRL files are reserved while Agent A works.

- **Field:** `period_start` on the emitted standardized point, then on the `financial_fact` row.
  The column already exists and is nullable, so no migration and no identity change
  (`uq_financial_fact_identity` is untouched).
- **Writers:** `edgar/instance_extractor.py` `_series_from_values` / `duration_series_with_currency`
  — the proof already exists there (`duration_in_window` filtered on it) and is discarded at the
  tuple boundary; `edgar/xbrl_service.py` `append_items`, which holds `item["start"]` and drops it,
  and `normalise_series`, which would need to carry the key through;
  `facts_service.normalize_standardized_to_facts`, which would read `point.get("period_start")`.
- **Readers:** `copilot_tools._fact_provenance` (already projects it),
  `copilot_service._fact_certifies_claim` (already requires it), `copilot_tools._has_duration` /
  `_prior_comparable` (derived metrics currently return `basis_unavailable` for the same reason —
  this would unblock them too).
- **Open question for allocation:** whether `xbrl_service`'s ranked fallback should additionally
  REJECT a non-annual duration for an annual form rather than only carry it forward, and whether a
  backfill is wanted for existing rows or forward-only is acceptable.

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

Evidence: no reported duration; quarterly (90-day), nine-month (273-day) and two-year (730-day)
durations; the exact window boundaries (320 and 390 days certify, 319 and 391 do not); the real
quarterly-point-in-an-annual-filing transformation above; equal amount with the wrong concept;
wrong accession; wrong full date; `period_of_report` disagreeing; an unlabelled period; a
non-annual filing form; `ambiguous_fact`; `not_disclosed`; `filing_scope_unavailable`; a malformed
result; wrong currency in the fact and wrong currency in the claim; unknown unit; wrong scale;
negative value against a positive claim; a value just outside the display-rounding half-interval;
a derived `yoy_growth` result; an unrepresentable numeral.

Text: year-only scope; quarter-ended; forward-looking "ending"; a date with no day; an impossible
date; missing currency; a segment-qualified subject; bare "sales"; quotation; conditional;
comparative; causal; hedged; multi-metric; convenience translation.

The known Microsoft advisory false positives carry markers, so rule 1 abstains;
`count_uncited_figures` is never consulted and never becomes a blocking validator.

### Deviation from the proposed file layout

The proposal allowed "a small adjacent helper if it materially improves readability". A separate
module would have had to duplicate `_CURRENCY_ALIASES` and the adjacency guards or move them
downward, and two divergent currency tables is a real correctness hazard. The repair therefore
lives beside the resolver in `copilot_service.py`, reusing one vocabulary.

## Verification

See the PR body for exact gate tails. Full backend gate on committed state, one test process,
isolated venv/cache/DB paths; Ruff and Bandit clean; `pytest -m ""` with all four CI-named
PostgreSQL lane variables live against a private cluster, zero skipped.

One mutation proof, on the invariant this revision establishes: removing the duration requirement
from `_fact_certifies_claim` lets the real quarterly-point-in-an-annual-filing record certify an
annual sentence.

All eleven locked anchors byte-identical. `copilot_tools.py` is read but unchanged — no selector
change was needed, because `_fact_provenance` already exposes `period_start`; it is simply NULL.
`facts_service.py`, the shared XBRL files, database identity and migrations are untouched, per the
Agent A reservation; the ingestion change they would need is the interface proposal above.

## Status

`READY FOR INTEGRATION`, with the citation slice reported as **incomplete**: the mechanism is
correct and demonstrated, but the retained BABA defect still abstains because its row carries no
duration. No push, no PR, no assessment, no deployment, no external action, no spend. Publication
waits on a Codex slot — a `backend/app/**` change matches the `eval-baseline` path filter and
fires on any pull-request event, draft included.
