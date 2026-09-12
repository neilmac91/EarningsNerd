# Agent A — source-qualified debt scope and the visible leverage owner

Lane note for `codex/wave3-debt-scope-agent-a`. Base: main #828
`48f3758e0729409c7ebbbb26c887cfa02f672455`, verified against the live remote at session start
(`main...origin/main` = 0/0, clean tree, single worktree). Codex owns `tasks/todo.md` and the
release ledger; this file is the lane's own record.

## 1. Engineering checkpoint (settled before the schema edits)

**Invariant 1 — scope fidelity.** No debt figure on any surface asserts a broader maturity,
measurement or entity scope than its own source evidence establishes. A TOTAL is emitted only from
a single issuer-reported combined-total concept; an "identified borrowing components" subtotal only
from a complete, non-overlapping set sharing one accession, instant, currency, basis and reporting
entity. Absent debt is stated as unestablished scope — never zero, never a net-cash position.

**Invariant 2 — visible ownership.** `balance_sheet_liquidity.leverage` is machine-authored on
every delivery path (final, progressive preview, degraded fallback), so a contradictory
model-authored total cannot survive beside a correct block.

### Actual available source rows (audited, not assumed)

Audited the fourth-report retained outcomes (`debt-selected-fourth-outcomes.json`, parent
`14440e57…`) for all seven issuers × two draws. What the pipeline retains today, per filing, is
**exactly one** debt row — value, instant, currency, form, accession and `raw_tag`:

| Issuer | selected concept | value | instant | ccy |
| --- | --- | --- | --- | --- |
| WMT 10-K | `us-gaap:LongTermDebtNoncurrent` | 34,624,000,000 | 2026-01-31 | USD |
| COIN 10-Q | `us-gaap:LongTermDebtNoncurrent` | 5,940,628,000 | 2026-03-31 | USD |
| ASML 20-F | `us-gaap:LongTermDebtNoncurrent` | 2,709,000,000 | 2025-12-31 | EUR |
| JD 20-F | `us-gaap:LongTermDebt` | 41,675,000,000 | 2025-12-31 | CNY |
| MELI 10-K | `us-gaap:LongTermDebt` | 9,193,000,000 | 2025-12-31 | USD |
| F 10-Q | *no `long_term_debt` key at all* | — | — | USD |
| NVO 20-F | *no `long_term_debt` key at all* | — | — | DKK |

No component rows, no context identity, no statement label, no completeness assertion exist today.
Two of seven issuers have no standardized debt row whatsoever, which is why "missing is unknown,
not zero" is the load-bearing rule rather than a footnote. The `edgartools` fact frame *does* expose
`context_ref`, `entity_identifier`, `entity_scheme`, `unit_ref`, `decimals` and
`element_period_type`, so real source identity is obtainable from the already-fetched instance.

### The contradictory visible claims this lane owns

From the same retained outcomes, the rendered §8 `Leverage:` slot:

- **WMT** (both draws): "Total debt was $38.2B … comprising $34.6B long-term debt and $3.5B due
  within one year". Only the $34,624M noncurrent balance is verifiable; $6,596M of short-term
  borrowings is omitted, so the "total" is understated and the $38.2B figure is not in the
  grounding at all.
- **ASML** run 0: "cash … and short-term investments of EUR 405.9M **exceed total debt**" — a
  net-cash comparison on a scope missing the current portion and the ECP carrying amount.
- **MELI** run 0: "**Long-term debt** rose to $9,193M … and current loans payable … were $4,623M" —
  a current-plus-noncurrent concept relabelled noncurrent, with a separate current figure placed
  beside it (aggregate and component together).
- **JD**: "**Total debt increased** with long-term debt of CNY 41.7B" — again the
  current-plus-noncurrent concept called long-term.
- **F**: "Company cash **net of debt** … was $3.3B", mixing Ford Credit with the ex-Credit entity,
  for a filing whose standardized debt row is absent.
- **COIN** run 1 correctly enumerates all three components; that material must survive the fix.
- **NVO** run 0's leverage paragraph makes no debt claim at all (assets, equity, cash) — valid
  analysis that must not be deleted by the correction.

### Contract

Source layer, `edgar/debt_concepts.py` (new, pure): a hand-audited literal table mapping seven
exact qualified concepts to a scope and a carrying basis, each with its admissibility reason; eleven
concepts excluded with their reason; the overlap graph; and the three scope sets that constitute a
complete borrowing partition. Scope is never inferred from a name suffix, a namespace or an amount
match. The `edgartools` bundle's `gaap_mappings.json` is **not** the authority — it files
`us-gaap:LongTermDebt` under non-current liabilities (that element includes current maturities) and
reports `us-gaap:DebtInstrumentFaceAmount`, a principal disclosure, as a balance-sheet total. It is
used only to corroborate the two IFRS names.

Acquisition, `edgar/instance_extractor.py`: `debt_component_observations` queries each admissible
concept **independently** (the `dividend_component_sum_series` precedent — disjoint maturity bands
are not alternative spellings) over the same already-fetched `xb` instance. No second SEC path, no
companyfacts fallback, no taxonomy download. Facts are filtered to the filing's resolved reporting
currency, then must be undimensioned, instant-typed, dated at the filing's own balance date and
unambiguous: more than one distinct value at that instant fails closed (duplicate contexts are not
rescued by preferring the finest `decimals`), as does more than one reporting entity.

Consumer, `ai/debt_scope.py` (new, pure): the single owner shared by both surfaces, per
`lessons/arch-guard-every-model-facing-surface.md`. It refuses a whole observation set rather than
dropping the odd member when filings, instants, currencies, bases or entities disagree, or when one
scope appears twice. It emits a total only from the combined-total concept, a subtotal only from a
complete non-overlapping partition, and otherwise names the bands not separately reported.

Visible owner, `ai/markdown_render.py`: authors `leverage` in `_apply_structured_fallbacks`, which
both the final path and the progressive-preview path already call, so preview and final cannot
diverge. Model leverage prose is kept verbatim **only** when it makes no debt or leverage claim at
all (NVO's equity/asset/cash read survives; WMT's total, ASML's net-cash comparison and Ford's
cross-entity net figure do not). Judgement is on the whole field: no sentence is rewritten, no
clause relabelled, no reporting-prefix regex is extended.

**Minimum interface: none reserved.** `debt_observations` rides through
`extract_standardized_metrics` exactly like `segments` — an annotation, not a standardized metric —
and `summary_sections._v2_balance_sheet_liquidity` already projects `leverage` to web, Markdown,
HTML/PDF and CSV. So `summary_pipeline.py`, `openai_service.py`, `summary_schema.py`,
`summary_sections.py`, `summary_versioning.py` and `evals/runner.py` are **untouched**. No sidecar,
no trust marker, no generation-version stamp is invented: `leverage` stays a plain string, so there
is no eligibility key an old model payload could forge.

### Preserved material

`liquidity`, `maturities_covenants`, `cash_flow`, `working_capital`, the §2 table, cash, equity and
every other section are untouched. WMT's maturity-schedule bullets and COIN's principal-amount
bullet stay in `maturities_covenants`, where they are correctly labelled.

### Named tradeoff (reported, not hidden)

Failing closed costs information the model sourced from filing TEXT that standardized extraction
cannot verify. COIN run 1's correct enumeration of the $1,271,056K current portion and $564,610K
short borrowings is dropped from the leverage slot unless COIN's instance actually tags
`us-gaap:LongTermDebtCurrent` and `us-gaap:ShortTermBorrowings` undimensioned — which the retained
artifacts cannot establish either way, and which no offline fixture may assert. The component
acquisition is the durable fix: where an issuer does tag those concepts, the enumeration and its
subtotal come from source. Codex should weigh this against a text-sourced alternative; it is a
scope decision, not a founder question.

A subtotal is deliberately **not** emitted for noncurrent + current portion alone. That sum is
34,624 + 3,542 = 38,166 — the exact figure the retained WMT outcome mislabelled "total debt" while
short-term borrowings were still missing. A partition must close before it may be added.

## 2. Status

- [x] Alignment preflight (no-op here: fresh clone equal to verified `origin/main`).
- [x] Source-row audit and checkpoint above.
- [x] Registry, acquisition, shared owner, both surfaces, figure-gate alignment.
- [ ] Dedicated debt-scope controls, two mutation proofs, full committed gate.
- [ ] Codex publication slot. Nothing pushed; no assessment dispatched; no paid run.

## 3. Not in this lane

Financing comparisons, distributions-versus-OCF, tax bridges, source-coverage expansion, Copilot
citations (`copilot_service.py` and its tests are agent B's), any locked anchor, any eval re-pin.
