# Financial-claim scope handback — declared table-cell scales (27 September 2026)

Engineering handback for the remaining financial-claim fidelity work, delivered as a separate
dated document; the continuation plan is not modified. Branch `codex/wave3-financial-claim-scope`
from main `7800a7392d04f1d12e6f81d7886bac1471c1c712` (#989); draft PR
[#992](https://github.com/neilmac91/EarningsNerd/pull/992), implementation commit `ce72481`,
evidence commit `2ac3226`; working tree clean at push. Codex owns integration and release;
nothing here merges, deploys, changes a flag, an account, a subscription or a database.

This is engineering evidence from retained packets and offline replay. It is not an E7 source brief,
a formal Fable verdict, or an adoption decision for candidate r.

## Baseline established

- Attachment `fable-financial-claims-2026-09-27.zip` (SHA-256 `3d294469…c49ebf`): all 60 members
  matched `SHA256SUMS.json` byte counts and hashes; report SHA-256
  `deaa1b52c85bbab1bbcd19b7e55ab483b58ec465d6523272931cbd67e6c7f80b` as stated; hand-check manifest
  `73801df7…095fd`. Hashes: `review-evidence/financial-claim-scope-2026-09-27/retained-package-hashes.json`.
- Open PRs at start: #988 (Codex, Analysis, ready), #952 (E8, draft, parked), #942 (candidate r, draft,
  head `47d040aa`). None was pushed to. The r branch merges cleanly onto current main (dry-run
  merge-tree, zero conflicts) and touches none of this branch's hunks (see Overlaps).
- Five prioritized defects were each re-read against the retained excerpt before accepting the prior
  reviewer's finding; all five reproduce. Per-finding locators, quotes and this engineer's two
  refutation attempts: `review-evidence/financial-claim-scope-2026-09-27/reconciliation.md`.

## Reconciliation summary

| Historical failure | Disposition |
| --- | --- |
| WMT run 1 — "$3,542 … Total: $38,166" from an "(Amounts in millions)" table | **Corrected by this patch** (declared table-cell scale owner). |
| JPM run 0 — 2023 gain called "prior year" in a 2025-vs-2024 filing | Still applicable, unresolved; smallest next decision below. |
| FIGS run 0 — reconciliation "deducts" items the table adds | Still applicable, unresolved; needs a structured reconciliation-table owner. |
| FIGS run 1 — statutory-rate explanation moved to the YoY comparison | Still applicable, unresolved; causal-transfer class, but its slot (`notable_footnotes[].impact`) is not scanned by the attribution gate at all, so arming the flags would not reach it. |
| PLTR run 0 — aggregate other income assigned to one gain component | Still applicable, unresolved; needs the statement-line owner (`statement_source` null for PLTR). |
| PLTR run 1 — cost-of-revenue driver presented as the gross-margin cause | Still applicable, unresolved; same causal-transfer class as FIGS run 1. |
| RIVN customer conflation, MELI fee scope (Risks) | Already prevented in the serving path by #981/#987 (`provenance_service` risk projection + truthful fallback); not prevented outside Risks. |
| AAPL +6.5% vs 6.4% | Already prevented by #977 (`metric_delta_service` exact XBRL operands). |

## The failure class corrected

A model copies a table cell ("3,542") from a table whose banner declares "(Amounts in millions)" and
writes "$3,542". The value is source-exact; the unit is one million times too small. This was invisible
to every existing check because each one matches values: `figure_trace` polices only dollar figures
carrying a b/m/t scale word and ignores unit-less ones by design; the eval numeric scorers and the
figure gate match comma-grouped excerpt numbers across ×1/×1e3/×1e6. A matching digit string never
established the unit the sentence asserts.

### Production behavior changed

`app/services/ai/source_units.py` (the existing source-unit owner) gains `build_table_unit_index`
and `restore_table_cell_units`. For every bare model-authored dollar figure in the policed prose slots
(`figure_trace.policed_prose_slots`: the_print, earnings_quality, value_drivers, forward_signals,
balance_sheet_liquidity prose lists, segment commentary, notable-footnote item/impact), the owner
finds every whole-cell occurrence of the same digits in the exact offered excerpt and inserts the
one scale word the governing table banner declares ("$3,542" → "$3,542 million"). It abstains, leaving
the text byte-identical and recording the reason, when:

- the issuer's own prose writes the figure bare (`prose_occurrence`; the COST section convention),
- the digits occur under different banners (`mixed_scales`), as a percentage (`percent_occurrence`),
  not at all (`no_occurrence`), or only under a non-dollar banner or below prose (`no_governing_banner`),
- the figure is not a demonstrated table cell — no cell separator (non-breaking space, two spaces,
  parentheses) or value-only line owns it (`undelimited_cell`),
- the row, or the detached label above a value-only row, is excluded from the scale — per-share,
  share counts, counts, or a unit/scope token such as "Fee ($)" (`unscaled_row`),
- standardized XBRL supports the literal reading (`literal_xbrl_match`),
- the section was recovery-authored (`recovered`).

Digits are never changed; verbatim `supporting_evidence` and quotes are never touched; nothing is
rescaled. The owner runs after the source binders (`bind_statement_relationship`,
`bind_capital_allocation`, `bind_issuer_cash_disclosure`) on both the final and the preview path, so it
measures only model prose that survives into the stored sections; slots those binders replace or remove
(`operating_vs_one_time` under a statement source, `capital_allocation`, `highlights`) never enter the
audit. The audit is persisted at `raw_summary["table_cell_unit_audit"]` with exact `restored_count` /
`unresolved_count` totals beside detail lists capped at 40, and the pipeline emits the count-first
counter `table_cell_units restored=… unresolved=… reasons=…` from the totals. Previews and the final
render use the same owner over the same supplied excerpt (`unit_index` threaded through
`_request_content` → `_stream_collect` → `_partial_markdown_preview`). The content stamp advances to
`summary-2026-09-s` (a deterministic content revision; `q`/`r` stay reserved by the held #942
experiment; no automatic regeneration or drain is authorized, so existing cached summaries remain an
explicit rollout limitation). No flag, schema, scorer, judge contract, baseline pin or locked test changed.

Files: `backend/app/services/ai/source_units.py`, `backend/app/services/ai/figure_trace.py`
(`policed_prose_slots`, a pure refactor of `_prose_blob` so both owners share one allowlist),
`backend/app/services/openai_service.py`, `backend/app/services/ai/provider_requests.py`,
`backend/app/services/summary_pipeline.py`, `backend/app/services/summary_versioning.py`,
`backend/tests/unit/test_table_cell_units.py`,
`lessons/arch-bind-bare-table-figures-to-the-declared-scale.md` (+ index).

### Preservation of valid source-supported cases

Offline replay of the owner over all 70 retained candidate-r outputs
(`review-evidence/financial-claim-scope-2026-09-27/offline-replay-70.json`, report SHA verified):
exactly one slot changed (WMT run 1 maturities, all seven figures restored, matching the SEC
companyconcept value for the year-two maturity, 3,237,000,000 USD, accession 0000104169-26-000055);
eight bare figures across COST (issuer-prose convention) and BYND (literal salary, not in excerpt)
were left as written with their reasons; the other 65 outputs carried no bare figure. Boeing's
"$10,550M"/"$9,566M" (model-scaled correctly) and every "$X thousand", "US$…", "NT$…", decimal and
percentage form are non-candidates by construction.

### Gate and mutation proof

`backend/tests/unit/test_table_cell_units.py` (26 cases): the retained WMT lines restored 7/7 including
year-glued cells ("20283,237"); cells at either end of a line under the two other edgartools table
flattenings; prose-bare (BA), missing, mixed-scale, percent, non-dollar banner,
banner-above-prose, share-count and XBRL-literal cases untouched with the documented reason; verbatim
evidence untouched; recovered section skipped; audit vocabulary; and the actual consumer
(`OpenAIService.summarize_filing` final path, `_partial_markdown_preview` with and without the index,
recovered path) rendering the same text into `business_overview`.

Gate tails, the single deliberate fault/restored proof and hosted findings are recorded below.

## Overlaps with the unmerged r branch (#942, head `47d040aa`)

r changes `openai_service.py` only at the `xbrl_narrative` import block and the ONE-HOME-PER-NUMBER
prompt rule; this branch changes the `source_units` import, `generate_structured_summary`,
`_stream_collect`, `_partial_markdown_preview`, the final owner site and the raw-summary payload —
different hunks. r advances `summary_versioning.SUMMARY_PROMPT_VERSION` to `summary-2026-09-r`; this
branch advances it to `summary-2026-09-s` on the chief engineer's instruction, documenting `q`/`r` as
reserved, so the two branches now conflict on that one line and its comment block. Integration order
decides the resolution: whichever lands second keeps `-s` as the later content revision (or a
successor), never reusing `q`/`r`. No other file overlaps
(`figure_trace.py`, `source_units.py`, `provider_requests.py`, `summary_pipeline.py` and the new test
are not touched by r; r's `debt_scope.py`, `markdown_render.py`, `xbrl_narrative.py`,
`xbrl_service.py`, `financial_basis.py`, `summary_schema.py` and prompt edits are not touched here).
A dry-run merge of r onto current main reports zero conflicts. Portable as one commit; nothing from
r was cherry-picked and no r adoption claim is revived.

## Remaining risks and the next smallest decision

- **Stamp (resolved by the chief engineer's integration decision).** `SUMMARY_PROMPT_VERSION` is
  `summary-2026-09-s`; `q`/`r` are documented as reserved by #942. Old rows read as stale; no automatic
  historical regeneration or drain is authorized, so cached summaries keep bare figures until a
  separately bounded refresh is verified.
- **Coverage.** The owner corrects table-cell copies only. The COST-style convention (issuer prose
  written bare under a section declaration) is abstained by design and remains reader-visible; the
  next bounded step is extending `attach_quote_unit_context`'s MD&A-title declaration path to bare
  prose figures whose paragraph it already certifies — a separate change with its own gate.
- **Period label (JPM).** Next smallest test: an audit-only detector in the same family that flags
  "prior year"/"prior-year period" beside an explicit fiscal date outside the filing's current or
  immediately prior period (`xbrl_grounding.*.prior.period`), measured on the retained 70 rows
  before any rewrite is allowed.
- **Causal transfer (FIGS run 1, PLTR run 1).** The owners exist (`attribution_gate`,
  `attribution_verify`) but cover only some slots. PLTR run 1 lives in `the_print.what_changed`, which
  is scanned, and the lexical finder passes it because the clause shares tokens with the source line
  it was transferred from. FIGS run 1 lives in `notable_footnotes[].impact`, which
  `attribution_gate._slots` never yields, so it is unscanned rather than passed; reaching it needs the
  slot list widened before any flag matters. The flag decision is founder-held
  (`AI_ATTRIBUTION_VERIFY`, one bounded model call per flagged generation) and was not touched.
- **Reconciliation sign (FIGS run 0) and aggregate-vs-component (PLTR run 0).** Need a structured
  reconciliation-row owner and the statement-line owner respectively; not bounded enough for this
  handoff.
- **Banner inheritance (narrowed after review).** The chief engineer's review of `d7f5ce0` showed
  three false insertions the first owner allowed: a short sentence under a banner, a per-share row
  whose label sits on the line above its value, and a new table whose header carries "Fee ($)".
  The owner now binds a scale only to a demonstrated cell (delimited or value-only), reads the
  detached label of a value-only row, and stops the banner walk at any prose line, any other
  unit/scope token, or a run of more than three heading lines; single-space prose figures and
  plural scale words ("$3,237 millions") are never candidates. Undelimited single-cell rows
  ("Total$38,166" with no trailing separator) are a narrowed, abstaining shape. The residual risk
  is a banner-less table of at most three short headings following a bannered one with a
  different scale and no unit token; the 70-output replay still changes exactly one slot.
- **Hosted measurement.** The draft PR triggers the advisory `eval-baseline` job (about USD 0.19–0.38
  per run at recent telemetry). Scorers read rendered prose, so the restored "$3,542 million" is now a
  scaled figure visible to numeric dims; expected neutral (it grounds via the excerpt), to be read from
  the actual run rather than assumed.

## Accounting ledger

DeepSeek balance read before push: USD 55.65 available (`balance-before-push.json`, 21:41:07 UTC).
No model call was made locally; the two network reads (balance, one SEC companyconcept corroboration)
cost nothing. Hosted `eval-baseline` runs are the only paid measurements: the first (run
36354356433, job 108718982686) was cancelled by my own documentation push after 47 successful
summary calls, USD 0.119453 by the run's telemetry, wasted; its replacement (run 36354819301) and
the run for the review-corrected head are recorded in `run-ledger.json` and in the PR thread, since a
further docs push would itself retrigger the paid job. Billed provider cost is not readable from this
session. Full ledger: `review-evidence/financial-claim-scope-2026-09-27/run-ledger.json`.

## Engineering evidence versus acceptance

Everything above is deterministic, offline, packet-bound engineering evidence plus the ordinary
local and hosted gates. It is not an E7 source brief, not a Fable contract-2 verdict, not a candidate
quality acceptance, and does not change the disposition of candidate r or the E7/E8 holds.

## Verification tails

Local gate from `backend/` on the committed implementation (`ce72481`), pinned toolchain
(`requirements-dev.txt`) in an isolated virtualenv:

```
== ruff check . ==
All checks passed!
ruff_exit=0
== bandit -r app -ll ==
bandit_exit=0
== python -m pytest ==
3720 passed, 39 skipped, 2 deselected in 285.84s (0:04:45)
pytest_exit=0
```

The trailing `--- Logging error ---` in the raw log is the pre-existing interpreter-exit Yahoo client
close in `app/routers/companies.py`, present on main before this branch; it is not a test failure.
Two earlier full runs are recorded in the ledger: the first pass on the pre-fix tree (3,718 passed)
and one aborted run superseded by the cell-boundary fix.

Frontend gate not run: no frontend file changes; the only new backend JSON key
(`raw_summary.table_cell_unit_audit`) is not read by the web client.

### Hosted evidence (advisory `eval-baseline`, real DeepSeek generation)

Run 36354819301 on head `d7f5ce0` (the first owner, before the review corrections): regression gate
`PASS — no hard regressions (1 warning(s))` against `baseline_scores.json` (35 filings × 3 runs), the
warning being the standing advisory `mean_untraceable_dollar_figures = 2.6286`. 70/70 attempted and
scored, 0 errors, actual model `deepseek-flash`; pass_rate 1.0, numeric_accuracy 1.0,
numeric_precision 1.0, coverage 1.0, delta_consistency 0.9917, citation_fidelity 0.9682,
currency_consistency 1.0, redundancy 0.9264, financial_depth 0.7857. Telemetry estimate USD 0.181092
across 71 calls; billed cost unknown. The run for the review-corrected head is recorded in the PR
thread, because a further documentation push would itself retrigger the paid job.

## Mutation proof (one deliberate implementation fault, committed state `ce72481`)

Fault: in `source_units._governing_table_scale`, a prose sentence between a banner and a cell no
longer ends the banner's table scope (the `if _is_prose_line(line): return None` early return removed).
Under the fault a bare figure below a section banner but past prose wrongly receives the banner's
scale word; the gate fails on exactly that case, and passes once `git checkout --` restores the file:

```
== committed HEAD: ce72481dff3613a3500e426ff3a2b43271deae9a ==
fault applied: prose no longer terminates a banner's table scope
== gate under fault ==
E         At index 0 diff: 'The filing reports $3,237 million for the period.' != 'The filing reports $3,237 for the period.'
FAILED tests/unit/test_table_cell_units.py::test_bare_figures_the_source_does_not_own_stay_as_written[$3,237-no_governing_banner-…]
1 failed, 17 passed in 3.64s
fault_exit=1
== restored: clean ==
18 passed in 3.13s
restored_exit=0
```

A first, weaker fault (removing the prose-occurrence abstention) also failed the gate (reason
vocabulary changed, 1 failed / 17 passed) but produced no false insertion; it is retained as
superseded in `review-evidence/financial-claim-scope-2026-09-27/mutation-proof-superseded.log`, not
counted as the proof.

## Second review round (chief engineer, 22:26 and 22:30 UTC)

P1 (banner scope through short prose, detached per-share labels, a new table's own unit header) and
P2 (plural scale words) are fixed in `ffdf371`, together with the two integration points: the owner
runs after the source binders on final and preview, the audit carries exact totals beside the capped
detail, and the stamp advances to `summary-2026-09-s`. Local gate on that committed head:

```
== ruff check . ==            All checks passed!   ruff_exit=0
== bandit -r app -ll ==                             bandit_exit=0
== python -m pytest ==        3728 passed, 39 skipped, 2 deselected in 277.04s   pytest_exit=0
```

Deliberate fault re-run on committed `ffdf371` (same fault: prose no longer ends a banner's scope):

```
fault applied: prose no longer terminates a banner's table scope
E   At index 0 diff: 'The filing reports $3,237 million for the period.' != 'The filing reports $3,237 for the period.'
FAILED tests/unit/test_table_cell_units.py::test_bare_figures_the_source_does_not_own_stay_as_written[$3,237-no_governing_banner-…]
1 failed, 25 passed in 3.14s   fault_exit=1
== restored: clean ==
26 passed in 3.14s             restored_exit=0
```

The intermediate P1/P2-only gate (3,726 passed) is retained as `local-gate-p1p2.log`. Offline replay of
the 70 retained outputs after both rounds: one slot changed (WMT run 1, 7/7), eight abstentions.
