# Shared financial explanation owner — offline feasibility, 2026-09-09

**A shared owner is viable, but the present standardized metrics cannot certify item inclusion, accounting scope or causation.** The smallest sound next implementation is a source-backed fact/relationship observation at the existing selected-filing extraction boundary, followed by a narrow arithmetic owner. Do not replace the failed prose instruction with a model-authored `included_in` boolean and call that validation. General adjusted-earnings narratives remain unsupported until the relationship evidence exists.

This is research and an implementation sketch, not a production change or quality clearance. No network, SEC, provider, model, settings, repository or locked-test changes occurred. The probes block socket connections. Application references were checked in `work/supported-financial-explanations` at `b6a3272e03ea397e3b434bfeba1e764ff91b099e`; the extraction files are unchanged from actual #803 main `5e6b673476b684ac681a7c46f890e38ca2c3ce70`. The ordinary `work/EarningsNerd` checkout is older and is not claimed as the candidate source.

## Existing owners and the missing seam

`edgar/xbrl_service.py::_extract_from_filing_instance_sync` obtains the selected accession's `xb` once. Its duration loop (around 374–400) reduces rows to end/value/form/accession/currency; most metrics do not retain their winning concept. `instance_extractor.py:362–400` deliberately filters undimensioned facts and standard durations, resolves duplicate precision, then drops original context ID, start date, entity/dimension identity, original fact ID and exact numeric lexical form. This is useful metric selection, but inadequate evidence for a new accounting assertion. A generic `net_income` key cannot distinguish parent income, consolidated income and income available to common shareholders.

`facts_service.py::normalize_standardized_to_facts` persists that reduced observation; its companyfacts path is a different owner, including historical series. Neither can recover lost source context by renaming a generic key. `schemas/summary.py::attach_normalized_facts` and `metric_delta_service.py` own display parsing/comparative arithmetic, not statement inclusion. `ai/normalize.py` cleans placeholders/evidence strings; it is not semantic validation. Preserve all of these contracts rather than use their normalized names as proof.

In #805, primary and recovery use `FINANCIAL_EXPLANATION_SUPPORT`, `FINANCIAL_DRIVER`, and `EARNINGS_RECONCILIATION` from `summary_schema.py:102–135`. These are instructions, not a runtime validator; `SummaryDoc` is lenient and its docstring explicitly says it has no production validation caller. `ai/markdown_render.py::_apply_structured_fallbacks` already owns deterministic cash/return/segment content. It is the appropriate eventual integration seam for an independently validated explanation projection, reused by previews and final assembly; `summary_sections.py:604–618` simply renders the earnings narrative. Public web/Markdown/export surfaces should consume that same projection, not independently re-interpret typed records.

## What pinned EdgarTools actually exposes

Installed 5.56.0 `xbrl/models.py:145–188` exposes original context references, entity, duration/instant, dimensions, unit references, lexical values, decimals and optional XML fact IDs. `PresentationNode` preserves hierarchy/preferred-label roles, but presentation membership is not an arithmetic inclusion relationship. `CalculationTree.all_arcs` preserves each role-scoped parent/child edge and weight; `XBRL.calculation_linkbase()` (`xbrl/xbrl.py:459–549`) returns those edges without fetching again.

The new offline probe `work/typed-explanation-calculation-probe.py` parsed an **already owned ASML** calculation document through the pinned parser and returned **287 actual arcs**. Source `asml-20251231_cal.xml`, same retained accession `0001628280-26-011378`, decoded-content UTF-8 hash `f7c8d35f74b8b76c8f6d1ea58bb54bd4dce2371ba05633f00e9122f7c03edb80`. Results: `work/typed-explanation-calculation-capability.json`. This proves the API exists, not that BA/PFE/RIVN have the needed relationship in a retained or loaded network.

Two important refutations prevent treating SDK output as a certificate:

1. `calculation.py:155–161` defaults absent or invalid weight to +1. The offline controls observed −1 for a genuine `weight="-1"`, but +1 for both `weight="garbage"` and a missing attribute. The adapter must validate original linkbase attributes and source identity; a plausible SDK float is insufficient. The parser also de-duplicates by role/parent/child, so a conflicting duplicate cannot be certified from the DataFrame alone.
2. The earlier independently reproducible `work/instance-provenance-probe.json` demonstrates namespace URI loss: different namespace bindings can produce the same retained prefixed concept. Calculation output likewise exposes prefix/local names, not original document+expanded-name proof. Resolve the original schema locator and namespace from owned source, or mark unknown. Do not infer a URI or source locator from a string prefix.

Calculation edges are statements of summation at a role, not causes of year-over-year change. They carry no fact context. Bind every selected fact separately by entity, exact duration/instant, dimensions and unit; then validate arithmetic closure within disclosed precision. Never recursively sum a graph without accounting for duplicate paths, cycles, missing children, inconsistent roles or overlapping scopes. A role name, matching amount or common CIK alone does not establish subtotal compatibility. Complete arithmetic closure still does not prove a business cause such as pricing, restructuring or demand.

## Three source controls and the limits they establish

`work/typed-explanation-probe.py` inventories exact original inline fact IDs, expanded names, context XML, units, attributes, source XPath and decoded UTF-8 source hash. Results are `work/typed-explanation-source-inventory.json` (PFE 40, BA 74, RIVN 34 selected undimensioned diagnostic occurrences). The selection is exploratory, not a general classifier. Additional dimensional examples below were read directly from the same owned HTML.

| Control | Positive evidence | Must remain unknown or rejected |
| --- | --- | --- |
| **BA: reported operating income and company core reconciliation** | Accession `0001628280-26-004357`, `f-88`, us-gaap OperatingIncomeLoss, context c-1, FY2025: 4,281M. Full-source F00653–F00658 explicitly reconciles FAS/CAS −1,045M to core 3,236M. This is a positive human-reviewed source reconciliation and 4,281−1,045=3,236. | Core 3,236 is not an inline nonFraction fact in this source. Tagged adjustment `f-563` is context c-74 with CorporateReconcilingItemsAndEliminationsMember. Gain 9,566 occurrences `f-714`/`f-2506` are respectively disposal-event and GlobalServices segment contexts. Matching numbers cannot automatically produce a consolidated, same-period ex-gain certificate. The company’s core definition excludes pension adjustment; it does not mean ex-divestiture income. |
| **PFE: signed tax bridge, positive arithmetic scope** | Accession `0000078003-26-000054`: f-67/69/71 share c-1, entity 0000078003, 2026-01-01–03-29, USD, no dimensions: pretax 3,170M minus tax 461M equals continuing income 2,709M. f-68/70/72 share prior c-11 (2025-01-01–03-30): 2,785−(−189)=2,974 versus reported 2,973M. The 1M residual is consistent with displayed million rounding; it must remain visible, not silently altered. Pretax rose 385M, tax expense rose 650M and continuing income fell 264M. | This is a source-bound **arithmetic bridge**, not a verified filed calculation edge: no PFE calculation file was acquired here. It cannot be relabeled operating income, common-shareholder net income, an ex-tax adjusted result, or a fully explained business cause. f-79 parent/common income is 2,687M, not 2,709M; noncontrolling interests and discontinued operations remain distinct. No inferred item tax effects. |
| **RIVN: reject sign/role/period substitution** | Accession `0001874178-26-000008`, source F01573 explicitly says 186M settlement expense increased other expense, partially offset by 101M gain; F02055 places gain in Other Income. `f-305` is extension GainOnEquityMethodInvestment, c-1 FY2025, +101M. This refutes #805's reversed expense/gain effects. | The tagged 186M occurrence `f-1123` is **PaymentsForLegalSettlements**, context c-257, **January 2026** plus litigation and SubsequentEvent dimensions. It does not prove a FY2025 expense's inclusion merely because the amount equals the prose expense. FY2025 common-stockholder net loss f-186 is −3,646M; −3,646+186−101=−3,561 is arithmetic only until target inclusion, tax and NCI compatibility are supported. |

Each case survived two independent challenges. BA: (1) the explicit filed core definition explains the 3,236 number without excluding the gain; (2) inspecting original contexts defeats a same-number/same-CIK automatic join. PFE: (1) original statement identities and signed tax figures support the continuing-income bridge rather than the model's pretax drivers applied to net income; (2) parent-income and prior rounding differences prevent a falsely exact/common-income certificate. RIVN: (1) source narrative explicitly states the opposite signs to the candidate; (2) the original tagged settlement is a subsequent-period payment, so a concept/amount matcher would validate the wrong item. None of these controls implies historical retained outputs were changed or all accounting explanations can be derived from inline tags.

## Minimum staged implementation

**First: evidence production, without replacing existing metrics.** At the existing selected-filing instance extraction boundary, optionally build a bounded immutable sidecar from already loaded facts and already owned source documents. Carry source hash/representation, accession, exact source ID, expanded concept identity, lexical Decimal, decimals, entity, period, dimensions, units and observed relationship provenance. No extra SEC requests, no companyfacts/latest-filing substitution, no cache invalidation. Missing original XML/linkbase ownership or a legacy cache hit returns a specific unavailable reason. The current HTML source-provenance observer captures a decoded response identity, not a fully parsed accounting registry; extending it is real engineering with parser/transform/resource limits, not a free reuse of its hash.

**Second: a narrow pure arithmetic owner.** Accept only code-created verified registry IDs and one of two explicit relation forms: (a) an original validated role-scoped filed summation with complete matched facts, or (b) a deliberately enumerated accounting identity, such as pretax minus tax equals continuing income, carrying a distinct `code_defined_identity` provenance label and checked source concepts/contexts/closure. Do not present (b) as a filed edge. Bounds, Decimal precision intervals and ambiguous duplicates must be handled before the registry becomes trusted. Do not permit arbitrary formula text or `included_in` supplied by a model. For an unsupported adjustment, preserve independently supported reported facts/item statements and omit the derived ex-item result; do not erase unrelated narrative content.

**Third: shared presentation after measured coverage.** The model may select a target or propose a source quote/ID; it cannot create a verified relation. The owner emits a conservative statement with exact named measure, formula and known residual/unknown scope. Route applicable P&L/Print/earnings slots to the same accepted record so one paragraph cannot contradict another. An optional internal field must be stripped before public/persisted schema projection, or deliberately versioned if retained; do not smuggle an unused key through lenient SummaryDoc. Previews must wait for completed validated records and use the same owner as final output, preserving the locked SSE envelope and current no-final-attempt-association semantics.

The first useful positive release can cover source-bound tax/continuing-income arithmetic, not all unusual items. BA’s untagged non-GAAP reconciliation and RIVN’s narrative expense require a separately verified structured table/narrative relation source; general language understanding has not become deterministic merely by assigning IDs. Accept this explicit gap rather than ship a false certificate or a universal adjusted-income suppression rule. Debt scope, source inclusion and cash basis remain separate owners.

## Code sketch (design only)

```python
# All Verified* records are constructed at the source adapter, never deserialized
# directly from model JSON. IDs resolve in a per-selected-filing immutable registry.
def explain_arithmetic(request, registry):
    facts = registry.resolve_exact_ids(request.fact_ids)
    if facts is None:
        return Unknown("unresolved_source_fact")
    relation = registry.resolve_verified_relation(request.relation_id)
    if relation is None:
        return Unknown("no_verified_relationship")
    # relation owns allowed concepts, coefficients and target; model owns none.
    if not relation.matches(facts):
        return Unknown("period_entity_unit_dimension_or_target_mismatch")
    interval_result = relation.evaluate_decimal_intervals(facts)
    if not interval_result.overlaps_reported_target:
        return Unknown("reconciliation_does_not_close")
    return ArithmeticExplanation(
        source_ids=facts.ids, relation_provenance=relation.provenance,
        target_label=relation.verified_label,
        formula=relation.formula, residual=interval_result.reported_residual,
        # No causal/business-driver claim follows from arithmetic closure.
    )
```

Minimum offline acceptance should include PFE's positive same-context bridge and visible 1M prior residual; BA's valid reported operating fact but unavailable automatic core/ex-sale relationship; RIVN's payment/expense/period rejection; mismatched namespace/entity/dimensions/units; invalid/missing calculation weights; and supplied non-GAAP definition not conflated with another adjustment. These are proposed tests, not executed production gates or mutation proofs. Existing delta/normalization functions can format the accepted values, but cannot manufacture their identity.

## Compatibility, locked boundaries and release decision

Read CLAUDE rules 1/2/5/6/9/12, the actual locked inventory, RUNBOOK, period-selection, figure-amplification, stop-prose-tuning and held-knobs lessons. No need to edit any of the eleven existing locked anchors for an optional evidence observer or pure helper. An eventual new public schema or SSE behavior would require explicit scope review; this proposal preserves existing events, callbacks, cache and background pipeline. Tests belong in existing unlocked extraction/normalization suites. Full local committed gates, one proof per real new invariant, actual retained-cohort generation and all-surface review follow only once implementation scope is accepted. No current artifact certifies the proposed owner or fixes #805.

The separately confirmed #805 instruction ambiguity is at `summary_schema.py:109–110`: “comparison or cause” may rely on “signed figures or filing explanation.” Two refutations: the stricter driver descriptor is absent from value_drivers/liquidity recovery snippets (`section_recovery.py:106,109,173`); requiring the same basis still does not make co-movement a business cause. Correct that contract to distinguish source-stated causation from validated comparisons/arithmetic relationships. It is a real narrow correction, not evidence that another warning will solve the observed accounting errors.

DeepSeek thinking remains disabled in the actual provider owner. Parent's separate `work/deepseek-reasoning-assessment-feasibility.md` reports that thinking mode ignores sampling parameters, so a future experiment must disclose that effective temperature cannot be held constant. It needs its own budget/timeout/usage design and authorization; neither this proposal nor a switch to High thinking constitutes a proved accounting validator or an authorized live experiment.
