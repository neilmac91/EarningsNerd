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

`backend/tests/unit/test_table_cell_units.py` (43 cases after four review rounds, over the retained WMT debt tables in `tests/fixtures/table_units/`): the retained WMT bullet restored 7/7 including
inline-XBRL-tagged and untagged cells; prose-bare (COST), scale-0 fact (BYND), missing, mixed-scale,
percent, non-dollar, undeclared adjacent table, share-count row, share column, label-less row and
XBRL-literal cases untouched with the documented reason; the flattened excerpt owning nothing; verbatim
evidence untouched; recovered section skipped; audit vocabulary; and the actual consumer
(`OpenAIService.summarize_filing` final path, `_partial_markdown_preview` with and without the index,
recovered path, cached-excerpt path) rendering the same text into `business_overview`; every review-adverse source (short prose, list items, colon line, detached per-share label, unit-token header, capitalised adjacent table, bare adjacent table, flattened text) abstains; a prose fact with `scale="6"` is owned; repeat application is a no-op.

Gate tails, the single deliberate fault/restored proof (re-run on each committed round) and hosted findings are recorded below.

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
- **Banner inheritance (closed by one finite proposition).** Five rounds of review showed every
  general mechanism moving the counterexample: flattened-text heuristics, banner-bound cells, header
  geometry, and finally digit-and-label binding, where a year or `Total` label bound the retained
  debt-maturity facts to "Expected registration fees by year are as follows: 2027: $3,542". The sixth
  round repairs exactly one named proposition, the complete long-term-debt maturity sequence, bound
  part by part to the filing's tagged schedule concepts and total on the DEI report period (see
  "Sixth review round"). Everything else is left unchanged with a reason. A second proposition is a
  second named grammar with its own source binding and gate, never a loosening of this one.
- **Hosted measurement.** The draft PR triggers the advisory `eval-baseline` job (about USD 0.19–0.38
  per run at recent telemetry). Scorers read rendered prose, so the restored "$3,542 million" is now a
  scaled figure visible to numeric dims; expected neutral (it grounds via the excerpt), to be read from
  the actual run rather than assumed.

## Accounting ledger

No model call was made locally in any round; the network reads (DeepSeek balance reads, one SEC
companyconcept corroboration, five SEC document reads for the offline replay) cost nothing. Hosted
`eval-baseline` runs are the only paid measurements, all estimated from the runs' own per-call
telemetry (billed cost is not readable from this session; the shared-account balance moved
55.65 → 54.59 → 54.41 → 54.05 across the reads, the last two steps matching the runs they bracket):

| Run | Head | Result | USD (telemetry) |
| --- | --- | --- | --- |
| 36354356433 | first push | cancelled by my own docs push after 47/70 calls; wasted | 0.119 |
| 36354819301 | `d7f5ce0` | PASS, standing advisory only | 0.181 |
| 36356321090 | `b4f0959` | PASS | 0.181 |
| 36383403453 | `5e6e244` | PASS | 0.179 |
| 36386298431 | `260cebd` | PASS; ran inside DeepSeek's peak tariff window (06:00–10:00 UTC weekdays) | 0.357 |
| Total | | | about 1.017 |

The cumulative USD 1.00 ceiling is exceeded by about USD 0.017: I projected the fourth-round run at
about USD 0.18 without accounting for the peak tariff. Disclosed in the PR thread at once; no further
push is made without root's explicit authorization on the PR. The committed ledger at `260cebd`
still carried the pre-run "about 0.84" expectation; this file and `run-ledger.json` are corrected in
the fifth-round evidence commit, which is held locally with the fifth-round code until that
authorization. Full ledger: `review-evidence/financial-claim-scope-2026-09-27/run-ledger.json`.

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
superseded in `review-evidence/financial-claim-scope-2026-09-27/mutation-proof-superseded.log.txt`, not
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

The intermediate P1/P2-only gate (3,726 passed) is retained as `local-gate-p1p2.log.txt`. Offline replay of
the 70 retained outputs after both rounds: one slot changed (WMT run 1, 7/7), eight abstentions.

## Third review round (source ownership by table block, 28 September)

The residual left by the second round — a banner-less table of a few short headings following a
bannered one, with no unit token of its own — is closed by validating the table block itself rather
than counting heading lines. `_governing_table_scale` now collects every line between a cell and the
nearest banner above it and reads that block top-down against the flattening's own structure:

- the banner may be followed by a header block of at most three text lines (column headers, period
  labels, a glued year line counts as a value line);
- after the first row, a text line is admitted only as a statement section heading set in capitals
  (`ASSETS`, `LIABILITIES AND EQUITY` — the statements' own convention) or as the label directly
  above a row or value-only line (one-value-per-line flattening);
- any other text line — a heading run, a new table's title and header with or without a unit token,
  a label with nothing numeric beneath it — severs the row from the banner and the figure abstains
  with `no_governing_banner`.

Prose lines, scope tokens and non-dollar banners abstain exactly as before, and the same-line row label,
detached label and plural-scale rules from the second round are unchanged.

Effect measured on the retained sources (read-only, no generation; `ownership-measure-round3.txt`
in the evidence directory): across the 70 retained excerpts there are 35,714 demonstrated comma-grouped
cells. The second-round rule owned 8,294 of them; this rule owns 7,732. 974 cells the second round
owned now abstain (26 excerpts) — sampled, they are mixed-case statement sub-headings (`Liabilities`
/ `Current liabilities:`), wrapped labels (`Adjustments to reconcile net income to non-GAAP net` /
`income:`), one-value-per-line rows whose label carries a footnote digit, and stray flattening
fragments (`)`, `%`, `*`) — genuine statement structure that the flattened representation cannot
tell apart from a new table's title, so ownership is treated as ambiguous and the figure is left as
written. 412 cells the second round abstained on are now owned: dash-only value lines and glued
year-value lines (`2029610`) that the old heading counter mistook for headings, and header blocks
under a capitalised statement heading. The output-level replay over the 70 retained outputs is
identical to the second round: one slot changed (WMT run 1, 7/7), eight abstentions with the same
reasons (`offline-replay-70.json`, regenerated).

Gate additions (`test_table_cell_units.py`, now 30 cases): the unit-less new table
(`Other fees` / `Name  Fee` / `Smith  3,237`) and a two-line label above a value line both abstain
with `no_governing_banner`; a capitalised statement heading with its colon sub-heading keeps the rows
beneath it owned (`$3,542 million`); repeat application on an already-restored slot is a no-op
(first pass 7/0, second pass returns None, text unchanged).

Remaining limitation of this shape: a unit-less dollar table whose title is set entirely in capitals,
placed inside a bannered statement's block with no prose, scope token or banner between, would still
inherit the banner. Table boundaries are not present in the offered excerpt; carrying them from the
structured source is E7 source orchestration (Codex-owned) and is not attempted here.

### Original PR promises checked against the final behavior

| Promise | Final behavior |
| --- | --- |
| Primary/recovery ownership | Recovered sections are skipped with reason `recovered`; only the primary model prose is edited (`test_recovered_sections_verbatim_fields_and_missing_source_are_untouched`, `test_actual_consumer_restores_once_and_renders_the_same_text[recovered]`). |
| Preview/final parity | Both paths call the owner after the three source binders with the same excerpt index (`test_owner_runs_after_the_source_binders_on_final_and_preview`, `test_actual_consumer_restores_once_and_renders_the_same_text[final|preview]`). |
| Shared prose allowlist | `figure_trace.policed_prose_slots` is the one slot list for the dollar gate and this owner; `_prose_blob` is built from it. |
| Untouched verbatim evidence | `supporting_evidence` and quote fields are outside the policed slots; the gate asserts them byte-identical while the sibling `impact` is restored. |
| Repeat application | Restored text is unit-bound and never a candidate again (`test_repeat_application_is_a_no_op`). |
| Cache/version limitation | Stamp `summary-2026-09-s` marks old rows stale; no regeneration or drain; cached summaries keep bare figures until a separately bounded refresh. Unchanged from the second round. |
| Audit truncation vs counts | `restored_count`/`unresolved_count` are exact; the detail lists are capped at 40; the pipeline counter reads the totals (`test_audit_totals_are_exact_while_detail_lists_are_capped`). |
| Every occurrence, not any occurrence | Every occurrence of the digits in the excerpt must be a demonstrated cell owned by the same declared scale; a single prose, percent, undelimited, unscaled-row or unowned occurrence abstains. |

JPM period transfer, FIGS reconciliation sign and comparison basis, and PLTR component/causal transfer
remain explicitly unresolved (see Remaining risks).

### Third-round verification tails

Local gate from `backend/` on the tree committed as `554d3c7` (pinned toolchain, isolated virtualenv;
`local-gate-round3.log.txt`):

```
== ruff check . ==            All checks passed!   ruff_exit=0
== bandit -r app -ll ==                             bandit_exit=0
== python -m pytest ==        3732 passed, 39 skipped, 2 deselected, 40 warnings in 284.67s (0:04:44)   EXIT=0
```

The `--- Logging error ---` line in the raw log is the pre-existing interpreter-exit Yahoo client close, as
in every earlier run.

### Third-round mutation proof (one deliberate implementation fault, committed state `554d3c7`)

Fault: after a table's first row every text line is admitted as if it were a statement heading, so an
adjacent unbannered table inherits the banner (the `_is_statement_heading` guard replaced by `True`).
The gate fails on exactly the ownership cases with false `$3,237 million` insertions, and passes once
`git checkout --` restores the file (`mutation-proof-round3.log.txt`):

```
== committed HEAD: 554d3c7 ==
fault applied: text lines after the first row no longer need a row beneath them
== gate under fault ==
E         At index 0 diff: 'Smith paid $3,237 million.' != 'Smith paid $3,237.'
E         At index 0 diff: 'Other obligations were $3,237 million.' != 'Other obligations were $3,237.'
FAILED …test_review_adverse_sources_abstain[$3,237-no_governing_banner-… Part II … Other matters … Smith  3,237-…]
FAILED …test_review_adverse_sources_abstain[$3,237-no_governing_banner-… Other fees … Name  Fee … Smith  3,237-…]
FAILED …test_review_adverse_sources_abstain[$3,237-no_governing_banner-… Other long-term … obligations … 3,237-…]
3 failed, 27 passed in 3.59s
fault_exit=1
== restored: clean ==
30 passed in 3.25s
restored_exit=0
```

The earlier proofs (prose no longer ending a banner's scope, on `ce72481` and `ffdf371`) are retained
as history in `mutation-proof.log.txt`; this round's proof is the one counted for the corrected head.

## Fourth review round (source-bound ownership, 28 September)

Root's review of `5e6e244` reproduced a remaining ownership defect: a short list item or colon line
after a bannered table (`• Registration fee:  $3,237`, `1. Registration fee:  $3,237`,
`Registration fee:  $3,237`) still inherited the banner, as did the disclosed all-capitals table
transition. The decision was not to accept that as a limitation and not to add another typography
heuristic. The flattened excerpt carries no table boundary, so this round stops using it for
ownership altogether and binds every figure to the filing's own source document, through the
existing structured seam the statement-relationship source already reads (`lxml` HTML, the
`_cells` / `_nearby` / `_text` helpers of `app/services/edgar/statement_relationship_source.py`):

- **Inline-XBRL facts.** An occurrence inside `ix:nonFraction` is owned by its own `scale`
  attribute and `unitRef`: unit must resolve to `iso4217:USD` alone; `scale="6"` → million,
  `"3"` → thousand, `"9"` → billion; `scale="0"` (or absent) declares the bare reading and the
  owner abstains with `declared_unscaled`; per-share or other units abstain with `non_dollar_unit`.
  The fact text must be exactly the digits.
- **Untagged table cells.** An occurrence inside a `<td>`/`<th>` is owned only when the cell holds
  exactly that amount (optionally `$` or parentheses), the enclosing `<table>` declares one dollar
  scale in its own cells or caption (or, failing that, as the whole text of the single node
  immediately before it), the row's leftmost text cell is a label not excluded from the scale
  (per-share, counts, a unit/scope token), no column header over that cell is a share / per-share /
  rate / percent / scope header, and no `%` follows the value.
- **Everything else is prose.** Text outside a cell and outside a fact abstains with
  `prose_occurrence`; a table without its own declaration abstains with `no_governing_banner`
  whatever precedes it; a value with no label to its left abstains with `no_row_label`.
- **Every occurrence must agree.** As before, a single prose, percent, unscaled or differently
  scaled occurrence of the digits anywhere in the document abstains.

The document is `filing_text`, the same source `acquire_statement_context` parses, on both the final
and the preview path; it is parsed once and only when a bare figure exists (0.16 s for the 2.3 MB
WMT document), so the 65 outputs with no bare figure cost nothing. A cached-excerpt generation
(`cache_is_valid`, `filing_text = ""`) has no document and the owner abstains entirely: cached rows
keep bare figures, as the statement binder already does on that path; this is a disclosed narrowing.

Demonstrated offline before any paid push (`tests/unit/test_table_cell_units.py`, 43 cases; the WMT
fixture is the iXBRL unit definitions plus the five debt tables of the retained WMT source,
`tests/fixtures/table_units/wmt-20260131-debt-tables.html.gz`):

| Root's reproduction | Now |
| --- | --- |
| `• Registration fee:  $3,237` after a millions table | `prose_occurrence`, text unchanged |
| `1. Registration fee:  $3,237` | `prose_occurrence` |
| `Registration fee:  $3,237` | `prose_occurrence` |
| `DIRECTOR COMPENSATION` table after a millions table | `no_governing_banner` |
| a bare adjacent table, `Name  Fee ($)` header | `no_governing_banner` / `unscaled_column` |
| the flattened excerpt itself (two-space cells, glued years) | `prose_occurrence` — owns nothing |
| retained WMT maturities bullet | 7/7 restored (`$3,542 million` … `$38,166 million`) |

Replay over the 70 retained outputs with the source documents fetched today through the app's SEC
transport (WMT, COST, BYND, BA): identical to every earlier round at the output level — one slot
changed (WMT run 1, 7/7), eight abstentions — with two reasons now stronger than before: the BYND
`$130,000` is the issuer's own `scale="0"` fact (`declared_unscaled`), and the COST figures are
untagged prose. Today's served bytes differ from the retained provenance hashes by exactly ten
characters per document; the retained bytes are not available here for a byte comparison, and the
cells and facts used read the same values as the retained, hash-verified grounding excerpts.

Behaviour that changes beyond the retained corpus: a bare figure the issuer's prose writes bare
but tags with `scale="6"` (the BA `$10,550` fixture) is now restored, because the fact itself
declares its scale; previously it was abstained as a prose convention.

Remaining limitations of the supported shape (all abstentions, never insertions): a declaration
node separated from its table by a title; a statement split across several `<table>` elements
with the declaration only in the first; a plain-text or non-HTML source (6-K exhibits); a table
whose declaration cell names a scale form the pattern does not recognise (`(RMB in millions)` is
`no_governing_banner`, not `non_dollar_banner`); rows whose label is not the leftmost cell.

### Fourth-round verification tails

Local gate from `backend/` on the tree committed as `595344c` (pinned toolchain, isolated virtualenv;
`local-gate-round4.log.txt`):

```
== ruff check . ==            All checks passed!   ruff_exit=0
== bandit -r app -ll ==                             bandit_exit=0
== python -m pytest ==        3745 passed, 39 skipped, 2 deselected, 40 warnings in 280.60s (0:04:40)   EXIT=0
```

### Fourth-round mutation proof (one deliberate implementation fault, committed state `595344c`)

Fault: a table without its own declaration inherits any declaration found in an earlier sibling,
bannered tables included (`_nearby` bounding and the whole-node `fullmatch` replaced by an unbounded
`search`). The gate fails on exactly the adjacent-table ownership cases with false `$3,237 million`
insertions, and passes once `git checkout --` restores the file (`mutation-proof-round4.log.txt`):

```
== committed HEAD: 595344c ==
fault applied: an undeclared table inherits any earlier sibling's declaration, bannered tables included
== gate under fault ==
E         At index 0 diff: 'Smith paid $3,237 million.' != 'Smith paid $3,237.'
FAILED …test_bare_figures_the_source_does_not_own_stay_as_written[$3,237-no_governing_banner-… adjacent <table> …]
FAILED …test_bare_figures_the_source_does_not_own_stay_as_written[$3,237-no_governing_banner-<p>(In millions)</p><p>Schedule of other amounts</p>…]
FAILED …test_review_adverse_sources_abstain[$3,237-no_governing_banner-… DIRECTOR COMPENSATION …]
FAILED …test_review_adverse_sources_abstain[$3,237-no_governing_banner-… <table><tr><td>Name</td><td>Fee</td></tr> …]
4 failed, 39 passed in 3.74s
fault_exit=1
== restored: clean ==
43 passed in 3.46s
restored_exit=0
```

The earlier rounds' proofs are retained as history in `mutation-proof.log.txt` and
`mutation-proof-round3.log.txt`; this round's proof is the one counted for the corrected head.

## Fifth review round (proposition-bound ownership, 28 September; local, not pushed)

Root's review of `260cebd` held generic adoption on three findings: a declaration row later in the
same table scaled an earlier explicit-dollar row; explicit per-share scope disappeared under
full-width, `rowspan` or `tfoot` header geometry and unknown banner exceptions; and the resolver
bound digits, not the authored claim, to a source cell. The instruction was to stop expanding the
banner/typography heuristic and narrow the mutation to a source-owned proposition whose exact
row/period/amount mapping matches the authored statement, or leave the statement unchanged.

The owner now reads none of banners, cells, geometry or flattened text. A bare figure is restored
only when all of the following hold, otherwise it abstains with the stated reason:

| Requirement | Abstention |
| --- | --- |
| the authored text pairs the figure with a label by a colon (`2027: $3,542`, `Total: $38,166`) | `no_authored_label` |
| the filing's HTML carries an `ix:nonFraction` fact whose text is exactly those digits | `no_tagged_fact` |
| that fact sits in a table row whose leftmost text cell is that label (case, spacing and a trailing colon ignored) | `no_matching_row` |
| the filing's DEI `DocumentPeriodEndDate` validates (`statement_context.source_report_period`) | `no_report_period` |
| the fact's context ends on that period | `period_mismatch` |
| the fact's `unitRef` resolves to `iso4217:USD` alone | `non_dollar_unit` |
| the fact's `scale` is 3, 6 or 9 (`0`/absent declares the bare reading) | `declared_unscaled`, `unsupported_scale` |
| every such bound fact agrees | `mixed_scales` |
| a source document exists (cached-excerpt generations have none) | `no_source_document` |
| standardized XBRL does not support the literal reading | `literal_xbrl_match` |

Root's three findings under this contract: the later in-table declaration is never read (an untagged
`$3,237` cell → `no_tagged_fact`; a tagged `scale="0"` one → `declared_unscaled`); per-share scope is
the fact's own unit (`usdPerShare` → `non_dollar_unit`) whatever the heading geometry — full-width
`Per Share Data`, a `rowspan="2"` header, a `tfoot` row and the unknown "except registration fees"
exception all abstain; and a `Revenue | 3,237` row never scales `Registration fee: $3,237`
(`no_matching_row`). The retained WMT sequence is exactly the supported shape: each authored pair
(`2027: $3,542` … `Total: $38,166`) binds to the maturities-table row of the same label, whose
fact (`us-gaap:LongTermDebtMaturitiesRepaymentsOfPrincipal…`, `us-gaap:LongTermDebt`) is USD,
`scale="6"`, on the 2026-01-31 DEI period → 7/7 restored.

Coverage is deliberately narrower than every earlier round: unlabelled prose figures, untagged
cells, prior-period columns and plain-text sources are all left unchanged. The 70-output replay
with today's fetched WMT/COST/BYND/BA documents is unchanged at the output level (one slot, 7/7,
eight abstentions, now all `no_authored_label`). The BA `$10,550` prose fact restored in the
fourth round is no longer restored (no label pairs it).

Gate: `test_table_cell_units.py`, 43 cases over a fixture that now carries the WMT DEI period
element, the facts' contexts, a prior-period context and the unit definitions beside the five debt
tables (`tests/fixtures/table_units/wmt-20260131-debt-tables.html.gz`, rebuilt). Mutation proof:
the row-label binding removed (any fact with the same digits owns the proposition).

Ceiling: cumulative hosted telemetry is about USD 1.017 after the fourth-round run landed in the
peak tariff window, so this round is committed locally and NOT pushed; the push is requested from
root on the PR with this evidence, and happens only on explicit authorization.

### Fifth-round verification tails

Local gate from `backend/` on the tree committed locally as `acee6d9` (`local-gate-round5.log.txt`):

```
== ruff check . ==            All checks passed!   ruff_exit=0
== bandit -r app -ll ==                             bandit_exit=0
== python -m pytest ==        3745 passed, 39 skipped, 2 deselected, 40 warnings in 299.50s (0:04:59)   EXIT=0
```

### Fifth-round mutation proof (one deliberate implementation fault, committed state `acee6d9`)

Fault: the row-label binding is removed, so any inline-XBRL fact with the same digits owns the
proposition whatever its row says. The gate fails on exactly the source-to-proposition cases (a
"Revenue" row scaling `Registration fee: $3,237`, a bullet label, a prose fact, a value-first row)
with false `$3,237 million` insertions, and passes once `git checkout --` restores the file
(`mutation-proof-round5.log.txt`):

```
== committed HEAD: acee6d9 ==
fault applied: the authored label no longer has to match the fact's row label
== gate under fault ==
FAILED …test_bare_figures_the_source_does_not_own_stay_as_written[$3,237-no_matching_row-…]  (x4)
FAILED …test_the_source_document_is_parsed_once_and_only_on_demand
5 failed, 38 passed in 3.95s
fault_exit=1
== restored: clean ==
43 passed in 3.87s
restored_exit=0
```

## Sixth review round (one finite proposition, 28 September; local, not pushed)

Root's exact-head review of `7c2f998` accepted the unit and report-period binding but held a P1:
when a year or `Total` is the entire authored label, the round-5 owner bound the retained
debt-maturity facts to unrelated prose ("Expected registration fees by year are as follows: 2027:
$3,542; 2028: $3,237" → "$3,542 million"; "Registration fees: Total: $38,166" → "$38,166 million").
The instruction was to make the supported unit repair one complete, source-owned long-term-debt
maturity proposition and to abstain on everything else, without label heuristics, issuer
hardcoding or digit matching.

The owner now recognises exactly one authored form and one source shape:

- **Authored.** `[Annual|Contractual|Scheduled] maturities of [our] long-term debt [during|for|over
  the next five [fiscal] years and thereafter] [are|were] as follows:` then exactly five consecutive
  fiscal-year pairs, `Thereafter` and `Total`, each a bare `$N,NNN`, `;`-separated, an optional final
  period and nothing else (`maturity_proposition`). A different subject, an unknown qualifier, a
  reordered, partial or already-scaled sequence, or trailing text is not a proposition and every bare
  figure in it abstains with `unsupported_proposition`.
- **Source.** On the filing's validated DEI report period, exactly one value for each of the six
  schedule concepts of the hand-audited `debt_concepts.DEBT_MATURITY_SEQUENCE`
  (`us-gaap:LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths` … `AfterYearFive`) and
  for the total (`us-gaap:LongTermDebt`), each in a table row whose leftmost cell is that year /
  `Thereafter` / `Total`, in USD alone, with one shared `scale` of 3/6/9, whose digits equal the
  authored amounts in order, whose first year is the year after the report period, and whose six
  amounts sum to the total. Repeated identical facts (the WMT total is tagged in the debt table and
  the schedule) are one fact; disagreeing repeats are `conflicting_facts`.
- **Abstention vocabulary.** `unsupported_proposition`, `no_source_document`, `no_report_period`,
  `year_mismatch`, `missing_fact`, `conflicting_facts`, `amount_mismatch`, `row_label_mismatch`,
  `non_dollar_unit`, `declared_unscaled`, `unsupported_scale`, `mixed_scales`,
  `sequence_does_not_sum`, `literal_xbrl_match`, `recovered`.

Measure (concept), reporting basis (the sum identity between the principal schedule and the
tagged total), period (context), unit and scale (the fact's own attributes), row (label) and order
(position) are all read from the source. Root's two reproductions and every earlier round's
counterexample abstain; the retained WMT bullet restores 7/7 on the fixture and on the full 2.3 MB
document (0.19 s). The 70-output replay is unchanged at the output level (one slot, 7/7, eight
abstentions, all `unsupported_proposition`).

Gate: `test_table_cell_units.py`, 51 cases — the retained bullet, a synthetic schedule in the
source's layout, the proposition grammar (positive and eleven negative forms), nine adverse prose
forms against the real fixture, fifteen source-ownership abstentions (missing/conflicting facts,
amount, row, unit, scale, period, DEI, year, sum, flattened excerpt), repeated-fact agreement, repeat
application, XBRL literal/corroboration, recovered/verbatim/missing-source, audit cap, lazy parse,
and the final/preview/recovered/cached-excerpt consumers. Mutation proof: the introduction grammar
disabled (any "… as follows:" prefix admits the sequence — root's P1 shape).

Not pushed: root asked for the exact local diff and proof before spending another head measurement;
cumulative hosted telemetry is USD 1.371 of the USD 1.65 ceiling.

### Sixth-round verification tails

Local gate from `backend/` on the tree committed locally as `d32e4e8` (`local-gate-round6.log.txt`):

```
== ruff check . ==            All checks passed!   ruff_exit=0
== bandit -r app -ll ==                             bandit_exit=0
== python -m pytest ==        3753 passed, 39 skipped, 2 deselected, 40 warnings in 289.68s (0:04:49)   EXIT=0
```

### Sixth-round mutation proof (one deliberate implementation fault, committed state `d32e4e8`)

Fault: the affirmative long-term-debt maturity introduction is no longer required, so any
"… as follows:" prefix admits a complete sequence (root's P1 shape). The gate fails on exactly the
subject/qualifier cases with false `$3,542 million` … insertions (a dated qualifier, an operating-lease
subject), and passes once `git checkout --` restores the file (`mutation-proof-round6.log.txt`):

```
== committed HEAD: d32e4e8 ==
fault applied: the debt-maturity introduction is no longer required
== gate under fault ==
E   At index 0 diff: 'As of January 31, 2026, annual maturities of long-term debt are as follows: 2027: $3,542 million; …'
FAILED …test_only_the_complete_maturity_sequence_is_a_proposition[As of January 31, 2026, annual maturities …]
FAILED …test_only_the_complete_maturity_sequence_is_a_proposition[Maturities of operating lease obligations …]
FAILED …test_everything_but_the_proposition_stays_as_written[As of January 31, 2026, annual maturities …]
3 failed, 48 passed in 3.52s
fault_exit=1
== restored: clean ==
51 passed in 3.63s
restored_exit=0
```

Root's own two reproductions abstain even under this fault because their sequences are partial; the
sequence grammar and the introduction grammar are independent guards.

## Seventh review round (context identity, 28 September; local, not pushed)

Root reconstructed the sixth-round owner to its hash and confirmed the grammar closes the fee /
year / `Total` counterexamples, but isolated the source-context half of the same P1: `_index`
reduced every maturity fact's context to a period end, and `source_report_period` validated only the
DEI fact's own context, so seven facts on a same-CIK context carrying
`us-gaap:SubsidiaryAxis=example:SubsidiaryMember`, seven facts alternating between two such
contexts, or seven facts on another entity's context all still repaired the consolidated prose 7/7.

The finite correction is one context-ownership guard in the existing owner:

- `statement_context.source_report_identity` returns the validated DEI `(report date, issuer CIK)`
  (CIK normalized, leading zeros dropped); `source_report_period` keeps its contract on top of it.
- `statement_context.source_context_identity(context)` (the EDGAR layer, where the CIK scheme
  literal is sanctioned) normalizes every context to `(CIK, period kind, period end, dimensional)`: exactly one `identifier` under the SEC CIK scheme, a numeric CIK, exactly one
  `instant` or exactly one `startDate`/`endDate` pair, and whether any `segment` / `scenario` /
  `explicitMember` / `typedMember` is present. Anything else is malformed and owns nothing.
- The proposition may draw only on facts whose context signature is `(issuer CIK, "instant",
  report date, non-dimensional)`. Facts on any other signature — a subsidiary member, another
  entity, a duration ending on the date, a malformed context — neither authorize the repair nor
  poison a complete consolidated sequence. Context IDs may differ when their normalized identities
  agree (`0000104169` and `104169` are one entity).

Root's reproductions abstain (`missing_fact`: no fact of the concept on the consolidated signature);
a consolidated schedule beside a subsidiary's own dimensional schedule still restores 7/7; the WMT
control's seven facts are all on `c-16` (`0000104169`, instant `2026-01-31`, no members) and restore
7/7 on the fixture and the full document. Gate: 57 cases (the sixth round's 51 plus one dimensional
context, two alternating dimensional contexts, a foreign CIK, a duration period, a malformed
context, a dimensional duplicate beside the consolidated schedule, and same-identity context IDs).
Mutation proof: the context identity reduced to its period end again. Replay over the 70 retained
outputs unchanged (one slot, 7/7, eight `unsupported_proposition`).

Not pushed; root asked for the exact owner/context-helper diff, hash and proof before another paid
push. Cumulative hosted telemetry USD 1.371 of USD 1.65.

### Seventh-round verification tails

Local gate from `backend/` on the tree committed locally as `1667523` (`local-gate-round7.log.txt`;
two earlier attempts are recorded as superseded in the ledger — a CIK-scheme literal first placed in
`source_units.py` tripped the `sec.gov` allow-list gate and the helper was moved into the EDGAR layer,
then a shell working-directory reset ran ruff at the repository root):

```
== ruff check . ==            All checks passed!   ruff_exit=0
== bandit -r app -ll ==                             bandit_exit=0
== python -m pytest ==        3759 passed, 39 skipped, 2 deselected, 40 warnings in 316.45s (0:05:16)   EXIT=0
```

### Seventh-round mutation proof (one deliberate implementation fault, committed state `1667523`)

Fault: the context identity is reduced to its period end again (any context ending on the report
date authorizes — the sixth-round behaviour). The gate fails on exactly the context-ownership cases
with the retained bullet falsely restored, and passes once `git checkout --` restores the file
(`mutation-proof-round7.log.txt`):

```
== committed HEAD: 1667523 ==
fault applied: the context identity is reduced to its period end
== gate under fault ==
FAILED …test_facts_outside_the_issuers_consolidated_instant_own_nothing[one dimensional context]
FAILED …test_facts_outside_the_issuers_consolidated_instant_own_nothing[two dimensional contexts]
FAILED …test_facts_outside_the_issuers_consolidated_instant_own_nothing[foreign CIK]
FAILED …test_facts_outside_the_issuers_consolidated_instant_own_nothing[duration period]
FAILED …test_a_dimensional_duplicate_never_poisons_the_consolidated_schedule
5 failed, 52 passed in 4.33s
fault_exit=1
== restored: clean ==
57 passed in 3.70s
restored_exit=0
```

## Eighth review round (repeated IDs and the DEI duration, 28 September)

Root verified the seventh-round hashes and reproduced its closures, then isolated one remaining
ambiguity class: `_index` overwrote duplicate context IDs and duplicate unit IDs, so a dimensional,
foreign or duration context redefined under the same ID as a consolidated one repaired 7/7 in one
definition order and abstained in the other, and a duplicate unit ID behaved the same way for
non-USD → USD. Root supplied the minimal correction and asked that the DEI prerequisite be made
explicit through the shared normalizer.

- A repeated context ID or unit ID is permanently unavailable in every order: the second definition
  sets the entry to `None` instead of replacing the first. Distinct IDs with equivalent normalized
  identities still pass.
- `source_report_identity` now validates the DEI context through `source_context_identity`: it must
  be a well-formed, non-dimensional duration whose end equals the parsed DEI date. End-only,
  instant-plus-end and multiple-start contexts fail closed (`no_report_period`); the issuer check is
  unchanged.

Gate: 66 cases (the seventh round's 57 plus four repeated-context orders, two repeated-unit orders
and three malformed DEI forms; the valid duration is every other case's DEI context). Mutation
proof: a repeated context ID resolving to its last definition again. Replay over the 70 retained
outputs unchanged (one slot, 7/7, eight `unsupported_proposition`).

Root replaced the publish hold for this corrected, locally gated candidate and reserved a revised
USD 2.10 cumulative planning ceiling (about USD 1.371 spent) covering one corrected-head 70-output
measurement and one eventual Copilot check; the reservation is confirmed on the PR before the push.

### Eighth-round verification tails

Local gate from `backend/` on the tree committed locally as `f4ead2f` (`local-gate-round8.log.txt`):

```
== ruff check . ==            All checks passed!   ruff_exit=0
== bandit -r app -ll ==                             bandit_exit=0
== python -m pytest ==        3768 passed, 39 skipped, 2 deselected, 40 warnings in 328.13s (0:05:28)   EXIT=0
```

### Eighth-round mutation proof (one deliberate implementation fault, committed state `f4ead2f`)

Fault: a repeated context ID resolves to whichever definition came last again (the seventh-round
behaviour). The gate fails on exactly the dimension → consolidated, foreign → consolidated and
duration → consolidated orders with the retained bullet falsely restored, and passes once
`git checkout --` restores the file (`mutation-proof-round8.log.txt`):

```
== committed HEAD: f4ead2f ==
fault applied: a repeated context ID resolves to its last definition
== gate under fault ==
FAILED …test_a_repeated_context_id_owns_nothing_in_any_order[dimension then consolidated]
FAILED …test_a_repeated_context_id_owns_nothing_in_any_order[foreign then consolidated]
FAILED …test_a_repeated_context_id_owns_nothing_in_any_order[duration then consolidated]
3 failed, 63 passed in 4.03s
fault_exit=1
== restored: clean ==
66 passed in 3.63s
restored_exit=0
```
